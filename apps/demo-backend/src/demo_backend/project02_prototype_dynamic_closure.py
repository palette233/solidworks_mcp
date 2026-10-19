"""Release planning for the Project02 prototype-estimated dynamic profile.

The module deliberately separates three claims:

* solver feasibility under the prototype-estimated engineering profile;
* CAD evidence that is still required for the newly selected pose;
* production dynamic authority, which remains closed until real limits exist.
"""

from __future__ import annotations

import math
from typing import Any


def _point_to_local(transform: list[float], point: list[float]) -> list[float]:
    if len(transform) != 16 or len(point) != 3:
        raise ValueError("SolidWorks transform and point must contain 16 and 3 values")
    shifted = [float(point[index]) - float(transform[index + 9]) for index in range(3)]
    matrix = [
        [float(transform[0]), float(transform[3]), float(transform[6])],
        [float(transform[1]), float(transform[4]), float(transform[7])],
        [float(transform[2]), float(transform[5]), float(transform[8])],
    ]
    return [
        sum(matrix[row][column] * shifted[row] for row in range(3))
        for column in range(3)
    ]


def _point_to_world(transform: list[float], point: list[float]) -> list[float]:
    if len(transform) != 16 or len(point) != 3:
        raise ValueError("SolidWorks transform and point must contain 16 and 3 values")
    return [
        float(transform[0]) * point[0]
        + float(transform[3]) * point[1]
        + float(transform[6]) * point[2]
        + float(transform[9]),
        float(transform[1]) * point[0]
        + float(transform[4]) * point[1]
        + float(transform[7]) * point[2]
        + float(transform[10]),
        float(transform[2]) * point[0]
        + float(transform[5]) * point[1]
        + float(transform[8]) * point[2]
        + float(transform[11]),
    ]


def _project(point: list[float], frame: dict[str, Any]) -> list[float]:
    origin = [float(value) for value in frame["origin"]]
    delta = [float(point[index]) - origin[index] for index in range(3)]
    return [
        sum(delta[index] * float(frame["uAxis"][index]) for index in range(3)),
        sum(delta[index] * float(frame["vAxis"][index]) for index in range(3)),
    ]


def recover_reference_layout(
    source_capture: dict[str, Any],
    reference_pose_capture: dict[str, Any],
) -> dict[str, list[float]]:
    """Recover bottom-anchor U/V from a transform-only reference capture."""
    frame = source_capture.get("baseFrame") or {}
    source_by_name = {
        str(item["componentName"]): item
        for item in source_capture.get("components") or []
    }
    recovered: dict[str, list[float]] = {}
    for reference in reference_pose_capture.get("components") or []:
        name = str(reference.get("componentName") or "")
        source = source_by_name.get(name)
        if not source:
            continue
        source_transform = source.get("sourceTransform")
        reference_transform = reference.get("sourceTransform")
        bottom_center = source.get("bottomCenterWorld")
        if not (
            isinstance(source_transform, list)
            and isinstance(reference_transform, list)
            and isinstance(bottom_center, list)
        ):
            continue
        local_anchor = _point_to_local(source_transform, bottom_center)
        reference_world = _point_to_world(reference_transform, local_anchor)
        recovered[name] = _project(reference_world, frame)
    return recovered


def compare_candidate_to_reference(
    solution: dict[str, Any],
    reference_layout: dict[str, list[float]],
    *,
    unchanged_tolerance_meters: float = 0.001,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for component in solution.get("components") or []:
        name = str(component.get("componentName") or "")
        layout = component.get("layout2d") or {}
        reference = reference_layout.get(name)
        if reference is None or "x" not in layout or "y" not in layout:
            continue
        candidate = [float(layout["x"]), float(layout["y"])]
        delta = [candidate[index] - reference[index] for index in range(2)]
        distance = math.hypot(*delta)
        rows.append(
            {
                "componentName": name,
                "candidateUvMeters": candidate,
                "referenceUvMeters": reference,
                "deltaUvMeters": delta,
                "translationDeltaMeters": distance,
                "referencePoseReusable": distance <= unchanged_tolerance_meters,
            }
        )
    changed = [row for row in rows if not row["referencePoseReusable"]]
    return {
        "unchangedToleranceMeters": unchanged_tolerance_meters,
        "comparedComponentCount": len(rows),
        "changedComponentCount": len(changed),
        "maximumTranslationDeltaMeters": max(
            (float(row["translationDeltaMeters"]) for row in rows),
            default=0.0,
        ),
        "cadReplayRequired": bool(changed),
        "components": rows,
    }


def build_closure_report(
    estimate: dict[str, Any],
    profile_audit: dict[str, Any],
    preview: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    metrics = preview.get("metrics") or {}
    solutions = preview.get("solutions") or []
    rank1 = solutions[0] if solutions else {}
    solver_passed = bool(
        metrics.get("hardFeasible")
        and metrics.get("processPassed") == metrics.get("processTotal")
        and metrics.get("spatialPassed") == metrics.get("spatialTotal")
        and metrics.get("interactionPassed") == metrics.get("interactionTotal")
    )
    estimated_profile_passed = bool(
        estimate.get("gate", {}).get("prototypeEstimatedDynamicDemoPassed")
        and profile_audit.get("estimatedProfilePassed")
    )
    replay_required = bool(comparison.get("cadReplayRequired"))
    predicted_pairs = int(rank1.get("predictedConditionalBrepPairCount") or 0)
    leaf_risks = rank1.get("conditionalLeafAabbRisks") or []
    if not estimated_profile_passed or not solver_passed:
        status = "ESTIMATED_PROFILE_OR_SOLVER_FAILED"
    elif replay_required:
        status = "ESTIMATED_PROFILE_SOLVER_PASSED_CAD_REPLAY_REQUIRED"
    else:
        status = "ESTIMATED_PROFILE_SOLVER_PASSED_REFERENCE_POSE_REUSABLE"
    return {
        "schemaVersion": "project02-prototype-estimated-closure/v1",
        "projectId": "project02",
        "status": status,
        "estimatedProfilePassed": estimated_profile_passed,
        "solverHardConstraintsPassed": solver_passed,
        "cadReplayRequired": replay_required,
        "productionDynamicReleaseAllowed": False,
        "solverMetrics": metrics,
        "selectedCandidate": {
            "rank": rank1.get("rank"),
            "score": rank1.get("score"),
            "predictedConditionalBrepPairCount": predicted_pairs,
            "predictedConditionalLeafAabbHitCount": int(
                rank1.get("predictedConditionalLeafAabbHitCount") or 0
            ),
            "priorityLeafRiskPairs": leaf_risks,
        },
        "referenceComparison": comparison,
        "stages": [
            {"id": "estimate", "passed": estimated_profile_passed},
            {"id": "solver", "passed": solver_passed},
            {
                "id": "cad-replay",
                "passed": not replay_required,
                "pending": replay_required,
                "reason": "candidate top-level poses differ from the accepted v52 reference",
            },
            {
                "id": "post-replay-aabb",
                "passed": False,
                "pending": replay_required,
                "reason": "world AABBs must be recaptured from the saved candidate assembly",
            },
            {
                "id": "conditional-brep",
                "passed": False,
                "pending": replay_required and predicted_pairs > 0,
                "reason": "run exact checks only for post-Replay overlapping conditional pairs",
            },
            {
                "id": "production-dynamic-release",
                "passed": False,
                "pending": True,
                "reason": "real A100 travel limits and any genuine A700 moving states remain unavailable",
            },
        ],
    }
