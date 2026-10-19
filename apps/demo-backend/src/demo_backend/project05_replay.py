"""Expand an approved Project 05 solve into eleven real top-level modules."""

from __future__ import annotations

import copy
import itertools
from typing import Any

from .project01_replay import build_project01_replay_layout


def _project05_code(name: str, expected_codes: set[str]) -> str:
    matches = [code for code in expected_codes if code.upper() in name.upper()]
    if len(matches) != 1:
        raise ValueError(
            f"Project 05 component '{name}' resolves to {len(matches)} member codes."
        )
    return matches[0]


def build_project05_replay_layout(
    selected: dict[str, Any],
    occupancy: dict[str, Any],
    top_level_poses: dict[str, Any],
) -> dict[str, Any]:
    """Preserve A/E and B/Z grouping while emitting all active CAD modules."""

    normalized_occupancy = copy.deepcopy(occupancy)
    frame = normalized_occupancy.get("installationFrame") or {}
    frame["axesWorld"] = {
        "u": list(frame.get("flowAxisWorld") or []),
        "v": list(frame.get("transverseAxisWorld") or []),
        "n": list(frame.get("upAxisWorld") or []),
    }
    normalized_occupancy["installationFrame"] = frame

    result = build_project01_replay_layout(
        selected,
        normalized_occupancy,
        top_level_poses,
        project_id="project05",
        code_marker="C254098",
        expected_component_count=11,
        base_component_name="FL9C254098A000.001-1",
        code_resolver=_project05_code,
    )

    # Top-level GetBox may include non-body construction/display geometry.  The
    # Project 05 occupancy capture is complete, so save/reopen geometry audits
    # must compare against the union of captured leaf bodies instead.
    u_axis = frame["axesWorld"]["u"]
    v_axis = frame["axesWorld"]["v"]
    n_axis = frame["axesWorld"]["n"]
    origin = frame["originWorldMeters"]
    leaf_boxes_by_code: dict[str, list[dict[str, float]]] = {}
    for layout_object in occupancy.get("layoutObjects") or []:
        for box in layout_object.get("leafBodyOccupancyBoxes") or []:
            leaf_boxes_by_code.setdefault(str(box["memberCode"]), []).append(
                box["installationBoundsMeters"]
            )

    for component in result["components"]:
        code = str(component["memberCode"])
        boxes = leaf_boxes_by_code.get(code) or []
        if not boxes:
            raise ValueError(f"Project 05 member '{code}' has no complete leaf-body boxes.")
        delta_u, delta_v = component["replayDeltaInstallationMeters"]
        world_points = []
        for box in boxes:
            for u, v, n in itertools.product(
                (float(box["minU"]) + delta_u, float(box["maxU"]) + delta_u),
                (float(box["minV"]) + delta_v, float(box["maxV"]) + delta_v),
                (float(box["minN"]), float(box["maxN"])),
            ):
                world_points.append([
                    float(origin[index])
                    + float(u_axis[index]) * u
                    + float(v_axis[index]) * v
                    + float(n_axis[index]) * n
                    for index in range(3)
                ])
        component["boundingBoxWorld"] = [
            min(point[index] for point in world_points) for index in range(3)
        ] + [
            max(point[index] for point in world_points) for index in range(3)
        ]
        component["boundingBoxEvidence"] = {
            "source": "complete-leaf-body-aabb-union",
            "leafBodyBoxCount": len(boxes),
        }
    result["constraintPlan"]["replayBoundingBoxEvidence"] = (
        "complete-leaf-body-aabb-union"
    )
    return result
