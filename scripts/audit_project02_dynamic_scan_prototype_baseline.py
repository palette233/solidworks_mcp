#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "demo/project02_engineering_inputs.json"
REQUEST_PATH = ROOT / "demo/FL9A24D062A000_real_process_request.json"
WINDOW_PATH = ROOT / "demo/layout_previews/project02_dynamic_scan_window.json"
ROBUSTNESS_PATH = ROOT / "demo/layout_previews/project02_parameter_robustness.json"
OUTPUT_PATH = (
    ROOT
    / "demo/layout_previews/project02_dynamic_scan_prototype_baseline_acceptance.json"
)
TRANSPORT = "FL9A24D062A800.001-1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def close(first: Any, second: Any, tolerance: float = 1e-12) -> bool:
    try:
        return math.isclose(float(first), float(second), abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def main() -> int:
    inputs = load(INPUT_PATH)
    request = load(REQUEST_PATH)
    window = load(WINDOW_PATH)
    robustness = load(ROBUSTNESS_PATH)

    configured = inputs.get("dynamicScan") or {}
    transport = request["moduleSemantics"][TRANSPORT]
    parameters = transport["parameters"]
    points = transport["points"]
    sequence = (request.get("assemblySequencePolicy") or {}).get("dynamicScan") or {}
    tolerance = float(configured.get("stopToleranceMeters") or 0.0)
    barcode = points["barcode"]
    low_name, high_name = parameters["dynamicScanWindowPointNames"]
    dimensions = ((window.get("evidence") or {}).get("barcodeFaceDimensionsMeters") or [])
    measured_half_width = min(map(float, dimensions)) / 2.0 if len(dimensions) == 2 else None

    scan_rows = {
        round(float(row["value"]), 6): row
        for row in robustness.get("scenarios") or []
        if row.get("parameter") == "dynamicScanStopToleranceMeters"
    }

    checks = {
        "prototypeBaselineDeclared": configured.get("sourceType") == "prototypeBaseline",
        "acceptedOnlyForCoarseLayout": configured.get("acceptedForCoarseLayout") is True,
        "vendorNotConfirmed": configured.get("vendorConfirmed") is False,
        "project02OnlyScope": configured.get("scope") == "project02-only",
        "baselineEqualsMeasuredQrHalfWidth": measured_half_width is not None
        and close(tolerance, measured_half_width),
        "lowEndpointApplied": close(points[low_name]["u"], float(barcode["u"]) - tolerance)
        and close(points[low_name]["v"], barcode["v"]),
        "highEndpointApplied": close(points[high_name]["u"], float(barcode["u"]) + tolerance)
        and close(points[high_name]["v"], barcode["v"]),
        "requestRemainsUnconfirmed": parameters.get("dynamicScanStopToleranceConfirmed")
        is False,
        "authorityPreserved": parameters.get("dynamicScanStopToleranceAuthority")
        == "prototypeBaselineAcceptedForCoarseLayout",
        "sequenceAuthorityPreserved": sequence.get("inputSourceType")
        == "prototypeBaseline"
        and sequence.get("estimateAcceptedForCoarseLayout") is True
        and sequence.get("confirmed") is False,
        "carrier8EvidenceResolved": window.get("success") is True
        and str(window.get("carrierInstance") or "").endswith("-8"),
        "bothEndpointsUseDistanceSightAndDirection": all(
            (window.get("generatedConstraintPolicy") or {}).get(name) is True
            for name in (
                "pointDistanceForBothEndpoints",
                "lineOfSightForBothEndpoints",
                "directedPointingForBothEndpoints",
            )
        ),
        "baselineFeasibleAndV52Equivalent": bool(scan_rows.get(0.005, {}).get("feasible"))
        and bool((scan_rows.get(0.005, {}).get("layoutComparison") or {}).get("equivalent")),
        "tenMillimetersFeasibleAndV52Equivalent": bool(scan_rows.get(0.01, {}).get("feasible"))
        and bool((scan_rows.get(0.01, {}).get("layoutComparison") or {}).get("equivalent")),
        "twentyMillimetersFeasibleAndV52Equivalent": bool(scan_rows.get(0.02, {}).get("feasible"))
        and bool((scan_rows.get(0.02, {}).get("layoutComparison") or {}).get("equivalent")),
        "thirtyMillimetersRejected": scan_rows.get(0.03, {}).get("feasible") is False,
    }
    success = all(checks.values())
    report = {
        "schemaVersion": "project02-dynamic-scan-prototype-baseline-acceptance/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": (
            "PROTOTYPE_BASELINE_ACCEPTED_LAYOUT_PRESERVED_TO_20MM_FAILURE_AT_30MM"
            if success
            else "DYNAMIC_SCAN_PROTOTYPE_BASELINE_REJECTED"
        ),
        "authority": "prototypeBaselineAcceptedForCoarseLayout",
        "vendorConfirmed": False,
        "scope": "project02-only",
        "carrierInstance": window.get("carrierInstance"),
        "windowAxis": parameters.get("dynamicScanStopToleranceAxis"),
        "baselineStopToleranceMeters": tolerance,
        "measuredQrFaceDimensionsMeters": dimensions,
        "nominalBarcodePointLocalMeters": barcode,
        "windowEndpointsLocalMeters": {
            low_name: points[low_name],
            high_name: points[high_name],
        },
        "checks": checks,
        "pressureScenarios": [scan_rows[key] for key in sorted(scan_rows)],
        "decision": {
            "formalBaselineMeters": tolerance,
            "maximumTestedLayoutPreservingToleranceMeters": 0.02,
            "firstTestedFailureToleranceMeters": 0.03,
            "promoteStressToleranceToFormalBaseline": False,
            "reason": (
                "The 5 mm value has direct Project02 QR geometry provenance. "
                "The 10/20 mm values are robustness margins only; PLC trigger and "
                "fixture stop evidence are required before replacing the formal baseline."
            ),
        },
        "sourceFiles": {
            "engineeringInputs": str(INPUT_PATH),
            "request": str(REQUEST_PATH),
            "dynamicWindow": str(WINDOW_PATH),
            "robustness": str(ROBUSTNESS_PATH),
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
