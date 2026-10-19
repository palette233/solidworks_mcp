#!/usr/bin/env python3
"""Verify that the accepted Project02 A100 reach baseline is explicit and reusable."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "demo/project02_engineering_inputs.json"
REQUEST = ROOT / "demo/FL9A24D062A000_real_process_request.json"
AXIS_EVIDENCE = ROOT / "demo/layout_previews/project02_a100_valve_axis_inference.json"
ABLATION = ROOT / "demo/layout_previews/project02_a300_a700_constraint_ablation.json"
OUTPUT = ROOT / "demo/layout_previews/project02_a100_prototype_baseline_acceptance.json"
GANTRY = "FL9A24D062A100.001-1"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def close_region(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return all(
        math.isclose(float(first[key]), float(second[key]), abs_tol=1e-12)
        for key in ("minU", "minV", "maxU", "maxV")
    )


def intersection(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    return {
        "minU": max(float(left["minU"]), float(right["minU"])),
        "minV": max(float(left["minV"]), float(right["minV"])),
        "maxU": min(float(left["maxU"]), float(right["maxU"])),
        "maxV": min(float(left["maxV"]), float(right["maxV"])),
    }


def main() -> int:
    inputs = read(INPUTS)
    request = read(REQUEST)
    axis = read(AXIS_EVIDENCE)
    ablation = read(ABLATION)
    configured = inputs.get("dualValveReach") or {}
    gantry = request["moduleSemantics"][GANTRY]
    regions = gantry["regions"]
    parameters = gantry["parameters"]
    left = configured.get("leftValveReachLocalMeters") or {}
    right = configured.get("rightValveReachLocalMeters") or {}
    common = intersection(left, right)
    current_sensitivity = next(
        item
        for item in axis.get("solverSensitivity") or []
        if item.get("id") == "current-10pct-envelope"
    )

    checks = {
        "prototypeBaselineDeclared": configured.get("sourceType") == "prototypeBaseline",
        "acceptedOnlyForCoarseLayout": configured.get("acceptedForCoarseLayout") is True,
        "vendorNotConfirmed": configured.get("vendorConfirmed") is False,
        "project02OnlyScope": configured.get("scope") == "project02-only",
        "leftRegionApplied": close_region(left, regions["leftValveReach"]),
        "rightRegionApplied": close_region(right, regions["rightValveReach"]),
        "commonIntersectionApplied": close_region(common, regions["dualValveReach"]),
        "requestRemainsProvisional": parameters.get("provisionalReach") is True,
        "authorityPreserved": parameters.get("reachEvidenceAuthority")
        == "prototypeBaselineAcceptedForCoarseLayout",
        "axisEvidenceMatchesBaseline": close_region(
            common, current_sensitivity["commonReachLocalMeters"]
        ),
        "baselineFeasible": current_sensitivity.get("feasible") is True,
        "baselineKeepsV52Pose": bool(
            (current_sensitivity.get("layoutComparison") or {}).get("equivalent")
        ),
        "balancedReachConflictDiagnosed": bool(
            (ablation.get("diagnosis") or {}).get(
                "relativeWindowWideningRecoversFeasibility"
            )
        ),
    }
    success = all(checks.values())
    report = {
        "schemaVersion": "project02-a100-prototype-baseline-acceptance/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": (
            "PROTOTYPE_BASELINE_ACCEPTED_KEEP_FORMAL_A300_A700_WINDOW"
            if success
            else "PROTOTYPE_BASELINE_INCONSISTENT"
        ),
        "authority": "prototypeBaselineAcceptedForCoarseLayout",
        "vendorConfirmed": False,
        "scope": "project02-only",
        "leftValveReachLocalMeters": left,
        "rightValveReachLocalMeters": right,
        "commonValveReachLocalMeters": common,
        "commonWidthMeters": {
            "u": common["maxU"] - common["minU"],
            "v": common["maxV"] - common["minV"],
        },
        "valveHeadSpacingMeters": configured.get("valveHeadSpacingMeters"),
        "checks": checks,
        "directionalPressureEvidence": {
            "currentBaseline": current_sensitivity,
            "geometryOptimistic": next(
                item
                for item in axis.get("solverSensitivity") or []
                if item.get("id") == "geometry-optimistic"
            ),
            "geometryBalanced": next(
                item
                for item in axis.get("solverSensitivity") or []
                if item.get("id") == "geometry-balanced"
            ),
        },
        "a300A700Decision": {
            "applyDiagnosticWideningNow": False,
            "reason": (
                "The accepted Project02 baseline is feasible and keeps the v52 rigid layout. "
                "The bounded A300-A700 widening is reserved for a future smaller reach input; "
                "applying it now would weaken a passing formal process relation without evidence."
            ),
            "diagnosticWindowMeters": {
                "minDeltaU": -0.1,
                "maxDeltaU": 0.1,
                "minDeltaV": 0.02,
                "maxDeltaV": 0.2,
            },
        },
        "sourceFiles": {
            "engineeringInputs": str(INPUTS),
            "request": str(REQUEST),
            "axisEvidence": str(AXIS_EVIDENCE),
            "constraintAblation": str(ABLATION),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
