from __future__ import annotations
import math
from typing import Any


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(first[index]) * float(second[index]) for index in range(3))


def _union_bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot build a Project05 workstation envelope from an empty body set")
    boxes = [[float(value) for value in body["BoundingBoxWorld"]] for body in bodies]
    return [min(box[index] for box in boxes) for index in range(3)] + [
        max(box[index + 3] for box in boxes) for index in range(3)
    ]


def _frame_point(point: list[float], frame: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in frame["originWorldMeters"]]
    offset = [point[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, frame["flowAxisWorld"]),
        "v": _dot(offset, frame["transverseAxisWorld"]),
        "normal": _dot(offset, frame["upAxisWorld"]),
    }


def infer_project05_work_positions(
    world_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    """Infer the two dispensing work points from explicit repeated KA00 header subtrees."""

    if not world_capture.get("coverageComplete"):
        raise ValueError("Project05 K000 world capture is absent or incomplete")
    bodies = list(world_capture.get("bodies") or [])
    frame = first_stage_geometry["installationFrame"]
    work_positions = []
    for instance in ("FL9C254098KA00.001-1", "FL9C254098KA00.001-2"):
        station_bodies = [
            body
            for body in bodies
            if str((body.get("Component") or {}).get("HierarchyPath", "")).startswith(instance)
            and "header 点胶位置" in str((body.get("Component") or {}).get("HierarchyPath", ""))
        ]
        bounds = _union_bounds(station_bodies)
        point = [
            (bounds[0] + bounds[3]) / 2.0,
            bounds[4],
            (bounds[2] + bounds[5]) / 2.0,
        ]
        work_positions.append({
            "sourceInstance": instance,
            "sourceProcessSubtree": "header 点胶位置",
            "bodyCount": len(station_bodies),
            "worldBoundsMeters": bounds,
            "worldPointMeters": point,
            "installationFramePointMeters": _frame_point(point, frame),
            "pointDefinition": "plan center and top elevation of the explicit header dispensing-position subtree",
        })
    work_positions.sort(key=lambda item: item["installationFramePointMeters"]["u"])
    if len(work_positions) != 2 or any(item["bodyCount"] < 1 for item in work_positions):
        raise ValueError("Expected two populated Project05 KA00 header dispensing-position subtrees")
    for index, item in enumerate(work_positions):
        item["stableId"] = "workPositionLowU" if index == 0 else "workPositionHighU"
        item["pptRoleCandidate"] = "Working Position 1/2; exact PLC numbering unresolved"

    separation = math.dist(
        work_positions[0]["worldPointMeters"], work_positions[1]["worldPointMeters"]
    )
    transverse_delta = abs(
        work_positions[0]["installationFramePointMeters"]["v"]
        - work_positions[1]["installationFramePointMeters"]["v"]
    )
    height_delta = abs(
        work_positions[0]["installationFramePointMeters"]["normal"]
        - work_positions[1]["installationFramePointMeters"]["normal"]
    )
    return {
        "schemaVersion": "project05-work-positions/v1",
        "projectId": "project05",
        "status": "PROJECT05_TWO_WORK_POSITIONS_INFERRED",
        "authority": "complete K000 standalone leaf capture mapped by prototype top-level pose plus 05-PPT slides 9 and 13",
        "coarseLayoutUsable": transverse_delta <= 0.001 and height_delta <= 0.001,
        "engineeringConfirmed": False,
        "workPositionCount": 2,
        "centerSeparationMeters": separation,
        "workPositions": work_positions,
        "geometricConsistency": {
            "transverseCoordinateDeltaMeters": transverse_delta,
            "heightCoordinateDeltaMeters": height_delta,
            "sameTransportLaneWithinOneMillimeter": transverse_delta <= 0.001,
            "sameWorkElevationWithinOneMillimeter": height_delta <= 0.001,
        },
        "captureCoverage": {
            "leafComponentCount": world_capture.get("leafComponentCount"),
            "bodyCount": world_capture.get("bodyCount"),
            "coverageComplete": True,
        },
        "pptProcessEvidence": {
            "slide9": "CCD and dispensing serve working position 1 followed by working position 2.",
            "slide13": "Two independent lift positions flank a distinct buffer scan position.",
        },
        "interpretationLimits": [
            "Low-U/high-U are stable geometric labels; PLC position 1/2 sign mapping is not asserted.",
            "The top-center point of each explicit header subtree is a coarse product-plane target, not a measured nozzle contact point for each of four products.",
            "The buffer barcode station is separate and remains to be recovered from D000/F000 geometry.",
        ],
    }
