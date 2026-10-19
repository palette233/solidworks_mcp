"""Build a conservative Project05 dual-valve planar reach baseline.

The authoritative CAD leaf capture of B000/Z000 is still pending.  For coarse
layout only, the model combines three independent prototype facts:

* B000 contains 950L and 800L linear-axis members;
* the B000 world envelope fixes their installation-frame centre;
* the two explicit P000 drain cups are 130 mm apart and act as a dual-head
  pitch proxy.

The common reach is the intersection of the two valve-tip reaches, so the
flow span is shortened by the valve pitch.  This is intentionally stricter
than treating the whole gantry bounding box as reachable.
"""

from __future__ import annotations

import re
from itertools import product
from typing import Any, Iterable


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _installation_point(point: Iterable[float], frame: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in frame["originWorldMeters"]]
    offset = [float(value) - origin[index] for index, value in enumerate(point)]
    return {
        "u": _dot(offset, frame["flowAxisWorld"]),
        "v": _dot(offset, frame["transverseAxisWorld"]),
        "normal": _dot(offset, frame["upAxisWorld"]),
    }


def _installation_bounds(bounds: list[float], frame: dict[str, Any]) -> dict[str, float]:
    points = [
        _installation_point(point, frame)
        for point in product(
            (float(bounds[0]), float(bounds[3])),
            (float(bounds[1]), float(bounds[4])),
            (float(bounds[2]), float(bounds[5])),
        )
    ]
    return {
        "minU": min(point["u"] for point in points),
        "maxU": max(point["u"] for point in points),
        "minV": min(point["v"] for point in points),
        "maxV": max(point["v"] for point in points),
        "minNormal": min(point["normal"] for point in points),
        "maxNormal": max(point["normal"] for point in points),
    }


def _top_pose(poses: dict[str, Any], token: str) -> dict[str, Any]:
    candidates = [
        item
        for item in poses.get("components") or []
        if token.casefold() in str(item.get("Name") or "").casefold()
        and isinstance(item.get("BoundingBoxWorld"), list)
        and len(item["BoundingBoxWorld"]) == 6
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected one active Project05 {token} pose; found {len(candidates)}")
    return candidates[0]


def _axis_lengths(file_names: Iterable[str]) -> list[float]:
    values: set[float] = set()
    for name in file_names:
        for match in re.finditer(r"(?:^|[-_])(\d{3,4})L(?:[-_.]|$)", str(name), re.IGNORECASE):
            millimeters = int(match.group(1))
            if 500 <= millimeters <= 1500:
                values.add(millimeters / 1000.0)
    return sorted(values, reverse=True)


def _ports_by_capability(service_points: dict[str, Any], capability: str) -> list[dict[str, Any]]:
    return [
        item
        for item in service_points.get("servicePorts") or []
        if item.get("capability") == capability
    ]


def infer_project05_dual_valve_reach(
    top_level_poses: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
    b000_file_names: Iterable[str],
) -> dict[str, Any]:
    frame = first_stage_geometry["installationFrame"]
    b_pose = _top_pose(top_level_poses, "B000")
    b_bounds = _installation_bounds(
        [float(value) for value in b_pose["BoundingBoxWorld"]], frame
    )
    lengths = _axis_lengths(b000_file_names)
    if len(lengths) < 2 or lengths[:2] != [0.95, 0.8]:
        raise ValueError(f"Project05 B000 950L/800L axis evidence is absent: {lengths}")
    flow_axis_length, transverse_axis_length = lengths[:2]

    drain_ports = _ports_by_capability(service_points, "glue_drain")
    if len(drain_ports) != 2:
        raise ValueError("Project05 needs exactly two drain ports to estimate dual-head pitch")
    drain_u = sorted(float(item["installationFrameMeters"]["u"]) for item in drain_ports)
    valve_pitch = drain_u[1] - drain_u[0]
    if not 0.05 <= valve_pitch <= 0.25:
        raise ValueError(f"Implausible Project05 dual-head pitch proxy: {valve_pitch}")

    center_u = (b_bounds["minU"] + b_bounds["maxU"]) / 2.0
    center_v = (b_bounds["minV"] + b_bounds["maxV"]) / 2.0
    common_flow_span = flow_axis_length - valve_pitch
    region = {
        "minU": center_u - common_flow_span / 2.0,
        "maxU": center_u + common_flow_span / 2.0,
        "minV": center_v - transverse_axis_length / 2.0,
        "maxV": center_v + transverse_axis_length / 2.0,
    }

    targets = []
    for item in work_positions.get("workPositions") or []:
        targets.append({
            "id": str(item.get("stableId")),
            "capability": "dispensing_work_position",
            "installationFrameMeters": item["installationFramePointMeters"],
        })
    for item in service_points.get("servicePorts") or []:
        targets.append({
            "id": str(item["id"]),
            "capability": str(item["capability"]),
            "installationFrameMeters": item["installationFrameMeters"],
        })

    checks = []
    for target in targets:
        point = target["installationFrameMeters"]
        u, v = float(point["u"]), float(point["v"])
        margins = {
            "toMinU": u - region["minU"],
            "toMaxU": region["maxU"] - u,
            "toMinV": v - region["minV"],
            "toMaxV": region["maxV"] - v,
        }
        checks.append({
            **target,
            "insideCommonPlanarReach": min(margins.values()) >= -1e-9,
            "minimumPlanarMarginMeters": min(margins.values()),
            "marginsMeters": margins,
        })

    all_inside = bool(checks) and all(item["insideCommonPlanarReach"] for item in checks)
    minimum_margin = min(item["minimumPlanarMarginMeters"] for item in checks)
    target_normals = [float(item["installationFrameMeters"]["normal"]) for item in targets]
    return {
        "schemaVersion": "project05-dual-valve-reach/v1",
        "projectId": "project05",
        "status": "PROJECT05_DUAL_VALVE_PLANAR_REACH_INFERRED_VERTICAL_PENDING",
        "authority": "Project05 B000 named 950L/800L axes + prototype installation envelope + P000 dual-cup pitch",
        "coarseLayoutUsable": all_inside,
        "engineeringConfirmed": False,
        "axisEvidence": {
            "sourceFileNameTokens": ["950L", "800L"],
            "flowAxisNominalLengthMeters": flow_axis_length,
            "transverseAxisNominalLengthMeters": transverse_axis_length,
            "axisAssignmentMethod": "950L assigned to transport-flow direction and 800L to transverse direction by prototype B000 aspect and target coverage",
            "assignmentEngineeringConfirmed": False,
        },
        "dualValvePitch": {
            "meters": valve_pitch,
            "method": "separation of the two explicit P000 drain-cup centers along installation flow",
            "engineeringConfirmed": False,
        },
        "commonPlanarReachInstallationMeters": region,
        "reachDerivation": {
            "centerFrom": "B000 prototype top-level envelope center",
            "flowSpanFormula": "950L nominal axis length minus dual-valve pitch",
            "transverseSpanFormula": "800L nominal axis length",
            "wholeB000EnvelopeUsedAsReach": False,
        },
        "targetChecks": checks,
        "targetCount": len(checks),
        "allTargetsInsideCommonPlanarReach": all_inside,
        "minimumPlanarMarginMeters": minimum_margin,
        "verticalEvidence": {
            "targetNormalRangeMeters": [min(target_normals), max(target_normals)],
            "zStrokeConfirmed": False,
            "status": "pending B000/Z000 leaf capture or vendor limits",
        },
        "releaseDecision": {
            "coarsePlanarLayoutMayBeUsed": all_inside,
            "productionReachMayBeUsed": False,
            "reason": "axis labels and valve pitch are prototype-derived; Z stroke, software limits and nozzle-tip datums are not authoritative",
        },
        "failedCaptureAttempt": {
            "attempted": True,
            "date": "2026-10-01",
            "stage": "MCP initialize handshake before B000 open",
            "elapsedSecondsBeforeAbort": 591,
            "solidWorksProcessTerminated": False,
            "followUp": "retry B000/Z000 complete leaf capture after a clean MCP/SolidWorks session",
        },
        "interpretationLimits": [
            "950L/800L file-name lengths are mechanical component evidence, not signed software limits.",
            "The P000 cup pitch is a dual-head pitch proxy; actual nozzle-tip offsets must replace it when measured.",
            "Only planar common reach is released for coarse layout; vertical reach and continuous swept collision remain blocked.",
        ],
    }
