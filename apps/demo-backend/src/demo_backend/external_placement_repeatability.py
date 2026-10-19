"""Build a second non-source-pose graph for external placement repeatability.

The first zero-anchor CAD solve establishes the configuration-specific root
transform.  The confirmation graph changes only the deterministic pre-mate
placement variant and uses that first solved transform as a read-only witness.
It never adds a pose anchor or drives the component from the witness.
"""

from __future__ import annotations

import copy
from typing import Any


class ExternalPlacementRepeatabilityError(ValueError):
    pass


def build_repeatability_confirmation_graph(
    graph: dict[str, Any],
    first_run: dict[str, Any],
    target_module_token: str,
    initial_placement_variant: int,
) -> dict[str, Any]:
    if initial_placement_variant <= 0:
        raise ExternalPlacementRepeatabilityError(
            "确认实验必须使用大于0的非原型初始位姿变体。"
        )
    tool = first_run.get("toolResult") or {}
    if not first_run.get("success") or not tool.get("Success"):
        raise ExternalPlacementRepeatabilityError("首次零锚点CAD实验未成功。")
    if tool.get("TargetCaseAnchored"):
        raise ExternalPlacementRepeatabilityError("首次实验使用了箱体位姿锚点。")
    if int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) != 0:
        raise ExternalPlacementRepeatabilityError("首次实验使用了叶级位姿锚点。")
    transform = tool.get("ReopenedTargetRootTransform")
    if not isinstance(transform, list) or len(transform) < 13:
        raise ExternalPlacementRepeatabilityError("首次实验未记录重开后的目标根变换。")

    target = target_module_token.strip().upper()
    confirmation = copy.deepcopy(graph)
    matches = [
        module
        for module in confirmation.get("Modules") or []
        if str(module.get("ModuleToken") or "").strip().upper() == target
    ]
    if len(matches) != 1:
        raise ExternalPlacementRepeatabilityError(
            f"目标模组{target}在图中命中{len(matches)}项。"
        )
    matches[0]["SourceTransform"] = [float(value) for value in transform]
    policy = confirmation.setdefault("EditPolicy", {})
    if policy.get("caseAnchoredModuleTokens"):
        raise ExternalPlacementRepeatabilityError("确认图不得包含箱体位姿锚点。")
    if policy.get("targetLeafPoseAnchors"):
        raise ExternalPlacementRepeatabilityError("确认图不得包含叶级位姿锚点。")
    policy["initialPlacementVariant"] = initial_placement_variant
    confirmation["ExternalPlacementRepeatabilityAudit"] = {
        "targetModuleToken": target,
        "witnessAuthority": "first_zero_anchor_cad_solve",
        "witnessTransform": [float(value) for value in transform],
        "initialPlacementVariant": initial_placement_variant,
        "witnessIsValidationOnly": True,
        "poseAnchorUsed": False,
        "firstRunOutputAssemblyPath": first_run.get("outputAssemblyPath"),
        "firstRunOutputAssemblySha256": first_run.get("outputAssemblySha256"),
    }
    return confirmation
