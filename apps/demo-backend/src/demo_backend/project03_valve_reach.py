from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in vector]


def _bounds(bodies: list[dict[str, Any]]) -> list[float]:
    boxes = [[float(value) for value in item["BoundingBoxWorld"]] for item in bodies]
    if not boxes:
        raise ValueError("Cannot calculate empty body bounds")
    return [min(box[index] for box in boxes) for index in range(3)] + [
        max(box[index + 3] for box in boxes) for index in range(3)
    ]


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _interval(bounds: list[float], origin: list[float], axis: list[float]) -> list[float]:
    values = []
    for choice in itertools.product((0, 1), repeat=3):
        corner = [bounds[index + (3 if choice[index] else 0)] for index in range(3)]
        values.append(_dot([corner[index] - origin[index] for index in range(3)], axis))
    return [min(values), max(values)]


def _capture(captures: list[dict[str, Any]], marker: str) -> dict[str, Any]:
    result = next(
        (
            item
            for item in captures
            if marker.upper()
            in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if result is None or not result.get("CoverageComplete"):
        raise ValueError(f"Project03 {marker} capture is absent or incomplete")
    return result


def _part_name(body: dict[str, Any]) -> str:
    return Path(str((body.get("Component") or {}).get("Path", ""))).name.upper()


def _rectangle(min_u: float, max_u: float, min_v: float, max_v: float) -> dict[str, float]:
    return {
        "minU": min_u,
        "maxU": max_u,
        "minV": min_v,
        "maxV": max_v,
        "widthU": max_u - min_u,
        "widthV": max_v - min_v,
    }


def infer_project03_valve_reach(
    leaf_capture: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    ab = _capture(captures, "AB00")
    ac = _capture(captures, "AC00")
    interface = first_stage_geometry["transportInstallationInterface"]
    origin = [float(value) for value in interface["originWorldMeters"]]
    flow = _normalize([float(value) for value in interface["flowAxisWorld"]])
    transverse = _normalize([float(value) for value in interface["transverseAxisWorld"]])

    transverse_scales = [
        body
        for body in ab.get("Bodies") or []
        if _part_name(body).endswith("FL201AR-00057.SLDPRT")
    ]
    if len(transverse_scales) != 2:
        raise ValueError(f"Expected two Project03 transverse scales; found {len(transverse_scales)}")
    transverse_interval = _interval(_bounds(transverse_scales), origin, transverse)

    flow_candidates = [
        body
        for body in ab.get("Bodies") or []
        if "T7509A-800L" in _part_name(body)
    ]
    if not flow_candidates:
        raise ValueError("Project03 T7509A-800L flow-axis body is absent")
    up = _normalize([float(value) for value in interface["upAxisWorld"]])

    def flow_span(body: dict[str, Any]) -> float:
        value = _interval([float(item) for item in body["BoundingBoxWorld"]], origin, flow)
        return value[1] - value[0]

    long_flow_candidates = [body for body in flow_candidates if flow_span(body) >= 0.75]
    if not long_flow_candidates:
        raise ValueError("Project03 T7509A-800L contains no long flow-axis scale body")

    def cross_section(body: dict[str, Any]) -> float:
        bounds = [float(value) for value in body["BoundingBoxWorld"]]
        transverse_span = _interval(bounds, origin, transverse)
        up_span = _interval(bounds, origin, up)
        return (transverse_span[1] - transverse_span[0]) * (up_span[1] - up_span[0])

    # The motor part is multi-body.  Its 900 mm magnetic/measurement strip is
    # the slender long body; choosing the longest structural rail would
    # overstate travel by about 160 mm.
    flow_scale = min(long_flow_candidates, key=cross_section)
    flow_interval = _interval(
        [float(value) for value in flow_scale["BoundingBoxWorld"]], origin, flow
    )

    valve_bodies = [
        body
        for body in ac.get("Bodies") or []
        if _part_name(body).endswith("FL237AA-00012.SLDPRT")
    ]
    valve_instances: dict[str, list[dict[str, Any]]] = {}
    for body in valve_bodies:
        name = str((body.get("Component") or {}).get("Name", ""))
        valve_instances.setdefault(name, []).append(body)
    if len(valve_instances) != 2:
        raise ValueError(f"Expected two Project03 dispensing valves; found {len(valve_instances)}")
    valve_centers = [(name, _center(_bounds(bodies))) for name, bodies in valve_instances.items()]
    valve_centers.sort(key=lambda item: _dot(item[1], flow))
    pair_center = [
        (valve_centers[0][1][index] + valve_centers[1][1][index]) / 2.0
        for index in range(3)
    ]
    offsets = []
    for name, center in valve_centers:
        delta = [center[index] - pair_center[index] for index in range(3)]
        offsets.append(
            {
                "componentName": name,
                "centerWorldMeters": center,
                "offsetFromPairCenterMeters": {
                    "u": _dot(delta, flow),
                    "v": _dot(delta, transverse),
                },
            }
        )

    individual = []
    for index, offset in enumerate(offsets, start=1):
        du = offset["offsetFromPairCenterMeters"]["u"]
        dv = offset["offsetFromPairCenterMeters"]["v"]
        individual.append(
            {
                "id": f"valve{index}",
                "componentName": offset["componentName"],
                "reachInstallationFrameMeters": _rectangle(
                    flow_interval[0] + du,
                    flow_interval[1] + du,
                    transverse_interval[0] + dv,
                    transverse_interval[1] + dv,
                ),
            }
        )
    common = _rectangle(
        max(item["reachInstallationFrameMeters"]["minU"] for item in individual),
        min(item["reachInstallationFrameMeters"]["maxU"] for item in individual),
        max(item["reachInstallationFrameMeters"]["minV"] for item in individual),
        min(item["reachInstallationFrameMeters"]["maxV"] for item in individual),
    )
    if common["widthU"] <= 0 or common["widthV"] <= 0:
        raise ValueError("Project03 dual-valve common reach is empty")

    targets = []
    for item in work_positions.get("workPositions") or []:
        point = item["installationFramePointMeters"]
        targets.append({"id": item["stableId"], "source": "transportWorkPosition", "u": float(point["u"]), "v": float(point["v"])})
    for item in service_points.get("servicePorts") or []:
        point = item["installationFrameMeters"]
        targets.append({"id": item["id"], "source": item["capability"], "u": float(point["u"]), "v": float(point["v"])})
    checks = []
    for target in targets:
        margins = {
            "minU": target["u"] - common["minU"],
            "maxU": common["maxU"] - target["u"],
            "minV": target["v"] - common["minV"],
            "maxV": common["maxV"] - target["v"],
        }
        checks.append(
            {
                **target,
                "insideCommonReach": all(value >= -1e-9 for value in margins.values()),
                "boundaryMarginsMeters": margins,
                "minimumBoundaryMarginMeters": min(margins.values()),
            }
        )
    all_reachable = bool(checks) and all(item["insideCommonReach"] for item in checks)

    return {
        "schemaVersion": "project03-dual-valve-reach/v1",
        "projectId": "project03",
        "status": "PROJECT03_DUAL_VALVE_REACH_INFERRED",
        "authority": "project03-prototype-axis-scale-and-dual-valve-offset-baseline",
        "coarseLayoutUsable": all_reachable,
        "engineeringConfirmed": False,
        "vendorConfirmed": False,
        "axisEvidence": {
            "flow": {
                "sourceComponent": str((flow_scale.get("Component") or {}).get("Name", "")),
                "scaleSpanMeters": flow_interval[1] - flow_interval[0],
                "installationIntervalMeters": {"min": flow_interval[0], "max": flow_interval[1]},
            },
            "transverse": {
                "sourcePart": "FL201AR-00057.SLDPRT",
                "scaleInstanceCount": len(transverse_scales),
                "scaleSpanMeters": transverse_interval[1] - transverse_interval[0],
                "installationIntervalMeters": {"min": transverse_interval[0], "max": transverse_interval[1]},
            },
        },
        "pptNominalTravelMeters": {
            "x": 0.8,
            "y": 0.65,
            "z": 0.1,
            "source": "03-PPT slide 12",
            "usedAsCadReachLimit": False,
            "reason": "PPT axis labels and CAD installation U/V mapping are not yet engineering-confirmed; using them directly would exclude prototype service targets.",
        },
        "valvePair": {
            "sourcePart": "FL237AA-00012.SLDPRT",
            "spacingMeters": math.dist(valve_centers[0][1], valve_centers[1][1]),
            "spacingAlongFlowMeters": abs(offsets[1]["offsetFromPairCenterMeters"]["u"] - offsets[0]["offsetFromPairCenterMeters"]["u"]),
            "spacingAlongTransverseMeters": abs(offsets[1]["offsetFromPairCenterMeters"]["v"] - offsets[0]["offsetFromPairCenterMeters"]["v"]),
            "instances": offsets,
        },
        "individualValveReachInstallationFrameMeters": individual,
        "commonReachInstallationFrameMeters": common,
        "requiredTargetCount": len(checks),
        "requiredTargetChecks": checks,
        "allRequiredTargetsInsideCommonReach": all_reachable,
        "minimumTargetBoundaryMarginMeters": min((item["minimumBoundaryMarginMeters"] for item in checks), default=None),
        "captureCoverage": {
            "ab00": {"leafComponentCount": ab.get("LeafComponentCount"), "bodyCount": ab.get("BodyCount"), "failedBodyCount": ab.get("FailedBodyCount"), "coverageComplete": ab.get("CoverageComplete")},
            "ac00": {"leafComponentCount": ac.get("LeafComponentCount"), "bodyCount": ac.get("BodyCount"), "failedBodyCount": ac.get("FailedBodyCount"), "coverageComplete": ac.get("CoverageComplete")},
        },
        "interpretationLimits": [
            "The 900/1100 mm CAD scale envelopes are prototype coarse-layout baselines, not mechanical or software limit-switch travel.",
            "03-PPT slide 12 reports 800/650/100 mm maximum travel; its machine-axis mapping to installation U/V/N remains unresolved and is recorded as a discrepancy.",
            "Valve offsets use assembly-envelope centers because authored nozzle-tip datums are absent.",
            "Only planar static reach is checked; Z stroke, two-photo calibration motion, hoses and motion-sweep collision are excluded.",
        ],
    }
