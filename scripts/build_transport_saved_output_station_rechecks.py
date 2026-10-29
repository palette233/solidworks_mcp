#!/usr/bin/env python3
"""Build read-only station rechecks for authenticated historical transport CAD."""

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _short_identity(value: str) -> str:
    project, token = value.split("::", 1)
    match = re.fullmatch(r"project(\d+)", project)
    prefix = f"p{int(match.group(1)):02d}" if match else project
    return f"{prefix}-{token.lower()}"


def _path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-report", type=Path, required=True)
    parser.add_argument("--planning-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    gap_path = _path(str(args.gap_report))
    planning_path = _path(str(args.planning_report))
    output = _path(str(args.output))
    for path in (gap_path, planning_path):
        path.relative_to(ROOT)
        if not path.is_file():
            raise FileNotFoundError(path)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite transport recheck batch: {output}")
    gap = _read(gap_path)
    planning = _read(planning_path)
    if gap.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap report")
    if planning.get("schemaVersion") != "transport-position-station-planning-report/v1":
        raise ValueError("unsupported transport planning report")
    gap_by_pair = {
        (row.get("sourceModuleDefinitionId"), row.get("targetBaseDefinitionId")): row
        for row in gap.get("queue") or [] if row.get("role") == "Transport"
    }
    output.mkdir(parents=True)
    ready = []
    fresh = []
    for row in planning.get("results") or []:
        source = row["sourceModuleDefinitionId"]
        base = row["targetBaseDefinitionId"]
        pair = (source, base)
        gap_row = gap_by_pair.get(pair)
        if not isinstance(gap_row, dict):
            raise ValueError(f"transport planning pair is absent from gap report: {pair}")
        history = gap_row.get("historicalPairEvidence") or {}
        if gap_row.get("gapCategory") != "target_station_postcheck_required_from_existing_saved_output":
            fresh.append({
                "sourceModuleDefinitionId": source,
                "targetBaseDefinitionId": base,
                "gapCategory": gap_row.get("gapCategory"),
                "nextAction": "execute_fresh_nonprototype_cad_queue",
            })
            continue
        cad_path = _path(str(history.get("cadResultPath") or ""))
        if not cad_path.is_file() or _sha256(cad_path) != history.get("cadResultSha256"):
            raise ValueError(f"historical transport CAD result changed: {pair}")
        cad = _read(cad_path)
        graph_path = Path(str(cad.get("executionEffectiveGraphPath") or "")).resolve()
        if not graph_path.is_file() or _sha256(graph_path) != cad.get("executionEffectiveGraphSha256"):
            raise ValueError(f"historical transport execution graph changed: {pair}")
        graph = _read(graph_path)
        tokens = {str(item.get("ModuleToken") or "") for item in graph.get("Modules") or []}
        source_token = source.split("::", 1)[1]
        base_token = base.split("::", 1)[1]
        if tokens != {source_token, base_token}:
            raise ValueError(f"historical transport graph identity differs: {pair}")
        station_plan_path = _path(str(row.get("planPath") or ""))
        if not station_plan_path.is_file():
            raise FileNotFoundError(station_plan_path)
        pair_dir = output / (_short_identity(source) + "--" + _short_identity(base))
        request_path = pair_dir / "request.json"
        state_path = pair_dir / "reopened-state.json"
        process_path = pair_dir / "inspection-process.json"
        assembly_path = Path(str(cad.get("outputAssemblyPath") or "")).resolve()
        if not assembly_path.is_file() or _sha256(assembly_path) != cad.get("outputAssemblySha256"):
            raise ValueError(f"historical transport output assembly changed: {pair}")
        request = {
            "schemaVersion": "saved-output-station-inspection-request/v1",
            "cadResult": {"path": _relative(cad_path), "sha256": _sha256(cad_path)},
            "outputAssemblySha256": _sha256(assembly_path),
            "expectedTopLevelComponentCount": len(graph.get("Modules") or []),
            "baseToken": base_token,
            "targetToken": source_token,
            "outputStatePath": _relative(state_path),
            "processReportPath": _relative(process_path),
            "claimBoundary": (
                "Read-only saved-output reopening for current target-station verification. "
                "It does not rerun assembly, prove fastening, collision/B-rep, transport "
                "work-area fit or production approval."
            ),
        }
        request["requestDigest"] = _digest(request)
        _write(request_path, request)
        inspection_plan = build_saved_output_station_inspection_plan(ROOT, request_path)
        ready.append({
            "sourceModuleDefinitionId": source,
            "targetBaseDefinitionId": base,
            "requestPath": _relative(request_path),
            "requestDigest": request["requestDigest"],
            "stationPlanPath": _relative(station_plan_path),
            "stationPlanSha256": _sha256(station_plan_path),
            "cadResultPath": _relative(cad_path),
            "cadResultSha256": _sha256(cad_path),
            "outputAssemblyPath": _relative(assembly_path),
            "outputAssemblySha256": _sha256(assembly_path),
            "readOnlyInspectionPlanned": inspection_plan["readOnly"],
            "cadReexecutionRequired": False,
            "nextAction": "run_readonly_reopen_then_verify_current_station_rule",
        })
    report = {
        "schemaVersion": "transport-saved-output-station-recheck-batch/v1",
        "sourceGapReport": {"path": _relative(gap_path), "sha256": _sha256(gap_path)},
        "sourcePlanningReport": {"path": _relative(planning_path), "sha256": _sha256(planning_path)},
        "candidateCount": len(planning.get("results") or []),
        "readyReadOnlyInspectionCount": len(ready),
        "freshCadStillRequiredCount": len(fresh),
        "ready": ready,
        "freshCadRequired": fresh,
        "cadStarted": False,
        "claimBoundary": (
            "Request preparation only. Historical CAD remains unpromoted until each "
            "assembly is reopened read-only and its current station plan passes."
        ),
    }
    _write(output / "batch-report.json", report)
    print(json.dumps({key: report[key] for key in (
        "candidateCount", "readyReadOnlyInspectionCount",
        "freshCadStillRequiredCount", "cadStarted"
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
