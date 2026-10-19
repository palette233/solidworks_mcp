"""Prepare a mate graph for strict non-prototype placement execution."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


SCHEMA = "nonprototype-execution-graph-preparation/v1"


class NonprototypeExecutionGraphError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def prepare_nonprototype_execution_graph(
    graph: dict[str, Any],
    *,
    target_module_token: str,
) -> dict[str, Any]:
    """Return a copy with target pose anchors removed and provenance recorded.

    Mechanical mate endpoints and source transforms are deliberately untouched.
    The generated graph remains deterministic, but it cannot use a prototype
    top-level or leaf transform to close missing external degrees of freedom.
    """

    target = str(target_module_token or "").strip().upper()
    if not target:
        raise NonprototypeExecutionGraphError("target_module_token不能为空。")
    modules_key = "Modules" if "Modules" in graph else "modules"
    tokens = {
        str(row.get("ModuleToken") or row.get("moduleToken") or "").strip().upper()
        for row in graph.get(modules_key) or []
    }
    if target not in tokens:
        raise NonprototypeExecutionGraphError(f"执行图缺少目标模组：{target}")

    prepared = copy.deepcopy(graph)
    policy_key = "EditPolicy" if "EditPolicy" in prepared else "editPolicy"
    policy = copy.deepcopy(prepared.get(policy_key) or {})
    case_key = (
        "caseAnchoredModuleTokens"
        if "caseAnchoredModuleTokens" in policy
        else "CaseAnchoredModuleTokens"
    )
    leaf_key = (
        "targetLeafPoseAnchors"
        if "targetLeafPoseAnchors" in policy
        else "TargetLeafPoseAnchors"
    )
    fixed_key = (
        "fixedModuleTokens"
        if "fixedModuleTokens" in policy
        else "FixedModuleTokens"
    )
    case_tokens = [str(value) for value in policy.get(case_key) or []]
    removed_case_tokens = [
        value for value in case_tokens if value.strip().upper() == target
    ]
    policy[case_key] = [
        value for value in case_tokens if value.strip().upper() != target
    ]
    leaf_anchors = list(policy.get(leaf_key) or [])
    policy[leaf_key] = []
    fixed_tokens = [str(value) for value in policy.get(fixed_key) or []]
    removed_fixed_tokens = [
        value for value in fixed_tokens if value.strip().upper() == target
    ]
    policy[fixed_key] = [
        value for value in fixed_tokens if value.strip().upper() != target
    ]
    policy["initialPlacementMode"] = "deterministic"
    policy["sourceGraphImmutable"] = True
    prepared[policy_key] = policy
    prepared["NonprototypePreparation"] = {
        "schemaVersion": SCHEMA,
        "targetModuleToken": target,
        "sourceGraphDigest": _digest(graph),
        "removedCaseAnchorTokens": removed_case_tokens,
        "removedTargetLeafPoseAnchorCount": len(leaf_anchors),
        "removedTargetFixedTokens": removed_fixed_tokens,
        "mechanicalMateSetModified": False,
        "sourceTransformsModified": False,
        "initialPlacementMode": "deterministic",
    }
    return prepared
