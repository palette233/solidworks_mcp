"""Explain failed relation checks using external pose and flexible-state evidence.

The external top-level pose check intentionally has precedence over an internal
state diagnosis.  A nested endpoint inside a flexible subassembly can only be
called an internal-state problem after the owning module itself has returned to
the expected installation pose.
"""

from __future__ import annotations

from typing import Any


RELATION_VALIDATION_STATE_AUDIT_SCHEMA = "relation-validation-state-audit/v2"
DEFAULT_EXTERNAL_POSE_TOLERANCE = 1e-5


def _pick(value: dict[str, Any], pascal: str, default=None):
    return value.get(pascal, value.get(pascal[0].lower() + pascal[1:], default))


def _endpoint_rows(relation: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_pick(relation, "Endpoints", []) or [])


def analyze_relation_validation_state_dependency(
    validation_graph: dict[str, Any],
    verification_result: dict[str, Any],
    *,
    installation_graphs: dict[str, dict[str, Any]] | None = None,
    external_pose_tolerance: float = DEFAULT_EXTERNAL_POSE_TOLERANCE,
) -> dict[str, Any]:
    installation_graphs = {
        str(key).upper(): value for key, value in (installation_graphs or {}).items()
    }
    module_rows = list(_pick(validation_graph, "Modules", []) or [])
    modules = {
        str(_pick(row, "ModuleToken", "")).upper(): row for row in module_rows
    }
    audit = _pick(validation_graph, "SemanticAssemblyPlanAudit", {}) or {}
    relations = list(_pick(audit, "ValidationRelations", []) or [])
    observed = {
        str(_pick(row, "RelationName", "")): row
        for row in verification_result.get("validationResults")
        or _pick(verification_result.get("toolResult") or {}, "ValidationResults", [])
        or []
    }
    pose_rows = list(
        _pick(verification_result.get("toolResult") or {}, "ModulePoses", [])
        or []
    )
    module_poses = {
        str(_pick(row, "ModuleToken", "")).upper(): row for row in pose_rows
    }
    relation_rows: list[dict[str, Any]] = []
    for relation in relations:
        relation_name = str(_pick(relation, "RelationName", ""))
        endpoint_audits: list[dict[str, Any]] = []
        for endpoint in _endpoint_rows(relation):
            token = str(_pick(endpoint, "ModuleToken", "")).upper()
            relative_leaf = str(
                _pick(endpoint, "RelativeLeafHierarchyPath", "") or ""
            )
            module = modules.get(token) or {}
            solving_state = _pick(module, "SolvingState")
            flexible = solving_state == 1 or str(
                _pick(module, "SolvingStateName", "")
            ).casefold() == "swcomponentflexiblesolving"
            installation = installation_graphs.get(token) or {}
            driving_mates = []
            for mate in _pick(installation, "Mates", []) or []:
                if bool(_pick(mate, "IsSuppressed", False)):
                    continue
                if any(
                    str(_pick(candidate, "ModuleToken", "")).upper() == token
                    and str(
                        _pick(candidate, "RelativeLeafHierarchyPath", "") or ""
                    )
                    == relative_leaf
                    for candidate in _pick(mate, "Endpoints", []) or []
                ):
                    driving_mates.append(str(_pick(mate, "MateName", "")))
            edit_policy = _pick(installation, "EditPolicy", {}) or {}
            anchors = list(_pick(edit_policy, "TargetLeafPoseAnchors", []) or [])
            matching_anchors = [
                row
                for row in anchors
                if str(
                    _pick(row, "RelativeLeafHierarchyPath", "") or ""
                )
                == relative_leaf
            ]
            nested = "/" in relative_leaf
            state_dependent = flexible and nested and not matching_anchors
            endpoint_audits.append(
                {
                    "index": _pick(endpoint, "Index"),
                    "moduleToken": token,
                    "relativeLeafHierarchyPath": relative_leaf,
                    "moduleSolvingState": solving_state,
                    "moduleFlexible": flexible,
                    "nestedEndpoint": nested,
                    "installationDrivingMateNamesUsingLeaf": sorted(driving_mates),
                    "matchingLeafPoseAnchorCount": len(matching_anchors),
                    "stateDependent": state_dependent,
                }
            )
        observed_row = observed.get(relation_name) or {}
        passed = bool(_pick(observed_row, "Passed", False))
        has_state_dependency = any(row["stateDependent"] for row in endpoint_audits)
        endpoint_tokens = sorted(
            {row["moduleToken"] for row in endpoint_audits if row["moduleToken"]}
        )
        external_pose_mismatches = []
        for token in endpoint_tokens:
            pose = module_poses.get(token)
            if pose is None:
                continue
            delta = float(_pick(pose, "MaximumTransformElementDelta", 0.0) or 0.0)
            if delta > external_pose_tolerance:
                external_pose_mismatches.append(
                    {
                        "moduleToken": token,
                        "maximumTransformElementDelta": delta,
                        "tolerance": external_pose_tolerance,
                        "sourceTransform": _pick(pose, "SourceTransform"),
                        "currentTransform": _pick(pose, "CurrentTransform"),
                    }
                )
        if passed:
            diagnosis = "passed"
        elif external_pose_mismatches:
            diagnosis = "failed_with_external_module_pose_branch_mismatch"
        elif has_state_dependency:
            diagnosis = "failed_with_unrestored_flexible_internal_state"
        else:
            diagnosis = "failure_not_explained_by_declared_state_audit"
        relation_rows.append(
            {
                "relationName": relation_name,
                "passed": passed,
                "expectedDistanceMeters": _pick(
                    observed_row,
                    "ExpectedDistanceMeters",
                    _pick(relation, "ExpectedDistanceMeters"),
                ),
                "measuredDistanceMeters": _pick(
                    observed_row, "MeasuredDistanceMeters"
                ),
                "absoluteErrorMeters": _pick(observed_row, "AbsoluteErrorMeters"),
                "hasFlexibleInternalStateDependency": has_state_dependency,
                "externalModulePoseMismatch": bool(external_pose_mismatches),
                "externalPoseMismatches": external_pose_mismatches,
                "diagnosis": diagnosis,
                "endpoints": endpoint_audits,
            }
        )
    pose_mismatches = [
        row
        for row in relation_rows
        if row["diagnosis"]
        == "failed_with_external_module_pose_branch_mismatch"
    ]
    diagnosed = [
        row
        for row in relation_rows
        if row["diagnosis"] == "failed_with_unrestored_flexible_internal_state"
    ]
    return {
        "schemaVersion": RELATION_VALIDATION_STATE_AUDIT_SCHEMA,
        "success": bool(relations) and len(pose_mismatches) + len(diagnosed) == len(
            [row for row in relation_rows if not row["passed"]]
        ),
        "relationCount": len(relation_rows),
        "diagnosedExternalPoseFailureCount": len(pose_mismatches),
        "diagnosedFlexibleStateFailureCount": len(diagnosed),
        "relations": relation_rows,
        "conclusion": (
            "The failed relation is primarily explained by an external top-level "
            "module pose branch mismatch; internal process-state conclusions are "
            "deferred until external placement equivalence is restored."
            if pose_mismatches
            else
            "The failed relation is not reproducible from external module placement alone; "
            "a named flexible internal process state must be restored first."
            if diagnosed
            else "No failed flexible-state-dependent relation was diagnosed."
        ),
    }
