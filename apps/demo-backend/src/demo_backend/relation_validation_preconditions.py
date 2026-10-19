"""Versioned preconditions for read-only engineering relation checks.

Validation may require evidence beyond a named relation: for example proof that
a flexible module recovered the same external installation pose.  Preconditions
are data-driven so missing evidence blocks before SolidWorks starts.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


RELATION_VALIDATION_PRECONDITION_SCHEMA = (
    "relation-validation-precondition-registry/v1"
)


class RelationValidationPreconditionError(ValueError):
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


def validate_relation_validation_precondition_registry(
    registry: dict[str, Any],
) -> dict[str, Any]:
    if registry.get("schemaVersion") != RELATION_VALIDATION_PRECONDITION_SCHEMA:
        raise RelationValidationPreconditionError("不支持的关系验证前置条件目录版本。")
    rows = registry.get("requirements")
    if not isinstance(rows, list):
        raise RelationValidationPreconditionError("requirements必须是数组。")
    seen: set[str] = set()
    for row in rows:
        template_id = str(row.get("globalTemplateId") or "").strip()
        evidence_id = str(
            row.get("requiredEvidenceId") or row.get("requiredStateId") or ""
        ).strip()
        if not template_id or not evidence_id:
            raise RelationValidationPreconditionError(
                "每条前置条件必须声明globalTemplateId和requiredEvidenceId。"
            )
        if template_id in seen:
            raise RelationValidationPreconditionError(
                f"关系模板重复声明验证前置条件：{template_id}"
            )
        seen.add(template_id)
        if str(row.get("dependencyKind") or "") not in {
            "flexible_internal_process_state",
            "external_placement_equivalence",
        }:
            raise RelationValidationPreconditionError(
                f"不支持的状态依赖类型：{row.get('dependencyKind')}"
            )
        if not str(row.get("reason") or "").strip():
            raise RelationValidationPreconditionError("状态依赖必须包含reason。")
    expected = registry.get("registryDigest")
    actual = relation_validation_precondition_registry_digest(registry)
    if expected is not None and expected != actual:
        raise RelationValidationPreconditionError("关系验证前置条件目录摘要不一致。")
    return registry


def relation_validation_precondition_registry_digest(
    registry: dict[str, Any],
) -> str:
    return _digest(
        {key: value for key, value in registry.items() if key != "registryDigest"}
    )


def relation_validation_precondition_registry_binding(
    registry: dict[str, Any],
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    validate_relation_validation_precondition_registry(registry)
    return {
        "schemaVersion": registry["schemaVersion"],
        "registryId": registry.get("registryId"),
        "registryDigest": relation_validation_precondition_registry_digest(registry),
        "registryPath": registry_path,
    }


def assess_relation_validation_precondition(
    global_template_id: str,
    *,
    registry: dict[str, Any] | None,
    state_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return an auditable decision for one validation template.

    Evidence is deliberately strict.  A state label alone is insufficient;
    callers must declare that the state was applied to the current assembly
    checkpoint and bind a non-empty evidence digest.
    """

    if registry is None:
        return {
            "required": False,
            "status": "not_declared",
            "globalTemplateId": global_template_id,
            "blockers": [],
        }
    validate_relation_validation_precondition_registry(registry)
    requirement = next(
        (
            row
            for row in registry.get("requirements") or []
            if str(row.get("globalTemplateId") or "") == global_template_id
        ),
        None,
    )
    if requirement is None:
        return {
            "required": False,
            "status": "not_declared",
            "globalTemplateId": global_template_id,
            "blockers": [],
        }
    required_evidence_id = str(
        requirement.get("requiredEvidenceId")
        or requirement.get("requiredStateId")
        or ""
    )
    matching = [
        row
        for row in state_evidence or []
        if str(row.get("evidenceId") or row.get("stateId") or "")
        == required_evidence_id
    ]
    accepted = next(
        (
            row
            for row in matching
            if row.get("appliedToCurrentCheckpoint") is True
            and str(row.get("evidenceDigest") or "").strip()
        ),
        None,
    )
    blockers: list[dict[str, Any]] = []
    if accepted is None:
        dependency_kind = str(requirement.get("dependencyKind") or "")
        blockers.append(
            {
                "code": (
                    "VALIDATION_EXTERNAL_PLACEMENT_EQUIVALENCE_REQUIRED"
                    if dependency_kind == "external_placement_equivalence"
                    else "VALIDATION_PROCESS_STATE_EVIDENCE_REQUIRED"
                ),
                "globalTemplateId": global_template_id,
                "requiredEvidenceId": required_evidence_id,
                "detail": requirement.get("reason"),
            }
        )
    return {
        "required": True,
        "status": "satisfied" if accepted is not None else "evidence_required",
        "globalTemplateId": global_template_id,
        "requiredEvidenceId": required_evidence_id,
        "dependencyKind": requirement.get("dependencyKind"),
        "moduleDefinitionId": requirement.get("moduleDefinitionId"),
        "relativeLeafHierarchyPath": requirement.get(
            "relativeLeafHierarchyPath"
        ),
        "reason": requirement.get("reason"),
        "acceptedEvidence": deepcopy(accepted),
        "blockers": blockers,
    }
