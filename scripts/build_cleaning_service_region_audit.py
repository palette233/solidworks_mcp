#!/usr/bin/env python3
"""Write cleaning service-region measurements; never start or modify CAD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cleaning_service_region import DEFAULT_RULE, build_cleaning_service_region_audit  # noqa: E402
from demo_backend.parameterized_datum_placement import compile_parameterized_datum_validation_package  # noqa: E402


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rule", type=Path, default=Path(DEFAULT_RULE), help="Combination-specific cleaning service-region rule JSON")
    parser.add_argument("--cad-result", type=Path)
    parser.add_argument("--state", type=Path, help="Readonly saved-output state; required for --cad-result to bind actual base/target poses")
    parser.add_argument("--candidate-output-dir", type=Path,
                        help="Also compile the suggested pair through the existing three-plane builder; never execute CAD")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite service-region evidence: {output}")
    candidate_dir = args.candidate_output_dir.resolve() if args.candidate_output_dir else None
    if candidate_dir and candidate_dir.exists():
        raise FileExistsError(f"Refusing to overwrite candidate: {candidate_dir}")
    if candidate_dir and args.cad_result:
        parser.error("Candidate compilation and saved-CAD review are separate invocations")
    started = time.perf_counter()
    rule_path = args.rule.resolve()
    rule = json.loads(rule_path.read_text(encoding="utf-8-sig"))
    report = build_cleaning_service_region_audit(ROOT, rule, cad_result_path=args.cad_result, saved_state_path=args.state)
    report["evidence"].append({"path": str(rule_path), "sha256": _file_hash(rule_path)})
    report["auditDigest"] = hashlib.sha256(json.dumps({key: value for key, value in report.items() if key != "auditDigest"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    package = None
    if candidate_dir:
        if (report.get("capabilityCoverage") or {}).get("passed") is not True:
            raise ValueError("Target service providers do not cover all source-module capabilities")
        if report["serviceRegionDemoPassed"] is not True:
            raise ValueError("Suggested candidate fails its explicitly approximate service-subtree region")
        package = compile_parameterized_datum_validation_package(
            ROOT, rule["sourceModuleDefinitionId"], rule["targetBaseDefinitionId"],
            initial_placement_variant=report["candidateSuggestion"]["initialPlacementVariant"],
            position_parameters=report["candidateSuggestion"]["positionParameters"],
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    _write(output, report)
    if package is not None:
        candidate_dir.mkdir(parents=True)
        artifacts = {}
        for key, name in (("effectiveGraph", "effective-mate-graph.json"), ("selectedEndpointCatalog", "selected-face-endpoint-catalog.json")):
            path = candidate_dir / name
            _write(path, package.pop(key))
            artifacts[key] = {"path": str(path), "sha256": _file_hash(path)}
        package["artifacts"] = artifacts
        _write(candidate_dir / "validation-package.json", package)
        binding = {
            "serviceRegionAudit": {"path": str(output), "sha256": _file_hash(output), "auditDigest": report["auditDigest"]},
            "candidateGraph": artifacts["effectiveGraph"], "cadStarted": False, "stationReady": False,
        }
        checkpoint_rule = rule.get("sourceCheckpointSuggestion")
        if checkpoint_rule:
            closure_path = ROOT / checkpoint_rule["closurePath"]
            closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
            steps = [row for row in closure["steps"] if row["stepId"] == checkpoint_rule["stepId"]]
            if len(steps) != 1:
                raise ValueError("Configured source checkpoint step is not unique")
            step = steps[0]
            checkpoint = Path(step["assemblyPath"])
            checkpoint_ok = step.get("status") == "passed" and _file_hash(checkpoint) == step.get("assemblySha256")
            binding["cumulativeSourceSuggestion"] = {"assemblyPath": str(checkpoint), "assemblySha256": step["assemblySha256"],
                "historicalClosureBindingVerified": checkpoint_ok, "expectedModuleTokens": checkpoint_rule["expectedModuleTokens"],
                "closurePath": str(closure_path), "closureSha256": _file_hash(closure_path),
                "notYetBoundIntoThisPairPackage": True, "freshContextAndPreservationVerificationRequired": True}
        _write(candidate_dir / "service-region-candidate-binding.json", binding)
    print(json.dumps({"output": str(output), "durationSeconds": time.perf_counter() - started,
                     "candidateOutputDirectory": str(candidate_dir) if candidate_dir else None,
                     "serviceRegionDemoPassed": report["serviceRegionDemoPassed"],
                     "wholeEnvelopeContained": report["fullEnvelope"]["nativeRoleEnvelopeRelation"]["envelopeContained"],
                     "stationReady": report["stationReady"], "cadStarted": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
