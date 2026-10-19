"""Fail-closed preflight for direct, multi-mate edits in an assembly context."""

from __future__ import annotations

from typing import Any

from .mate_dof_analysis import MateDofAnalysisError, analyze_target_mate_dof


class MateTransactionPreflightError(ValueError):
    pass


_MUTATING_OPERATIONS = {"addmate", "updatemate", "removemate"}


def _active_mates(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [mate for mate in graph.get("Mates") or [] if not bool(mate.get("IsSuppressed", False))]


def preflight_direct_mate_transaction(
    effective_graph: dict[str, Any],
    target_module_token: str,
    *,
    require_closed_dof: bool = False,
    require_multiple_operations: bool = False,
    reject_redundant_mutations: bool = False,
) -> dict[str, Any]:
    """Validate one immutable-file direct-edit transaction before CAD mutation.

    The preflight deliberately distinguishes geometric closure from CAD authority:
    a rank-six result permits execution, but SolidWorks save/reopen verification is
    still the final acceptance boundary.
    """

    target = str(target_module_token or "").strip().upper()
    if not target:
        raise MateTransactionPreflightError("target_module_token is required.")
    patch_audit = effective_graph.get("PatchAudit")
    if not isinstance(patch_audit, dict):
        raise MateTransactionPreflightError(
            "Direct mate transaction requires PatchAudit; legacy remate graphs are not accepted."
        )
    operations = patch_audit.get("operations")
    if not isinstance(operations, list) or not operations:
        raise MateTransactionPreflightError("PatchAudit contains no mate operations.")
    if require_multiple_operations and len(operations) < 2:
        raise MateTransactionPreflightError(
            "Multi-mate closure requires at least two auditable operations."
        )

    indexes = [int(item.get("index", -1)) for item in operations]
    if indexes != list(range(len(operations))):
        raise MateTransactionPreflightError(
            "PatchAudit operation indexes must be contiguous and ordered from zero."
        )
    unsupported_operations = [
        str(item.get("operation") or "")
        for item in operations
        if str(item.get("operation") or "").strip().lower() not in _MUTATING_OPERATIONS
    ]
    if unsupported_operations:
        raise MateTransactionPreflightError(
            "Unsupported direct-edit operations: " + ", ".join(unsupported_operations)
        )

    active = _active_mates(effective_graph)
    active_names = {str(mate.get("MateName") or "").casefold() for mate in active}
    create_names = {
        str(item.get("mateName") or "").casefold()
        for item in operations
        if str(item.get("operation") or "").strip().lower() in {"addmate", "updatemate"}
    }
    missing_creates = sorted(name for name in create_names if name not in active_names)
    if missing_creates:
        raise MateTransactionPreflightError(
            "PatchAudit create/update names are absent from the effective graph: "
            + ", ".join(missing_creates)
        )

    unrelated = [
        str(mate.get("MateName") or "")
        for mate in active
        if target
        not in {str(value).upper() for value in mate.get("ModuleTokens") or []}
    ]
    if unrelated:
        raise MateTransactionPreflightError(
            "Target-local transaction contains unrelated active mates: " + ", ".join(unrelated)
        )

    try:
        dof = analyze_target_mate_dof(effective_graph, target)
    except MateDofAnalysisError as exc:
        raise MateTransactionPreflightError(str(exc)) from exc

    blockers: list[dict[str, Any]] = []
    if dof["unsupportedRelations"]:
        blockers.append({
            "code": "UNSUPPORTED_DOF_RELATION",
            "message": "At least one active mate cannot be linearized conservatively.",
            "relations": dof["unsupportedRelations"],
        })
    if require_closed_dof and not dof["closed"]:
        blockers.append({
            "code": "RESIDUAL_DOF",
            "message": f"Target retains {dof['residualDof']} rigid-body DOF.",
        })

    redundant = [
        relation["mateName"]
        for relation in dof["relations"]
        if int(relation.get("independentConstraintCount") or 0) == 0
    ]
    redundant_mutations = sorted(
        name
        for name in redundant
        if str(name).casefold() in create_names
    )
    if reject_redundant_mutations and redundant_mutations:
        blockers.append(
            {
                "code": "REDUNDANT_MUTATING_RELATION",
                "message": (
                    "A proposed add/update relation contributes no independent rigid-body "
                    "constraint rows; keep it as verification-only or remove the redundant mate."
                ),
                "mateNames": redundant_mutations,
            }
        )
    status = "ready_for_cad_execution" if not blockers else "blocked"
    decision = (
        "blocked_before_cad"
        if blockers
        else "verification_only_redundant_relation"
        if redundant_mutations
        else "candidate_for_driving_cad_trial"
    )
    return {
        "schemaVersion": "direct-mate-transaction-preflight/v1",
        "status": status,
        "publishAllowed": not blockers,
        "targetModuleToken": target,
        "operationCount": len(operations),
        "operationKinds": [str(item.get("operation") or "") for item in operations],
        "activeMateCount": len(active),
        "requireClosedDof": require_closed_dof,
        "requireMultipleOperations": require_multiple_operations,
        "rejectRedundantMutations": reject_redundant_mutations,
        "rigidBodyDofAnalysis": dof,
        "redundantMateNames": redundant,
        "redundantMutatingMateNames": redundant_mutations,
        "drivingDecision": decision,
        "warnings": (
            [{
                "code": "REDUNDANT_CONSTRAINT_ROWS",
                "message": "Some relations add no independent linearized constraint rows.",
                "mateNames": redundant,
            }]
            if redundant
            else []
        ),
        "blockers": blockers,
        "cadAuthorityBoundary": (
            "Preflight is necessary but not authoritative; the copied assembly must still "
            "save, reopen, preserve component state, and verify mate parameters in SolidWorks."
        ),
    }
