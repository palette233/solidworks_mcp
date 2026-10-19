"""Compile project-independent semantic DAG steps into CAD transaction packets.

Packets are an execution contract, not a CAD result.  They identify the target
CAD definition, endpoint evidence and cumulative checkpoint flow while leaving
SolidWorks mutation to the existing transactional executor layer.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .global_assembly_transactions import compile_global_assembly_transaction_dag
from .relation_validation_preconditions import (
    assess_relation_validation_precondition,
    relation_validation_precondition_registry_binding,
)
from .relation_driving_safety import (
    assess_relation_driving_safety,
    relation_driving_safety_registry_binding,
)


GLOBAL_CAD_TRANSACTION_MANIFEST_SCHEMA = "global-cad-transaction-manifest/v1"
GLOBAL_CAD_TRANSACTION_PACKET_SCHEMA = "global-cad-transaction-packet/v1"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _role_map(port: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for endpoint in port.get("endpointEvidence") or []:
        role = str(endpoint.get("role") or "")
        if role:
            result.setdefault(role, []).append(endpoint)
    return result


def _mate_roles(mate: dict[str, Any], side: str) -> list[str]:
    direct = str(mate.get(f"endpointRole{side}") or "")
    if direct:
        return [direct]
    return [
        str(row.get("role"))
        for row in mate.get("endpointRoles") or []
        if str(row.get("side") or "").upper() == side and row.get("role")
    ]


def _compile_connection(
    connection: dict[str, Any],
    *,
    ports: dict[str, dict[str, Any]],
    templates: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection_id = str(connection.get("connectionId") or "")
    port_a = ports.get(str(connection.get("portAId") or "")) or {}
    port_b = ports.get(str(connection.get("portBId") or "")) or {}
    template = templates.get(str(connection.get("globalTemplateId") or "")) or {}
    roles_a = _role_map(port_a)
    roles_b = _role_map(port_b)
    blockers: list[dict[str, Any]] = []
    compiled_mates: list[dict[str, Any]] = []
    for order, mate in enumerate(template.get("mateSteps") or [], start=1):
        mate_roles_a = _mate_roles(mate, "A")
        mate_roles_b = _mate_roles(mate, "B")
        endpoint_roles_a = [
            {"role": role, "candidates": roles_a.get(role) or []}
            for role in mate_roles_a
        ]
        endpoint_roles_b = [
            {"role": role, "candidates": roles_b.get(role) or []}
            for role in mate_roles_b
        ]
        if not mate_roles_a:
            endpoint_roles_a = [{"role": None, "candidates": []}]
        if not mate_roles_b:
            endpoint_roles_b = [{"role": None, "candidates": []}]
        for endpoint_role in endpoint_roles_a:
            if not endpoint_role["candidates"]:
                blockers.append(
                    {
                        "code": "ENDPOINT_ROLE_A_NOT_REGISTERED",
                        "connectionId": connection_id,
                        "mateOrder": order,
                        "detail": endpoint_role["role"],
                    }
                )
        for endpoint_role in endpoint_roles_b:
            if not endpoint_role["candidates"]:
                blockers.append(
                    {
                        "code": "ENDPOINT_ROLE_B_NOT_REGISTERED",
                        "connectionId": connection_id,
                        "mateOrder": order,
                        "detail": endpoint_role["role"],
                    }
                )
        compiled_mates.append(
            {
                "order": order,
                "mateName": mate.get("mateName"),
                "mateType": mate.get("mateType"),
                "mateTypeName": mate.get("mateTypeName"),
                "alignment": mate.get("alignment"),
                "alignmentName": mate.get("alignmentName"),
                "distance": mate.get("distance"),
                "angle": mate.get("angle"),
                "advancedOptions": {
                    key: value
                    for key, value in mate.items()
                    if key
                    not in {
                        "mateName",
                        "mateType",
                        "mateTypeName",
                        "alignment",
                        "alignmentName",
                        "distance",
                        "angle",
                        "endpointRoleA",
                        "endpointRoleB",
                    }
                },
                "endpointsA": {
                    "portId": port_a.get("globalPortId"),
                    "roles": endpoint_roles_a,
                },
                "endpointsB": {
                    "portId": port_b.get("globalPortId"),
                    "roles": endpoint_roles_b,
                },
            }
        )
    provenance = template.get("provenance") or {}
    explicit_effective_graph = str(
        provenance.get("effectiveMateGraphPath") or ""
    ).strip()
    semantic_catalog_path = str(provenance.get("semanticCatalogPath") or "")
    effective_graph_candidate = explicit_effective_graph or (
        semantic_catalog_path.rsplit("/", 1)[0] + "/assembly_plan_effective.json"
        if "/" in semantic_catalog_path
        else None
    )
    return (
        {
            "connectionId": connection_id,
            "instanceAId": connection.get("instanceAId"),
            "portAId": connection.get("portAId"),
            "instanceBId": connection.get("instanceBId"),
            "portBId": connection.get("portBId"),
            "globalTemplateId": connection.get("globalTemplateId"),
            "templateEvidenceSource": provenance,
            "effectiveMateGraphCandidate": effective_graph_candidate,
            "mates": compiled_mates,
        },
        blockers,
    )


def compile_global_cad_transaction_manifest(
    catalog: dict[str, Any],
    context: dict[str, Any],
    *,
    base_instance_id: str | None = None,
    positioning_standard: dict[str, Any] | None = None,
    validation_precondition_registry: dict[str, Any] | None = None,
    validation_precondition_registry_path: str | None = None,
    driving_safety_registry: dict[str, Any] | None = None,
    driving_safety_registry_path: str | None = None,
    driving_strategy_selections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dag = compile_global_assembly_transaction_dag(
        catalog,
        context,
        base_instance_id=base_instance_id,
        positioning_standard=positioning_standard,
    )
    definitions = {
        str(row.get("moduleDefinitionId")): row
        for row in catalog.get("moduleDefinitions") or []
    }
    instances = {
        str(row.get("instanceId")): row for row in context.get("instances") or []
    }
    ports = {str(row.get("globalPortId")): row for row in catalog.get("semanticPorts") or []}
    templates = {
        str(row.get("globalTemplateId")): row
        for row in catalog.get("connectionTemplates") or []
    }
    base_definition = definitions.get(
        str((dag.get("baseInstance") or {}).get("moduleDefinitionId") or "")
    ) or {}
    base_sources = list(base_definition.get("cadSources") or [])
    manifest_blockers: list[dict[str, Any]] = []
    selection_rows = list(driving_strategy_selections or [])
    selection_by_template: dict[str, dict[str, Any]] = {}
    for selection in selection_rows:
        if not isinstance(selection, dict):
            manifest_blockers.append(
                {
                    "code": "DRIVING_STRATEGY_SELECTION_INVALID",
                    "detail": "策略选择必须是对象。",
                }
            )
            continue
        template_id = str(selection.get("globalTemplateId") or "").strip()
        if not template_id:
            manifest_blockers.append(
                {
                    "code": "DRIVING_STRATEGY_SELECTION_TEMPLATE_REQUIRED",
                    "detail": selection,
                }
            )
            continue
        if template_id in selection_by_template:
            manifest_blockers.append(
                {
                    "code": "DRIVING_STRATEGY_SELECTION_DUPLICATE",
                    "globalTemplateId": template_id,
                }
            )
            continue
        selection_by_template[template_id] = selection
    if not base_sources:
        manifest_blockers.append(
            {
                "code": "BASE_CAD_SOURCE_NOT_REGISTERED",
                "instanceId": (dag.get("baseInstance") or {}).get("instanceId"),
            }
        )

    packets: list[dict[str, Any]] = []
    previous_packet_id: str | None = None
    for dag_step in dag.get("steps") or []:
        packet_id = f"packet-{int(dag_step['order']):03d}"
        operation = str(dag_step.get("operation") or "INSERT_AND_CONNECT")
        relation_operation = operation in {"ADD_RELATION", "VERIFY_RELATION"}
        target_definition = definitions.get(
            str(dag_step.get("targetModuleDefinitionId") or "")
        ) or {}
        blockers = list(dag_step.get("blockers") or [])
        compiled_connections: list[dict[str, Any]] = []
        for connection in dag_step.get("connections") or []:
            compiled, connection_blockers = _compile_connection(
                connection,
                ports=ports,
                templates=templates,
            )
            compiled_connections.append(compiled)
            blockers.extend(connection_blockers)
        validation_preconditions: list[dict[str, Any]] = []
        if operation == "VERIFY_RELATION":
            for connection in compiled_connections:
                assessment = assess_relation_validation_precondition(
                    str(connection.get("globalTemplateId") or ""),
                    registry=validation_precondition_registry,
                    state_evidence=context.get("validationStateEvidence") or [],
                )
                validation_preconditions.append(assessment)
                blockers.extend(assessment.get("blockers") or [])
        driving_safety_assessments: list[dict[str, Any]] = []
        driving_execution_overrides: list[dict[str, Any]] = []
        if operation != "VERIFY_RELATION":
            for connection in compiled_connections:
                template_id = str(connection.get("globalTemplateId") or "")
                assessment = assess_relation_driving_safety(
                    template_id,
                    registry=driving_safety_registry,
                    explicit_selection=selection_by_template.get(template_id),
                )
                if assessment.get("declared"):
                    driving_safety_assessments.append(assessment)
                blockers.extend(assessment.get("blockers") or [])
                override = assessment.get("executionOverride")
                if override:
                    connection["effectiveMateGraphCandidate"] = override[
                        "effectiveMateGraphPath"
                    ]
                    connection["drivingExecutionOverride"] = override
                    driving_execution_overrides.append(override)
        if driving_execution_overrides and len(compiled_connections) != 1:
            blockers.append(
                {
                    "code": "CALIBRATED_FALLBACK_REQUIRES_SINGLE_CONNECTION_PACKET",
                    "detail": len(compiled_connections),
                }
            )
        if len(driving_execution_overrides) > 1:
            blockers.append(
                {
                    "code": "MULTIPLE_CALIBRATED_FALLBACKS_IN_ONE_PACKET_UNSUPPORTED",
                    "detail": [
                        row.get("strategyId") for row in driving_execution_overrides
                    ],
                }
            )
        relation_module_tokens: list[str] = []
        if relation_operation:
            relation_projects = {
                str((connection.get("templateEvidenceSource") or {}).get("projectId") or "")
                .strip()
                .lower()
                for connection in compiled_connections
            }
            relation_projects.discard("")
            for instance_id in sorted(
                {
                    str(connection.get(key) or "")
                    for connection in compiled_connections
                    for key in ("instanceAId", "instanceBId")
                    if str(connection.get(key) or "")
                }
            ):
                instance = instances.get(instance_id) or {}
                definition = definitions.get(
                    str(instance.get("moduleDefinitionId") or "")
                ) or {}
                aliases = list(definition.get("projectAliases") or [])
                if len(relation_projects) == 1:
                    project_id = next(iter(relation_projects))
                    aliases = [
                        alias
                        for alias in aliases
                        if str(alias.get("projectId") or "").strip().lower()
                        == project_id
                    ]
                tokens = sorted(
                    {
                        str(alias.get("moduleToken") or "").strip().upper()
                        for alias in aliases
                        if str(alias.get("moduleToken") or "").strip()
                    }
                )
                if len(tokens) != 1:
                    blockers.append(
                        {
                            "code": "RELATION_INSTANCE_MODULE_TOKEN_NOT_UNIQUE",
                            "instanceId": instance_id,
                            "detail": tokens,
                        }
                    )
                else:
                    relation_module_tokens.append(tokens[0])
            relation_module_tokens = sorted(set(relation_module_tokens))
            if len(relation_module_tokens) != 2:
                blockers.append(
                    {
                        "code": "RELATION_MODULE_PAIR_NOT_UNIQUE",
                        "detail": relation_module_tokens,
                    }
                )
        accepted_step_statuses = (
            {
                "compiled_requires_cad_verification",
                "ready_for_relation_verification",
            }
            if relation_operation
            else {"ready_for_generic_cad_transaction"}
        )
        if dag_step.get("status") not in accepted_step_statuses:
            blockers.append(
                {
                    "code": "DAG_STEP_NOT_EXECUTION_READY",
                    "detail": dag_step.get("status"),
                }
            )
        packet = {
            "schemaVersion": GLOBAL_CAD_TRANSACTION_PACKET_SCHEMA,
            "packetId": packet_id,
            "order": dag_step.get("order"),
            "operation": operation,
            "relationReleaseBinding": context.get("relationReleaseBinding"),
            "executionStrategy": (
                "direct_existing_component_mate_edit"
                if operation == "ADD_RELATION"
                else "read_only_existing_relation_verification"
                if operation == "VERIFY_RELATION"
                else driving_execution_overrides[0]["executionStrategy"]
                if len(driving_execution_overrides) == 1
                else "incremental_component_insert"
            ),
            "targetInstanceId": dag_step.get("targetInstanceId"),
            "targetModuleDefinitionId": dag_step.get("targetModuleDefinitionId"),
            "targetCadSources": dag_step.get("cadSources") or [],
            "targetProjectAliases": target_definition.get("projectAliases") or [],
            **(
                {"relationModuleTokens": relation_module_tokens}
                if relation_operation
                else {}
            ),
            "semanticDependsOn": dag_step.get("dependsOn") or [],
            "cumulativeInput": (
                {
                    "kind": "existing_assembly_checkpoint_required",
                    "contextId": context.get("contextId"),
                    "contextDigest": context.get("contextDigest"),
                    "reason": "existing-instance relation operations cannot run on a lone base source",
                }
                if previous_packet_id is None and relation_operation
                else {
                    "kind": "base_module_source",
                    "instanceId": (dag.get("baseInstance") or {}).get("instanceId"),
                    "cadSources": base_sources,
                }
                if previous_packet_id is None
                else {
                    "kind": "previous_transaction_checkpoint",
                    "packetId": previous_packet_id,
                }
            ),
            "connections": compiled_connections,
            **(
                {"validationPreconditions": validation_preconditions}
                if operation == "VERIFY_RELATION"
                else {}
            ),
            **(
                {"drivingSafetyAssessments": driving_safety_assessments}
                if driving_safety_assessments
                else {}
            ),
            **(
                {"drivingExecutionOverride": driving_execution_overrides[0]}
                if len(driving_execution_overrides) == 1
                else {}
            ),
            "constraintAssessment": dag_step.get("constraintAssessment"),
            "positioningStandardBinding": dag_step.get(
                "positioningStandardBinding"
            ),
            "verificationRequirements": (
                [
                    "relation_endpoints_resolved",
                    "requested_relation_created",
                    "authoritative_cad_overconstraint_state_accepted",
                    "save_close_reopen",
                    "mate_parameters_match",
                    "source_files_unchanged",
                    "output_checkpoint_closed",
                ]
                if operation == "ADD_RELATION"
                else [
                    "relation_endpoints_resolved",
                    "requested_relation_observed",
                    "relation_parameters_match",
                    "source_files_unchanged",
                    "save_close_reopen_without_mate_mutation",
                ]
                if operation == "VERIFY_RELATION"
                else [
                    "explicit_project_calibrated_fallback_bound",
                    "case_anchor_pose_match",
                    "internal_leaf_pose_anchors_match",
                    "authoritative_cad_constraint_state_accepted",
                    "save_close_reopen",
                    "source_files_unchanged",
                    "output_checkpoint_closed",
                ]
                if len(driving_execution_overrides) == 1
                else [
                    "all_requested_mates_created",
                    "authoritative_cad_constraint_state_accepted",
                    "save_close_reopen",
                    "mate_parameters_match",
                    "source_files_unchanged",
                    "output_checkpoint_closed",
                ]
            ),
            "collisionAssessment": {
                "status": "not_evaluated",
                "reason": "collision_and_brep_are_deferred_by_current_scope",
            },
            "status": "ready_for_executor_implementation" if not blockers else "blocked",
            "blockers": blockers,
        }
        packet["packetDigest"] = _digest(packet)
        packets.append(packet)
        manifest_blockers.extend(
            {"packetId": packet_id, **blocker} for blocker in blockers
        )
        previous_packet_id = packet_id

    used_template_ids = {
        str(connection.get("globalTemplateId") or "")
        for packet in packets
        for connection in packet.get("connections") or []
    }
    for template_id in sorted(set(selection_by_template) - used_template_ids):
        manifest_blockers.append(
            {
                "code": "DRIVING_STRATEGY_SELECTION_UNUSED",
                "globalTemplateId": template_id,
            }
        )

    manifest = {
        "schemaVersion": GLOBAL_CAD_TRANSACTION_MANIFEST_SCHEMA,
        "contextId": context.get("contextId"),
        "contextRevision": context.get("revision"),
        "contextDigest": context.get("contextDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "relationReleaseBinding": context.get("relationReleaseBinding"),
        "validationPreconditionRegistryBinding": (
            relation_validation_precondition_registry_binding(
                validation_precondition_registry,
                registry_path=validation_precondition_registry_path,
            )
            if validation_precondition_registry is not None
            else None
        ),
        "drivingSafetyRegistryBinding": (
            relation_driving_safety_registry_binding(
                driving_safety_registry,
                registry_path=driving_safety_registry_path,
            )
            if driving_safety_registry is not None
            else None
        ),
        "drivingStrategySelections": selection_rows,
        "drivingStrategySelectionDigest": _digest(selection_rows),
        "dagDigest": dag.get("dagDigest"),
        "planningMode": "project_independent_semantic_graph",
        "projectSequenceRequired": False,
        "positioningStandard": dag.get("positioningStandard"),
        "status": "ready_for_generic_executor_implementation"
        if packets and not manifest_blockers
        else "blocked",
        "baseInstance": dag.get("baseInstance"),
        "baseCadSources": base_sources,
        "packetCount": len(packets),
        "packets": packets,
        "blockers": manifest_blockers,
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionStatus": "not_evaluated",
            "statement": (
                "数据包已包含目标CAD、端口端点和配合语义；尚未调用累计SolidWorks执行器。"
            ),
        },
    }
    manifest["manifestDigest"] = _digest(manifest)
    return manifest
