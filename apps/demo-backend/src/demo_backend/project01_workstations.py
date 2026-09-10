from __future__ import annotations

import math
from typing import Any


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _union_bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot build a workstation envelope from an empty body set")
    bounds = [float(value) for value in bodies[0]["BoundingBoxWorld"]]
    for body in bodies[1:]:
        current = [float(value) for value in body["BoundingBoxWorld"]]
        for index in range(3):
            bounds[index] = min(bounds[index], current[index])
            bounds[index + 3] = max(bounds[index + 3], current[index + 3])
    return bounds


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def infer_project01_work_positions(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    ff_capture = next(
        (
            capture
            for capture in captures
            if "FF00" in str((capture.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if ff_capture is None or not ff_capture.get("CoverageComplete"):
        raise ValueError("FF00 leaf-body capture is absent or incomplete")

    interface = first_stage_geometry["transportInstallationInterface"]
    origin = [float(value) for value in interface["originWorldMeters"]]
    flow = [float(value) for value in interface["flowAxisWorld"]]
    transverse = [float(value) for value in interface["transverseAxisWorld"]]
    up = [float(value) for value in interface["upAxisWorld"]]
    work_positions = []
    for instance in ("FL9C24N074FF10.001-1", "FL9C24N074FF10.001-2"):
        needle = f"/{instance}/"
        bodies = [
            body
            for body in ff_capture.get("Bodies") or []
            if needle in str((body.get("Component") or {}).get("Name", ""))
            and "SNAP CARRIER" in str((body.get("Component") or {}).get("Name", "")).upper()
        ]
        bounds = _union_bounds(bodies)
        center = _center(bounds)
        offset = [center[index] - origin[index] for index in range(3)]
        work_positions.append(
            {
                "sourceInstance": instance,
                "semanticEvidence": "SNAP CARRIER / US dispensing product subtree",
                "bodyCount": len(bodies),
                "worldBoundsMeters": bounds,
                "worldCenterMeters": center,
                "installationFramePointMeters": {
                    "u": _dot(offset, flow),
                    "v": _dot(offset, transverse),
                    "normal": _dot(offset, up),
                },
            }
        )
    work_positions.sort(key=lambda item: item["installationFramePointMeters"]["u"])
    if len(work_positions) != 2 or any(item["bodyCount"] < 1 for item in work_positions):
        raise ValueError("Expected two populated FF10 SNAP CARRIER workstation subtrees")
    for index, item in enumerate(work_positions):
        item["stableId"] = "workPositionLowU" if index == 0 else "workPositionHighU"
    separation = math.dist(
        work_positions[0]["worldCenterMeters"], work_positions[1]["worldCenterMeters"]
    )
    return {
        "schemaVersion": "project01-work-positions/v1",
        "projectId": "project01",
        "status": "PROJECT01_TWO_WORK_POSITIONS_INFERRED",
        "authority": "prototype-subtree-geometry-project01-only",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "workPositionCount": 2,
        "centerSeparationMeters": separation,
        "workPositions": work_positions,
        "captureCoverage": {
            "ff00LeafComponentCount": ff_capture.get("LeafComponentCount"),
            "ff00BodyCount": ff_capture.get("BodyCount"),
            "ff00FailedBodyCount": ff_capture.get("FailedBodyCount"),
            "coverageComplete": ff_capture.get("CoverageComplete"),
        },
        "interpretationLimits": [
            "Low-U/high-U are stable geometric labels; PPT work-position numbering has not been asserted.",
            "Envelope centers are coarse process targets, not measured valve contact points.",
            "The second carrier is rotated/elevated relative to the first, so only plan U/V is used for gantry coverage.",
        ],
    }
