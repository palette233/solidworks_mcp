"""Map standalone Project05 module captures into the prototype assembly frame."""
from __future__ import annotations

from itertools import product
from typing import Any, Iterable


def _transform_point(point: Iterable[float], pose: dict[str, Any]) -> list[float]:
    x, y, z = (float(value) for value in point)
    axes = [pose["XAxis"], pose["YAxis"], pose["ZAxis"]]
    translation = [float(value) for value in pose["Translation"]]
    return [
        translation[index]
        + x * float(axes[0][index])
        + y * float(axes[1][index])
        + z * float(axes[2][index])
        for index in range(3)
    ]


def transform_aabb(box: Iterable[float], pose: dict[str, Any]) -> list[float]:
    """Transform all eight AABB corners and return a conservative world AABB."""

    values = [float(value) for value in box]
    if len(values) != 6:
        raise ValueError("A body envelope must contain six AABB coordinates")
    points = [
        _transform_point((x, y, z), pose)
        for x, y, z in product(
            (values[0], values[3]),
            (values[1], values[4]),
            (values[2], values[5]),
        )
    ]
    return [
        min(point[index] for point in points) for index in range(3)
    ] + [
        max(point[index] for point in points) for index in range(3)
    ]


def map_standalone_capture_to_project05_world(
    capture: dict[str, Any],
    top_level_poses: dict[str, Any],
    module_token: str,
) -> dict[str, Any]:
    candidates = [
        item
        for item in top_level_poses.get("components") or []
        if module_token.casefold() in str(item.get("Name") or "").casefold()
        and item.get("Translation") is not None
        and item.get("XAxis") is not None
        and item.get("YAxis") is not None
        and item.get("ZAxis") is not None
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Module token {module_token!r} must resolve to one active top-level pose; found {len(candidates)}"
        )
    pose = candidates[0]
    captures = capture.get("captures") or []
    if len(captures) != 1:
        raise ValueError("Standalone capture must contain exactly one @root result")
    root_capture = captures[0]
    if not bool(root_capture.get("CoverageComplete", root_capture.get("coverageComplete"))):
        raise ValueError("Standalone capture coverage is incomplete")

    mapped_bodies = []
    for body in root_capture.get("Bodies", root_capture.get("bodies", [])):
        local_box = body.get("BoundingBoxWorld", body.get("boundingBoxWorld"))
        if local_box is None:
            raise ValueError("Captured body is missing BoundingBoxWorld")
        mapped = dict(body)
        mapped["BoundingBoxStandaloneModule"] = [float(value) for value in local_box]
        mapped["BoundingBoxWorld"] = transform_aabb(local_box, pose)
        mapped_bodies.append(mapped)

    return {
        "schemaVersion": "project05-standalone-capture-world-map/v1",
        "projectId": "project05",
        "moduleToken": module_token,
        "moduleTopLevelPose": pose,
        "sourceStandaloneAssemblyPath": capture.get("assemblyPath"),
        "sourcePrototypeAssemblyPath": top_level_poses.get("sourceAssemblyPath"),
        "leafComponentCount": root_capture.get("LeafComponentCount", root_capture.get("leafComponentCount")),
        "bodyCount": len(mapped_bodies),
        "coverageComplete": True,
        "bodies": mapped_bodies,
        "method": "transform all eight standalone AABB corners by the captured top-level module pose",
    }
