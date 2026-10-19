"""Audit whether a selected layout can reuse a previously closed CAD result."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def angle_error_degrees(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def applied_layout_from_replay(replay: dict[str, Any]) -> list[dict[str, Any]]:
    step = next(
        (
            item
            for item in replay.get("steps") or []
            if item.get("tool") == "apply_captured_common_base_layout"
        ),
        None,
    )
    if not step or not isinstance(step.get("payload"), dict):
        raise ValueError("Replay evidence has no apply_captured_common_base_layout payload.")
    components = step["payload"].get("components") or []
    if not components:
        raise ValueError("Replay evidence contains no applied components.")
    return components


def compare_layouts(
    selected_components: list[dict[str, Any]],
    closed_components: list[dict[str, Any]],
    *,
    xy_tolerance_meters: float = 1e-9,
    theta_tolerance_degrees: float = 1e-7,
    normal_offset_tolerance_meters: float = 1e-9,
) -> dict[str, Any]:
    selected = {item["componentName"]: item for item in selected_components}
    closed = {item["componentName"]: item for item in closed_components}
    missing = sorted(set(selected) - set(closed))
    extra = sorted(set(closed) - set(selected))
    diagnostics: list[dict[str, Any]] = []
    for name in sorted(set(selected) & set(closed)):
        current = selected[name].get("layout2d") or {}
        previous = closed[name].get("layout2d") or {}
        xy_error = math.dist(
            (float(current.get("x", math.inf)), float(current.get("y", math.inf))),
            (float(previous.get("x", -math.inf)), float(previous.get("y", -math.inf))),
        )
        theta_error = angle_error_degrees(
            float(current.get("thetaDegrees", math.inf)),
            float(previous.get("thetaDegrees", -math.inf)),
        )
        offset_error = abs(
            float(current.get("normalOffsetMeters", math.inf))
            - float(previous.get("normalOffsetMeters", -math.inf))
        )
        axis_matches = str(current.get("thetaAxis", "x")) == str(
            previous.get("thetaAxis", "x")
        )
        success = (
            math.isfinite(xy_error)
            and xy_error <= xy_tolerance_meters
            and theta_error <= theta_tolerance_degrees
            and offset_error <= normal_offset_tolerance_meters
            and axis_matches
        )
        diagnostics.append(
            {
                "componentName": name,
                "xyErrorMeters": xy_error,
                "thetaErrorDegrees": theta_error,
                "normalOffsetErrorMeters": offset_error,
                "thetaAxisMatches": axis_matches,
                "success": success,
            }
        )
    return {
        "success": not missing and not extra and all(item["success"] for item in diagnostics),
        "componentCount": len(diagnostics),
        "missingComponents": missing,
        "extraComponents": extra,
        "maxXyErrorMeters": max(
            (item["xyErrorMeters"] for item in diagnostics), default=None
        ),
        "maxThetaErrorDegrees": max(
            (item["thetaErrorDegrees"] for item in diagnostics), default=None
        ),
        "maxNormalOffsetErrorMeters": max(
            (item["normalOffsetErrorMeters"] for item in diagnostics), default=None
        ),
        "xyToleranceMeters": xy_tolerance_meters,
        "thetaToleranceDegrees": theta_tolerance_degrees,
        "normalOffsetToleranceMeters": normal_offset_tolerance_meters,
        "diagnostics": diagnostics,
    }


def source_geometry_unchanged(
    selected_components: list[dict[str, Any]], reference_path: Path
) -> dict[str, Any]:
    reference_timestamp = reference_path.stat().st_mtime
    diagnostics = []
    for item in selected_components:
        source = Path(str(item.get("filePath") or ""))
        exists = source.is_file()
        modified_after_reference = bool(exists and source.stat().st_mtime > reference_timestamp)
        diagnostics.append(
            {
                "componentName": item.get("componentName"),
                "filePath": str(source),
                "exists": exists,
                "modifiedAfterReferenceClosure": modified_after_reference,
                "success": exists and not modified_after_reference,
            }
        )
    return {
        "success": bool(diagnostics) and all(item["success"] for item in diagnostics),
        "referencePath": str(reference_path.resolve()),
        "componentCount": len(diagnostics),
        "diagnostics": diagnostics,
    }


def solver_gate(preview: dict[str, Any]) -> dict[str, Any]:
    diagnostics = preview.get("diagnostics") or []
    hard = [item for item in diagnostics if item.get("hard") is True]
    directed = [item for item in hard if item.get("type") == "directedPointing"]
    return {
        "success": bool(hard) and all(item.get("success") is True for item in hard) and bool(directed),
        "hardConstraintCount": len(hard),
        "hardConstraintPassedCount": sum(item.get("success") is True for item in hard),
        "directedPointingPresent": bool(directed),
        "directedPointingPassed": bool(directed) and all(
            item.get("success") is True for item in directed
        ),
    }


def visual_approval_gate(
    selected: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    approval = selected.get("visualApproval") or {}
    return {
        "success": bool(approval.get("approved"))
        and approval.get("sourcePreviewGeneratedAt") == preview.get("generatedAt"),
        "approved": bool(approval.get("approved")),
        "selectedSolutionRank": approval.get("selectedSolutionRank"),
        "approvedPreviewGeneratedAt": approval.get("sourcePreviewGeneratedAt"),
        "currentPreviewGeneratedAt": preview.get("generatedAt"),
    }


def build_closure_reuse_report(
    *,
    selected: dict[str, Any],
    preview: dict[str, Any],
    closed_replay: dict[str, Any],
    closed_plan: dict[str, Any],
    closed_plan_path: Path,
) -> dict[str, Any]:
    layout = compare_layouts(
        selected.get("components") or [], applied_layout_from_replay(closed_replay)
    )
    geometry = source_geometry_unchanged(
        selected.get("components") or [], closed_plan_path
    )
    approval = visual_approval_gate(selected, preview)
    solver = solver_gate(preview)
    prior_closure = {
        "success": closed_plan.get("staticCollisionReady") is True,
        "status": closed_plan.get("status"),
        "assemblyPath": closed_plan.get("assemblyPath"),
        "staticCollisionReady": closed_plan.get("staticCollisionReady"),
        "productionReady": closed_plan.get("productionReady"),
    }
    success = all(
        gate["success"] for gate in (layout, geometry, approval, solver, prior_closure)
    )
    return {
        "schemaVersion": 1,
        "caseId": "project02",
        "success": success,
        "status": (
            "CAD_CLOSURE_REUSED_FROM_EQUIVALENT_LAYOUT"
            if success
            else "CAD_REPLAY_REQUIRED"
        ),
        "replayRequired": not success,
        "aabbBroadPhaseRequired": not success,
        "conditionalBrepRequired": not success,
        "layoutEquivalence": layout,
        "sourceGeometry": geometry,
        "visualApproval": approval,
        "solverGate": solver,
        "priorCadClosure": prior_closure,
        "staticCollisionReady": success,
        "productionReady": False,
        "decisionReason": (
            "The approved layout, source module files, and all rigid placement parameters "
            "match the previously reopened CAD closure; geometry-dependent AABB/B-rep "
            "evidence remains valid."
            if success
            else "At least one reuse gate changed; run a new Replay and staged collision check."
        ),
    }
