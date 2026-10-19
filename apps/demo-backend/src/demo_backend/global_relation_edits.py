from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .global_assembly_context import context_digest, validate_global_assembly_context
from .global_module_catalog import validate_global_module_catalog
from .global_relation_semantics import (
    evaluate_connection_candidates_for_relation,
    parse_relation_intent,
)


GLOBAL_RELATION_EDIT_PREVIEW_SCHEMA = "global-relation-edit-preview/v1"


class GlobalRelationEditError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _next_connection_id(context: dict[str, Any]) -> str:
    existing = {str(row.get("connectionId") or "") for row in context.get("connections") or []}
    index = 1
    while f"connection-{index:03d}" in existing:
        index += 1
    return f"connection-{index:03d}"


def _relation_candidates(
    catalog: dict[str, Any],
    context: dict[str, Any],
    instance_a_id: str,
    instance_b_id: str,
) -> list[dict[str, Any]]:
    instances = {str(row.get("instanceId") or ""): row for row in context.get("instances") or []}
    instance_a = instances.get(instance_a_id)
    instance_b = instances.get(instance_b_id)
    if instance_a is None or instance_b is None:
        raise GlobalRelationEditError("instanceAId或instanceBId不存在。")
    if instance_a_id == instance_b_id:
        raise GlobalRelationEditError("关系两端必须是不同的模组实例。")
    ports = {
        str(row.get("globalPortId") or ""): row for row in catalog.get("semanticPorts") or []
    }
    definition_a = str(instance_a.get("moduleDefinitionId") or "")
    definition_b = str(instance_b.get("moduleDefinitionId") or "")
    rows: list[dict[str, Any]] = []
    for compatibility in catalog.get("compatibility") or []:
        port_a_id = str(compatibility.get("portAId") or "")
        port_b_id = str(compatibility.get("portBId") or "")
        port_a = ports.get(port_a_id) or {}
        port_b = ports.get(port_b_id) or {}
        port_a_definition = str(port_a.get("moduleDefinitionId") or "")
        port_b_definition = str(port_b.get("moduleDefinitionId") or "")
        if (port_a_definition, port_b_definition) == (definition_a, definition_b):
            actual_a_id, actual_b_id = instance_a_id, instance_b_id
        elif (port_a_definition, port_b_definition) == (definition_b, definition_a):
            actual_a_id, actual_b_id = instance_b_id, instance_a_id
        else:
            continue
        rows.append(
            {
                "newSide": "A",
                "newPortId": port_a_id,
                "existingPortId": port_b_id,
                "existingInstanceId": actual_b_id,
                "instanceAId": actual_a_id,
                "portAId": port_a_id,
                "instanceBId": actual_b_id,
                "portBId": port_b_id,
                "globalTemplateId": compatibility.get("globalTemplateId"),
                "purpose": compatibility.get("purpose"),
                "portable": bool(compatibility.get("portableForTemplate")),
            }
        )
    # Standalone geometric relations are undirected at the graph level.  Some
    # source catalogs materialize both A-B and B-A compatibility rows; expose
    # them as one deterministic candidate instead of a false user ambiguity.
    unique: dict[tuple[tuple[str, str], str], dict[str, Any]] = {}
    for row in rows:
        key = (
            tuple(sorted((str(row["portAId"]), str(row["portBId"])))),
            str(row["globalTemplateId"]),
        )
        unique.setdefault(key, row)
    return sorted(
        unique.values(),
        key=lambda row: (
            not row["portable"],
            str(row["globalTemplateId"]),
            str(row["portAId"]),
            str(row["portBId"]),
        ),
    )


def preview_global_relation_edit(
    catalog: dict[str, Any], context: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalRelationEditError("上下文与目录摘要不一致。")
    operation = str(payload.get("operation") or "add").strip().lower()
    if operation not in {"add", "verify", "replace", "delete"}:
        raise GlobalRelationEditError("operation只能为add、verify、replace或delete。")
    requirement = str(payload.get("requirement") or "").strip()
    connections = {
        str(row.get("connectionId") or ""): row for row in context.get("connections") or []
    }
    source_connection_id = str(payload.get("connectionId") or "").strip()
    blockers: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    relation_intent: dict[str, Any] | None = None
    proposed_patch: dict[str, Any] | None = None
    status = "blocked"

    if operation == "delete":
        if source_connection_id not in connections:
            blockers.append({"code": "CONNECTION_NOT_FOUND", "connectionId": source_connection_id})
        else:
            status = "ready"
            proposed_patch = {
                "operation": "delete_relation",
                "connectionId": source_connection_id,
                "before": deepcopy(connections[source_connection_id]),
            }
    else:
        if not requirement:
            raise GlobalRelationEditError("add或replace必须提供requirement。")
        relation_intent = parse_relation_intent(requirement)
        if relation_intent.get("status") == "blocked":
            blockers.extend(
                {"source": "relation_intent", **row}
                for row in relation_intent.get("blockers") or []
            )
        if operation == "replace":
            source_connection = connections.get(source_connection_id)
            if source_connection is None:
                blockers.append(
                    {"code": "CONNECTION_NOT_FOUND", "connectionId": source_connection_id}
                )
                instance_a_id = str(payload.get("instanceAId") or "").strip()
                instance_b_id = str(payload.get("instanceBId") or "").strip()
            else:
                instance_a_id = str(
                    payload.get("instanceAId") or source_connection.get("instanceAId") or ""
                )
                instance_b_id = str(
                    payload.get("instanceBId") or source_connection.get("instanceBId") or ""
                )
        else:
            source_connection = None
            instance_a_id = str(payload.get("instanceAId") or "").strip()
            instance_b_id = str(payload.get("instanceBId") or "").strip()
        if not instance_a_id or not instance_b_id:
            blockers.append({"code": "RELATION_ENDPOINT_INSTANCES_REQUIRED"})
        elif relation_intent.get("status") != "blocked" and not any(
            row["code"] == "CONNECTION_NOT_FOUND" for row in blockers
        ):
            raw_candidates = _relation_candidates(
                catalog, context, instance_a_id, instance_b_id
            )
            candidates, assessments = evaluate_connection_candidates_for_relation(
                catalog,
                raw_candidates,
                relation_intent,
                allow_validation_only=operation == "verify",
            )
            allowed_template_ids = payload.get("allowedTemplateIds")
            if allowed_template_ids is not None:
                allowed = {
                    str(value)
                    for value in allowed_template_ids
                    if str(value)
                }
                unauthorized = [
                    row
                    for row in candidates
                    if str(row.get("globalTemplateId") or "") not in allowed
                ]
                candidates = [
                    row
                    for row in candidates
                    if str(row.get("globalTemplateId") or "") in allowed
                ]
                if unauthorized and not candidates:
                    blockers.append(
                        {
                            "code": "RELATION_TEMPLATE_NOT_AUTHORIZED_BY_RELEASE",
                            "templateIds": sorted(
                                {
                                    str(row.get("globalTemplateId") or "")
                                    for row in unauthorized
                                }
                            ),
                        }
                    )
            selected_port_a = str(payload.get("portAId") or "").strip()
            selected_port_b = str(payload.get("portBId") or "").strip()
            selected_template = str(payload.get("globalTemplateId") or "").strip()
            if any((selected_port_a, selected_port_b, selected_template)):
                candidates = [
                    row
                    for row in candidates
                    if (not selected_port_a or row["portAId"] == selected_port_a)
                    and (not selected_port_b or row["portBId"] == selected_port_b)
                    and (
                        not selected_template
                        or row["globalTemplateId"] == selected_template
                    )
                ]
            if len(candidates) == 1:
                selected = candidates[0]
                if not selected["portable"]:
                    status = "needs_confirmation"
                    blockers.append({"code": "PORT_EVIDENCE_NOT_PORTABLE"})
                else:
                    status = "ready"
                connection_id = (
                    source_connection_id
                    if operation == "replace"
                    else _next_connection_id(context)
                )
                connection = {
                    "connectionId": connection_id,
                    "instanceAId": selected["instanceAId"],
                    "portAId": selected["portAId"],
                    "instanceBId": selected["instanceBId"],
                    "portBId": selected["portBId"],
                    "globalTemplateId": selected["globalTemplateId"],
                    "purpose": selected.get("purpose") or relation_intent.get("primaryRelation"),
                    "relationIntent": relation_intent,
                    "relationProfile": (
                        selected.get("relationAssessment") or {}
                    ).get("templateProfile"),
                    "executionStatus": (
                        "planned_relation_verification_not_executed_in_cad"
                        if operation == "verify"
                        else "planned_relation_edit_not_executed_in_cad"
                    ),
                }
                duplicate = next(
                    (
                        row
                        for row in context.get("connections") or []
                        if row.get("connectionId") != source_connection_id
                        and row.get("instanceAId") == connection["instanceAId"]
                        and row.get("instanceBId") == connection["instanceBId"]
                        and row.get("portAId") == connection["portAId"]
                        and row.get("portBId") == connection["portBId"]
                        and row.get("globalTemplateId") == connection["globalTemplateId"]
                    ),
                    None,
                )
                if duplicate is not None:
                    status = "blocked"
                    blockers.append(
                        {
                            "code": "RELATION_ALREADY_EXISTS",
                            "connectionId": duplicate.get("connectionId"),
                        }
                    )
                proposed_patch = {
                    "operation": f"{operation}_relation",
                    "connectionId": connection_id,
                    "before": deepcopy(source_connection),
                    "after": connection,
                }
            elif candidates:
                status = "needs_confirmation"
                blockers.append({"code": "RELATION_CONNECTION_SELECTION_REQUIRED"})
            else:
                blockers.append(
                    {
                        "code": "REQUESTED_RELATION_TEMPLATE_NOT_AVAILABLE",
                        "candidateTemplateAssessments": assessments,
                    }
                )

    preview = {
        "schemaVersion": GLOBAL_RELATION_EDIT_PREVIEW_SCHEMA,
        "status": status,
        "operation": operation,
        "requirement": requirement,
        "catalogDigest": catalog["catalogDigest"],
        "relationReleaseBinding": deepcopy(context.get("relationReleaseBinding")),
        "sourceContextDigest": context["contextDigest"],
        "relationIntent": relation_intent,
        "connectionCandidates": candidates,
        "relationCandidateAssessments": assessments,
        "proposedPatch": proposed_patch,
        "blockers": blockers,
        "cadExecution": {
            "status": "not_executed",
            "statement": "本预览只编辑配合语义图，不修改SolidWorks。",
        },
    }
    preview["previewDigest"] = _digest(preview)
    return preview


def apply_global_relation_edit(
    context: dict[str, Any],
    preview: dict[str, Any],
    *,
    preview_digest: str,
    confirmed: bool,
) -> dict[str, Any]:
    validate_global_assembly_context(context)
    if not confirmed:
        raise GlobalRelationEditError("必须显式confirmed=true才能提交关系编辑。")
    if str(preview.get("previewDigest") or "") != str(preview_digest or ""):
        raise GlobalRelationEditError("previewDigest与预览不一致。")
    if _digest({key: value for key, value in preview.items() if key != "previewDigest"}) != str(
        preview_digest or ""
    ):
        raise GlobalRelationEditError("关系编辑预览内容已被修改。")
    if preview.get("sourceContextDigest") != context.get("contextDigest"):
        raise GlobalRelationEditError("上下文在预览后已变化，请重新预览。")
    if preview.get("relationReleaseBinding") != context.get("relationReleaseBinding"):
        raise GlobalRelationEditError("关系编辑预览与上下文的发布绑定不一致。")
    if preview.get("status") != "ready" or not isinstance(preview.get("proposedPatch"), dict):
        raise GlobalRelationEditError("只有status=ready的关系编辑预览可以提交。")

    result = deepcopy(context)
    patch = preview["proposedPatch"]
    operation = patch.get("operation")
    connection_id = str(patch.get("connectionId") or "")
    if operation in {"add_relation", "verify_relation"}:
        result["connections"].append(deepcopy(patch["after"]))
    elif operation == "replace_relation":
        indexes = [
            index
            for index, row in enumerate(result["connections"])
            if row.get("connectionId") == connection_id
        ]
        if len(indexes) != 1:
            raise GlobalRelationEditError("待替换关系在提交时已不存在或不唯一。")
        result["connections"][indexes[0]] = deepcopy(patch["after"])
    elif operation == "delete_relation":
        before = len(result["connections"])
        result["connections"] = [
            row for row in result["connections"] if row.get("connectionId") != connection_id
        ]
        if len(result["connections"]) != before - 1:
            raise GlobalRelationEditError("待删除关系在提交时已不存在或不唯一。")
    else:
        raise GlobalRelationEditError("未知关系编辑操作。")

    result["revision"] = int(result.get("revision") or 0) + 1
    result["updatedAt"] = _now()
    result.setdefault("history", []).append(
        {
            "revision": result["revision"],
            "sourceContextDigest": context.get("contextDigest"),
            "operation": operation,
            "connectionId": connection_id,
            "requirement": preview.get("requirement"),
            "previewDigest": preview_digest,
            "timestamp": result["updatedAt"],
        }
    )
    result["contextDigest"] = context_digest(result)
    validate_global_assembly_context(result)
    return result
