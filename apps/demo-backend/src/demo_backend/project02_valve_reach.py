from __future__ import annotations
from typing import Any


GANTRY = "FL9A24D062A100.001-1"
REQUIRED_REACH_DIAGNOSTICS = {
    "coarse-left-drain-reach",
    "coarse-right-drain-reach",
    "coarse-a700-weighing-reach",
    "auto-work-reach-FL9A24D062A800.001-1-workPosition1-dualValveReach",
    "auto-work-reach-FL9A24D062A800.001-1-workPosition2-dualValveReach",
    "auto-calibration-reach-FL9A24D062A500.001-1-dualValveReach",
    "auto-cleaning-reach-FL9A24D062A700.001-1-dualValveReach",
    "reach-dualValveReach",
    "reach-leftValveReach",
    "reach-rightValveReach",
}


def _intersection(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {
        "minU": max(float(a["minU"]), float(b["minU"])),
        "minV": max(float(a["minV"]), float(b["minV"])),
        "maxU": min(float(a["maxU"]), float(b["maxU"])),
        "maxV": min(float(a["maxV"]), float(b["maxV"])),
    }


def build_project02_valve_reach_audit(
    request: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    gantry = (request.get("moduleSemantics") or {}).get(GANTRY) or {}
    regions = gantry.get("regions") or {}
    parameters = gantry.get("parameters") or {}
    left = regions.get("leftValveReach") or {}
    right = regions.get("rightValveReach") or {}
    common = regions.get("dualValveReach") or {}
    all_regions_defined = all((left, right, common))
    expected_common = _intersection(left, right) if all_regions_defined else {}
    common_matches = all_regions_defined and all(
        abs(float(common[key]) - float(expected_common[key])) <= 1e-9
        for key in expected_common
    )

    diagnostic_by_id = {
        item.get("id"): item for item in preview.get("diagnostics") or []
    }
    checks = [
        {
            "id": diagnostic_id,
            "passed": bool(
                diagnostic_by_id.get(diagnostic_id, {}).get("success") is True
            ),
            "measured": diagnostic_by_id.get(diagnostic_id, {}).get("measured"),
        }
        for diagnostic_id in sorted(REQUIRED_REACH_DIAGNOSTICS)
    ]
    all_checks_passed = all(item["passed"] for item in checks)
    spacing = float(parameters.get("estimatedValveHeadSpacingMeters") or 0.0)
    spacing_supported = spacing > 0
    success = bool(
        preview.get("metrics", {}).get("hardFeasible")
        and common_matches
        and spacing_supported
        and all_checks_passed
    )
    return {
        "schemaVersion": "project02-dual-valve-reach-audit/v1",
        "success": success,
        "status": (
            "COARSE_DUAL_VALVE_REACH_CLEAR_AXIS_LIMIT_CONFIRMATION_PENDING"
            if success
            else "DUAL_VALVE_REACH_MODEL_FAILED"
        ),
        "projectId": "project02",
        "reachModel": parameters.get("reachModel"),
        "leftValveReachLocalMeters": left,
        "rightValveReachLocalMeters": right,
        "computedCommonIntersectionLocalMeters": expected_common,
        "configuredDualValveReachLocalMeters": common,
        "commonIntersectionMatches": common_matches,
        "estimatedValveHeadSpacingMeters": spacing,
        "targetAndContainmentChecks": checks,
        "usableForCoarseLayout": success,
        "engineeringConfirmed": False,
        "authoritativeForFinalMotion": False,
        "remainingInput": (
            "Measure the left/right valve axis limits and validate the common reachable "
            "envelope; the current model is an equivalent static reach approximation."
        ),
    }
