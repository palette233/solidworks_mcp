"""Materialize a dependency-ablation preview candidate for audited CAD execution."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

from .layout_preview import LayoutPreviewError, _materialize_solution


def _placements_from_preview_solution(solution: dict[str, Any]) -> list[dict[str, Any]]:
    placements: list[dict[str, Any]] = []
    for module in solution.get("modules") or []:
        center = module.get("center") or []
        bounds = module.get("bounds") or []
        if len(center) != 2 or len(bounds) != 4:
            raise LayoutPreviewError(
                f"Preview module '{module.get('componentName')}' has invalid center/bounds."
            )
        placements.append(
            {
                "componentName": module.get("componentName"),
                "x": float(center[0]),
                "y": float(center[1]),
                "thetaDegrees": float(module.get("thetaDegrees") or 0.0),
                "rotationQuarters": int(module.get("rotationQuarters") or 0),
                "bounds": [float(value) for value in bounds],
            }
        )
    return placements


def materialize_ablation_cad_layout(
    baseline_layout: dict[str, Any],
    preview: dict[str, Any],
    *,
    variant: str,
    solution_rank: int = 1,
    authorization_note: str,
) -> dict[str, Any]:
    """Create a new CAD input without changing the baseline selected solution."""

    variant = variant.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]{0,15}", variant):
        raise ValueError(f"Invalid dependency-ablation/collision-iteration variant: {variant}")
    if not authorization_note.strip():
        raise ValueError("An explicit CAD execution authorization note is required.")
    metrics = preview.get("metrics") or {}
    if metrics.get("hardFeasible") is not True:
        raise LayoutPreviewError(f"Variant {variant} is not hard-feasible.")
    solution = next(
        (
            item
            for item in preview.get("solutions") or []
            if int(item.get("rank") or 0) == solution_rank
        ),
        None,
    )
    if solution is None:
        raise LayoutPreviewError(
            f"Variant {variant} preview does not contain solution rank {solution_rank}."
        )
    selected = {
        "rank": solution_rank,
        "score": float(solution.get("score") or 0.0),
        "candidateRanks": solution.get("candidateRanks") or [],
        "placements": _placements_from_preview_solution(solution),
    }
    result = _materialize_solution(
        copy.deepcopy(baseline_layout),
        selected,
        allow_orientation_change=True,
    )
    preview_modules = {
        item.get("componentName"): item
        for item in solution.get("modules") or []
        if item.get("componentName")
    }
    for component in result.get("components") or []:
        module = preview_modules.get(component.get("componentName"))
        if not module:
            continue
        for key in (
            "interactionEnvelope",
            "hardBodyEnvelope",
            "transportSweepEnvelope",
            "transportStaticKeepoutEnvelope",
        ):
            if key in module:
                component[key] = copy.deepcopy(module.get(key))

    executed_at = datetime.now(timezone.utc).isoformat()
    plan = result.setdefault("constraintPlan", {})
    plan["staticCollisionPolicy"] = copy.deepcopy(
        preview.get("staticCollisionPolicy") or {}
    )
    plan["dependencyAblationCadExecution"] = {
        "variant": variant,
        "solutionRank": solution_rank,
        "sourcePreviewGeneratedAt": preview.get("generatedAt"),
        "sourcePreviewPath": preview.get("previewPath"),
        "hardFeasible": True,
        "predictedConditionalBrepPairCount": solution.get(
            "predictedConditionalBrepPairCount"
        ),
        "predictedConditionalLeafAabbHitCount": solution.get(
            "predictedConditionalLeafAabbHitCount"
        ),
        "cadValidationStillRequired": True,
        "productionReady": False,
    }
    result["visualApproval"] = {
        "approved": True,
        "approvalKind": "explicit-user-cad-execution-authorization",
        "approvedAt": executed_at,
        "selectedSolutionRank": solution_rank,
        "reviewerNote": authorization_note.strip(),
        "allowsDirectAssemblyBuild": True,
        "allowsBrepNow": False,
    }
    result["message"] = (
        f"Project02 dependency-ablation variant {variant} rank {solution_rank} "
        "materialized for direct nine-module CAD generation; CAD validation remains open."
    )
    return result
