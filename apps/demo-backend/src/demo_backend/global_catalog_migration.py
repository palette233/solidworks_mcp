from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .global_assembly_context import (
    context_digest,
    validate_global_assembly_context,
)
from .global_module_catalog import validate_global_module_catalog


GLOBAL_CATALOG_MIGRATION_PLAN_SCHEMA = "global-catalog-migration-plan/v1"
GLOBAL_CONTEXT_CATALOG_BINDING_SCHEMA = "global-context-catalog-binding/v1"


class GlobalCatalogMigrationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or ""): row for row in rows if str(row.get(key) or "")}


def _compatibility_key(row: dict[str, Any]) -> tuple[str, str, str]:
    first, second = sorted((str(row.get("portAId") or ""), str(row.get("portBId") or "")))
    return first, second, str(row.get("globalTemplateId") or "")


def _catalog_diff(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    specs = (
        ("moduleDefinitions", "moduleDefinitionId"),
        ("semanticPorts", "globalPortId"),
        ("connectionTemplates", "globalTemplateId"),
    )
    result: dict[str, Any] = {}
    for collection, identity in specs:
        source_rows = _index(source.get(collection) or [], identity)
        candidate_rows = _index(candidate.get(collection) or [], identity)
        common = sorted(set(source_rows) & set(candidate_rows))
        result[collection] = {
            "addedIds": sorted(set(candidate_rows) - set(source_rows)),
            "removedIds": sorted(set(source_rows) - set(candidate_rows)),
            "changedIds": [
                item
                for item in common
                if _digest(source_rows[item]) != _digest(candidate_rows[item])
            ],
            "unchangedCount": sum(
                1
                for item in common
                if _digest(source_rows[item]) == _digest(candidate_rows[item])
            ),
        }

    source_compatibility = {
        _compatibility_key(row): row for row in source.get("compatibility") or []
    }
    candidate_compatibility = {
        _compatibility_key(row): row for row in candidate.get("compatibility") or []
    }
    common_compatibility = sorted(set(source_compatibility) & set(candidate_compatibility))
    result["compatibility"] = {
        "addedCount": len(set(candidate_compatibility) - set(source_compatibility)),
        "removedCount": len(set(source_compatibility) - set(candidate_compatibility)),
        "changedCount": sum(
            1
            for item in common_compatibility
            if _digest(source_compatibility[item]) != _digest(candidate_compatibility[item])
        ),
        "portableUpgrades": sum(
            1
            for item in common_compatibility
            if not bool(source_compatibility[item].get("portableForTemplate"))
            and bool(candidate_compatibility[item].get("portableForTemplate"))
        ),
        "portableDowngrades": sum(
            1
            for item in common_compatibility
            if bool(source_compatibility[item].get("portableForTemplate"))
            and not bool(candidate_compatibility[item].get("portableForTemplate"))
        ),
    }
    return result


def assess_context_catalog_migration(
    source_catalog: dict[str, Any],
    candidate_catalog: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Check whether a context can be rebound without changing its graph semantics."""

    validate_global_module_catalog(source_catalog)
    validate_global_module_catalog(candidate_catalog)
    validate_global_assembly_context(context)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    source_digest = str(source_catalog["catalogDigest"])
    candidate_digest = str(candidate_catalog["catalogDigest"])
    if context.get("catalogDigest") != source_digest:
        blockers.append(
            {
                "code": "SOURCE_CONTEXT_CATALOG_DIGEST_MISMATCH",
                "contextCatalogDigest": context.get("catalogDigest"),
                "sourceCatalogDigest": source_digest,
            }
        )
    if source_digest == candidate_digest:
        blockers.append({"code": "SOURCE_AND_CANDIDATE_CATALOG_ARE_IDENTICAL"})

    source_definitions = _index(source_catalog.get("moduleDefinitions") or [], "moduleDefinitionId")
    candidate_definitions = _index(
        candidate_catalog.get("moduleDefinitions") or [], "moduleDefinitionId"
    )
    source_ports = _index(source_catalog.get("semanticPorts") or [], "globalPortId")
    candidate_ports = _index(candidate_catalog.get("semanticPorts") or [], "globalPortId")
    source_templates = _index(
        source_catalog.get("connectionTemplates") or [], "globalTemplateId"
    )
    candidate_templates = _index(
        candidate_catalog.get("connectionTemplates") or [], "globalTemplateId"
    )
    source_compatibility = {
        _compatibility_key(row): row for row in source_catalog.get("compatibility") or []
    }
    candidate_compatibility = {
        _compatibility_key(row): row for row in candidate_catalog.get("compatibility") or []
    }

    used_definition_ids = sorted(
        {str(row.get("moduleDefinitionId") or "") for row in context.get("instances") or []}
    )
    used_port_ids: set[str] = set()
    used_template_ids: set[str] = set()
    for definition_id in used_definition_ids:
        source_row = source_definitions.get(definition_id)
        candidate_row = candidate_definitions.get(definition_id)
        if source_row is None:
            blockers.append(
                {"code": "SOURCE_MODULE_DEFINITION_MISSING", "moduleDefinitionId": definition_id}
            )
            continue
        if candidate_row is None:
            blockers.append(
                {"code": "CANDIDATE_MODULE_DEFINITION_MISSING", "moduleDefinitionId": definition_id}
            )
            continue
        identity_fields = ("category", "componentNames")
        changed = [field for field in identity_fields if source_row.get(field) != candidate_row.get(field)]
        if changed:
            blockers.append(
                {
                    "code": "MODULE_IDENTITY_PAYLOAD_CHANGED",
                    "moduleDefinitionId": definition_id,
                    "changedFields": changed,
                }
            )

    for connection in context.get("connections") or []:
        connection_id = str(connection.get("connectionId") or "")
        port_a = str(connection.get("portAId") or "")
        port_b = str(connection.get("portBId") or "")
        template_id = str(connection.get("globalTemplateId") or "")
        used_port_ids.update((port_a, port_b))
        used_template_ids.add(template_id)
        for port_id in (port_a, port_b):
            source_port = source_ports.get(port_id)
            candidate_port = candidate_ports.get(port_id)
            if source_port is None:
                blockers.append(
                    {
                        "code": "SOURCE_PORT_MISSING",
                        "connectionId": connection_id,
                        "globalPortId": port_id,
                    }
                )
                continue
            if candidate_port is None:
                blockers.append(
                    {
                        "code": "CANDIDATE_PORT_MISSING",
                        "connectionId": connection_id,
                        "globalPortId": port_id,
                    }
                )
                continue
            semantic_fields = ("moduleDefinitionId", "category", "interfaceClass", "geometryClass")
            changed = [
                field for field in semantic_fields if source_port.get(field) != candidate_port.get(field)
            ]
            if changed:
                blockers.append(
                    {
                        "code": "PORT_SEMANTIC_IDENTITY_CHANGED",
                        "connectionId": connection_id,
                        "globalPortId": port_id,
                        "changedFields": changed,
                    }
                )

        source_template = source_templates.get(template_id)
        candidate_template = candidate_templates.get(template_id)
        if source_template is None:
            blockers.append(
                {
                    "code": "SOURCE_CONNECTION_TEMPLATE_MISSING",
                    "connectionId": connection_id,
                    "globalTemplateId": template_id,
                }
            )
        elif candidate_template is None:
            blockers.append(
                {
                    "code": "CANDIDATE_CONNECTION_TEMPLATE_MISSING",
                    "connectionId": connection_id,
                    "globalTemplateId": template_id,
                }
            )
        else:
            semantic_fields = ("legacyTemplateId", "purpose", "mateSteps", "constraintEffect")
            changed = [
                field
                for field in semantic_fields
                if source_template.get(field) != candidate_template.get(field)
            ]
            if changed:
                blockers.append(
                    {
                        "code": "CONNECTION_TEMPLATE_SEMANTICS_CHANGED",
                        "connectionId": connection_id,
                        "globalTemplateId": template_id,
                        "changedFields": changed,
                    }
                )

        compatibility_key = _compatibility_key(
            {"portAId": port_a, "portBId": port_b, "globalTemplateId": template_id}
        )
        source_compat = source_compatibility.get(compatibility_key)
        candidate_compat = candidate_compatibility.get(compatibility_key)
        if source_compat is None:
            blockers.append(
                {"code": "SOURCE_COMPATIBILITY_MISSING", "connectionId": connection_id}
            )
        elif candidate_compat is None:
            blockers.append(
                {"code": "CANDIDATE_COMPATIBILITY_MISSING", "connectionId": connection_id}
            )
        elif bool(source_compat.get("portableForTemplate")) and not bool(
            candidate_compat.get("portableForTemplate")
        ):
            blockers.append(
                {"code": "USED_CONNECTION_PORTABILITY_DOWNGRADED", "connectionId": connection_id}
            )
        elif not bool(source_compat.get("portableForTemplate")) and bool(
            candidate_compat.get("portableForTemplate")
        ):
            warnings.append(
                {"code": "USED_CONNECTION_PORTABILITY_UPGRADED", "connectionId": connection_id}
            )

    status = "ready" if not blockers else "blocked"
    assessment_core = {
        "sourceCatalogDigest": source_digest,
        "candidateCatalogDigest": candidate_digest,
        "contextId": context.get("contextId"),
        "sourceContextDigest": context.get("contextDigest"),
        "status": status,
        "usedModuleDefinitionIds": used_definition_ids,
        "usedPortIds": sorted(used_port_ids),
        "usedTemplateIds": sorted(used_template_ids),
        "blockers": blockers,
        "warnings": warnings,
    }
    assessment = dict(assessment_core)
    assessment["assessmentDigest"] = _digest(assessment_core)
    return assessment


def build_catalog_migration_plan(
    source_catalog: dict[str, Any],
    candidate_catalog: dict[str, Any],
    contexts: list[dict[str, Any]],
    *,
    source_catalog_path: str | None = None,
    candidate_catalog_path: str | None = None,
) -> dict[str, Any]:
    validate_global_module_catalog(source_catalog)
    validate_global_module_catalog(candidate_catalog)
    assessments = [
        assess_context_catalog_migration(source_catalog, candidate_catalog, context)
        for context in contexts
    ]
    plan_core = {
        "schemaVersion": GLOBAL_CATALOG_MIGRATION_PLAN_SCHEMA,
        "sourceCatalogPath": source_catalog_path,
        "candidateCatalogPath": candidate_catalog_path,
        "sourceCatalogDigest": source_catalog["catalogDigest"],
        "candidateCatalogDigest": candidate_catalog["catalogDigest"],
        "catalogDiff": _catalog_diff(source_catalog, candidate_catalog),
        "contextAssessments": assessments,
        "summary": {
            "contextCount": len(assessments),
            "readyContextCount": sum(1 for row in assessments if row["status"] == "ready"),
            "blockedContextCount": sum(
                1 for row in assessments if row["status"] == "blocked"
            ),
        },
    }
    plan = {**plan_core, "generatedAt": _now()}
    plan["planDigest"] = _digest(plan_core)
    return plan


def migrate_context_catalog_binding(
    source_catalog: dict[str, Any],
    candidate_catalog: dict[str, Any],
    context: dict[str, Any],
    *,
    target_context_id: str,
    expected_assessment_digest: str,
    confirmed: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not confirmed:
        raise GlobalCatalogMigrationError("必须显式confirmed=true才能迁移目录绑定。")
    assessment = assess_context_catalog_migration(source_catalog, candidate_catalog, context)
    if assessment["assessmentDigest"] != str(expected_assessment_digest or ""):
        raise GlobalCatalogMigrationError("迁移评估摘要已过期，请重新预览。")
    if assessment["status"] != "ready":
        raise GlobalCatalogMigrationError("当前上下文不满足无损目录迁移条件。")
    normalized_target = str(target_context_id or "").strip()
    if not normalized_target or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", normalized_target
    ):
        raise GlobalCatalogMigrationError(
            "targetContextId只能包含字母、数字、点、下划线和连字符。"
        )
    if normalized_target == context.get("contextId"):
        raise GlobalCatalogMigrationError("必须提供不同于源上下文的新targetContextId。")

    migrated = deepcopy(context)
    source_context_id = str(context["contextId"])
    source_context_digest = str(context["contextDigest"])
    migrated["contextId"] = normalized_target
    migrated["displayName"] = f"{context.get('displayName') or source_context_id}（目录迁移）"
    migrated["catalogDigest"] = candidate_catalog["catalogDigest"]
    migrated["revision"] = int(context.get("revision") or 0) + 1
    migrated["updatedAt"] = _now()
    migrated.setdefault("history", []).append(
        {
            "revision": migrated["revision"],
            "operation": "catalog_binding_migration",
            "sourceContextId": source_context_id,
            "sourceContextDigest": source_context_digest,
            "sourceCatalogDigest": source_catalog["catalogDigest"],
            "candidateCatalogDigest": candidate_catalog["catalogDigest"],
            "assessmentDigest": assessment["assessmentDigest"],
            "timestamp": migrated["updatedAt"],
        }
    )
    migrated["contextDigest"] = context_digest(migrated)
    validate_global_assembly_context(migrated)

    binding_core = {
        "schemaVersion": GLOBAL_CONTEXT_CATALOG_BINDING_SCHEMA,
        "sourceContextId": source_context_id,
        "targetContextId": normalized_target,
        "sourceContextDigest": source_context_digest,
        "targetContextDigest": migrated["contextDigest"],
        "sourceCatalogDigest": source_catalog["catalogDigest"],
        "candidateCatalogDigest": candidate_catalog["catalogDigest"],
        "assessmentDigest": assessment["assessmentDigest"],
        "sourcePreserved": True,
    }
    binding = {**binding_core, "createdAt": migrated["updatedAt"]}
    binding["bindingDigest"] = _digest(binding_core)
    return migrated, binding
