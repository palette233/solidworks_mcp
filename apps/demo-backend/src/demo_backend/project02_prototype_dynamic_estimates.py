"""Prototype-derived dynamic estimates for Project02.

This profile is intentionally weaker than production engineering evidence.  It
models A700 as one installed body with three functional zones, because its
internal mate graph contains static installation relations but no three-state
mechanism.  A100 planar travel comes from the accepted prototype reach model;
vertical travel is inferred from the prototype process-height envelope plus an
explicit safety margin, and remains a non-production estimate.
"""

from __future__ import annotations

from typing import Any


def union_box(boxes: list[list[float]]) -> list[float]:
    if not boxes or any(len(box) != 6 for box in boxes):
        raise ValueError("At least one six-value AABB is required")
    return [
        min(float(box[axis]) for box in boxes) for axis in range(3)
    ] + [
        max(float(box[axis]) for box in boxes) for axis in range(3, 6)
    ]


def aggregate_bodies(capture: dict[str, Any], token: str) -> list[float]:
    boxes = [
        list(body["BoundingBoxWorld"])
        for body in capture.get("Bodies") or []
        if token.casefold() in str((body.get("Component") or {}).get("Name") or "").casefold()
    ]
    if not boxes:
        raise ValueError(f"No captured bodies for {token}")
    return union_box(boxes)


def expand_function_zone(
    solid_box: list[float],
    *,
    operator_outward_meters: float,
    service_height_meters: float,
) -> list[float]:
    """Expand toward prototype operation side (-world X) and upward (+world Y)."""
    box = list(map(float, solid_box))
    box[0] -= operator_outward_meters
    box[4] = max(box[4], box[1] + service_height_meters)
    return box


def build_estimate(
    request: dict[str, Any],
    a700_capture: dict[str, Any],
    *,
    static_closure_passed: bool,
    service_access_passed: bool,
    reach_audit_passed: bool,
) -> dict[str, Any]:
    semantics = request["moduleSemantics"]
    a100 = semantics["FL9A24D062A100.001-1"]
    reach = a100["regions"]
    cleaning_a710 = aggregate_bodies(a700_capture, "A710")
    cleaning_a720 = aggregate_bodies(a700_capture, "A720")
    cleaning_solid = union_box([cleaning_a710, cleaning_a720])
    weighing_solid = aggregate_bodies(a700_capture, "A730")
    installed_solid = union_box([cleaning_solid, weighing_solid])
    cleaning_zone = expand_function_zone(
        cleaning_solid,
        operator_outward_meters=0.0385,
        service_height_meters=0.45,
    )
    weighing_zone = expand_function_zone(
        weighing_solid,
        operator_outward_meters=0.079,
        service_height_meters=0.45,
    )
    maintenance_zone = union_box([cleaning_zone, weighing_zone])

    # The process frame is explicitly not claimed to be the native A100 model
    # coordinate system.  U/V are the same axes used by the layout solver; N is
    # normal/vertical.  The N range is derived from the 450 mm service-safe
    # plane down to the lowest prototype process height, plus a 20 mm margin.
    # It is used for sensitivity and coarse collision zoning only.
    left = reach["leftValveReach"]
    right = reach["rightValveReach"]
    common = reach["dualValveReach"]
    target_heights = {
        "transport": float(
            semantics["FL9A24D062A800.001-1"]["parameters"]["interactionHeightRangeMeters"][1]
        ),
        "calibration": float(
            semantics["FL9A24D062A500.001-1"]["parameters"]["interactionHeightRangeMeters"][1]
        ),
        "cleaning": 0.2045,
        "weighing": 0.2104,
        "drain": float(
            semantics["FL9A24D062A300.001-1"]["parameters"]["interactionHeightRangeMeters"][1]
        ),
    }
    safe_service_height = 0.45
    required_vertical_stroke = safe_service_height - min(target_heights.values())
    vertical_margin = 0.02
    recommended_vertical_stroke = required_vertical_stroke + vertical_margin
    vertical = [0.0, recommended_vertical_stroke]
    limits = {
        "coordinateFrame": "project02-layout-process-frame(U,V,N)",
        "axisMapping": {
            "U": "approximately A100 world Z / cross-axis",
            "V": "approximately A100 world X / long rail axis",
            "N": "approximately negative A100 world Y / downward vertical axis from the 450 mm service-safe plane",
        },
        "leftValve": {
            "u": [float(left["minU"]), float(left["maxU"])],
            "v": [float(left["minV"]), float(left["maxV"])],
            "n": vertical,
        },
        "rightValve": {
            "u": [float(right["minU"]), float(right["maxU"])],
            "v": [float(right["minV"]), float(right["maxV"])],
            "n": vertical,
        },
        "commonPlanarReach": {
            "u": [float(common["minU"]), float(common["maxU"])],
            "v": [float(common["minV"]), float(common["maxV"])],
        },
        "targetTopHeightsMeters": target_heights,
        "serviceSafeHeightMeters": safe_service_height,
        "minimumRequiredVerticalStrokeMeters": required_vertical_stroke,
        "verticalStrokeMarginMeters": vertical_margin,
        "verticalStrokeEstimateMeters": recommended_vertical_stroke,
        "verticalStrokeSensitivityRangeMeters": [required_vertical_stroke, 0.3],
        "authority": "prototype-measured-and-estimated",
        "confidence": {"u": "medium", "v": "medium", "n": "medium-low-prototype-process-height-derived"},
    }
    estimated_gate = bool(
        static_closure_passed and service_access_passed and reach_audit_passed
    )
    return {
        "schemaVersion": "project02-prototype-dynamic-estimates/v1",
        "projectId": "project02",
        "authority": "prototype-measured-and-estimated",
        "productionAuthority": False,
        "a700": {
            "modelKind": "single-static-installation-with-functional-zones",
            "modelDecision": "No three rigid A700 states were found in the prototype mate/configuration evidence.",
            "measuredSolidAabbsWorldMeters": {
                "cleaningA710": cleaning_a710,
                "cleaningA720": cleaning_a720,
                "cleaningCombined": cleaning_solid,
                "weighingA730": weighing_solid,
                "installedCombined": installed_solid,
            },
            "estimatedFunctionalZonesWorldMeters": {
                "cleaning": cleaning_zone,
                "weighing": weighing_zone,
                "maintenance": maintenance_zone,
            },
            "estimateRules": {
                "cleaningOperatorOutwardExtensionMeters": 0.0385,
                "weighingOperatorOutwardExtensionMeters": 0.079,
                "verticalServiceHeightMeters": 0.45,
                "operationSideDirection": "negative world X in the accepted prototype pose",
            },
            "confidence": {
                "solidAabbs": "high-prototype-measurement",
                "cleaningAndWeighingZones": "medium-prototype-derived",
                "maintenanceZone": "low-to-medium-conservative-estimate",
            },
        },
        "a100": limits,
        "gate": {
            "staticClosurePassed": static_closure_passed,
            "serviceAccessPassed": service_access_passed,
            "representativeReachPassed": reach_audit_passed,
            "prototypeEstimatedDynamicDemoPassed": estimated_gate,
            "productionDynamicReleaseAllowed": False,
        },
        "limitations": [
            "A700 zones are occupied/process/maintenance spaces, not three saved mechanism states.",
            "A100 U/V ranges are prototype-equivalent layout reach, not switch or mechanical-stop measurements.",
            "A100 N stroke is a sensitivity estimate and must not drive production motion.",
            "Estimated zones may overlap the valve/tool envelope by design; this is reach, not solid interference.",
        ],
    }


def evaluate_vertical_stroke_scenarios(
    estimate: dict[str, Any],
    strokes_meters: list[float],
) -> dict[str, Any]:
    required = float(estimate["a100"]["minimumRequiredVerticalStrokeMeters"])
    rows = []
    for stroke in strokes_meters:
        available = float(stroke)
        rows.append(
            {
                "strokeMeters": available,
                "accepted": available + 1e-12 >= required,
                "marginMeters": available - required,
            }
        )
    return {
        "requiredStrokeMeters": required,
        "scenarioCount": len(rows),
        "acceptedCount": sum(1 for row in rows if row["accepted"]),
        "scenarios": rows,
    }


def validate_solver_binding(
    request: dict[str, Any],
    estimate: dict[str, Any],
    *,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    semantics = request["moduleSemantics"]
    a700 = semantics["FL9A24D062A700.001-1"]["parameters"]
    occupancies = {row["id"]: row for row in a700["occupancyBoxesLocal"]}
    measured = estimate["a700"]["measuredSolidAabbsWorldMeters"]

    def spans(box: list[float]) -> tuple[float, float, float]:
        return tuple(float(box[index + 3]) - float(box[index]) for index in range(3))

    def local_span(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
        min_u = min(float(row["bounds"][0]) for row in rows)
        min_v = min(float(row["bounds"][1]) for row in rows)
        max_u = max(float(row["bounds"][2]) for row in rows)
        max_v = max(float(row["bounds"][3]) for row in rows)
        min_n = min(float(row["heightRangeMeters"][0]) for row in rows)
        max_n = max(float(row["heightRangeMeters"][1]) for row in rows)
        return max_u - min_u, max_v - min_v, max_n - min_n

    cleaning_local = local_span([occupancies["cleaning-a710"], occupancies["cleaning-a720"]])
    weighing_local = local_span([occupancies["weighing-a730"]])
    cleaning_world_xyz = spans(measured["cleaningCombined"])
    weighing_world_xyz = spans(measured["weighingA730"])
    # Layout U/V/N map to the accepted prototype's world Z/X/Y spans.
    cleaning_world_uvn = (cleaning_world_xyz[2], cleaning_world_xyz[0], cleaning_world_xyz[1])
    weighing_world_uvn = (weighing_world_xyz[2], weighing_world_xyz[0], weighing_world_xyz[1])

    def equivalent(first: tuple[float, ...], second: tuple[float, ...]) -> bool:
        return all(abs(a - b) <= tolerance for a, b in zip(first, second))

    reach = semantics["FL9A24D062A100.001-1"]["regions"]["dualValveReach"]
    bound_reach = estimate["a100"]["commonPlanarReach"]
    checks = {
        "cleaningOccupancyMatchesMeasuredBodySpans": equivalent(cleaning_local, cleaning_world_uvn),
        "weighingOccupancyMatchesMeasuredBodySpans": equivalent(weighing_local, weighing_world_uvn),
        "commonReachUMatchesSolver": abs(float(reach["minU"]) - float(bound_reach["u"][0])) <= tolerance
        and abs(float(reach["maxU"]) - float(bound_reach["u"][1])) <= tolerance,
        "commonReachVMatchesSolver": abs(float(reach["minV"]) - float(bound_reach["v"][0])) <= tolerance
        and abs(float(reach["maxV"]) - float(bound_reach["v"][1])) <= tolerance,
        "serviceSafeHeightMatchesProtectedZones": all(
            abs(float(row["heightRangeMeters"][1]) - float(estimate["a100"]["serviceSafeHeightMeters"])) <= tolerance
            for row in a700["protectedSpaceBoxesLocal"]
            if "vertical-service-approach" in str(row["id"])
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "spansMeters": {
            "cleaningRequestUVN": cleaning_local,
            "cleaningMeasuredUVN": cleaning_world_uvn,
            "weighingRequestUVN": weighing_local,
            "weighingMeasuredUVN": weighing_world_uvn,
        },
    }
