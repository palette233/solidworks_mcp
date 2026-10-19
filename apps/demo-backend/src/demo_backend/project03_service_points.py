from __future__ import annotations

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


def _frame_point(point: list[float], interface: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    offset = [point[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, interface["flowAxisWorld"]),
        "v": _dot(offset, interface["transverseAxisWorld"]),
        "normal": _dot(offset, interface["upAxisWorld"]),
    }


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


def _bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot calculate empty body bounds")
    boxes = [[float(value) for value in item["BoundingBoxWorld"]] for item in bodies]
    return [min(box[index] for box in boxes) for index in range(3)] + [
        max(box[index + 3] for box in boxes) for index in range(3)
    ]


def _top_center(bounds: list[float], up_axis: list[float]) -> list[float]:
    point = [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]
    axis = max(range(3), key=lambda index: abs(up_axis[index]))
    point[axis] = bounds[axis + 3] if up_axis[axis] >= 0 else bounds[axis]
    return point


def _subtree_bodies(capture: dict[str, Any], subtree_name: str) -> list[dict[str, Any]]:
    marker = f"/{subtree_name}/".upper()
    return [
        body
        for body in capture.get("Bodies") or []
        if marker in str((body.get("Component") or {}).get("Name", "")).upper()
    ]


def _part_bodies(bodies: list[dict[str, Any]], part_file_name: str) -> list[dict[str, Any]]:
    expected = part_file_name.upper()
    return [
        body
        for body in bodies
        if Path(str((body.get("Component") or {}).get("Path", ""))).name.upper()
        == expected
    ]


def _port(
    *,
    port_id: str,
    capability: str,
    point: list[float],
    interface: dict[str, Any],
    source_subassembly: str,
    source_components: list[str],
    proxy_method: str,
    confidence: str,
) -> dict[str, Any]:
    up = _normalize([float(value) for value in interface["upAxisWorld"]])
    return {
        "id": port_id,
        "capability": capability,
        "worldMeters": point,
        "installationFrameMeters": _frame_point(point, interface),
        "approachAxisWorld": [-value for value in up],
        "sourceSubassembly": source_subassembly,
        "sourceComponents": source_components,
        "proxyMethod": proxy_method,
        "confidence": confidence,
        "engineeringConfirmed": False,
    }


def infer_project03_service_points(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    ag = _capture(captures, "AG00")
    ah = _capture(captures, "AH00")
    interface = first_stage_geometry["transportInstallationInterface"]
    up = _normalize([float(value) for value in interface["upAxisWorld"]])
    flow = _normalize([float(value) for value in interface["flowAxisWorld"]])

    cleaning_subtrees = ["FL9A24D063AG12.001-2", "FL9A24D063AG13.001-2"]
    cleaning_points = []
    for subtree in cleaning_subtrees:
        bodies = _subtree_bodies(ag, subtree)
        if not bodies:
            raise ValueError(f"Project03 cleaning subtree {subtree} is absent")
        cleaning_points.append((subtree, _top_center(_bounds(bodies), up)))
    cleaning_points.sort(key=lambda item: _dot(item[1], flow))

    ag20 = _subtree_bodies(ag, "FL9A24D063AG20.001-1")
    weighing_cup = _part_bodies(ag20, "24D063辅料-FL00002-00468.SLDPRT")
    if not weighing_cup:
        raise ValueError("Project03 AG20 weighing cup FL00002-00468 is absent")
    weighing_point = _top_center(_bounds(weighing_cup), up)

    ag30 = _subtree_bodies(ag, "FL9A24D063AG30.001-1")
    hardness_plate = _part_bodies(ag30, "FL5A24D063AG30002.01.SLDPRT")
    if not hardness_plate:
        raise ValueError("Project03 AG30 hardness-test plate is absent")
    hardness_point = _top_center(_bounds(hardness_plate), up)

    ag40 = _subtree_bodies(ag, "FL9A24D063AG40.001-1")
    drain_cups = _part_bodies(ag40, "24D063辅料-FL00002-00549.SLDPRT")
    drain_instances: dict[str, list[dict[str, Any]]] = {}
    for body in drain_cups:
        name = str((body.get("Component") or {}).get("Name", ""))
        drain_instances.setdefault(name, []).append(body)
    if len(drain_instances) != 2:
        raise ValueError(f"Expected two Project03 drain cups; found {len(drain_instances)}")
    drain_points = [
        (name, _top_center(_bounds(bodies), up))
        for name, bodies in drain_instances.items()
    ]
    drain_points.sort(key=lambda item: _dot(item[1], flow))

    prism = _part_bodies(
        ah.get("Bodies") or [], "24D063电气-FL812AA-00003.SLDPRT"
    )
    if not prism:
        raise ValueError("Project03 AH00 explicit 30 mm calibration prism is absent")
    calibration_point = _top_center(_bounds(prism), up)

    ports = []
    for index, (subtree, point) in enumerate(cleaning_points, start=1):
        ports.append(
            _port(
                port_id=f"cleaning-position-{index}",
                capability="cleaning",
                point=point,
                interface=interface,
                source_subassembly=subtree,
                source_components=[subtree],
                proxy_method="top-center of one repeated AG12/AG13 cleaning-clamp subtree envelope",
                confidence="medium",
            )
        )
    ports.extend(
        [
            _port(
                port_id="weighing-cup",
                capability="weighing",
                point=weighing_point,
                interface=interface,
                source_subassembly="FL9A24D063AG20.001-1",
                source_components=["24D063辅料-FL00002-00468.SLDPRT"],
                proxy_method="top-center of the explicit AG20 weighing-cup leaf envelope",
                confidence="high",
            ),
            _port(
                port_id="glue-hardness-test-bench",
                capability="glue_hardness_test",
                point=hardness_point,
                interface=interface,
                source_subassembly="FL9A24D063AG30.001-1",
                source_components=["FL5A24D063AG30002.01.SLDPRT"],
                proxy_method="top-center of the explicit AG30 test-bench plate envelope",
                confidence="high",
            ),
        ]
    )
    for index, (component, point) in enumerate(drain_points, start=1):
        ports.append(
            _port(
                port_id=f"glue-drain-cup-{index}",
                capability="glue_drain",
                point=point,
                interface=interface,
                source_subassembly="FL9A24D063AG40.001-1",
                source_components=[component],
                proxy_method="top-center of an explicit AG40 drain-cup leaf envelope",
                confidence="high",
            )
        )
    ports.append(
        _port(
            port_id="calibration-prism-target",
            capability="calibration",
            point=calibration_point,
            interface=interface,
            source_subassembly="FL9A24D063AH10.001-1",
            source_components=["24D063电气-FL812AA-00003.SLDPRT"],
            proxy_method="top-center of the explicit 30 x 30 x 30 mm AH10 prism envelope",
            confidence="high",
        )
    )

    return {
        "schemaVersion": "project03-service-points/v1",
        "projectId": "project03",
        "status": "PROJECT03_SERVICE_POINTS_INFERRED",
        "authority": "project03-complete-leaf-geometry-plus-03-ppt-slides-17-27",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "combinedServiceModule": {
            "cadId": "FL9A24D063AG00.001",
            "functionCount": 4,
            "reachTargetCount": 6,
            "functions": ["cleaning", "weighing", "glue_drain", "glue_hardness_test"],
        },
        "calibrationModule": {
            "cadId": "FL9A24D063AH00.001",
            "reachTargetCount": 1,
        },
        "servicePorts": ports,
        "captureCoverage": {
            "ag00": {
                "leafComponentCount": ag.get("LeafComponentCount"),
                "bodyCount": ag.get("BodyCount"),
                "failedBodyCount": ag.get("FailedBodyCount"),
                "coverageComplete": ag.get("CoverageComplete"),
            },
            "ah00": {
                "leafComponentCount": ah.get("LeafComponentCount"),
                "bodyCount": ah.get("BodyCount"),
                "failedBodyCount": ah.get("FailedBodyCount"),
                "coverageComplete": ah.get("CoverageComplete"),
            },
        },
        "evidence": [
            "03-PPT slide 23 maps AG00 to cleaning, weighing, glue draining and glue-hardness functions.",
            "03-PPT slide 27 requires two cleaning positions A/B; repeated AG12 and AG13 clamp subtrees supply two independent coarse targets.",
            "Explicit AG20 FL00002-00468 weighing cup, AG30 test plate and two AG40 FL00002-00549 drain cups are present in complete CAD capture.",
            "03-PPT slides 17-18 specify a 30 mm calibration prism; AH10 contains the explicit 30 x 30 x 30 mm FL812AA-00003 part.",
        ],
        "interpretationLimits": [
            "Cleaning targets are repeated clamp-subtree top-center proxies, not authored nozzle dip datums.",
            "The calibration point is the prism top-center proxy; two-photo camera offsets and the 40 mm second-shot motion are not modeled.",
            "All seven targets support planar coarse reach only; insertion depth, Z travel, tool sweep and maintenance clearance remain unconfirmed.",
        ],
    }
