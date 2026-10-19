"""Infer the Project05 operation-side plane and coarse residual service space."""

from __future__ import annotations

from itertools import product
from typing import Any, Iterable


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _point(point: Iterable[float], frame: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in frame["originWorldMeters"]]
    offset = [float(value) - origin[index] for index, value in enumerate(point)]
    return {
        "u": _dot(offset, frame["flowAxisWorld"]),
        "v": _dot(offset, frame["transverseAxisWorld"]),
        "normal": _dot(offset, frame["upAxisWorld"]),
    }


def _bounds(bounds: list[float], frame: dict[str, Any]) -> dict[str, float]:
    values = [
        _point(point, frame)
        for point in product(
            (bounds[0], bounds[3]),
            (bounds[1], bounds[4]),
            (bounds[2], bounds[5]),
        )
    ]
    return {
        "minU": min(item["u"] for item in values),
        "maxU": max(item["u"] for item in values),
        "minV": min(item["v"] for item in values),
        "maxV": max(item["v"] for item in values),
        "minNormal": min(item["normal"] for item in values),
        "maxNormal": max(item["normal"] for item in values),
    }


def _pose(poses: dict[str, Any], token: str) -> dict[str, Any]:
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


def infer_project05_operation_side(
    top_level_poses: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    frame = first_stage_geometry["installationFrame"]
    a_bounds = _bounds(_pose(top_level_poses, "A000")["BoundingBoxWorld"], frame)
    d_bounds = _bounds(_pose(top_level_poses, "D000")["BoundingBoxWorld"], frame)
    service_codes = ("G000", "N000", "P000")
    service = {
        code: _bounds(_pose(top_level_poses, code)["BoundingBoxWorld"], frame)
        for code in service_codes
    }
    operation_plane_v = a_bounds["maxV"]
    strip = {
        "minU": a_bounds["minU"] + 0.05,
        "maxU": a_bounds["maxU"] - 0.05,
        "minV": d_bounds["maxV"] + 0.02,
        "maxV": operation_plane_v - 0.05,
    }
    checks = []
    for code, bounds in service.items():
        inside = (
            bounds["minU"] >= strip["minU"]
            and bounds["maxU"] <= strip["maxU"]
            and bounds["minV"] >= strip["minV"]
            and bounds["maxV"] <= strip["maxV"]
        )
        checks.append({
            "moduleToken": code,
            "boundsInstallationMeters": bounds,
            "insideCoarseOperationSideStrip": inside,
            "clearanceToOperationPlaneMeters": operation_plane_v - bounds["maxV"],
            "clearanceFromTransportEnvelopeMeters": bounds["minV"] - d_bounds["maxV"],
        })
    all_inside = all(item["insideCoarseOperationSideStrip"] for item in checks)
    return {
        "schemaVersion": "project05-operation-side/v1",
        "projectId": "project05",
        "status": "PROJECT05_OPERATION_SIDE_COARSE_CAPACITY_INFERRED",
        "authority": "A000 prototype envelope, +transverse service-side cluster and D000 transport envelope",
        "coarseLayoutUsable": all_inside,
        "engineeringConfirmed": False,
        "operationSide": {
            "sign": "+v",
            "worldAxis": frame["transverseAxisWorld"],
            "planeCoordinateV": operation_plane_v,
            "planeDefinition": "outer +transverse plane of the active A000 envelope",
            "exactOperatorDoorFaceRegistered": False,
        },
        "coarseServiceStripInstallationMeters": strip,
        "serviceModuleChecks": checks,
        "allPrototypeServiceModulesInsideStrip": all_inside,
        "clearancePolicyMeters": {
            "frameEdgeInset": 0.05,
            "transportEnvelopeGap": 0.02,
            "source": "explicit coarse-layout allowance; not a maintenance standard",
        },
        "releaseDecision": {
            "coarseOperationSidePlacementMayBeUsed": all_inside,
            "maintenanceReleaseMayBeUsed": False,
            "reason": "the side and residual strip are structurally supported, but door opening and tool-removal sweeps are not captured",
        },
        "interpretationLimits": [
            "The operation-side plane is an A000 envelope proxy, not a registered operator-door face.",
            "The strip only screens coarse planar placement; human reach, door sweep, cable access and replacement paths remain unverified.",
        ],
    }
