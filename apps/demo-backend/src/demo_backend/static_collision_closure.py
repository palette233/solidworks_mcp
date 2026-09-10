"""Plan the staged Project 02 static-collision CAD closure.

The solver must stay fast and CAD-independent.  This module therefore turns
the static-collision policy, the current layout, and previously completed
leaf-level B-Rep checks into an auditable execution plan.  Exact CAD evidence
is reusable only when the checked component pair keeps the same relative 2D
pose and the source component files have not changed since the evidence was
written.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable


COMPONENT_CODES = ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401")

PAIR_PRIORITY: dict[frozenset[str], tuple[int, str]] = {
    frozenset(("A100", "A200")): (
        0,
        "Primary unresolved non-convex gantry/CCD interference gate.",
    ),
    frozenset(("A200", "A800")): (
        1,
        "CCD portal and transport pass-through require exact validation.",
    ),
    frozenset(("A200", "A700")): (
        1,
        "Latest coarse occupancy still reports CCD/service-module proximity.",
    ),
    frozenset(("A100", "A800")): (
        1,
        "Transport passes through the gantry footprint; a prior candidate moved the portal collision into a gantry rail.",
    ),
    frozenset(("A200", "A500")): (
        2,
        "Historical exact interference regression pair.",
    ),
    frozenset(("A300", "A800")): (
        2,
        "Historical exact interference regression pair.",
    ),
    frozenset(("A500", "A800")): (
        2,
        "Historical exact interference regression pair.",
    ),
    frozenset(("A300", "A700")): (
        2,
        "Non-convex service-cluster pair; v33 has focused exact evidence.",
    ),
    frozenset(("A100", "A180")): (
        2,
        "Historical exact interference regression pair.",
    ),
    frozenset(("A100", "A500")): (
        2,
        "Historical exact interference regression pair.",
    ),
    frozenset(("A180", "A800")): (
        2,
        "Historical scanner/transport exact interference regression pair.",
    ),
}


def component_code(name: str) -> str:
    upper = str(name).upper()
    for code in COMPONENT_CODES:
        if code in upper:
            return code
    return str(name)


def pair_key(first: str, second: str) -> frozenset[str]:
    return frozenset((component_code(first), component_code(second)))


def canonical_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((component_code(first), component_code(second))))


def _layout_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(document.get("placements"), list):
        return list(document["placements"])
    if isinstance(document.get("components"), list):
        return list(document["components"])
    layout = document.get("layout")
    if isinstance(layout, dict) and isinstance(layout.get("components"), list):
        return list(layout["components"])
    raise ValueError("Layout document does not contain placements or components.")


def layout_pose_by_code(document: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    result: dict[str, tuple[float, float, float]] = {}
    for item in _layout_items(document):
        name = str(item.get("componentName") or item.get("name") or "")
        code = component_code(name)
        if code not in COMPONENT_CODES:
            continue
        layout = item.get("layout2d") if isinstance(item.get("layout2d"), dict) else item
        result[code] = (
            float(layout["x"]),
            float(layout["y"]),
            normalize_angle_degrees(float(layout.get("thetaDegrees", 0.0))),
        )
    return result


def normalize_angle_degrees(value: float) -> float:
    normalized = (value + 180.0) % 360.0 - 180.0
    return 180.0 if math.isclose(normalized, -180.0, abs_tol=1e-12) else normalized


def relative_pair_pose(
    document: dict[str, Any], first: str, second: str
) -> tuple[float, float, float]:
    poses = layout_pose_by_code(document)
    first_code, second_code = canonical_pair(first, second)
    if first_code not in poses or second_code not in poses:
        raise ValueError(f"Layout is missing pair {first_code}/{second_code}.")
    first_pose = poses[first_code]
    second_pose = poses[second_code]
    return (
        second_pose[0] - first_pose[0],
        second_pose[1] - first_pose[1],
        normalize_angle_degrees(second_pose[2] - first_pose[2]),
    )


def relative_pose_matches(
    current: dict[str, Any],
    evidence_layout: dict[str, Any],
    first: str,
    second: str,
    *,
    position_tolerance_meters: float = 1e-6,
    angle_tolerance_degrees: float = 1e-4,
) -> bool:
    current_pose = relative_pair_pose(current, first, second)
    evidence_pose = relative_pair_pose(evidence_layout, first, second)
    return (
        math.isclose(
            current_pose[0], evidence_pose[0], abs_tol=position_tolerance_meters
        )
        and math.isclose(
            current_pose[1], evidence_pose[1], abs_tol=position_tolerance_meters
        )
        and math.isclose(
            normalize_angle_degrees(current_pose[2] - evidence_pose[2]),
            0.0,
            abs_tol=angle_tolerance_degrees,
        )
    )


def evidence_is_complete_and_clear(payload: dict[str, Any]) -> bool:
    complete = payload.get("ExactCheckComplete", payload.get("exactCheckComplete"))
    interference = payload.get("HasInterference", payload.get("hasInterference"))
    failures = payload.get("FailedBodyPairCount", payload.get("failedBodyPairCount", 0))
    return complete is True and interference is False and int(failures or 0) == 0


def component_files_older_than_evidence(
    evidence_path: Path, component_paths: Iterable[Path]
) -> bool:
    if not evidence_path.exists():
        return False
    evidence_mtime = evidence_path.stat().st_mtime
    paths = list(component_paths)
    return bool(paths) and all(path.exists() and path.stat().st_mtime <= evidence_mtime for path in paths)


def priority_for_pair(first: str, second: str) -> tuple[int, str]:
    return PAIR_PRIORITY.get(
        pair_key(first, second),
        (3, "Remaining conditional B-Rep pair after priority gates pass."),
    )


def aabb_separated(
    first: list[float], second: list[float], inflation_per_side_meters: float
) -> bool:
    if len(first) != 6 or len(second) != 6:
        raise ValueError("World AABB must contain six values.")
    margin = float(inflation_per_side_meters)
    return any(
        (float(first[axis + 3]) + margin) < (float(second[axis]) - margin)
        or (float(second[axis + 3]) + margin) < (float(first[axis]) - margin)
        for axis in range(3)
    )


def build_execution_plan(
    *,
    preview: dict[str, Any],
    current_layout: dict[str, Any],
    reusable_evidence: list[dict[str, Any]],
    world_aabbs_by_component: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    policy = preview.get("staticCollisionPolicy") or {}
    strict_pairs = policy.get("strictAabbPairs") or []
    conditional_pairs = policy.get("brepOnAabbOverlapPairs") or []
    installation_pairs = policy.get("installationContactPairs") or []
    modules = {item["componentName"]: item for item in preview.get("modules") or []}
    inflation = float(policy.get("aabbInflationPerSideMeters", 0.0))
    world_aabbs_by_component = world_aabbs_by_component or {}

    strict_diagnostics = {
        pair_key(str(item.get("firstComponent")), str(item.get("secondComponent"))): item
        for item in preview.get("diagnostics") or []
        if item.get("type") == "strictInflatedAabbSeparation"
    }
    strict_results: list[dict[str, Any]] = []
    for first, second in strict_pairs:
        diagnostic = strict_diagnostics.get(pair_key(first, second))
        first_world = world_aabbs_by_component.get(first)
        second_world = world_aabbs_by_component.get(second)
        measured_success = (
            aabb_separated(first_world, second_world, inflation)
            if first_world and second_world
            else None
        )
        strict_results.append(
            {
                "components": [first, second],
                "codes": list(canonical_pair(first, second)),
                "success": (
                    bool(measured_success)
                    if measured_success is not None
                    else bool(diagnostic and diagnostic.get("success"))
                ),
                "diagnosticId": diagnostic.get("id") if diagnostic else None,
                "source": (
                    "savedAssemblyWorldAabb"
                    if measured_success is not None
                    else "previewDiagnosticFallback"
                ),
                "inflationPerSideMeters": inflation,
            }
        )

    evidence_by_pair = {
        pair_key(*item["codes"]): item
        for item in reusable_evidence
        if item.get("reusable") is True
    }
    pending: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    broad_phase_clear: list[dict[str, Any]] = []
    for first, second in conditional_pairs:
        codes = canonical_pair(first, second)
        key = pair_key(first, second)
        first_world = world_aabbs_by_component.get(first)
        second_world = world_aabbs_by_component.get(second)
        if (
            first_world
            and second_world
            and aabb_separated(first_world, second_world, inflation)
        ):
            broad_phase_clear.append(
                {
                    "components": [first, second],
                    "codes": list(codes),
                    "inflationPerSideMeters": inflation,
                    "reason": "Saved-assembly world AABBs are strictly separated after inflation.",
                }
            )
            continue
        evidence = evidence_by_pair.get(key)
        if evidence:
            reused.append(
                {
                    "components": [first, second],
                    "codes": list(codes),
                    "evidencePath": evidence.get("evidencePath"),
                    "reason": "Exact clear evidence reused because relative pose and source geometry match.",
                }
            )
            continue
        priority, reason = priority_for_pair(first, second)
        first_bounds = (modules.get(first) or {}).get("bounds")
        second_bounds = (modules.get(second) or {}).get("bounds")
        pending.append(
            {
                "components": [first, second],
                "codes": list(codes),
                "priority": priority,
                "reason": reason,
                "predictedPlanarOverlap": bool(
                    first_bounds
                    and second_bounds
                    and not (
                        first_bounds[2] < second_bounds[0]
                        or second_bounds[2] < first_bounds[0]
                        or first_bounds[3] < second_bounds[1]
                        or second_bounds[3] < first_bounds[1]
                    )
                ),
                "relativePose": list(relative_pair_pose(current_layout, *codes)),
            }
        )
    pending.sort(key=lambda item: (int(item["priority"]), tuple(item["codes"])))

    batches: list[dict[str, Any]] = []
    for priority in range(4):
        pairs = [item for item in pending if item["priority"] == priority]
        if not pairs:
            continue
        batches.append(
            {
                "priority": priority,
                "status": "pending",
                "stopOnFirstHardInterference": True,
                "pairs": pairs,
            }
        )

    strict_ok = bool(strict_results) and all(item["success"] for item in strict_results)
    return {
        "schemaVersion": 1,
        "caseId": "project02",
        "status": (
            "READY_FOR_PRIORITY_BREP_GATE" if strict_ok else "STRICT_AABB_GATE_FAILED"
        ),
        "productionReady": False,
        "staticCollisionReady": False,
        "policy": {
            "solverInvokesBrep": False,
            "manualModuleMoveAfterFailure": False,
            "stopOnFirstHardInterference": True,
            "reusePassingEvidenceWhenRelativePoseAndGeometryMatch": True,
            "fullBrepAfterPriorityGatesOnly": True,
        },
        "strictAabb": {
            "pairCount": len(strict_results),
            "passedCount": sum(1 for item in strict_results if item["success"]),
            "results": strict_results,
        },
        "conditionalBrep": {
            "policyPairCount": len(conditional_pairs),
            "worldAabbClearPairCount": len(broad_phase_clear),
            "reusedClearPairCount": len(reused),
            "pendingPairCount": len(pending),
            "worldAabbClearPairs": broad_phase_clear,
            "reusedClearPairs": reused,
            "batches": batches,
        },
        "installationContact": {
            "policyPairCount": len(installation_pairs),
            "status": "pending_replay_penetration_review" if installation_pairs else "not_required",
            "pairs": installation_pairs,
            "acceptanceRule": (
                "Nominal A600 mounting contact is allowed; material penetration outside the "
                "recorded installation interface and keepout semantics is rejected."
            ),
        },
        "nextAction": (
            "Run only priority batch 0 (A100/A200); stop and recalibrate constraints on interference."
            if strict_ok and batches
            else "Repair strict AABB failures before any CAD B-Rep."
        ),
    }
