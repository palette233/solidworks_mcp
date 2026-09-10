from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any


TRANSVERSE_SCALE_PART = "FL201AR-00057.SLDPRT"
VALVE_ASSEMBLY_PART = "FL237AA-00012.SLDPRT"


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in vector]


def _bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot calculate bounds for an empty body collection")
    boxes = [[float(value) for value in item["BoundingBoxWorld"]] for item in bodies]
    return [min(box[axis] for box in boxes) for axis in range(3)] + [
        max(box[axis + 3] for box in boxes) for axis in range(3)
    ]


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _projection_interval(bounds: list[float], origin: list[float], axis: list[float]) -> list[float]:
    values = []
    for choice in itertools.product((0, 1), repeat=3):
        corner = [bounds[index + (3 if choice[index] else 0)] for index in range(3)]
        values.append(_dot([corner[index] - origin[index] for index in range(3)], axis))
    return [min(values), max(values)]


def _capture_for(captures: list[dict[str, Any]], marker: str) -> dict[str, Any]:
    capture = next(
        (
            item
            for item in captures
            if marker.upper()
            in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if capture is None or not capture.get("CoverageComplete"):
        raise ValueError(f"{marker} leaf-body capture is absent or incomplete")
    return capture


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


def infer_project01_valve_reach(
    leaf_capture: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    lm_capture = _capture_for(captures, "LM00")
    zz_capture = _capture_for(captures, "ZZ00")
    interface = first_stage_geometry["transportInstallationInterface"]
    origin = [float(value) for value in interface["originWorldMeters"]]
    flow = _normalize([float(value) for value in interface["flowAxisWorld"]])
    transverse = _normalize([float(value) for value in interface["transverseAxisWorld"]])

    transverse_scale_bodies = [
        body
        for body in lm_capture.get("Bodies") or []
        if _part_name(body).endswith(TRANSVERSE_SCALE_PART)
    ]
    if len(transverse_scale_bodies) != 2:
        raise ValueError(
            f"Expected two transverse grating scales; found {len(transverse_scale_bodies)}"
        )
    transverse_bounds = _bounds(transverse_scale_bodies)
    transverse_interval = _projection_interval(transverse_bounds, origin, transverse)

    flow_candidates = [
        body
        for body in lm_capture.get("Bodies") or []
        if "磁栅尺" in _part_name(body)
    ]
    if not flow_candidates:
        raise ValueError("LM00 flow-axis magnetic scale is absent")
    flow_scale = max(
        flow_candidates,
        key=lambda body: (
            _projection_interval(
                [float(value) for value in body["BoundingBoxWorld"]], origin, flow
            )[1]
            - _projection_interval(
                [float(value) for value in body["BoundingBoxWorld"]], origin, flow
            )[0]
        ),
    )
    flow_bounds = [float(value) for value in flow_scale["BoundingBoxWorld"]]
    flow_interval = _projection_interval(flow_bounds, origin, flow)

    valve_bodies = [
        body
        for body in zz_capture.get("Bodies") or []
        if _part_name(body).endswith(VALVE_ASSEMBLY_PART)
    ]
    valve_instances: dict[str, list[dict[str, Any]]] = {}
    for body in valve_bodies:
        name = str((body.get("Component") or {}).get("Name", ""))
        valve_instances.setdefault(name, []).append(body)
    if len(valve_instances) != 2:
        raise ValueError(
            f"Expected two {VALVE_ASSEMBLY_PART} instances; found {len(valve_instances)}"
        )
    valve_centers = [
        (name, _center(_bounds(bodies))) for name, bodies in valve_instances.items()
    ]
    valve_centers.sort(key=lambda item: _dot(item[1], flow))
    pair_center = [
        (valve_centers[0][1][axis] + valve_centers[1][1][axis]) / 2.0
        for axis in range(3)
    ]
    valve_offsets = []
    for name, center in valve_centers:
        delta = [center[index] - pair_center[index] for index in range(3)]
        valve_offsets.append(
            {
                "componentName": name,
                "centerWorldMeters": center,
                "offsetFromPairCenterMeters": {
                    "u": _dot(delta, flow),
                    "v": _dot(delta, transverse),
                },
            }
        )
    head_spacing = math.dist(valve_centers[0][1], valve_centers[1][1])

    individual = []
    for index, offset in enumerate(valve_offsets, start=1):
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
        raise ValueError("The inferred two valve reach rectangles have no common intersection")

    targets = []
    for item in work_positions.get("workPositions") or []:
        point = item["installationFramePointMeters"]
        targets.append(
            {
                "id": item["stableId"],
                "source": "transportWorkPosition",
                "u": float(point["u"]),
                "v": float(point["v"]),
            }
        )
    for item in service_points.get("servicePorts") or []:
        point = item["installationFrameMeters"]
        targets.append(
            {
                "id": item["id"],
                "source": item["capability"],
                "u": float(point["u"]),
                "v": float(point["v"]),
            }
        )
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
    all_targets_reachable = bool(checks) and all(
        item["insideCommonReach"] for item in checks
    )

    return {
        "schemaVersion": "project01-dual-valve-reach/v1",
        "projectId": "project01",
        "status": "PROJECT01_DUAL_VALVE_REACH_INFERRED",
        "authority": "prototype-axis-scale-and-dual-valve-offset-baseline-project01-only",
        "coarseLayoutUsable": all_targets_reachable,
        "engineeringConfirmed": False,
        "vendorConfirmed": False,
        "axisEvidence": {
            "flow": {
                "sourceComponent": str((flow_scale.get("Component") or {}).get("Name", "")),
                "scaleSpanMeters": flow_interval[1] - flow_interval[0],
                "installationIntervalMeters": {"min": flow_interval[0], "max": flow_interval[1]},
            },
            "transverse": {
                "sourcePart": TRANSVERSE_SCALE_PART,
                "scaleInstanceCount": len(transverse_scale_bodies),
                "scaleSpanMeters": transverse_interval[1] - transverse_interval[0],
                "installationIntervalMeters": {
                    "min": transverse_interval[0],
                    "max": transverse_interval[1],
                },
            },
        },
        "valvePair": {
            "sourcePart": VALVE_ASSEMBLY_PART,
            "spacingMeters": head_spacing,
            "spacingAlongFlowMeters": abs(
                valve_offsets[1]["offsetFromPairCenterMeters"]["u"]
                - valve_offsets[0]["offsetFromPairCenterMeters"]["u"]
            ),
            "spacingAlongTransverseMeters": abs(
                valve_offsets[1]["offsetFromPairCenterMeters"]["v"]
                - valve_offsets[0]["offsetFromPairCenterMeters"]["v"]
            ),
            "instances": valve_offsets,
        },
        "individualValveReachInstallationFrameMeters": individual,
        "commonReachInstallationFrameMeters": common,
        "requiredTargetCount": len(checks),
        "requiredTargetChecks": checks,
        "allRequiredTargetsInsideCommonReach": all_targets_reachable,
        "minimumTargetBoundaryMarginMeters": min(
            (item["minimumBoundaryMarginMeters"] for item in checks), default=None
        ),
        "captureCoverage": {
            "lm00": {
                "leafComponentCount": lm_capture.get("LeafComponentCount"),
                "bodyCount": lm_capture.get("BodyCount"),
                "failedBodyCount": lm_capture.get("FailedBodyCount"),
                "coverageComplete": lm_capture.get("CoverageComplete"),
            },
            "zz00": {
                "leafComponentCount": zz_capture.get("LeafComponentCount"),
                "bodyCount": zz_capture.get("BodyCount"),
                "failedBodyCount": zz_capture.get("FailedBodyCount"),
                "coverageComplete": zz_capture.get("CoverageComplete"),
            },
        },
        "interpretationLimits": [
            "Scale body spans are prototype static-equivalent travel baselines, not mechanical/software limit-switch measurements.",
            "Valve target positions use the FL237AA-00012 assembly envelope centers to recover pair offset; authored nozzle-tip datums are absent.",
            "The common rectangle is valid for coarse plan-layout reach only; Z stroke, acceleration, hoses and motion-sweep collision are not validated.",
        ],
    }
