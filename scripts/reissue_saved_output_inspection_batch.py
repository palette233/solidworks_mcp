#!/usr/bin/env python3
"""Reissue an immutable inspection batch with exact reference-resolution evidence."""

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


def _digest(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("requestDigest", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _pair_slug(source: str, base: str) -> str:
    def slug(value: str) -> str:
        project, token = value.split("::", 1)
        match = re.fullmatch(r"project(\d+)", project)
        prefix = f"p{int(match.group(1)):02d}" if match else project
        return f"{prefix}-{token.lower()}"

    return f"{slug(source)}--{slug(base)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_report", type=Path)
    parser.add_argument("--resolution-manifest", type=Path, action="append", default=[])
    parser.add_argument("--deferral-manifest", type=Path, action="append", default=[])
    parser.add_argument(
        "--preserve-unaffected-requests",
        action="store_true",
        help=(
            "Keep immutable source request paths for pairs without new reference "
            "resolution, so already completed evidence is not repeated."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_batch_path = args.batch_report.resolve()
    output = args.output.resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite reissued batch: {output}")
    source_batch = _read(source_batch_path)
    if source_batch.get("schemaVersion") != "saved-output-inspection-batch/v1":
        raise ValueError("unsupported source inspection batch")
    manifests = {}
    manifest_bindings = []
    for value in args.resolution_manifest:
        path = value.resolve()
        manifest = _read(path)
        if (
            manifest.get("schemaVersion")
            != "solidworks-reference-resolution-manifest/v1"
            or manifest.get("success") is not True
        ):
            raise ValueError("reference-resolution manifest is not complete")
        key = str(Path(manifest["assemblyPath"]).resolve()).casefold()
        if key in manifests:
            raise ValueError("duplicate resolution manifest for one assembly")
        manifests[key] = manifest
        manifest_bindings.append({"path": str(path), "sha256": _sha(path)})
    deferrals = {}
    deferral_bindings = []
    for value in args.deferral_manifest:
        path = value.resolve()
        manifest = _read(path)
        if manifest.get("schemaVersion") != "saved-output-inspection-deferral/v1":
            raise ValueError("unsupported saved-output inspection deferral")
        key = (
            str(manifest.get("sourceModuleDefinitionId") or ""),
            str(manifest.get("targetBaseDefinitionId") or ""),
        )
        if not all(key) or key in deferrals:
            raise ValueError("duplicate or incomplete inspection deferral")
        for evidence in manifest.get("evidence") or []:
            evidence_path = Path(str(evidence.get("path") or "")).resolve()
            if not evidence_path.is_file() or _sha(evidence_path) != evidence.get("sha256"):
                raise ValueError("inspection deferral evidence is missing or changed")
        deferrals[key] = manifest
        deferral_bindings.append({"path": str(path), "sha256": _sha(path)})
    output.mkdir(parents=True)
    requests = []
    matched = set()
    matched_deferrals = set()
    deferred_requests = []
    for row in source_batch.get("requests") or []:
        old_request_path = (ROOT / row["requestPath"]).resolve()
        request = _read(old_request_path)
        cad_path = (ROOT / request["cadResult"]["path"]).resolve()
        cad = _read(cad_path)
        assembly_key = str(Path(cad["outputAssemblyPath"]).resolve()).casefold()
        source = row["sourceModuleDefinitionId"]
        base = row["targetBaseDefinitionId"]
        pair_key = (source, base)
        if pair_key in deferrals:
            manifest = deferrals[pair_key]
            deferred_requests.append(
                {
                    "sourceModuleDefinitionId": source,
                    "targetBaseDefinitionId": base,
                    "role": row.get("role"),
                    "reasonCode": manifest.get("reasonCode"),
                    "reason": manifest.get("reason"),
                    "deferralManifest": next(
                        binding
                        for binding in deferral_bindings
                        if _read(Path(binding["path"]))["sourceModuleDefinitionId"]
                        == source
                        and _read(Path(binding["path"]))["targetBaseDefinitionId"]
                        == base
                    ),
                    "strictStationValidationPassed": False,
                }
            )
            matched_deferrals.add(pair_key)
            continue
        if args.preserve_unaffected_requests and assembly_key not in manifests:
            if request.get("requestDigest") != row.get("requestDigest"):
                raise ValueError("preserved request digest differs from its source row")
            requests.append(dict(row))
            continue
        pair_dir = output / _pair_slug(source, base)
        request["outputStatePath"] = _relative(pair_dir / "reopened-state.json")
        request["processReportPath"] = _relative(pair_dir / "inspection-process.json")
        if assembly_key in manifests:
            manifest = manifests[assembly_key]
            if manifest["assemblySha256"] != request["outputAssemblySha256"]:
                raise ValueError("resolution manifest assembly digest differs")
            request["referenceResolution"] = {
                "policy": "transient-exact-file-parent-search/v1",
                "mappings": [
                    {
                        "savedPath": item["savedPath"],
                        "resolvedPath": item["resolvedPath"],
                        "sha256": item["sha256"],
                    }
                    for item in manifest["mappings"]
                ],
                "manifest": {
                    "path": next(
                        binding["path"]
                        for binding in manifest_bindings
                        if _read(Path(binding["path"]))["assemblyPath"]
                        == manifest["assemblyPath"]
                    ),
                    "sha256": next(
                        binding["sha256"]
                        for binding in manifest_bindings
                        if _read(Path(binding["path"]))["assemblyPath"]
                        == manifest["assemblyPath"]
                    ),
                },
            }
            matched.add(assembly_key)
        request["requestDigest"] = _digest(request)
        request_path = pair_dir / "request.json"
        _write_once(request_path, request)
        plan = build_saved_output_station_inspection_plan(ROOT, request_path)
        requests.append(
            {
                **{key: value for key, value in row.items() if key not in {"requestPath", "requestDigest"}},
                "requestPath": _relative(request_path),
                "requestDigest": request["requestDigest"],
                "referenceResolutionCount": len(plan["referenceResolutionMappings"]),
            }
        )
    if matched != set(manifests):
        raise ValueError("one or more reference-resolution manifests did not match the batch")
    if matched_deferrals != set(deferrals):
        raise ValueError("one or more deferral manifests did not match the batch")
    report = {
        **source_batch,
        "sourceBatchReport": {"path": str(source_batch_path), "sha256": _sha(source_batch_path)},
        "referenceResolutionManifests": manifest_bindings,
        "deferralManifests": deferral_bindings,
        "requestCount": len(requests),
        "deferredRequestCount": len(deferred_requests),
        "requests": requests,
        "deferredRequests": deferred_requests,
        "cadStarted": False,
        "claimBoundary": (
            "Immutable request reissue with exact transient reference resolution "
            "or explicit deferral; unaffected request paths may be preserved. "
            "No assembly, component, mate, or source CAD file was modified."
        ),
    }
    _write_once(output / "batch-report.json", report)
    print(json.dumps({
        "requestCount": len(requests),
        "deferredRequestCount": len(deferred_requests),
        "matchedResolutionManifestCount": len(matched),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
