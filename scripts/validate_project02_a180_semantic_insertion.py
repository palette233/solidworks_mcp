#!/usr/bin/env python3
"""Audit the cumulative A600 -> A800 -> A180 mechanical and optical closure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_A180_RESULT = ROOT / "demo/semantic_ports/project02_A180_scanner_installation_v1/project02_A800_then_A180_context_insert_V2.context-insert.result.json"
DEFAULT_A800_RESULT = ROOT / "demo/semantic_ports/project02_A800_case_anchored_installation_v1/project02_A800_context_insert_V6.context-insert.result.json"
DEFAULT_OPTICAL = ROOT / "demo/layout_previews/project02_scanner_barcode_points.json"
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project02_A180_scanner_installation_v1/project02_A800_then_A180_semantic_validation.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("toolResult") or payload.get("ToolResult") or {}


def build_audit(
    a180_run: dict[str, Any],
    a800_run: dict[str, Any],
    optical: dict[str, Any],
    minimum_working_distance: float = 0.100,
    maximum_working_distance: float = 0.160,
) -> dict[str, Any]:
    a180 = tool_result(a180_run)
    a800 = tool_result(a800_run)
    entries = optical["entries"]
    scanner = entries["scanner"]
    barcode = entries["barcode"]
    relation = barcode["scannerRelationship"]
    distance = float(relation["prototypeScannerToBarcodeDistanceMeters"])
    mechanical_checks = {
        "a800InsertionSucceeded": bool(a800_run.get("success") and a800.get("Success")),
        "a800CaseAnchorPoseMatch": bool(a800.get("CaseAnchorPoseMatch")),
        "a180InsertionSucceeded": bool(a180_run.get("success") and a180.get("Success")),
        "a180IndependentComponentInserted": bool(a180.get("IndependentComponentInserted")),
        "a180RequestedMatesCreated": int(a180.get("CreatedMateCount", -1))
        == int(a180.get("RequestedMateCount", -2)),
        "a180Reopened": bool(a180.get("Reopened")),
        "a180MateParametersMatch": bool(a180.get("ReopenedMateParametersMatch")),
        "a180CaseAnchorPoseMatch": bool(a180.get("CaseAnchorPoseMatch")),
        "a180FullyConstrained": bool(a180.get("TargetFullyConstrained")),
        "a180ComponentSemanticsMatch": bool(a180.get("ComponentSemanticsMatch")),
    }
    optical_checks = {
        "scannerOriginAvailableForCoarseLayout": bool(scanner.get("readyForCoarseLayout")),
        "scannerOriginEvidenceClass": scanner.get("measurementStatus"),
        "barcodeFaceDirectlyMeasured": barcode.get("measurementStatus") == "direct-face-measured",
        "workingDistanceMeters": distance,
        "workingDistanceRangeMeters": [minimum_working_distance, maximum_working_distance],
        "workingDistanceInRange": minimum_working_distance <= distance <= maximum_working_distance,
        "relativePosePreservedByCaseAnchors": bool(
            a800.get("CaseAnchorPoseMatch") and a180.get("CaseAnchorPoseMatch")
        ),
        "opticalAxisSignConfirmed": False,
        "lineOfSightProductionVerified": False,
    }
    mechanical_pass = all(mechanical_checks.values())
    coarse_optical_pass = all(
        optical_checks[key]
        for key in (
            "scannerOriginAvailableForCoarseLayout",
            "barcodeFaceDirectlyMeasured",
            "workingDistanceInRange",
            "relativePosePreservedByCaseAnchors",
        )
    )
    return {
        "schemaVersion": "project02-a180-semantic-insertion-validation/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": (
            "MECHANICAL_CAD_CLOSED_OPTICAL_PROVISIONAL"
            if mechanical_pass and coarse_optical_pass
            else "REJECTED"
        ),
        "success": mechanical_pass and coarse_optical_pass,
        "mechanicalCadClosed": mechanical_pass,
        "coarseOpticalRelationPreserved": coarse_optical_pass,
        "productionOpticalReady": False,
        "mechanicalChecks": mechanical_checks,
        "opticalChecks": optical_checks,
        "limitations": [
            "A180 and A800 still use explicit Project02 case anchors to close residual source-mate DOF.",
            "The scan origin is inferred from symmetric illumination windows rather than a directly registered central lens face.",
            "Optical-axis sign, production line of sight, PLC stop and vendor-approved working distance remain unconfirmed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a180-result", type=Path, default=DEFAULT_A180_RESULT)
    parser.add_argument("--a800-result", type=Path, default=DEFAULT_A800_RESULT)
    parser.add_argument("--optical", type=Path, default=DEFAULT_OPTICAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audit = build_audit(
        read_json(args.a180_result.resolve()),
        read_json(args.a800_result.resolve()),
        read_json(args.optical.resolve()),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": audit["status"],
        "success": audit["success"],
        "mechanicalCadClosed": audit["mechanicalCadClosed"],
        "coarseOpticalRelationPreserved": audit["coarseOpticalRelationPreserved"],
        "productionOpticalReady": audit["productionOpticalReady"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if audit["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
