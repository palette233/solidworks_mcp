"""Conservative Project03 AD00 flip-sweep proxy in the installation frame."""

from __future__ import annotations

import itertools
import math
from typing import Any


def _axis_value(point: list[float], axis: list[float]) -> float:
    return sum(point[index] * axis[index] for index in range(3))


def _world_bounds_to_frame_bounds(
    world_bounds: list[float], interface: dict[str, Any]
) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    axes = {
        "u": [float(value) for value in interface["flowAxisWorld"]],
        "v": [float(value) for value in interface["transverseAxisWorld"]],
        "n": [float(value) for value in interface["upAxisWorld"]],
    }
    points = []
    for x, y, z in itertools.product(
        (float(world_bounds[0]), float(world_bounds[3])),
        (float(world_bounds[1]), float(world_bounds[4])),
        (float(world_bounds[2]), float(world_bounds[5])),
    ):
        offset = [x - origin[0], y - origin[1], z - origin[2]]
        points.append({name: _axis_value(offset, axis) for name, axis in axes.items()})
    return {
        "minU": min(point["u"] for point in points),
        "maxU": max(point["u"] for point in points),
        "minV": min(point["v"] for point in points),
        "maxV": max(point["v"] for point in points),
        "minN": min(point["n"] for point in points),
        "maxN": max(point["n"] for point in points),
    }


def _corners(bounds: dict[str, float]) -> list[tuple[float, float, float]]:
    return list(
        itertools.product(
            (float(bounds["minU"]), float(bounds["maxU"])),
            (float(bounds["minV"]), float(bounds["maxV"])),
            (float(bounds["minN"]), float(bounds["maxN"])),
        )
    )


def _sweep_about_v(
    bounds: dict[str, float],
    pivot: tuple[float, float, float],
    angle_degrees: float,
    sample_step_degrees: float,
    uncertainty: float,
) -> tuple[dict[str, float], list[float]]:
    samples = max(1, int(math.ceil(angle_degrees / sample_step_degrees)))
    angles = sorted(
        {
            0.0,
            *(
                sign * angle_degrees * index / samples
                for sign in (-1.0, 1.0)
                for index in range(1, samples + 1)
            ),
        }
    )
    rotated: list[tuple[float, float, float]] = []
    for angle in angles:
        radians = math.radians(angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        for u, v, n in _corners(bounds):
            relative_u, relative_n = u - pivot[0], n - pivot[2]
            rotated.append(
                (
                    pivot[0] + cosine * relative_u + sine * relative_n,
                    v,
                    pivot[2] - sine * relative_u + cosine * relative_n,
                )
            )
    return (
        {
            "minU": min(point[0] for point in rotated) - uncertainty,
            "maxU": max(point[0] for point in rotated) + uncertainty,
            "minV": min(point[1] for point in rotated) - uncertainty,
            "maxV": max(point[1] for point in rotated) + uncertainty,
            "minN": min(point[2] for point in rotated) - uncertainty,
            "maxN": max(point[2] for point in rotated) + uncertainty,
        },
        angles,
    )


def _overlap(first: dict[str, float], second: dict[str, float], clearance: float) -> bool:
    return not (
        first["maxU"] + clearance <= second["minU"]
        or second["maxU"] + clearance <= first["minU"]
        or first["maxV"] + clearance <= second["minV"]
        or second["maxV"] + clearance <= first["minV"]
        or first["maxN"] + clearance <= second["minN"]
        or second["maxN"] + clearance <= first["minN"]
    )


def build_project03_ad00_dynamic_sweep(
    work_positions: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    occupancy: dict[str, Any],
    dynamic_estimates: dict[str, Any],
) -> dict[str, Any]:
    if dynamic_estimates.get("schemaVersion") != "project03-dynamic-estimates/v1":
        raise ValueError("Unsupported Project03 dynamic-estimate schema.")
    model = dynamic_estimates.get("ad00Flip") or {}
    angle = float(model.get("angleDegrees") or 0.0)
    step = float(model.get("sampleStepDegrees") or 0.0)
    uncertainty = float(model.get("pivotUncertaintyMeters") or 0.0)
    if not 0.0 < angle <= 90.0 or not 0.0 < step <= angle or uncertainty < 0.0:
        raise ValueError("AD00 dynamic angle, sample step or pivot uncertainty is invalid.")
    if work_positions.get("workPositionCount") != 2:
        raise ValueError("Project03 AD00 sweep expects exactly two work positions.")
    interface = first_stage_geometry["transportInstallationInterface"]
    sweep_rows = []
    for position in work_positions.get("workPositions") or []:
        static_bounds = _world_bounds_to_frame_bounds(
            position["worldBoundsMeters"], interface
        )
        center = position["installationFramePointMeters"]
        pivot = (float(center["u"]), float(center["v"]), float(center["normal"]))
        swept_bounds, angles = _sweep_about_v(
            static_bounds, pivot, angle, step, uncertainty
        )
        sweep_rows.append(
            {
                "workPositionId": position["stableId"],
                "sourceInstance": position["sourceInstance"],
                "staticBoundsInstallationMeters": static_bounds,
                "pivotInstallationMeters": {
                    "u": pivot[0],
                    "v": pivot[1],
                    "n": pivot[2],
                },
                "sweepBoundsInstallationMeters": swept_bounds,
                "sampleCount": len(angles),
                "sampleAnglesDegrees": angles,
            }
        )

    candidates = []
    for layout_object in occupancy.get("layoutObjects") or []:
        code = str(layout_object.get("primaryCode") or "")
        if code == "AD00":
            continue
        for sweep in sweep_rows:
            hits = [
                str(box.get("id") or "")
                for box in layout_object.get("occupancyBoxes") or []
                if _overlap(
                    sweep["sweepBoundsInstallationMeters"],
                    box["installationBoundsMeters"],
                    0.0,
                )
            ]
            if hits:
                candidates.append(
                    {
                        "workPositionId": sweep["workPositionId"],
                        "otherModuleCode": code,
                        "overlappingOccupancyBoxIds": hits,
                        "classification": (
                            "declared-process-neighbor-requires-state-specific-brep"
                            if code == "AE00"
                            else "unexpected-broad-phase-candidate-requires-exact-dynamic-check"
                        ),
                    }
                )
    return {
        "schemaVersion": "project03-ad00-dynamic-sweep-estimate/v1",
        "projectId": "project03",
        "success": True,
        "status": "AD00_CONSERVATIVE_SWEEP_ESTIMATE_BUILT_EXACT_DYNAMIC_VALIDATION_PENDING",
        "authority": model.get("axisAuthority"),
        "engineeringConfirmed": model.get("engineeringConfirmed") is True,
        "movingSubtree": model.get("movingSubtree"),
        "rotationAxisFrame": model.get("axisFrame"),
        "angleDegrees": angle,
        "directionPolicy": model.get("directionPolicy"),
        "pivotPolicy": model.get("pivotPolicy"),
        "pivotUncertaintyMeters": uncertainty,
        "sampleStepDegrees": step,
        "workPositionSweeps": sweep_rows,
        "broadPhaseCandidateCount": len(candidates),
        "broadPhaseCandidates": candidates,
        "staticBroadPhaseClear": len(candidates) == 0,
        "productionDynamicReady": False,
        "blockers": [
            "The revolute axis and pivot are inferred, not read from an authored CAD mate/controller limit.",
            "AABB sweep is conservative and identifies candidates; it cannot prove exact moving-body clearance.",
            "Carrier/product state and contact with AE00 must be validated in state-specific CAD before release.",
        ],
        "nextGate": "Create authored start/end CAD states for each AD20 station and run exact B-rep only for the reported candidates.",
    }
