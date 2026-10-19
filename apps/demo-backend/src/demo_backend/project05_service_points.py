"""Infer coarse Project05 service targets from complete G000/N000/P000 CAD captures.

The returned ports are deliberately geometry-backed proxies.  They are suitable
for planar layout/reach screening, but they are not vendor-authored nozzle
datums and therefore must not be presented as production calibration values.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in values]


def _box(body: dict[str, Any]) -> list[float]:
    value = body.get("BoundingBoxWorld", body.get("boundingBoxWorld"))
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError("Captured service body is missing a six-value world AABB")
    return [float(item) for item in value]


def _component(body: dict[str, Any]) -> dict[str, Any]:
    return body.get("Component", body.get("component", {})) or {}


def _hierarchy(body: dict[str, Any]) -> str:
    component = _component(body)
    return str(component.get("HierarchyPath", component.get("hierarchyPath", "")))


def _path(body: dict[str, Any]) -> str:
    component = _component(body)
    return str(component.get("Path", component.get("path", "")))


def _complete(capture: dict[str, Any], token: str) -> list[dict[str, Any]]:
    if not capture.get("coverageComplete"):
        raise ValueError(f"Project05 {token} world capture is incomplete")
    bodies = capture.get("bodies") or []
    if not bodies:
        raise ValueError(f"Project05 {token} world capture contains no bodies")
    return bodies


def _union(bodies: Iterable[dict[str, Any]]) -> list[float]:
    boxes = [_box(body) for body in bodies]
    if not boxes:
        raise ValueError("Cannot calculate bounds for an empty CAD selection")
    return [min(box[index] for box in boxes) for index in range(3)] + [
        max(box[index + 3] for box in boxes) for index in range(3)
    ]


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _top_center(bounds: list[float], up_axis: list[float]) -> list[float]:
    point = _center(bounds)
    axis = max(range(3), key=lambda index: abs(up_axis[index]))
    point[axis] = bounds[axis + 3] if up_axis[axis] >= 0 else bounds[axis]
    return point


def _installation_point(point: Iterable[float], frame: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in frame["originWorldMeters"]]
    relative = [float(value) - origin[index] for index, value in enumerate(point)]
    return {
        "u": _dot(relative, frame["flowAxisWorld"]),
        "v": _dot(relative, frame["transverseAxisWorld"]),
        "normal": _dot(relative, frame["upAxisWorld"]),
    }


def _by_part(bodies: Iterable[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    expected = token.casefold()
    return [
        body
        for body in bodies
        if expected in Path(_path(body)).name.casefold()
        or expected in _hierarchy(body).casefold()
    ]


def _by_subtree_instance(
    bodies: Iterable[dict[str, Any]], subtree_token: str
) -> dict[str, list[dict[str, Any]]]:
    expression = re.compile(rf"({re.escape(subtree_token)}-\d+)", re.IGNORECASE)
    result: dict[str, list[dict[str, Any]]] = {}
    for body in bodies:
        match = expression.search(_hierarchy(body))
        if match:
            result.setdefault(match.group(1), []).append(body)
    return result


def _by_component_instance(
    bodies: Iterable[dict[str, Any]], part_token: str
) -> dict[str, list[dict[str, Any]]]:
    expression = re.compile(rf"({re.escape(part_token)}-\d+)$", re.IGNORECASE)
    result: dict[str, list[dict[str, Any]]] = {}
    for body in bodies:
        name = str(_component(body).get("Name", _component(body).get("name", "")))
        match = expression.search(name)
        if match:
            result.setdefault(match.group(1), []).append(body)
    return result


def _port(
    *,
    port_id: str,
    capability: str,
    point: list[float],
    frame: dict[str, Any],
    source_module: str,
    source_components: list[str],
    proxy_method: str,
    confidence: str,
) -> dict[str, Any]:
    up = _normalize(frame["upAxisWorld"])
    return {
        "id": port_id,
        "capability": capability,
        "worldMeters": point,
        "installationFrameMeters": _installation_point(point, frame),
        "approachAxisWorld": [-value for value in up],
        "sourceModule": source_module,
        "sourceComponents": source_components,
        "proxyMethod": proxy_method,
        "confidence": confidence,
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
    }


def infer_project05_service_points(
    g000_capture: dict[str, Any],
    n000_capture: dict[str, Any],
    p000_capture: dict[str, Any],
    first_stage_geometry: dict[str, Any],
) -> dict[str, Any]:
    """Return six CAD-backed reach targets for the Project05 service modules."""

    g_bodies = _complete(g000_capture, "G000")
    n_bodies = _complete(n000_capture, "N000")
    p_bodies = _complete(p000_capture, "P000")
    frame = first_stage_geometry["installationFrame"]
    up = _normalize(frame["upAxisWorld"])
    flow = _normalize(frame["flowAxisWorld"])

    calibration_plate = _by_part(g_bodies, "FL5C251093G100013.01")
    if not calibration_plate:
        raise ValueError("Project05 G000 calibration target plate is absent")
    # The thin plate is the observed glue-dot target.  Its center is a safer
    # planar proxy than choosing an arbitrary edge as a 'top' face.
    calibration_point = _center(_union(calibration_plate))

    weighing_cup = _by_part(g_bodies, "FL00002-00468")
    if not weighing_cup:
        raise ValueError("Project05 G000 weighing cup FL00002-00468 is absent")
    weighing_point = _top_center(_union(weighing_cup), up)

    cleaner_instances = _by_subtree_instance(n_bodies, "FL9C251093NB21.001")
    if len(cleaner_instances) != 2:
        raise ValueError(
            f"Expected two Project05 N000 cleaner-head subtrees; found {len(cleaner_instances)}"
        )
    cleaner_points = [
        (name, _top_center(_union(bodies), up))
        for name, bodies in cleaner_instances.items()
    ]
    cleaner_points.sort(key=lambda item: _dot(item[1], flow))

    drain_instances = _by_component_instance(p_bodies, "FL00002-00549")
    if len(drain_instances) != 2:
        raise ValueError(
            f"Expected two Project05 P000 drain cups; found {len(drain_instances)}"
        )
    drain_points = [
        (name, _top_center(_union(bodies), up))
        for name, bodies in drain_instances.items()
    ]
    drain_points.sort(key=lambda item: _dot(item[1], flow))

    ports = [
        _port(
            port_id="calibration-glue-target",
            capability="calibration",
            point=calibration_point,
            frame=frame,
            source_module="G000",
            source_components=["FL5C251093G100013.01"],
            proxy_method="center of the explicit 30 x 30 x 2 mm calibration target plate envelope",
            confidence="medium-high",
        ),
        _port(
            port_id="weighing-cup",
            capability="weighing",
            point=weighing_point,
            frame=frame,
            source_module="G000",
            source_components=["FL00002-00468"],
            proxy_method="top-center of the explicit G000 weighing-cup leaf envelope",
            confidence="high",
        ),
    ]
    for index, (name, point) in enumerate(cleaner_points, start=1):
        ports.append(
            _port(
                port_id=f"cleaning-position-{index}",
                capability="cleaning",
                point=point,
                frame=frame,
                source_module="N000",
                source_components=[name],
                proxy_method="top-center of one repeated N000 NB21 cleaner-head subtree envelope",
                confidence="medium",
            )
        )
    for index, (name, point) in enumerate(drain_points, start=1):
        ports.append(
            _port(
                port_id=f"glue-drain-cup-{index}",
                capability="glue_drain",
                point=point,
                frame=frame,
                source_module="P000",
                source_components=[name],
                proxy_method="top-center of one explicit P000 FL00002-00549 cup envelope",
                confidence="high",
            )
        )

    aggregate_cleaning_point = [
        sum(point[index] for _, point in cleaner_points) / len(cleaner_points)
        for index in range(3)
    ]
    return {
        "schemaVersion": "project05-service-points/v1",
        "projectId": "project05",
        "status": "PROJECT05_SERVICE_POINTS_INFERRED_FOR_COARSE_LAYOUT",
        "authority": "complete G000/N000/P000 leaf geometry plus Project05 PPT function mapping",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "servicePorts": ports,
        "moduleSummary": {
            "G000": {"functions": ["calibration", "weighing"], "targetCount": 2},
            "N000": {"functions": ["cleaning"], "targetCount": 2},
            "P000": {"functions": ["glue_drain"], "targetCount": 2},
        },
        "legacyCompatibility": {
            "cleaningServicePointWorldMeters": aggregate_cleaning_point,
            "method": "midpoint of two independently retained cleaning positions",
        },
        "captureCoverage": {
            "G000": {"bodyCount": len(g_bodies), "coverageComplete": True},
            "N000": {"bodyCount": len(n_bodies), "coverageComplete": True},
            "P000": {"bodyCount": len(p_bodies), "coverageComplete": True},
        },
        "releaseDecision": {
            "coarsePlanarReachMayBeUsed": True,
            "productionMotionMayBeUsed": False,
            "reason": "real CAD structures are identified, but exact nozzle insertion heights and vendor datums remain unconfirmed",
        },
        "evidence": [
            "G000 contains a dedicated calibration CCD subtree, a thin calibration target plate and an explicit FL00002-00468 weighing cup.",
            "N000 contains exactly two repeated NB21 cleaner-head subtrees in the active top-level instance.",
            "P000 contains exactly two active FL00002-00549 drain cups; the second top-level P000 pose is suppressed and is not counted.",
        ],
        "interpretationLimits": [
            "Service targets are envelope-derived proxy points, not authored SolidWorks reference points.",
            "Cleaning and drain points represent opening/head top centers; insertion depth and tool sweep are not modeled.",
            "The calibration target uses the thin target-plate center; the exact glue-dot surface normal still requires engineering confirmation.",
        ],
    }
