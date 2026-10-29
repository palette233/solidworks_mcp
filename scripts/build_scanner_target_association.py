#!/usr/bin/env python3
"""Recalculate the existing AI00/JJ00 proxy route into a fresh evidence folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cross_project_scanner_alternate_route import build_scanner_alternate_route_evaluation  # noqa: E402
from demo_backend.scanner_target_association import (  # noqa: E402
    build_scanner_target_association,
    preflight_scanner_target_for_cumulative_chain,
)


def load_inputs(root: Path = ROOT) -> tuple[dict, dict]:
    case = "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00"
    paths = {
        "discovery": f"{case}/scanner_slot_discovery.json",
        "endpoint_recovery": f"{case}/endpoint_recovery_evidence.json",
        "target_face_catalog": f"{case}/jj00-scanner-support-leaf-face-catalog.json",
        "source_face_catalog": "demo/semantic_ports/project03_AI00_third_increment_v1/face_endpoint_catalog.json",
        "source_graph": "demo/global_assembly_contexts/manifest_jobs/project-global-job-f0aa2d732403/packet-runs/packet-003-attempt-01/execution-effective-mate-graph.json",
        "target_transport_graph": "demo/global_assembly_catalog/v1/relation-v2-preview/project01-ss00-current-insert-v1/execution-effective-mate-graph.json",
        "prior_process_evidence": "demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.json",
    }
    values, evidence = {}, {}
    for key, relative in paths.items():
        path = root / relative
        raw = path.read_bytes()
        values[key] = json.loads(raw.decode("utf-8-sig"))
        evidence[key] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return values, evidence


def evaluate(inputs: dict, association: dict | None) -> dict:
    return build_scanner_alternate_route_evaluation(
        **{key: value for key, value in inputs.items() if key != "target_transport_graph"},
        source_support_endpoint_id="face:fl9a24d063ai00:916bba1ff4ce84b0",
        source_hole_endpoint_ids=["face:fl9a24d063ai00:90a1d02db6e9d829", "face:fl9a24d063ai00:aa9f3e759104cfd0"],
        target_association=association,
    )


def planned_context(association: dict, evaluation: dict) -> list[dict]:
    return [{"instanceId": association[role]["instanceId"],
             "moduleDefinitionId": association[role]["moduleDefinitionId"],
             "transform": association[role].get("installedTransform") if role != "scanner" else
             evaluation["selectedCandidate"]["candidateTransform"]}
            for role in ("targetBase", "transport", "scanner")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authorize-prototype-estimate", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; use a fresh directory to preserve old evidence.")
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    inputs, evidence = load_inputs()
    loaded = time.perf_counter()
    association = build_scanner_target_association(
        prior_process_evidence=inputs["prior_process_evidence"],
        scanner_graph=inputs["source_graph"],
        target_transport_graph=inputs["target_transport_graph"],
        target_face_catalog=inputs["target_face_catalog"],
        prototype_estimate_authorized=args.authorize_prototype_estimate,
    )
    associated = time.perf_counter()
    evaluation = evaluate(inputs, association)
    evaluated = time.perf_counter()
    preflight = preflight_scanner_target_for_cumulative_chain(
        evaluation=evaluation, association=association,
        planned_components=planned_context(association, evaluation),
        world_frame_id=association["coordinateFrame"]["worldFrameId"],
        allow_prototype_proxy=args.authorize_prototype_estimate,
    )
    checked = time.perf_counter()
    summary = {
        "status": evaluation["status"], "evaluatedPoseCount": evaluation["evaluatedPoseCount"],
        "associationStatus": association["status"],
        "associationReady": association["coarseGeometryEvaluationReady"],
        "processCandidateCompileAllowed": preflight["processCandidateCompileAllowed"],
        "workingDistanceMeters": evaluation["selectedCandidate"]["processProxyChecks"]["requiredWorkingDistanceMeters"],
        "crossTrackErrorMeters": evaluation["selectedCandidate"]["processProxyChecks"]["crossTrackErrorMeters"],
        "cadPerformed": False, "measuredScanSuccess": False,
        "engineeringEvidenceMissing": association["engineeringEvidenceMissing"],
        "blockingReasonCodes": preflight["blockingReasonCodes"],
    }
    output.mkdir(parents=True)
    for filename, value in {
        "target-association.json": association,
        "alternate-route-evaluation.json": evaluation,
        "chain-process-preflight.json": preflight,
        "source-evidence-index.json": evidence,
        "summary.json": summary,
    }.items():
        (output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    written = time.perf_counter()
    timing = {"startedAt": started_at, "completedAt": datetime.now(timezone.utc).isoformat(),
              "loadInputsSeconds": loaded-started, "associationSeconds": associated-loaded,
              "candidateCalculationSeconds": evaluated-associated,
              "chainPreflightSeconds": checked-evaluated, "evidenceWriteSeconds": written-checked,
              "totalBeforeTimingWriteSeconds": written-started, "cadSeconds": 0.0,
              "scope": "offline existing-input computation only; no CAD session access"}
    (output / "timing-report.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**summary, "outputDirectory": str(output), "timing": timing}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
