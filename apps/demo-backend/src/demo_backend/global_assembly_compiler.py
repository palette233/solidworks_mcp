"""Compile an approved assembly graph into auditable CAD transaction packets.

This layer is intentionally side-effect free.  It validates catalog/release
bindings, identifies the newly inserted instance for each connection, and
projects released semantic relations into project-adapter requests.  SolidWorks
is only mutated by the downstream packet executor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .global_assembly_context import validate_global_assembly_context
from .global_module_catalog import validate_global_module_catalog
from .assembly_user_failure import build_assembly_user_failure
from .relation_execution_policy import (
    RelationExecutionPolicyError,
    assess_template_execution_policy,
)


GLOBAL_EXECUTION_MANIFEST_SCHEMA = "global-assembly-execution-manifest/v1"


class GlobalAssemblyCompilerError(ValueError):
    pass


def _source_provenance(port: dict[str, Any], semantic_catalog_path: str) -> dict[str, Any] | None:
    for row in port.get("provenance") or []:
        if str(row.get("semanticCatalogPath") or "") == semantic_catalog_path:
            return row
    return None


def compile_global_assembly_execution_manifest(
    workspace: Path,
    catalog: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Compile the global graph into project-adapter packets without running CAD."""

    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyCompilerError("上下文与全局目录摘要不一致。")
    release_binding = context.get("relationReleaseBinding")
    authorized_template_ids = set(
        (release_binding or {}).get("authorizedDrivingTemplateIds") or []
    )
    workspace = workspace.resolve()
    ports = {str(item["globalPortId"]): item for item in catalog.get("semanticPorts") or []}
    templates = {
        str(item["globalTemplateId"]): item for item in catalog.get("connectionTemplates") or []
    }
    instances = {
        str(item["instanceId"]): item for item in context.get("instances") or []
    }
    compatibility = {
        (
            str(item.get("portAId") or ""),
            str(item.get("portBId") or ""),
            str(item.get("globalTemplateId") or ""),
        ): item
        for item in catalog.get("compatibility") or []
    }
    known_instances: set[str] = set()
    if context.get("instances"):
        known_instances.add(str(context["instances"][0]["instanceId"]))
    steps: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for order, connection in enumerate(context.get("connections") or [], start=1):
        connection_id = str(connection.get("connectionId") or f"connection-{order:03d}")
        instance_a_id = str(connection.get("instanceAId") or "")
        instance_b_id = str(connection.get("instanceBId") or "")
        new_ids = [item for item in (instance_a_id, instance_b_id) if item not in known_instances]
        target_instance_id = new_ids[0] if len(new_ids) == 1 else None
        template_id = str(connection.get("globalTemplateId") or "")
        port_a_id = str(connection.get("portAId") or "")
        port_b_id = str(connection.get("portBId") or "")
        template = templates.get(template_id)
        port_a = ports.get(port_a_id)
        port_b = ports.get(port_b_id)
        step_blockers: list[dict[str, Any]] = []
        if template is None:
            step_blockers.append({"code": "TEMPLATE_NOT_FOUND", "detail": template_id})
        else:
            try:
                execution_policy = assess_template_execution_policy(
                    template,
                    requested_mode=connection.get("relationExecutionMode"),
                )
            except RelationExecutionPolicyError as exc:
                execution_policy = {
                    "allowed": False,
                    "code": "RELATION_EXECUTION_MODE_INVALID",
                    "detail": str(exc),
                }
            if execution_policy.get("allowed") is not True:
                step_blockers.append(
                    {
                        "code": execution_policy.get("code")
                        or "RELATION_EXECUTION_MODE_MISMATCH",
                        "detail": execution_policy.get("detail"),
                    }
                )
        if release_binding is not None and template_id not in authorized_template_ids:
            step_blockers.append(
                {
                    "code": "TEMPLATE_NOT_AUTHORIZED_BY_BOUND_RELEASE",
                    "detail": template_id,
                }
            )
        if port_a is None or port_b is None:
            step_blockers.append(
                {"code": "PORT_NOT_FOUND", "detail": f"{port_a_id} / {port_b_id}"}
            )
        if target_instance_id is None:
            step_blockers.append(
                {
                    "code": "INCREMENTAL_TARGET_NOT_UNIQUE",
                    "detail": "连接不能唯一识别本步新增的模组实例。",
                }
            )
        semantic_path = str((template or {}).get("provenance", {}).get("semanticCatalogPath") or "")
        provenance_a = _source_provenance(port_a or {}, semantic_path)
        provenance_b = _source_provenance(port_b or {}, semantic_path)
        if not semantic_path or provenance_a is None or provenance_b is None:
            step_blockers.append(
                {
                    "code": "LEGACY_PORT_PROVENANCE_INCOMPLETE",
                    "detail": "无法在同一来源语义目录中恢复两个旧端口编号。",
                }
            )
        compatibility_row = compatibility.get((port_a_id, port_b_id, template_id))
        if compatibility_row is None:
            step_blockers.append(
                {"code": "COMPATIBILITY_NOT_FOUND", "detail": "全局连接不在兼容矩阵中。"}
            )
        elif compatibility_row.get("portableForTemplate") is not True:
            step_blockers.append(
                {
                    "code": "TEMPLATE_ENDPOINTS_NOT_PORTABLE",
                    "detail": "模板使用的端点角色缺少完整模组局部恢复证据。",
                }
            )
        semantic_file = (workspace / semantic_path).resolve() if semantic_path else None
        endpoint_path = str((template or {}).get("provenance", {}).get("endpointCatalogPath") or "")
        source_graph_candidates: list[str] = []
        if semantic_file is not None and semantic_file.is_file():
            source_graph_candidates = [
                str(path.resolve())
                for path in sorted(semantic_file.parent.glob("base*_graph.json"))
            ]
        else:
            step_blockers.append(
                {"code": "SOURCE_SEMANTIC_CATALOG_MISSING", "detail": semantic_path}
            )
        if not source_graph_candidates:
            step_blockers.append(
                {
                    "code": "SOURCE_GRAPH_ADAPTER_REQUIRED",
                    "detail": "没有找到项目适配器可复用的base*_graph.json。",
                }
            )
        target_instance = instances.get(target_instance_id or "") or {}
        step = {
            "order": order,
            "connectionId": connection_id,
            "status": "ready_for_project_adapter" if not step_blockers else "blocked",
            "targetInstanceId": target_instance_id,
            "targetModuleDefinitionId": target_instance.get("moduleDefinitionId"),
            "semanticCatalogPath": str(semantic_file) if semantic_file else None,
            "endpointCatalogPath": str((workspace / endpoint_path).resolve()) if endpoint_path else None,
            "sourceGraphCandidates": source_graph_candidates,
            "semanticConnectionRequest": {
                "schemaVersion": "semantic-connection-request/v1",
                "connectionId": connection_id,
                "intent": connection.get("purpose") or "installation",
                "portAId": (provenance_a or {}).get("legacyPortId"),
                "portBId": (provenance_b or {}).get("legacyPortId"),
                "templateId": (template or {}).get("legacyTemplateId"),
                "relationExecutionMode": connection.get(
                    "relationExecutionMode"
                )
                or "direct_installation",
            },
            "blockers": step_blockers,
        }
        steps.append(step)
        blockers.extend({"connectionId": connection_id, **item} for item in step_blockers)
        known_instances.update(item for item in (instance_a_id, instance_b_id) if item)

    status = "ready_for_project_adapter" if steps and not blockers else "blocked"
    return {
        "schemaVersion": GLOBAL_EXECUTION_MANIFEST_SCHEMA,
        "contextId": context["contextId"],
        "contextDigest": context["contextDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "relationReleaseBinding": release_binding,
        "status": status,
        "baseInstance": context.get("instances", [None])[0] if context.get("instances") else None,
        "stepCount": len(steps),
        "steps": steps,
        "blockers": blockers,
        "userFailureExplanation": (
            build_assembly_user_failure(
                blockers=blockers,
                status=status,
                stage="manifest_compilation",
            )
            if blockers
            else None
        ),
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
            "nextAdapter": "existing semantic-port compiler and context-incremental CAD runner",
            "statement": "清单只完成全局图到项目语义请求的编译；执行前仍需选择累计源装配体。",
        },
    }
