"""Project-independent command IR and semantic assembly transaction DAG.

This module deliberately stops before SolidWorks execution.  It turns the
versioned global assembly context into deterministic, auditable insertion
transactions without consulting a project-specific installation sequence.
Project provenance remains evidence; it is not used as the planning key.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .global_assembly_context import validate_global_assembly_context
from .global_module_catalog import validate_global_module_catalog
from .global_relation_semantics import normalize_template_relation_profile


GLOBAL_COMMAND_IR_SCHEMA = "global-assembly-command-ir/v1"
GLOBAL_TRANSACTION_DAG_SCHEMA = "global-assembly-transaction-dag/v1"


class GlobalAssemblyTransactionError(ValueError):
    pass


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_global_command_ir(preview: dict[str, Any]) -> dict[str, Any]:
    """Normalize an add/connect preview into a project-independent command IR."""

    patch = preview.get("proposedPatch")
    operations: list[dict[str, Any]] = []
    if isinstance(patch, dict):
        instance = patch.get("instance") or {}
        if instance:
            operations.append(
                {
                    "operation": "ADD",
                    "instanceId": instance.get("instanceId"),
                    "moduleDefinitionId": instance.get("moduleDefinitionId"),
                    "displayName": instance.get("displayName"),
                }
            )
        connection = patch.get("connection")
        if isinstance(connection, dict):
            operations.append(
                {
                    "operation": "CONNECT",
                    "connectionId": connection.get("connectionId"),
                    "instanceAId": connection.get("instanceAId"),
                    "portAId": connection.get("portAId"),
                    "instanceBId": connection.get("instanceBId"),
                    "portBId": connection.get("portBId"),
                    "globalTemplateId": connection.get("globalTemplateId"),
                    "purpose": connection.get("purpose") or "installation",
                    "relationIntent": connection.get("relationIntent"),
                    "relationProfile": connection.get("relationProfile"),
                }
            )
    result = {
        "schemaVersion": GLOBAL_COMMAND_IR_SCHEMA,
        "requirement": preview.get("requirement"),
        "status": preview.get("status"),
        "resolution": preview.get("resolution"),
        "relationIntent": preview.get("relationIntent"),
        "sourceContextDigest": preview.get("sourceContextDigest"),
        "catalogDigest": preview.get("catalogDigest"),
        "relationReleaseBinding": preview.get("relationReleaseBinding"),
        "operations": operations,
        "blockers": preview.get("blockers") or [],
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionStatus": "not_evaluated",
            "statement": "命令中间态只描述模组实例与语义连接，不直接修改CAD。",
        },
    }
    result["commandDigest"] = _digest(result)
    return result


def _constraint_assessment(
    templates: list[dict[str, Any]],
    template_combinations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    effects = [template.get("constraintEffect") or {} for template in templates]
    fully_values = [effect.get("fullyLocatesAddedComponent") for effect in effects]
    residual_values = [
        int(effect["expectedResidualDof"])
        for effect in effects
        if isinstance(effect.get("expectedResidualDof"), (int, float))
    ]
    verified_markers = {
        str(value).strip().lower()
        for value in fully_values
        if isinstance(value, str)
    }
    legacy_template_ids = {
        str(template.get("legacyTemplateId") or "")
        for template in templates
        if str(template.get("legacyTemplateId") or "")
    }
    global_template_ids = {
        str(template.get("globalTemplateId") or "")
        for template in templates
        if str(template.get("globalTemplateId") or "")
    }
    first_class_combinations = []
    for combination in template_combinations or []:
        members = {
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        }
        exact_required = combination.get("exactMemberSetRequired") is not False
        matched = members == global_template_ids if exact_required else members <= global_template_ids
        if matched:
            first_class_combinations.append(combination)
    first_class_closed = next(
        (
            row
            for row in first_class_combinations
            if row.get("fullyLocatesAddedComponent") is True
            and int(row.get("expectedResidualDof") or 0) == 0
        ),
        None,
    )
    declared_combinations = []
    for template, effect in zip(templates, effects):
        complements = {
            str(value)
            for value in effect.get("completesWithLegacyTemplateIds") or []
            if str(value)
        }
        matched = sorted(complements & legacy_template_ids)
        combined_residual = effect.get("combinedExpectedResidualDof")
        if matched and isinstance(combined_residual, (int, float)):
            declared_combinations.append(
                {
                    "completionTemplateId": template.get("globalTemplateId"),
                    "completionLegacyTemplateId": template.get("legacyTemplateId"),
                    "matchedLegacyTemplateIds": matched,
                    "combinedExpectedResidualDof": int(combined_residual),
                    "completionScope": effect.get("completionScope"),
                    "completionExplanation": effect.get("completionExplanation"),
                }
            )
    closed_combination = next(
        (
            row
            for row in declared_combinations
            if row["combinedExpectedResidualDof"] == 0
        ),
        None,
    )
    if first_class_closed is not None:
        closed_combination = {
            "globalCombinationId": first_class_closed.get("globalCombinationId"),
            "legacyCombinationId": first_class_closed.get("legacyCombinationId"),
            "memberGlobalTemplateIds": list(
                first_class_closed.get("memberGlobalTemplateIds") or []
            ),
            "memberLegacyTemplateIds": list(
                first_class_closed.get("memberLegacyTemplateIds") or []
            ),
            "primaryGlobalTemplateId": first_class_closed.get(
                "primaryGlobalTemplateId"
            ),
            "primaryLegacyTemplateId": first_class_closed.get(
                "primaryLegacyTemplateId"
            ),
            "combinedExpectedResidualDof": int(
                first_class_closed.get("expectedResidualDof") or 0
            ),
            "completionScope": first_class_closed.get("applicationScope"),
            "completionExplanation": first_class_closed.get("explanation"),
            "evidence": "catalog_template_combination",
        }
        state = "closed_by_declared_template_combination"
        residual = 0
        execution_policy = "ready_for_generic_cad_transaction"
    elif closed_combination is not None:
        state = "closed_by_declared_template_combination"
        residual = 0
        execution_policy = "ready_for_generic_cad_transaction"
    elif any(value is True for value in fully_values) or any(
        "verified" in value for value in verified_markers
    ):
        state = "declared_or_cad_verified_closed"
        residual: int | None = 0
        execution_policy = "ready_for_generic_cad_transaction"
    elif residual_values and min(residual_values) == 0:
        state = "declared_closed"
        residual = 0
        execution_policy = "ready_for_generic_cad_transaction"
    elif any(value is False for value in fully_values):
        state = "declared_underconstrained"
        residual = min(residual_values) if residual_values else None
        execution_policy = "blocked_until_additional_datum_or_confirmed_anchor"
    else:
        state = "requires_cad_verification"
        residual = min(residual_values) if residual_values else None
        execution_policy = "compile_only_requires_authoritative_cad_solve"
    return {
        "state": state,
        "expectedResidualDof": residual,
        "closedByCatalogEvidence": residual == 0,
        "executionPolicy": execution_policy,
        "authoritativeCadSolveRequired": True,
        "declaredTemplateCombination": closed_combination,
        "effects": effects,
        "templateExplanations": [
            normalize_template_relation_profile(template)["constraintExplanation"]
            for template in templates
        ],
    }


def _positioning_standard_binding_for_definition(
    definition: dict[str, Any],
    positioning_standard: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve an explicitly supplied project baseline for one target definition.

    The caller must opt in by supplying the standard.  Project aliases are used
    only to bind the target to a standard rule; they do not affect transaction
    order.
    """

    if not positioning_standard:
        return None
    project_id = str(positioning_standard.get("projectId") or "").lower()
    modules = positioning_standard.get("modules") or {}
    matches = [
        str(alias.get("moduleToken") or "").upper()
        for alias in definition.get("projectAliases") or []
        if str(alias.get("projectId") or "").lower() == project_id
        and str(alias.get("moduleToken") or "").upper() in modules
    ]
    if len(matches) != 1:
        return None
    token = matches[0]
    module = modules[token]
    return {
        "schemaVersion": positioning_standard.get("schemaVersion"),
        "standardVersion": positioning_standard.get("standardVersion"),
        "standardDigest": positioning_standard.get("standardDigest"),
        "scope": positioning_standard.get("scope"),
        "projectId": project_id,
        "moduleToken": token,
        "ruleId": module.get("ruleId"),
        "authorityRequirementIds": list(module.get("authorityRequirementIds") or []),
        "releaseState": "ready-with-project-baseline",
        "productionUseAllowed": bool(
            (positioning_standard.get("releaseBoundary") or {}).get(
                "productionUseAllowed"
            )
        ),
    }
def _connection_evidence(
    connection: dict[str, Any],
    *,
    instances: dict[str, dict[str, Any]],
    ports: dict[str, dict[str, Any]],
    templates: dict[str, dict[str, Any]],
    compatibility: set[tuple[str, str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    connection_id = str(connection.get("connectionId") or "")
    instance_a = instances.get(str(connection.get("instanceAId") or ""))
    instance_b = instances.get(str(connection.get("instanceBId") or ""))
    port_a_id = str(connection.get("portAId") or "")
    port_b_id = str(connection.get("portBId") or "")
    template_id = str(connection.get("globalTemplateId") or "")
    port_a = ports.get(port_a_id)
    port_b = ports.get(port_b_id)
    template = templates.get(template_id)

    if instance_a is None or instance_b is None:
        blockers.append(
            {
                "code": "CONNECTION_INSTANCE_NOT_FOUND",
                "detail": connection_id,
            }
        )
    if port_a is None or port_b is None:
        blockers.append({"code": "CONNECTION_PORT_NOT_FOUND", "detail": connection_id})
    if template is None:
        blockers.append({"code": "CONNECTION_TEMPLATE_NOT_FOUND", "detail": connection_id})
    if port_a is not None and instance_a is not None and (
        port_a.get("moduleDefinitionId") != instance_a.get("moduleDefinitionId")
    ):
        blockers.append({"code": "PORT_A_INSTANCE_MISMATCH", "detail": connection_id})
    if port_b is not None and instance_b is not None and (
        port_b.get("moduleDefinitionId") != instance_b.get("moduleDefinitionId")
    ):
        blockers.append({"code": "PORT_B_INSTANCE_MISMATCH", "detail": connection_id})
    if (port_a_id, port_b_id, template_id) not in compatibility:
        blockers.append({"code": "PORT_TEMPLATE_INCOMPATIBLE", "detail": connection_id})
    if port_a is not None and port_a.get("portable") is not True:
        blockers.append({"code": "PORT_A_NOT_PORTABLE", "detail": connection_id})
    if port_b is not None and port_b.get("portable") is not True:
        blockers.append({"code": "PORT_B_NOT_PORTABLE", "detail": connection_id})
    mate_steps = list((template or {}).get("mateSteps") or [])
    if isinstance((template or {}).get("mateSteps"), dict):
        mate_steps = [(template or {})["mateSteps"]]
    if not mate_steps:
        blockers.append({"code": "NO_DRIVING_MATE_STEPS", "detail": connection_id})

    return (
        {
            "connectionId": connection_id,
            "instanceAId": connection.get("instanceAId"),
            "portAId": port_a_id,
            "instanceBId": connection.get("instanceBId"),
            "portBId": port_b_id,
            "globalTemplateId": template_id,
            "purpose": connection.get("purpose") or "installation",
            "mateStepCount": len(mate_steps),
            "mateSteps": mate_steps,
            "templateProvenance": (template or {}).get("provenance"),
            "relationIntent": connection.get("relationIntent"),
            "relationSemantics": (
                normalize_template_relation_profile(template) if template else None
            ),
            "portable": not any(
                blocker["code"] in {"PORT_A_NOT_PORTABLE", "PORT_B_NOT_PORTABLE"}
                for blocker in blockers
            ),
        },
        blockers,
    )


def compile_global_assembly_transaction_dag(
    catalog: dict[str, Any],
    context: dict[str, Any],
    *,
    base_instance_id: str | None = None,
    positioning_standard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile any connected global assembly graph into deterministic transactions.

    No project profile, fixed project sequence, or SolidWorks runner is consulted.
    The first/base instance is treated as the already available assembly context.
    """

    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyTransactionError("上下文与全局目录摘要不一致。")
    release_binding = context.get("relationReleaseBinding")
    authorized_template_ids = set(
        (release_binding or {}).get("authorizedDrivingTemplateIds") or []
    )

    instance_rows = list(context.get("instances") or [])
    if not instance_rows:
        raise GlobalAssemblyTransactionError("装配上下文没有模组实例。")
    instances = {str(row.get("instanceId")): row for row in instance_rows}
    if len(instances) != len(instance_rows):
        raise GlobalAssemblyTransactionError("装配上下文存在重复instanceId。")
    definitions = {
        str(row.get("moduleDefinitionId")): row
        for row in catalog.get("moduleDefinitions") or []
    }
    ports = {str(row.get("globalPortId")): row for row in catalog.get("semanticPorts") or []}
    templates = {
        str(row.get("globalTemplateId")): row
        for row in catalog.get("connectionTemplates") or []
    }
    authorized_validation_template_ids = {
        template_id
        for template_id, template in templates.items()
        if normalize_template_relation_profile(template).get("drivesPlacement") is False
        and int(
            normalize_template_relation_profile(template).get(
                "validationMateStepCount"
            )
            or 0
        )
        > 0
    }
    compatibility = {
        (
            str(row.get("portAId") or ""),
            str(row.get("portBId") or ""),
            str(row.get("globalTemplateId") or ""),
        )
        for row in catalog.get("compatibility") or []
        if row.get("portableForTemplate") is True
    }

    base_candidates = [
        str(row["instanceId"])
        for row in instance_rows
        if row.get("placementStatus") == "base_context_unlocated"
    ]
    selected_base = str(base_instance_id or "").strip()
    if selected_base:
        if selected_base not in instances:
            raise GlobalAssemblyTransactionError("指定的baseInstanceId不存在。")
    elif len(base_candidates) == 1:
        selected_base = base_candidates[0]
    elif not base_candidates:
        selected_base = str(instance_rows[0]["instanceId"])
    else:
        raise GlobalAssemblyTransactionError("存在多个基座候选，必须显式指定baseInstanceId。")

    order_index = {
        str(row["instanceId"]): index for index, row in enumerate(instance_rows)
    }
    connection_rows = list(context.get("connections") or [])
    connection_records: dict[str, dict[str, Any]] = {}
    connection_blockers: dict[str, list[dict[str, Any]]] = {}
    for connection in connection_rows:
        record, blockers = _connection_evidence(
            connection,
            instances=instances,
            ports=ports,
            templates=templates,
            compatibility=compatibility,
        )
        read_only_verification = str(
            connection.get("executionStatus") or ""
        ).startswith("planned_relation_verification")
        allowed_by_release = (
            authorized_template_ids | authorized_validation_template_ids
            if read_only_verification
            else authorized_template_ids
        )
        if release_binding is not None and record["globalTemplateId"] not in allowed_by_release:
            blockers.append(
                {
                    "code": "TEMPLATE_NOT_AUTHORIZED_BY_BOUND_RELEASE",
                    "detail": record["globalTemplateId"],
                }
            )
        connection_records[record["connectionId"]] = record
        connection_blockers[record["connectionId"]] = blockers

    installed = {selected_base}
    introduced_by_step: dict[str, str | None] = {selected_base: None}
    remaining = set(instances) - installed
    pending = list(connection_rows)
    steps: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    while remaining:
        candidates: list[tuple[int, str, list[dict[str, Any]]]] = []
        for instance_id in remaining:
            links = [
                row
                for row in pending
                if not str(row.get("executionStatus") or "").startswith(
                    "planned_relation_"
                )
                if instance_id in {str(row.get("instanceAId")), str(row.get("instanceBId"))}
                and (
                    str(row.get("instanceBId")) in installed
                    if str(row.get("instanceAId")) == instance_id
                    else str(row.get("instanceAId")) in installed
                )
            ]
            if links:
                candidates.append((order_index[instance_id], instance_id, links))
        if not candidates:
            for instance_id in sorted(remaining, key=lambda value: order_index[value]):
                blockers.append(
                    {
                        "code": "INSTANCE_NOT_REACHABLE_FROM_BASE",
                        "instanceId": instance_id,
                        "detail": "该实例没有连接到已安装上下文，无法生成累计插入顺序。",
                    }
                )
            break

        _, target_id, links = min(candidates, key=lambda row: (row[0], row[1]))
        primary_legacy_template_ids = {
            str(
                templates.get(str(row.get("globalTemplateId") or ""), {}).get(
                    "legacyTemplateId"
                )
                or ""
            )
            for row in links
        }
        primary_legacy_template_ids.discard("")
        primary_global_template_ids = {
            str(row.get("globalTemplateId") or "") for row in links
        }
        primary_global_template_ids.discard("")
        declared_completion_template_ids: set[str] = set()
        for combination in catalog.get("templateCombinations") or []:
            members = {
                str(value)
                for value in combination.get("memberGlobalTemplateIds") or []
                if str(value)
            }
            if (
                combination.get("applicationScope") == "same_target_insertion"
                and primary_global_template_ids
                and primary_global_template_ids.issubset(members)
                and primary_global_template_ids != members
            ):
                declared_completion_template_ids.update(
                    members - primary_global_template_ids
                )
        completion_links = []
        for row in pending:
            if row in links or not str(row.get("executionStatus") or "").startswith(
                "planned_relation_"
            ):
                continue
            endpoint_ids = {
                str(row.get("instanceAId") or ""),
                str(row.get("instanceBId") or ""),
            }
            if target_id not in endpoint_ids or not (endpoint_ids - {target_id}) & installed:
                continue
            template = templates.get(str(row.get("globalTemplateId") or "")) or {}
            template_id = str(template.get("globalTemplateId") or "")
            if template_id in declared_completion_template_ids:
                completion_links.append(row)
                continue
            effect = template.get("constraintEffect") or {}
            if effect.get("completionScope") != "same_target_insertion":
                continue
            complements = {
                str(value)
                for value in effect.get("completesWithLegacyTemplateIds") or []
                if str(value)
            }
            if complements & primary_legacy_template_ids:
                completion_links.append(row)
        links = [*links, *completion_links]
        connection_ids = [str(row.get("connectionId") or "") for row in links]
        records = [connection_records[connection_id] for connection_id in connection_ids]
        step_blockers = [
            {"connectionId": connection_id, **blocker}
            for connection_id in connection_ids
            for blocker in connection_blockers[connection_id]
        ]
        step_templates = [
            templates[record["globalTemplateId"]]
            for record in records
            if record["globalTemplateId"] in templates
        ]
        definition = definitions.get(str(instances[target_id].get("moduleDefinitionId"))) or {}
        positioning_binding = _positioning_standard_binding_for_definition(
            definition,
            positioning_standard,
        )
        constraint = _constraint_assessment(
            step_templates, catalog.get("templateCombinations") or []
        )
        if (
            constraint["state"] == "declared_underconstrained"
            and positioning_binding is not None
            and bool(
                (positioning_standard.get("releaseBoundary") or {}).get(
                    "coarseLayoutUseAllowed"
                )
            )
        ):
            constraint = {
                **constraint,
                "state": "closed_by_explicit_project_baseline",
                "expectedResidualDof": 0,
                "closedByCatalogEvidence": False,
                "closedByProjectBaseline": True,
                "executionPolicy": "ready_for_generic_cad_transaction",
                "positioningStandardBinding": positioning_binding,
            }
        elif constraint["state"] == "declared_underconstrained":
            step_blockers.append(
                {
                    "code": "TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE",
                    "instanceId": target_id,
                    "detail": "现有配合未声明完整定位；需补机械基准、确认锚点或人工选面。",
                }
            )
        context_ids = sorted(
            {
                str(row.get("instanceBId"))
                if str(row.get("instanceAId")) == target_id
                else str(row.get("instanceAId"))
                for row in links
            },
            key=lambda value: order_index[value],
        )
        dependencies = sorted(
            {
                introduced_by_step[instance_id]
                for instance_id in context_ids
                if introduced_by_step.get(instance_id)
            }
        )
        if not definition:
            step_blockers.append(
                {
                    "code": "MODULE_DEFINITION_NOT_FOUND",
                    "instanceId": target_id,
                    "detail": instances[target_id].get("moduleDefinitionId"),
                }
            )
        cad_sources = list(definition.get("cadSources") or [])
        if not cad_sources:
            step_blockers.append(
                {
                    "code": "MODULE_CAD_SOURCE_NOT_REGISTERED",
                    "instanceId": target_id,
                    "detail": definition.get("moduleDefinitionId"),
                }
            )
        step_id = f"transaction-{len(steps) + 1:03d}"
        step = {
            "stepId": step_id,
            "order": len(steps) + 1,
            "operation": "INSERT_AND_CONNECT",
            "targetInstanceId": target_id,
            "targetModuleDefinitionId": instances[target_id].get("moduleDefinitionId"),
            "targetDisplayName": instances[target_id].get("displayName"),
            "contextInstanceIds": context_ids,
            "dependsOn": dependencies,
            "connections": records,
            "constraintAssessment": constraint,
            "positioningStandardBinding": positioning_binding,
            "cadSources": cad_sources,
            "status": (
                "ready_for_generic_cad_transaction"
                if not step_blockers
                and constraint["executionPolicy"] == "ready_for_generic_cad_transaction"
                else "compiled_requires_cad_verification"
                if not step_blockers
                else "blocked"
            ),
            "blockers": step_blockers,
        }
        steps.append(step)
        blockers.extend({"stepId": step_id, **item} for item in step_blockers)
        installed.add(target_id)
        remaining.remove(target_id)
        introduced_by_step[target_id] = step_id
        pending = [row for row in pending if row not in links]

    if pending and not remaining:
        # Connections left after all instances are installed are not insertion
        # failures.  They are explicit relation-edit/verification transactions
        # between existing instances and must be scheduled after both endpoints.
        for row in sorted(
            pending, key=lambda item: str(item.get("connectionId") or "")
        ):
            connection_id = str(row.get("connectionId") or "")
            record = connection_records[connection_id]
            step_blockers = [
                {"connectionId": connection_id, **item}
                for item in connection_blockers[connection_id]
            ]
            template = templates.get(record["globalTemplateId"])
            profile = (
                normalize_template_relation_profile(template) if template else None
            )
            drives_placement = bool((profile or {}).get("drivesPlacement"))
            endpoint_ids = [
                str(row.get("instanceAId") or ""),
                str(row.get("instanceBId") or ""),
            ]
            dependencies = sorted(
                {
                    introduced_by_step[instance_id]
                    for instance_id in endpoint_ids
                    if introduced_by_step.get(instance_id)
                }
            )
            constraint = _constraint_assessment(
                [template] if template else [],
                catalog.get("templateCombinations") or [],
            )
            constraint = {
                **constraint,
                "relationEditMode": True,
                "requiresFullPlacementClosure": False,
                "overconstraintMustBeCheckedByCad": drives_placement,
                "executionPolicy": (
                    "compile_relation_edit_requires_authoritative_cad_solve"
                    if drives_placement
                    else "ready_for_relation_verification"
                ),
            }
            step_id = f"transaction-{len(steps) + 1:03d}"
            step = {
                "stepId": step_id,
                "order": len(steps) + 1,
                "operation": "ADD_RELATION" if drives_placement else "VERIFY_RELATION",
                "targetInstanceId": None,
                "targetModuleDefinitionId": None,
                "targetDisplayName": None,
                "contextInstanceIds": endpoint_ids,
                "dependsOn": dependencies,
                "connections": [record],
                "constraintAssessment": constraint,
                "positioningStandardBinding": None,
                "cadSources": [],
                "status": (
                    "blocked"
                    if step_blockers
                    else "compiled_requires_cad_verification"
                    if drives_placement
                    else "ready_for_relation_verification"
                ),
                "blockers": step_blockers,
            }
            steps.append(step)
            blockers.extend({"stepId": step_id, **item} for item in step_blockers)

    unresolved = sorted(remaining, key=lambda value: order_index[value])
    if blockers:
        status = "blocked"
    elif any(step["status"] == "compiled_requires_cad_verification" for step in steps):
        status = "compiled_requires_cad_verification"
    else:
        status = "ready_for_generic_cad_executor"
    result = {
        "schemaVersion": GLOBAL_TRANSACTION_DAG_SCHEMA,
        "contextId": context.get("contextId"),
        "contextDigest": context.get("contextDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "relationReleaseBinding": release_binding,
        "planningMode": "project_independent_semantic_graph",
        "projectSequenceRequired": False,
        "positioningStandard": (
            {
                "schemaVersion": positioning_standard.get("schemaVersion"),
                "standardVersion": positioning_standard.get("standardVersion"),
                "standardDigest": positioning_standard.get("standardDigest"),
                "scope": positioning_standard.get("scope"),
                "projectId": positioning_standard.get("projectId"),
                "explicitlySelected": True,
            }
            if positioning_standard
            else None
        ),
        "status": status,
        "baseInstance": instances[selected_base],
        "instanceCount": len(instance_rows),
        "transactionCount": len(steps),
        "steps": steps,
        "unresolvedInstanceIds": unresolved,
        "blockers": blockers,
        "collisionAssessment": {
            "status": "not_evaluated",
            "reason": "collision_and_brep_are_deferred_by_current_scope",
        },
        "executionBoundary": {
            "solidWorksExecuted": False,
            "nextAdapter": "generic cumulative resolved-pair executor",
            "statement": (
                "本DAG不依赖项目固定顺序；CAD执行仍需逐步消费事务、保存重开并提交检查点。"
            ),
        },
    }
    result["dagDigest"] = _digest(result)
    return result

