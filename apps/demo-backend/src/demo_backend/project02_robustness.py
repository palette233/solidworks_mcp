from __future__ import annotations

from copy import deepcopy
from typing import Any


GANTRY = "FL9A24D062A100.001-1"
TRANSPORT = "FL9A24D062A800.001-1"
SERVICE_COMPONENTS = (
    "FL9A24D062A500.001-1",
    "FL9A24D062A700.001-1",
    "FL9A24D062A300.001-1",
)


def with_scan_tolerance(request: dict[str, Any], tolerance_meters: float) -> dict[str, Any]:
    updated = deepcopy(request)
    transport = updated["moduleSemantics"][TRANSPORT]
    barcode = transport["points"]["barcode"]
    low_name, high_name = transport["parameters"]["dynamicScanWindowPointNames"]
    transport["points"][low_name] = {"u": float(barcode["u"]) - tolerance_meters, "v": float(barcode["v"])}
    transport["points"][high_name] = {"u": float(barcode["u"]) + tolerance_meters, "v": float(barcode["v"])}
    transport["parameters"]["dynamicScanStopToleranceMeters"] = tolerance_meters
    return updated


def with_service_space_scale(request: dict[str, Any], factor: float) -> dict[str, Any]:
    updated = deepcopy(request)
    for component in SERVICE_COMPONENTS:
        parameters = updated["moduleSemantics"][component]["parameters"]
        for space in parameters.get("protectedSpaceBoxesLocal") or []:
            min_u, min_v, max_u, max_v = map(float, space["bounds"])
            center_u = (min_u + max_u) / 2.0
            center_v = (min_v + max_v) / 2.0
            half_u = (max_u - min_u) * factor / 2.0
            half_v = (max_v - min_v) * factor / 2.0
            space["bounds"] = [center_u - half_u, center_v - half_v, center_u + half_u, center_v + half_v]
    return updated


def with_service_component_scale(
    request: dict[str, Any], component: str, factor: float
) -> dict[str, Any]:
    """Scale one service module's protected spaces without altering the others."""

    if component not in SERVICE_COMPONENTS:
        raise ValueError(f"Unsupported service component: {component}")
    updated = deepcopy(request)
    parameters = updated["moduleSemantics"][component]["parameters"]
    for space in parameters.get("protectedSpaceBoxesLocal") or []:
        min_u, min_v, max_u, max_v = map(float, space["bounds"])
        center_u = (min_u + max_u) / 2.0
        center_v = (min_v + max_v) / 2.0
        half_u = (max_u - min_u) * float(factor) / 2.0
        half_v = (max_v - min_v) * float(factor) / 2.0
        space["bounds"] = [
            center_u - half_u,
            center_v - half_v,
            center_u + half_u,
            center_v + half_v,
        ]
    return updated


def with_valve_reach_inset(request: dict[str, Any], inset_meters: float) -> dict[str, Any]:
    updated = deepcopy(request)
    regions = updated["moduleSemantics"][GANTRY]["regions"]
    for name in ("leftValveReach", "rightValveReach"):
        source = regions[name]
        shrunk = {
            "minU": float(source["minU"]) + inset_meters,
            "minV": float(source["minV"]) + inset_meters,
            "maxU": float(source["maxU"]) - inset_meters,
            "maxV": float(source["maxV"]) - inset_meters,
        }
        if not (shrunk["minU"] < shrunk["maxU"] and shrunk["minV"] < shrunk["maxV"]):
            raise ValueError("Valve reach inset removes the entire reach region")
        regions[name] = shrunk
    left = regions["leftValveReach"]
    right = regions["rightValveReach"]
    regions["dualValveReach"] = {
        "minU": max(left["minU"], right["minU"]),
        "minV": max(left["minV"], right["minV"]),
        "maxU": min(left["maxU"], right["maxU"]),
        "maxV": min(left["maxV"], right["maxV"]),
    }
    return updated


def with_valve_reach_directional_insets(
    request: dict[str, Any], inset_u_meters: float, inset_v_meters: float
) -> dict[str, Any]:
    """Shrink both valve envelopes independently along the two layout axes."""

    updated = deepcopy(request)
    regions = updated["moduleSemantics"][GANTRY]["regions"]
    for name in ("leftValveReach", "rightValveReach"):
        source = regions[name]
        shrunk = {
            "minU": float(source["minU"]) + float(inset_u_meters),
            "minV": float(source["minV"]) + float(inset_v_meters),
            "maxU": float(source["maxU"]) - float(inset_u_meters),
            "maxV": float(source["maxV"]) - float(inset_v_meters),
        }
        if not (shrunk["minU"] < shrunk["maxU"] and shrunk["minV"] < shrunk["maxV"]):
            raise ValueError("Directional valve reach insets remove the entire reach region")
        regions[name] = shrunk
    left = regions["leftValveReach"]
    right = regions["rightValveReach"]
    common = {
        "minU": max(left["minU"], right["minU"]),
        "minV": max(left["minV"], right["minV"]),
        "maxU": min(left["maxU"], right["maxU"]),
        "maxV": min(left["maxV"], right["maxV"]),
    }
    if not (common["minU"] < common["maxU"] and common["minV"] < common["maxV"]):
        raise ValueError("Directional valve reach insets remove the common valve reach")
    regions["dualValveReach"] = common
    return updated


def placement_signature(generated: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    solutions = ((generated.get("constraintPlan") or {}).get("jointSearch") or {}).get("solutions") or []
    if not solutions:
        return {}
    return {
        item["componentName"]: (
            float(item["x"]),
            float(item["y"]),
            float(item["thetaDegrees"]),
            float(item.get("normalOffsetMeters") or 0.0),
        )
        for item in solutions[0].get("placements") or []
    }


def compare_signatures(
    reference: dict[str, tuple[float, float, float, float]],
    candidate: dict[str, tuple[float, float, float, float]],
) -> dict[str, Any]:
    if set(reference) != set(candidate):
        return {"equivalent": False, "maxXyErrorMeters": None, "maxThetaErrorDegrees": None}
    max_xy = 0.0
    max_theta = 0.0
    for component, first in reference.items():
        second = candidate[component]
        max_xy = max(max_xy, ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5)
        max_theta = max(max_theta, abs(first[2] - second[2]))
    return {
        "equivalent": max_xy <= 1e-9 and max_theta <= 1e-7,
        "maxXyErrorMeters": max_xy,
        "maxThetaErrorDegrees": max_theta,
    }
