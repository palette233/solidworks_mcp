"""Plan a longer cumulative assembly chain from released interface evidence.

This module is intentionally small.  It does not infer geometry and it does not
run SolidWorks.  It verifies that every requested module can be connected to
the selected base by exactly one *released* installation template whose ports
are portable and whose declared constraint bundle closes the external rigid
body degrees of freedom.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .cross_project_module_substitution import (
    build_module_role_overlay,
    resolve_module_reference,
)
from .global_assembly_context import (
    create_global_assembly_context,
    preview_global_assembly_command,
)
from .global_module_catalog import validate_global_module_catalog


SCHEMA = "evidence-backed-cross-project-long-chain-plan/v1"
ORDERING_SCHEMA = "released-installation-dependency-ordering/v1"


ROLE_ORDER = {
    "Base": 0,
    "Transport": 10,
    "Scanner": 20,
    "CCD": 30,
    "Calibration": 40,
    "Positioning": 50,
    "GlueSupply": 60,
    "CleaningWeighing": 70,
    "Cleaning": 71,
    "WasteCup": 72,
    "Gantry": 90,
    "Unclassified": 100,
}


class EvidenceBackedLongChainError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _projects(definition: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("projectId") or "").strip().lower()
            for row in definition.get("projectAliases") or []
            if str(row.get("projectId") or "").strip()
        }
    )


def _tokens(definition: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("moduleToken") or "").strip().upper()
            for row in definition.get("projectAliases") or []
            if str(row.get("moduleToken") or "").strip()
        }
    )


def _primary_token(definition: dict[str, Any]) -> str:
    tokens = _tokens(definition)
    return tokens[0] if tokens else str(definition.get("displayName") or "")


def build_evidence_backed_long_chain_plan(
    catalog: dict[str, Any],
    release_manifest: dict[str, Any],
    *,
    base_module: str | dict[str, str],
    ordered_modules: list[str | dict[str, str]],
) -> dict[str, Any]:
    """Build an auditable, fail-closed cumulative chain plan.

    A plan is ready only when every module has one unique released installation
    relation to the base.  The same base slot cannot be consumed twice.  The
    function deliberately does not treat role equality or an unreleased native
    template as execution authority.
    """

    validate_global_module_catalog(catalog)
    if release_manifest.get("schemaVersion") != (
        "global-relation-catalog-release/v1"
    ):
        raise EvidenceBackedLongChainError("不支持的关系发布清单版本。")
    if release_manifest.get("status") != "released_for_demo_relation_execution":
        raise EvidenceBackedLongChainError("关系目录尚未发布为Demo可执行版本。")
    if release_manifest.get("catalogDigest") != catalog.get("catalogDigest"):
        raise EvidenceBackedLongChainError("发布清单与关系目录摘要不匹配。")
    if not ordered_modules:
        raise EvidenceBackedLongChainError("累计装配链至少需要一个新增模组。")

    base = resolve_module_reference(catalog, base_module)
    additions = [resolve_module_reference(catalog, value) for value in ordered_modules]
    definition_ids = [
        str(base.get("moduleDefinitionId") or ""),
        *[str(row.get("moduleDefinitionId") or "") for row in additions],
    ]
    if len(definition_ids) != len(set(definition_ids)):
        raise EvidenceBackedLongChainError("基座或新增模组重复。")

    ports = {
        str(row.get("globalPortId") or ""): row
        for row in catalog.get("semanticPorts") or []
    }
    authorized = set(
        (release_manifest.get("scope") or {}).get(
            "authorizedDrivingTemplateIds"
        )
        or []
    )
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("globalTemplateId") in authorized
        and "installation" in (row.get("purposes") or [])
    ]
    base_id = str(base["moduleDefinitionId"])
    base_projects = set(_projects(base))
    consumed_slots: set[str] = set()
    steps: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for order, module in enumerate(additions, start=1):
        module_id = str(module["moduleDefinitionId"])
        candidates: list[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]] = []
        for template in templates:
            port_ids = [
                str(value)
                for key in ("candidatePortIdsA", "candidatePortIdsB")
                for value in template.get(key) or []
            ]
            referenced = [ports[value] for value in port_ids if value in ports]
            owners = {
                str(row.get("moduleDefinitionId") or "") for row in referenced
            }
            if owners != {base_id, module_id}:
                continue
            base_ports = [
                row
                for row in referenced
                if row.get("moduleDefinitionId") == base_id
            ]
            module_ports = [
                row
                for row in referenced
                if row.get("moduleDefinitionId") == module_id
            ]
            candidates.append((template, base_ports, module_ports))

        if len(candidates) != 1:
            blockers.append(
                {
                    "code": (
                        "NO_AUTHORIZED_INSTALLATION_TEMPLATE"
                        if not candidates
                        else "AUTHORIZED_INSTALLATION_TEMPLATE_AMBIGUOUS"
                    ),
                    "moduleDefinitionId": module_id,
                    "moduleTokens": _tokens(module),
                    "candidateCount": len(candidates),
                }
            )
            continue

        template, base_ports, module_ports = candidates[0]
        effect = template.get("constraintEffect") or {}
        template_id = str(template.get("globalTemplateId") or "")
        step_blockers: list[str] = []
        if effect.get("fullyLocatesAddedComponent") is not True or int(
            effect.get("expectedResidualDof", -1)
        ) != 0:
            step_blockers.append("INSTALLATION_TEMPLATE_DOES_NOT_CLOSE_EXTERNAL_DOF")
        if not base_ports or not module_ports:
            step_blockers.append("INSTALLATION_TEMPLATE_ENDPOINT_OWNERSHIP_INVALID")
        if not all(
            row.get("portable") is True for row in [*base_ports, *module_ports]
        ):
            step_blockers.append("INSTALLATION_PORT_NOT_PORTABLE")
        slot_ids = sorted(str(row.get("globalPortId") or "") for row in base_ports)
        duplicate_slots = sorted(set(slot_ids) & consumed_slots)
        if duplicate_slots:
            step_blockers.append("BASE_SLOT_ALREADY_CONSUMED")
        compatibility = [
            row
            for row in catalog.get("compatibility") or []
            if row.get("globalTemplateId") == template_id
            and row.get("portableForTemplate") is True
        ]
        if not compatibility:
            step_blockers.append("PORT_COMPATIBILITY_NOT_RELEASED")
        if step_blockers:
            blockers.append(
                {
                    "code": "INSTALLATION_TEMPLATE_REJECTED",
                    "moduleDefinitionId": module_id,
                    "moduleTokens": _tokens(module),
                    "templateId": template_id,
                    "reasons": step_blockers,
                }
            )
            continue
        consumed_slots.update(slot_ids)
        module_projects = set(_projects(module))
        steps.append(
            {
                "order": order,
                "moduleDefinitionId": module_id,
                "moduleTokens": _tokens(module),
                "displayName": module.get("displayName"),
                "projectIds": sorted(module_projects),
                "relationKind": (
                    "cross_project_replacement"
                    if base_projects.isdisjoint(module_projects)
                    else "base_project_native"
                ),
                "globalTemplateId": template_id,
                "legacyTemplateId": template.get("legacyTemplateId"),
                "baseSlotPortIds": slot_ids,
                "modulePortIds": sorted(
                    str(row.get("globalPortId") or "") for row in module_ports
                ),
                "declaredResidualDof": effect.get("expectedResidualDof"),
                "prototypeTopLevelPoseRequired": False,
            }
        )

    ready = not blockers and len(steps) == len(additions)
    project_ids = sorted(
        {
            *_projects(base),
            *(project for row in additions for project in _projects(row)),
        }
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_natural_language_job_compilation" if ready else "blocked",
        "releaseId": release_manifest.get("releaseId"),
        "releaseDigest": release_manifest.get("releaseDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "base": {
            "moduleDefinitionId": base_id,
            "moduleTokens": _tokens(base),
            "displayName": base.get("displayName"),
            "projectIds": _projects(base),
            "fixedContext": True,
        },
        "requestedAdditionCount": len(additions),
        "plannedAdditionCount": len(steps),
        "finalTopLevelModuleCount": 1 + len(steps) if ready else None,
        "projectIds": project_ids,
        "crossProjectAdditionCount": sum(
            row["relationKind"] == "cross_project_replacement" for row in steps
        ),
        "nativeAdditionCount": sum(
            row["relationKind"] == "base_project_native" for row in steps
        ),
        "steps": steps,
        "blockers": blockers,
        "policy": {
            "releasedTemplatesOnly": True,
            "uniqueInstallationTemplateRequired": True,
            "portablePortsRequired": True,
            "externalResidualDofMustBeZero": True,
            "duplicateBaseSlotForbidden": True,
            "prototypeTopLevelPoseAllowed": False,
            "collisionOrBrepRequired": False,
        },
        "statement": (
            "链路仅由已发布、端口可移植且声明封闭外部自由度的安装关系组成；"
            "碰撞/B-rep仍是独立后验项。"
        ),
    }
    return {**deepcopy(core), "planDigest": _digest(core)}


def order_requirements_by_released_installation_dependencies(
    catalog: dict[str, Any],
    release_manifest: dict[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    """Order unambiguous module requests using released installation evidence.

    The function is intentionally conservative.  It supports the common
    cumulative-assembly case in which one selected base exposes a unique,
    released installation slot for every requested addition.  It never guesses
    through an ambiguous natural-language module match and never treats role
    equality as mechanical compatibility.
    """

    validate_global_module_catalog(catalog)
    if not requirements:
        raise EvidenceBackedLongChainError("自然语言需求列表不能为空。")
    authorized = list(
        (release_manifest.get("scope") or {}).get(
            "authorizedDrivingTemplateIds"
        )
        or []
    )
    preview_context = create_global_assembly_context(
        "released-dependency-order-preview",
        catalog_digest=str(catalog.get("catalogDigest") or ""),
    )
    resolved: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for input_order, requirement in enumerate(requirements, start=1):
        preview = preview_global_assembly_command(
            catalog,
            preview_context,
            {
                "requirement": requirement,
                "allowedTemplateIds": authorized,
            },
        )
        definition_id = str(preview.get("selectedModuleDefinitionId") or "")
        if preview.get("status") != "ready" or not definition_id:
            blockers.append(
                {
                    "code": "REQUIREMENT_MODULE_NOT_UNIQUE",
                    "inputOrder": input_order,
                    "requirement": requirement,
                    "previewStatus": preview.get("status"),
                    "previewBlockers": preview.get("blockers") or [],
                }
            )
            continue
        resolved.append(
            {
                "inputOrder": input_order,
                "requirement": requirement,
                "moduleDefinitionId": definition_id,
            }
        )

    definition_ids = [row["moduleDefinitionId"] for row in resolved]
    if len(definition_ids) != len(set(definition_ids)):
        blockers.append(
            {
                "code": "DUPLICATE_MODULE_REQUIREMENT",
                "moduleDefinitionIds": sorted(
                    value
                    for value in set(definition_ids)
                    if definition_ids.count(value) > 1
                ),
            }
        )
    role_overlay = build_module_role_overlay(catalog)
    role_by_definition = {
        str(row.get("moduleDefinitionId") or ""): str(
            row.get("primaryRole") or "Unclassified"
        )
        for row in role_overlay.get("modules") or []
    }
    base_rows = [
        row
        for row in resolved
        if role_by_definition.get(row["moduleDefinitionId"]) == "Base"
    ]
    if len(base_rows) != 1:
        blockers.append(
            {
                "code": "UNIQUE_BASE_REQUIREMENT_REQUIRED",
                "candidateCount": len(base_rows),
                "candidateDefinitionIds": [
                    row["moduleDefinitionId"] for row in base_rows
                ],
            }
        )

    if blockers:
        core = {
            "schemaVersion": ORDERING_SCHEMA,
            "status": "blocked",
            "releaseId": release_manifest.get("releaseId"),
            "inputRequirements": requirements,
            "orderedRequirements": [],
            "steps": [],
            "blockers": blockers,
            "cadStarted": False,
        }
        return {**core, "orderingDigest": _digest(core)}

    base_row = base_rows[0]
    additions = [row for row in resolved if row is not base_row]
    additions.sort(
        key=lambda row: (
            ROLE_ORDER.get(
                role_by_definition.get(row["moduleDefinitionId"], "Unclassified"),
                100,
            ),
            row["moduleDefinitionId"],
        )
    )
    plan = build_evidence_backed_long_chain_plan(
        catalog,
        release_manifest,
        base_module=base_row["moduleDefinitionId"],
        ordered_modules=[row["moduleDefinitionId"] for row in additions],
    )
    if plan.get("status") != "ready_for_natural_language_job_compilation":
        blockers = [
            {
                "code": "RELEASED_INSTALLATION_DEPENDENCY_NOT_CLOSED",
                "planBlockers": plan.get("blockers") or [],
            }
        ]
        core = {
            "schemaVersion": ORDERING_SCHEMA,
            "status": "blocked",
            "releaseId": release_manifest.get("releaseId"),
            "inputRequirements": requirements,
            "orderedRequirements": [],
            "steps": [],
            "blockers": blockers,
            "cadStarted": False,
        }
        return {**core, "orderingDigest": _digest(core)}

    ordered_rows = [base_row, *additions]
    core = {
        "schemaVersion": ORDERING_SCHEMA,
        "status": "ready",
        "releaseId": release_manifest.get("releaseId"),
        "releaseDigest": release_manifest.get("releaseDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "inputRequirements": requirements,
        "orderedRequirements": [row["requirement"] for row in ordered_rows],
        "reordered": [row["inputOrder"] for row in ordered_rows]
        != list(range(1, len(ordered_rows) + 1)),
        "steps": [
            {
                "plannedOrder": planned_order,
                "inputOrder": row["inputOrder"],
                "requirement": row["requirement"],
                "moduleDefinitionId": row["moduleDefinitionId"],
                "primaryRole": role_by_definition.get(
                    row["moduleDefinitionId"], "Unclassified"
                ),
                "dependsOnPlannedOrder": [] if planned_order == 1 else [1],
            }
            for planned_order, row in enumerate(ordered_rows, start=1)
        ],
        "chainPlanDigest": plan["planDigest"],
        "blockers": [],
        "cadStarted": False,
        "statement": (
            "自然语言输入顺序仅用于表达需求；实际累计顺序由已发布安装关系、"
            "唯一基座和确定性角色顺序生成。"
        ),
    }
    return {**core, "orderingDigest": _digest(core)}
