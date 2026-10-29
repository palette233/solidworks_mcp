#!/usr/bin/env python3
"""Build read-only saved-output inspection requests from one gap category."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.saved_output_station_inspection import (  # noqa: E402
    build_saved_output_station_inspection_plan,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def _digest(payload: dict) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "requestDigest"}
    return hashlib.sha256(json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _slug(value: str) -> str:
    project, token = value.split("::", 1)
    match = re.fullmatch(r"project(\d+)", project)
    prefix = f"p{int(match.group(1)):02d}" if match else project
    slug = f"{prefix}-{token.lower()}"
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError(f"unsafe identity: {value}")
    return slug


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-report", type=Path, required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--gap-category", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    gap_path = _resolve(str(args.gap_report))
    output = _resolve(str(args.output))
    gap_path.relative_to(ROOT)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite inspection batch: {output}")
    gap = _read(gap_path)
    if gap.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap report")
    categories = set(args.gap_category)
    rows = [
        row for row in gap.get("queue") or []
        if row.get("role") == args.role and row.get("gapCategory") in categories
    ]
    if not rows:
        raise ValueError("gap filter produced no inspection candidates")
    output.mkdir(parents=True)
    requests = []
    for row in rows:
        source = row["sourceModuleDefinitionId"]
        base = row["targetBaseDefinitionId"]
        history = row.get("historicalPairEvidence") or {}
        cad_path = _resolve(str(history.get("cadResultPath") or ""))
        if not cad_path.is_file() or _sha(cad_path) != history.get("cadResultSha256"):
            raise ValueError(f"historical CAD result missing or changed: {source}->{base}")
        cad = _read(cad_path)
        graph_path = Path(str(cad.get("executionEffectiveGraphPath") or "")).resolve()
        if not graph_path.is_file() or _sha(graph_path) != cad.get("executionEffectiveGraphSha256"):
            raise ValueError(f"historical execution graph missing or changed: {source}->{base}")
        graph = _read(graph_path)
        source_token, base_token = source.split("::", 1)[1], base.split("::", 1)[1]
        tokens = {str(item.get("ModuleToken") or "") for item in graph.get("Modules") or []}
        if tokens != {source_token, base_token}:
            raise ValueError(f"historical graph pair identity differs: {source}->{base}")
        assembly = Path(str(cad.get("outputAssemblyPath") or "")).resolve()
        if not assembly.is_file() or _sha(assembly) != cad.get("outputAssemblySha256"):
            raise ValueError(f"historical assembly missing or changed: {source}->{base}")
        pair_dir = output / (_slug(source) + "--" + _slug(base))
        request_path = pair_dir / "request.json"
        request = {
            "schemaVersion": "saved-output-station-inspection-request/v1",
            "cadResult": {"path": _relative(cad_path), "sha256": _sha(cad_path)},
            "outputAssemblySha256": _sha(assembly),
            "expectedTopLevelComponentCount": len(graph.get("Modules") or []),
            "baseToken": base_token,
            "targetToken": source_token,
            "outputStatePath": _relative(pair_dir / "reopened-state.json"),
            "processReportPath": _relative(pair_dir / "inspection-process.json"),
            "claimBoundary": (
                "Read-only saved-output state capture for the selected gap category. "
                "It does not rerun assembly or prove target function, fastening, "
                "collision/B-rep or production approval."
            ),
        }
        request["requestDigest"] = _digest(request)
        _write(request_path, request)
        plan = build_saved_output_station_inspection_plan(ROOT, request_path)
        requests.append({
            "sourceModuleDefinitionId": source,
            "targetBaseDefinitionId": base,
            "role": args.role,
            "gapCategory": row["gapCategory"],
            "requestPath": _relative(request_path),
            "requestDigest": request["requestDigest"],
            "cadResultPath": _relative(cad_path),
            "cadResultSha256": _sha(cad_path),
            "readOnlyInspectionPlanned": plan["readOnly"],
            "cadReexecutionRequired": False,
        })
    report = {
        "schemaVersion": "saved-output-inspection-batch/v1",
        "sourceGapReport": {"path": _relative(gap_path), "sha256": _sha(gap_path)},
        "role": args.role,
        "gapCategories": sorted(categories),
        "requestCount": len(requests),
        "requests": requests,
        "cadStarted": False,
        "claimBoundary": (
            "Request preparation only. Saved base and target transforms remain untrusted "
            "until read-only reopening succeeds."
        ),
    }
    _write(output / "batch-report.json", report)
    print(json.dumps({
        "role": report["role"], "requestCount": report["requestCount"],
        "cadStarted": report["cadStarted"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
