from __future__ import annotations

from typing import Any

from .global_assembly_context import validate_global_assembly_context
from .global_module_catalog import validate_global_module_catalog


class GlobalCommandAuditError(ValueError):
    pass


def build_global_command_audit(
    catalog: dict[str, Any],
    context: dict[str, Any],
    transaction_dag: dict[str, Any],
    cad_manifest: dict[str, Any],
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    if any(
        value != context.get(key)
        for key, value in (
            ("contextId", transaction_dag.get("contextId")),
            ("contextDigest", transaction_dag.get("contextDigest")),
            ("catalogDigest", transaction_dag.get("catalogDigest")),
        )
    ):
        raise GlobalCommandAuditError("事务DAG与装配上下文绑定不一致。")
    if (
        cad_manifest.get("contextId") != context.get("contextId")
        or cad_manifest.get("contextDigest") != context.get("contextDigest")
        or cad_manifest.get("catalogDigest") != context.get("catalogDigest")
    ):
        raise GlobalCommandAuditError("CAD事务清单与装配上下文绑定不一致。")

    instances = {
        str(row.get("instanceId") or ""): row for row in context.get("instances") or []
    }
    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    ports = {
        str(row.get("globalPortId") or ""): row
        for row in catalog.get("semanticPorts") or []
    }
    connections = {
        str(row.get("connectionId") or ""): row
        for row in context.get("connections") or []
    }
    step_by_connection: dict[str, dict[str, Any]] = {}
    for step in transaction_dag.get("steps") or []:
        for connection in step.get("connections") or []:
            step_by_connection[str(connection.get("connectionId") or "")] = step
    packet_by_connection: dict[str, dict[str, Any]] = {}
    for packet in cad_manifest.get("packets") or []:
        for connection in packet.get("connections") or []:
            packet_by_connection[str(connection.get("connectionId") or "")] = packet

    requirement_connections: dict[str, list[str]] = {}
    for connection_id, connection in connections.items():
        requirement = str(
            (connection.get("relationIntent") or {}).get("requirement") or ""
        )
        if requirement:
            requirement_connections.setdefault(requirement, []).append(connection_id)

    base_instance = next(
        (
            row
            for row in context.get("instances") or []
            if row.get("placementStatus") == "base_context_unlocated"
        ),
        None,
    )
    rows: list[dict[str, Any]] = []
    for history in context.get("history") or []:
        requirement = str(history.get("requirement") or "")
        operation = str(history.get("operation") or "")
        connection_ids = []
        if history.get("connectionId"):
            connection_ids = [str(history["connectionId"])]
        elif operation != "add_base_instance":
            connection_ids = requirement_connections.get(requirement, [])
        if operation == "add_base_instance":
            definition = definitions.get(
                str((base_instance or {}).get("moduleDefinitionId") or "")
            ) or {}
            rows.append(
                {
                    "revision": history.get("revision"),
                    "requirement": requirement,
                    "operation": operation,
                    "moduleInstances": [base_instance] if base_instance else [],
                    "moduleCategories": [definition.get("category")]
                    if definition
                    else [],
                    "connections": [],
                    "transactionStepIds": [],
                    "cadPacketIds": [],
                    "selectedTemplateCombinationIds": [],
                    "combinedExpectedResidualDof": None,
                    "status": "base_context_declared",
                }
            )
            continue

        connection_audits = []
        step_ids: set[str] = set()
        packet_ids: set[str] = set()
        combination_ids: set[str] = set()
        combined_dofs: set[int] = set()
        module_instance_ids: set[str] = set()
        for connection_id in connection_ids:
            connection = connections.get(connection_id) or {}
            step = step_by_connection.get(connection_id) or {}
            packet = packet_by_connection.get(connection_id) or {}
            constraint = step.get("constraintAssessment") or {}
            combination = constraint.get("declaredTemplateCombination") or {}
            combination_id = str(combination.get("globalCombinationId") or "")
            if combination_id:
                combination_ids.add(combination_id)
            combined_dof = constraint.get("expectedResidualDof")
            if isinstance(combined_dof, int):
                combined_dofs.add(combined_dof)
            if step.get("stepId"):
                step_ids.add(str(step["stepId"]))
            if packet.get("packetId"):
                packet_ids.add(str(packet["packetId"]))
            endpoint_instances = [
                str(connection.get("instanceAId") or ""),
                str(connection.get("instanceBId") or ""),
            ]
            module_instance_ids.update(value for value in endpoint_instances if value)
            connection_audits.append(
                {
                    "connectionId": connection_id,
                    "globalTemplateId": connection.get("globalTemplateId"),
                    "purpose": connection.get("purpose"),
                    "instanceAId": endpoint_instances[0],
                    "instanceBId": endpoint_instances[1],
                    "portA": _port_audit(ports.get(str(connection.get("portAId") or ""))),
                    "portB": _port_audit(ports.get(str(connection.get("portBId") or ""))),
                    "singleTemplateExpectedResidualDof": (
                        ((connection.get("relationProfile") or {}).get(
                            "constraintExplanation"
                        ) or {}).get("expectedResidualDof")
                    ),
                    "transactionStepId": step.get("stepId"),
                    "cadPacketId": packet.get("packetId"),
                    "selectedTemplateCombinationId": combination_id or None,
                }
            )
        module_rows = [instances[value] for value in sorted(module_instance_ids) if value in instances]
        rows.append(
            {
                "revision": history.get("revision"),
                "requirement": requirement,
                "operation": operation,
                "moduleInstances": module_rows,
                "moduleCategories": sorted(
                    {
                        str(
                            definitions.get(
                                str(row.get("moduleDefinitionId") or ""), {}
                            ).get("category")
                            or ""
                        )
                        for row in module_rows
                        if definitions.get(str(row.get("moduleDefinitionId") or ""))
                    }
                ),
                "connections": connection_audits,
                "transactionStepIds": sorted(step_ids),
                "cadPacketIds": sorted(packet_ids),
                "selectedTemplateCombinationIds": sorted(combination_ids),
                "combinedExpectedResidualDof": (
                    next(iter(combined_dofs)) if len(combined_dofs) == 1 else None
                ),
                "status": "mapped" if connection_audits else "unmapped",
            }
        )

    return {
        "schemaVersion": "global-command-audit/v1",
        "contextId": context.get("contextId"),
        "contextDigest": context.get("contextDigest"),
        "catalogDigest": context.get("catalogDigest"),
        "releaseBinding": context.get("relationReleaseBinding"),
        "commandCount": len(rows),
        "mappedCommandCount": sum(
            row["status"] in {"mapped", "base_context_declared"} for row in rows
        ),
        "commands": rows,
        "collisionStatus": "not_evaluated",
    }


def _port_audit(port: dict[str, Any] | None) -> dict[str, Any] | None:
    if not port:
        return None
    return {
        "globalPortId": port.get("globalPortId"),
        "displayName": port.get("displayName"),
        "interfaceType": port.get("interfaceType"),
        "aliases": port.get("aliases") or [],
        "endpointRoles": sorted(
            str(row.get("role") or "")
            for row in port.get("endpointEvidence") or []
            if str(row.get("role") or "")
        ),
    }
