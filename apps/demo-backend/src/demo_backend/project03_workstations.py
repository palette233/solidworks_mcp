from __future__ import annotations

import math
from typing import Any


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _union_bounds(bodies: list[dict[str, Any]]) -> list[float]:
    if not bodies:
        raise ValueError("Cannot build a Project03 workstation envelope from an empty body set")
    bounds = [float(value) for value in bodies[0]["BoundingBoxWorld"]]
    for body in bodies[1:]:
        current = [float(value) for value in body["BoundingBoxWorld"]]
        for index in range(3):
            bounds[index] = min(bounds[index], current[index])
            bounds[index + 3] = max(bounds[index + 3], current[index + 3])
    return bounds


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _frame_point(center: list[float], interface: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    offset = [center[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, [float(value) for value in interface["flowAxisWorld"]]),
        "v": _dot(offset, [float(value) for value in interface["transverseAxisWorld"]]),
        "normal": _dot(offset, [float(value) for value in interface["upAxisWorld"]]),
    }


def _direct_child(name: str) -> str | None:
    parts = str(name).split("/")
    return parts[1] if len(parts) > 1 else None


def infer_project03_work_positions(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    """Infer two Project03 dispensing stations from the repeated AD10/AD20 subtrees."""

    captures = leaf_capture.get("captures") or []
    ad_capture = next(
        (
            item
            for item in captures
            if "AD00" in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    ae_capture = next(
        (
            item
            for item in captures
            if "AE00" in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if ad_capture is None or not ad_capture.get("CoverageComplete"):
        raise ValueError("Project03 AD00 leaf-body capture is absent or incomplete")
    if ae_capture is None or not ae_capture.get("CoverageComplete"):
        raise ValueError("Project03 AE00 leaf-body capture is absent or incomplete")

    interface = first_stage_geometry["transportInstallationInterface"]
    work_positions = []
    for instance in ("FL9A24D063AD10.001-1", "FL9A24D063AD10.001-2"):
        station_bodies = [
            body
            for body in ad_capture.get("Bodies") or []
            if _direct_child(str((body.get("Component") or {}).get("Name", ""))) == instance
            and "/FL9A24D063AD20.001-1/"
            in f"/{str((body.get('Component') or {}).get('Name', ''))}/"
        ]
        bounds = _union_bounds(station_bodies)
        center = _center(bounds)
        work_positions.append(
            {
                "sourceInstance": instance,
                "sourceProcessSubtree": "FL9A24D063AD20.001-1",
                "semanticEvidence": "Repeated AD10 station with AD20 lift/rotation carrier-support subtree",
                "bodyCount": len(station_bodies),
                "worldBoundsMeters": bounds,
                "worldCenterMeters": center,
                "installationFramePointMeters": _frame_point(center, interface),
            }
        )
    work_positions.sort(key=lambda item: item["installationFramePointMeters"]["u"])
    if len(work_positions) != 2 or any(item["bodyCount"] < 1 for item in work_positions):
        raise ValueError("Expected two populated Project03 AD10/AD20 workstation subtrees")

    for index, item in enumerate(work_positions):
        item["stableId"] = "workPositionLowU" if index == 0 else "workPositionHighU"
        item["pptRoleCandidate"] = "Working Position A/B; exact A/B sign mapping unresolved"

    guard_groups: dict[str, list[dict[str, Any]]] = {}
    for body in ae_capture.get("Bodies") or []:
        child = _direct_child(str((body.get("Component") or {}).get("Name", "")))
        if child and child.startswith("FL9A24D063AE90.001-"):
            guard_groups.setdefault(child, []).append(body)
    station_guards = []
    for instance, bodies in guard_groups.items():
        bounds = _union_bounds(bodies)
        center = _center(bounds)
        station_guards.append(
            {
                "sourceInstance": instance,
                "bodyCount": len(bodies),
                "worldBoundsMeters": bounds,
                "worldCenterMeters": center,
                "installationFramePointMeters": _frame_point(center, interface),
            }
        )
    station_guards.sort(key=lambda item: item["installationFramePointMeters"]["u"])

    midpoint_checks = []
    if len(station_guards) == 3:
        for index, work_position in enumerate(work_positions):
            lower = station_guards[index]["installationFramePointMeters"]["u"]
            upper = station_guards[index + 1]["installationFramePointMeters"]["u"]
            midpoint = (lower + upper) / 2.0
            actual = work_position["installationFramePointMeters"]["u"]
            midpoint_checks.append(
                {
                    "workPositionId": work_position["stableId"],
                    "lowerGuardInstance": station_guards[index]["sourceInstance"],
                    "upperGuardInstance": station_guards[index + 1]["sourceInstance"],
                    "guardMidpointU": midpoint,
                    "workPositionU": actual,
                    "absoluteDeltaMeters": abs(actual - midpoint),
                }
            )

    center_separation = math.dist(
        work_positions[0]["worldCenterMeters"], work_positions[1]["worldCenterMeters"]
    )
    maximum_midpoint_delta = max(
        (item["absoluteDeltaMeters"] for item in midpoint_checks), default=float("inf")
    )
    coarse_usable = len(station_guards) == 3 and maximum_midpoint_delta <= 0.03
    return {
        "schemaVersion": "project03-work-positions/v1",
        "projectId": "project03",
        "status": "PROJECT03_TWO_WORK_POSITIONS_INFERRED",
        "authority": "project03-prototype-subtree-geometry-plus-03-ppt-slides-9-and-14",
        "coarseLayoutUsable": coarse_usable,
        "engineeringConfirmed": False,
        "workPositionCount": 2,
        "centerSeparationMeters": center_separation,
        "workPositions": work_positions,
        "transportStationGuards": station_guards,
        "geometricConsistency": {
            "guardCount": len(station_guards),
            "midpointChecks": midpoint_checks,
            "maximumGuardMidpointDeltaMeters": maximum_midpoint_delta,
            "passesThirtyMillimeterTolerance": maximum_midpoint_delta <= 0.03,
        },
        "pptProcessEvidence": {
            "slide9": "Two carriers use working position 1/2 in overlapping sequence.",
            "slide14": "Two independent working positions A/B use lift and rotation; buffer scanning is separate.",
            "rotationAngleDegrees": 25.0,
        },
        "captureCoverage": {
            "ae00LeafComponentCount": ae_capture.get("LeafComponentCount"),
            "ae00BodyCount": ae_capture.get("BodyCount"),
            "ae00FailedBodyCount": ae_capture.get("FailedBodyCount"),
            "ad00LeafComponentCount": ad_capture.get("LeafComponentCount"),
            "ad00BodyCount": ad_capture.get("BodyCount"),
            "ad00FailedBodyCount": ad_capture.get("FailedBodyCount"),
            "coverageComplete": bool(
                ae_capture.get("CoverageComplete") and ad_capture.get("CoverageComplete")
            ),
        },
        "interpretationLimits": [
            "Low-U/high-U are stable geometric labels; the sign of the recovered flow axis has not been tied to PLC infeed direction, so A/B numbering is not asserted.",
            "AD20 subtree envelope centers are coarse plan targets for gantry coverage, not measured nozzle contact points on all four products.",
            "The buffer barcode stop is a distinct future scanner target and is not treated as a dispensing work position.",
            "The 25-degree rotation is PPT process evidence; this artifact does not simulate the moving swept volume.",
        ],
    }
