from __future__ import annotations

import math
from pathlib import Path
from typing import Any


GN_GROUPS = {
    "cleaning": "FL9C24N074GN10.001-1",
    "weighing": "FL9C24N074GN20.001-1",
    "glueDrain": "FL9C24N074FJ00.001-1",
    "glueHardnessTest": "FL9C24N074GN30.001-1",
}


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in vector]


def _installation_frame_point(
    point: list[float], interface: dict[str, Any]
) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    offset = [point[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, [float(value) for value in interface["flowAxisWorld"]]),
        "v": _dot(offset, [float(value) for value in interface["transverseAxisWorld"]]),
        "normal": _dot(offset, [float(value) for value in interface["upAxisWorld"]]),
    }


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


def _bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot calculate bounds for an empty body collection")
    boxes = [[float(value) for value in item["BoundingBoxWorld"]] for item in bodies]
    return [
        min(box[axis] for box in boxes) for axis in range(3)
    ] + [
        max(box[axis + 3] for box in boxes) for axis in range(3)
    ]


def _top_center(bounds: list[float], up_axis: list[float]) -> list[float]:
    point = [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]
    axis = max(range(3), key=lambda index: abs(up_axis[index]))
    point[axis] = bounds[axis + 3] if up_axis[axis] >= 0 else bounds[axis]
    return point


def _group_bodies(capture: dict[str, Any], nested_group: str) -> list[dict[str, Any]]:
    marker = f"/{nested_group}/".upper()
    return [
        body
        for body in capture.get("Bodies") or []
        if marker in str((body.get("Component") or {}).get("Name", "")).upper()
    ]


def _part_bodies(
    bodies: list[dict[str, Any]], part_file_name: str
) -> list[dict[str, Any]]:
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
    return {
        "id": port_id,
        "capability": capability,
        "worldMeters": point,
        "installationFrameMeters": _installation_frame_point(point, interface),
        "approachAxisWorld": [
            -value for value in _normalize([float(value) for value in interface["upAxisWorld"]])
        ],
        "sourceSubassembly": source_subassembly,
        "sourceComponents": source_components,
        "proxyMethod": proxy_method,
        "confidence": confidence,
        "engineeringConfirmed": False,
    }


def infer_project01_service_points(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    gn_capture = _capture_for(captures, "GN00")
    bd_capture = _capture_for(captures, "BD00")
    interface = first_stage_geometry["transportInstallationInterface"]
    up = _normalize([float(value) for value in interface["upAxisWorld"]])

    grouped = {
        capability: _group_bodies(gn_capture, nested_group)
        for capability, nested_group in GN_GROUPS.items()
    }
    if any(not bodies for bodies in grouped.values()):
        missing = [name for name, bodies in grouped.items() if not bodies]
        raise ValueError(f"GN00 nested function groups are absent: {missing}")

    cleaning_point = _top_center(_bounds(grouped["cleaning"]), up)

    weighing_cup = _part_bodies(grouped["weighing"], "FL00002-00468.SLDPRT")
    if not weighing_cup:
        raise ValueError("GN20 weighing cup FL00002-00468 is absent")
    weighing_point = _top_center(_bounds(weighing_cup), up)

    drain_cups = _part_bodies(grouped["glueDrain"], "FL00002-00549.SLDPRT")
    drain_instances: dict[str, list[dict[str, Any]]] = {}
    for body in drain_cups:
        name = str((body.get("Component") or {}).get("Name", ""))
        drain_instances.setdefault(name, []).append(body)
    if len(drain_instances) != 2:
        raise ValueError(
            f"Expected two GN00 drain cups FL00002-00549; found {len(drain_instances)}"
        )
    drain_points = [
        (
            name,
            _top_center(_bounds(bodies), up),
        )
        for name, bodies in drain_instances.items()
    ]
    flow = _normalize([float(value) for value in interface["flowAxisWorld"]])
    drain_points.sort(key=lambda item: _dot(item[1], flow))

    hardness_plate = _part_bodies(
        grouped["glueHardnessTest"], "FL5A24N074GN30002.01.SLDPRT"
    )
    if not hardness_plate:
        raise ValueError("GN30 hardness-test top plate is absent")
    hardness_point = _top_center(_bounds(hardness_plate), up)

    bd_target_parts = [
        body
        for body in bd_capture.get("Bodies") or []
        if any(
            token in Path(str((body.get("Component") or {}).get("Path", ""))).name.upper()
            for token in ("BD00007", "BD00008", "BD00009")
        )
    ]
    if not bd_target_parts:
        raise ValueError("BD00 prism-end target stack BD00007-09 is absent")
    highest_target = max(
        bd_target_parts,
        key=lambda body: _dot(_top_center([float(value) for value in body["BoundingBoxWorld"]], up), up),
    )
    calibration_point = _top_center(
        [float(value) for value in highest_target["BoundingBoxWorld"]], up
    )

    ports = [
        _port(
            port_id="cleaning-service",
            capability="cleaning",
            point=cleaning_point,
            interface=interface,
            source_subassembly=GN_GROUPS["cleaning"],
            source_components=[GN_GROUPS["cleaning"]],
            proxy_method="top-center of the complete GN10 cleaning subtree envelope",
            confidence="medium",
        ),
        _port(
            port_id="weighing-cup",
            capability="weighing",
            point=weighing_point,
            interface=interface,
            source_subassembly=GN_GROUPS["weighing"],
            source_components=["FL00002-00468.SLDPRT"],
            proxy_method="top-center of the explicit weighing-cup leaf envelope",
            confidence="high",
        ),
        _port(
            port_id="glue-drain-cup-1",
            capability="glue_drain",
            point=drain_points[0][1],
            interface=interface,
            source_subassembly=GN_GROUPS["glueDrain"],
            source_components=[drain_points[0][0]],
            proxy_method="top-center of explicit drain-cup leaf envelope",
            confidence="high",
        ),
        _port(
            port_id="glue-drain-cup-2",
            capability="glue_drain",
            point=drain_points[1][1],
            interface=interface,
            source_subassembly=GN_GROUPS["glueDrain"],
            source_components=[drain_points[1][0]],
            proxy_method="top-center of explicit drain-cup leaf envelope",
            confidence="high",
        ),
        _port(
            port_id="glue-hardness-test-bench",
            capability="glue_hardness_test",
            point=hardness_point,
            interface=interface,
            source_subassembly=GN_GROUPS["glueHardnessTest"],
            source_components=["FL5A24N074GN30002.01.SLDPRT"],
            proxy_method="top-center of the explicit GN30 test-bench plate envelope",
            confidence="high",
        ),
        _port(
            port_id="calibration-prism-target",
            capability="calibration",
            point=calibration_point,
            interface=interface,
            source_subassembly="FL9C24N074BD00.001-1",
            source_components=[
                Path(str((highest_target.get("Component") or {}).get("Path", ""))).name
            ],
            proxy_method="top-center of the highest leaf in the BD00007-09 prism-end target stack",
            confidence="medium",
        ),
    ]

    return {
        "schemaVersion": "project01-service-points/v1",
        "projectId": "project01",
        "status": "PROJECT01_SERVICE_POINTS_INFERRED",
        "authority": "prototype-leaf-geometry-and-ppt-functional-baseline-project01-only",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "combinedServiceModule": {
            "cadId": "FL9C24N074GN00.001",
            "functionCount": 4,
            "reachTargetCount": 5,
            "functions": ["cleaning", "weighing", "glue_drain", "glue_hardness_test"],
        },
        "calibrationModule": {
            "cadId": "FL9C24N074BD00.001",
            "reachTargetCount": 1,
        },
        "servicePorts": ports,
        "captureCoverage": {
            "gn00": {
                "leafComponentCount": gn_capture.get("LeafComponentCount"),
                "bodyCount": gn_capture.get("BodyCount"),
                "failedBodyCount": gn_capture.get("FailedBodyCount"),
                "coverageComplete": gn_capture.get("CoverageComplete"),
            },
            "bd00": {
                "leafComponentCount": bd_capture.get("LeafComponentCount"),
                "bodyCount": bd_capture.get("BodyCount"),
                "failedBodyCount": bd_capture.get("FailedBodyCount"),
                "coverageComplete": bd_capture.get("CoverageComplete"),
            },
        },
        "evidence": [
            "Project01 PPT slide 24 maps GN10, GN20, FJ00 and GN30 to cleaning, weighing, glue drain and hardness test.",
            "Project01 PPT slide 18 places nozzle calibration at the prism/light end, not at the CCD housing center.",
            "Leaf-body capture is complete for GN00 and BD00; explicit cup and test-bench leaves are used where available.",
        ],
        "interpretationLimits": [
            "Cleaning and calibration targets are prototype geometry proxies because an authored service datum is absent.",
            "All ports are suitable for coarse valve-reach layout only; nozzle clearance, insertion depth and vendor tolerances remain unconfirmed.",
            "The two drain cups are retained as separate reach targets although glue drain is one functional capability.",
        ],
    }
