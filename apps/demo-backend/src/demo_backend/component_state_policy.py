"""General rigid/flexible component-state policy for mate-graph execution."""

from __future__ import annotations

from typing import Any


def _is_flexible(module: dict[str, Any]) -> bool:
    name = str(module.get("SolvingStateName") or "").casefold()
    if "flex" in name or "柔性" in name:
        return True
    # SOLIDWORKS swComponentFlexibleSolving is currently serialized as 2 in
    # the captured graphs.  Prefer the name when present, retain the value for
    # older captures.
    return module.get("SolvingState") == 2


def evaluate_component_state_policy(
    effective_graph: dict[str, Any],
    target_module_token: str,
    *,
    execution_mode: str,
) -> dict[str, Any]:
    target = str(target_module_token or "").strip().upper()
    modules = effective_graph.get("Modules") or []
    matches = [
        module
        for module in modules
        if str(module.get("ModuleToken") or "").upper() == target
    ]
    if len(matches) != 1:
        return {
            "status": "blocked",
            "reason": f"target module {target} resolved to {len(matches)} graph modules",
        }
    target_module = matches[0]
    flexible_modules = [
        str(module.get("ModuleToken") or "")
        for module in modules
        if _is_flexible(module)
    ]
    anchors = (effective_graph.get("EditPolicy") or {}).get("targetLeafPoseAnchors") or []
    direct = execution_mode == "direct_existing_component_mate_edit"
    target_flexible = _is_flexible(target_module)
    if target_flexible and not direct and not anchors:
        status = "blocked"
        reason = "flexible target reconstruction requires internal pose anchors or an authoritative named state"
    else:
        status = "ready"
        reason = (
            "direct edit preserves the existing parent-context flexible state and requires subtree fingerprint verification"
            if target_flexible and direct
            else "rigid target does not require internal flexible-state anchors"
            if not target_flexible
            else "flexible target reconstruction has explicit internal state anchors"
        )
    return {
        "schemaVersion": "component-state-execution-policy/v1",
        "status": status,
        "executionMode": execution_mode,
        "targetModuleToken": target,
        "targetFlexible": target_flexible,
        "flexibleModuleTokens": flexible_modules,
        "targetLeafPoseAnchorCount": len(anchors),
        "requiresTargetLeafPoseAnchors": target_flexible and not direct,
        "requiresParentContextPreservation": target_flexible and direct,
        "requiresSubtreeFingerprintVerification": bool(flexible_modules),
        "reason": reason,
    }
