"""Materialize an approved Project 01 layout as a ten-component Replay document."""

from __future__ import annotations

import copy
import math
from typing import Any


def _code_from_name(name: str, marker: str = "N074") -> str:
    stem = name.split("-", 1)[0]
    if marker not in stem:
        raise ValueError(f"Cannot derive module code from '{name}' using marker '{marker}'.")
    return stem.split(marker, 1)[1].split(".", 1)[0]


def _object_center(layout_object: dict[str, Any]) -> tuple[float, float]:
    boxes = layout_object.get("occupancyBoxes") or []
    if not boxes:
        raise ValueError(f"Layout object '{layout_object.get('id')}' has no occupancy boxes.")
    bounds = [box["installationBoundsMeters"] for box in boxes]
    return (
        (min(float(box["minU"]) for box in bounds) + max(float(box["maxU"]) for box in bounds)) / 2.0,
        (min(float(box["minV"]) for box in bounds) + max(float(box["maxV"]) for box in bounds)) / 2.0,
    )


def _add_scaled(origin: list[float], u_axis: list[float], v_axis: list[float], u: float, v: float) -> list[float]:
    return [
        float(origin[index]) + float(u_axis[index]) * u + float(v_axis[index]) * v
        for index in range(3)
    ]


def _shift_world(values: list[float], delta: list[float]) -> list[float]:
    return [float(values[index]) + delta[index] for index in range(3)]


def _shift_box(values: list[float], delta: list[float]) -> list[float]:
    if len(values) != 6:
        raise ValueError("World bounding box must contain six values.")
    return [
        float(values[0]) + delta[0],
        float(values[1]) + delta[1],
        float(values[2]) + delta[2],
        float(values[3]) + delta[0],
        float(values[4]) + delta[1],
        float(values[5]) + delta[2],
    ]


def build_project01_replay_layout(
    selected: dict[str, Any],
    occupancy: dict[str, Any],
    top_level_poses: dict[str, Any],
    *,
    project_id: str = "project01",
    code_marker: str = "N074",
    expected_component_count: int = 10,
    base_component_name: str = "FL9C24N074SS00.001-1",
) -> dict[str, Any]:
    approval = selected.get("visualApproval") or {}
    selected_rank = int(approval.get("selectedSolutionRank") or 0)
    if approval.get("approved") is not True or selected_rank < 1:
        raise ValueError("Project Replay requires a visually approved positive solution rank.")

    frame = occupancy.get("installationFrame") or {}
    axes = frame.get("axesWorld") or {}
    origin = [float(value) for value in frame.get("originWorldMeters") or []]
    u_axis = [float(value) for value in axes.get("u") or []]
    v_axis = [float(value) for value in axes.get("v") or []]
    n_axis = [float(value) for value in axes.get("n") or []]
    if any(len(value) != 3 for value in (origin, u_axis, v_axis, n_axis)):
        raise ValueError("Project 01 installation frame is incomplete.")

    objects = {item["id"]: item for item in occupancy.get("layoutObjects") or []}
    selected_objects = {item["layoutObjectId"]: item for item in selected.get("components") or []}
    poses = top_level_poses.get("components") or []
    expected_codes = {
        code
        for source_object in objects.values()
        for code in source_object.get("memberCodes") or []
    }
    pose_by_code = {}
    for item in poses:
        try:
            code = _code_from_name(item["Name"], code_marker)
        except ValueError:
            continue
        if code in expected_codes:
            pose_by_code[code] = item

    components: list[dict[str, Any]] = []
    member_coverage: list[str] = []
    for object_id, selected_object in selected_objects.items():
        source_object = objects.get(object_id)
        if source_object is None:
            raise ValueError(f"Selected layout object '{object_id}' is missing from occupancy evidence.")
        source_u, source_v = _object_center(source_object)
        target_layout = selected_object.get("layout2d") or {}
        target_u = float(target_layout["x"])
        target_v = float(target_layout["y"])
        delta_u = target_u - source_u
        delta_v = target_v - source_v
        delta_world = [
            u_axis[index] * delta_u + v_axis[index] * delta_v for index in range(3)
        ]
        source_anchor = _add_scaled(origin, u_axis, v_axis, source_u, source_v)

        member_codes = list(source_object.get("memberCodes") or selected_object.get("memberCodes") or [])
        if not member_codes:
            raise ValueError(f"Layout object '{object_id}' has no member codes.")
        for code in member_codes:
            pose = pose_by_code.get(code)
            if pose is None:
                raise ValueError(f"Top-level pose for Project 01 member '{code}' is missing.")
            translation = [float(value) for value in pose["Translation"]]
            x_axis = [float(value) for value in pose["XAxis"]]
            y_axis = [float(value) for value in pose["YAxis"]]
            z_axis = [float(value) for value in pose["ZAxis"]]
            components.append(
                {
                    "componentName": pose["Name"],
                    "filePath": pose["Path"],
                    "hierarchyPath": pose.get("HierarchyPath") or pose["Name"],
                    "bottomFaceName": "底面",
                    "sourceTransform": copy.deepcopy(pose["Transform"]),
                    "componentTranslation": translation,
                    "componentXAxis": x_axis,
                    "componentYAxis": y_axis,
                    "componentZAxis": z_axis,
                    "bottomCenterWorld": source_anchor,
                    "bottomNormalWorld": n_axis,
                    "boundingBoxWorld": _shift_box(pose["BoundingBoxWorld"], delta_world),
                    "layout2d": {
                        "x": target_u,
                        "y": target_v,
                        "thetaDegrees": float(target_layout.get("thetaDegrees") or 0.0),
                    },
                    "targetXAxisWorld": x_axis,
                    "targetYAxisWorld": y_axis,
                    "targetZAxisWorld": z_axis,
                    "targetComponentTranslation": _shift_world(translation, delta_world),
                    "layoutObjectId": object_id,
                    "memberCode": code,
                    "replayDeltaInstallationMeters": [delta_u, delta_v],
                    "replayDeltaWorldMeters": delta_world,
                    "constraintPlacement": {
                        "selectedTopKSolutionRank": selected_rank,
                        "rotationQuarters": int((selected_object.get("constraintPlacement") or {}).get("rotationQuarters") or 0),
                    },
                }
            )
            member_coverage.append(code)

    actual_codes = set(member_coverage)
    if expected_codes != actual_codes or len(components) != expected_component_count:
        raise ValueError(
            f"{project_id} Replay must cover all expected top-level modules; missing={sorted(expected_codes-actual_codes)}, "
            f"extra={sorted(actual_codes-expected_codes)}, count={len(components)}."
        )
    maximum_delta = max(
        math.sqrt(sum(value * value for value in component["replayDeltaWorldMeters"]))
        for component in components
    )
    return {
        "success": True,
        "message": f"Approved {project_id} solution expanded from 8 solve objects to {expected_component_count} real top-level modules.",
        "caseId": project_id,
        "sourceAssemblyPath": top_level_poses["sourceAssemblyPath"],
        "baseComponentName": base_component_name,
        "baseFrame": {
            "origin": origin,
            "uAxis": u_axis,
            "vAxis": v_axis,
            "normal": n_axis,
        },
        "layoutKind": "constraintGenerated",
        "components": components,
        "constraintPlan": {
            "keepTopLevelMatesSuppressed": True,
            "selectedSolutionRank": selected_rank,
            "solveObjectCount": len(selected_objects),
            "replayComponentCount": len(components),
            "maximumReplayDeltaMeters": maximum_delta,
            "prototypeEquivalent": maximum_delta <= 1e-9,
        },
        "prototypePoseUsedForSolving": bool(selected.get("prototypePoseUsedForSolving")),
        "visualApproval": approval,
    }
