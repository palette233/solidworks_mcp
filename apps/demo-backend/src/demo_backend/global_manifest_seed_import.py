"""Convert an imported historical CAD checkpoint into a manifest seed.

The conversion does not claim that the historical assembly was produced by the
current transaction manifest.  It proves instead that the signed checkpoint
contains the same instance set expected by the migrated context and binds that
immutable CAD file to the packet prefix immediately preceding a selected
manifest suffix.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .global_cad_packet_executor import sha256_file
from .semantic_assembly_jobs import canonical_json


EXTERNAL_SEED_SCHEMA = "global-cad-manifest-external-seed/v1"


class GlobalManifestSeedImportError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _token_bindings(
    context: dict[str, Any],
    catalog: dict[str, Any],
    project_id: str,
) -> list[dict[str, str]]:
    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    bindings: list[dict[str, str]] = []
    for instance in context.get("instances") or []:
        instance_id = str(instance.get("instanceId") or "")
        definition = definitions.get(str(instance.get("moduleDefinitionId") or "")) or {}
        tokens = sorted(
            {
                str(alias.get("moduleToken") or "").strip().upper()
                for alias in definition.get("projectAliases") or []
                if str(alias.get("projectId") or "").strip().lower()
                == project_id.lower()
                and str(alias.get("moduleToken") or "").strip()
            }
        )
        if len(tokens) != 1:
            raise GlobalManifestSeedImportError(
                f"实例{instance_id}在{project_id}中无法解析唯一模组令牌。"
            )
        bindings.append({"instanceId": instance_id, "moduleToken": tokens[0]})
    return sorted(bindings, key=lambda row: row["instanceId"])


def _file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise GlobalManifestSeedImportError(f"签认文件不存在：{resolved}")
    return {
        "path": str(resolved),
        "sizeBytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def build_existing_assembly_subset_seed_evidence(
    *,
    plan: dict[str, Any],
    context: dict[str, Any],
    catalog: dict[str, Any],
    project_id: str,
    assembly_path: Path,
    component_inventory_path: Path,
) -> dict[str, Any]:
    """Bind an immutable existing assembly when the context is a verified subset.

    Relation-only transactions frequently operate on two existing modules in a
    larger assembly.  Requiring inventory equality would reject that legitimate
    case, so this attestation requires every context instance exactly once and
    records all unmatched top-level components as explicit extras.
    """

    expected = plan.get("expectedSeed") or {}
    if not plan.get("requiresSeedCheckpoint") or not expected:
        raise GlobalManifestSeedImportError("该清单计划不需要外部种子检查点。")
    if context.get("contextId") != plan.get("contextId") or context.get(
        "contextDigest"
    ) != plan.get("contextDigest"):
        raise GlobalManifestSeedImportError("上下文与清单计划不一致。")
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalManifestSeedImportError("上下文与目录摘要不一致。")

    assembly_identity = _file_identity(assembly_path)
    inventory_identity = _file_identity(component_inventory_path)
    inventory = json.loads(component_inventory_path.resolve().read_text(encoding="utf-8-sig"))
    inventory_assembly = Path(str(inventory.get("assemblyPath") or "")).resolve()
    if inventory_assembly != assembly_path.resolve():
        raise GlobalManifestSeedImportError("组件清单记录的装配体与种子装配体不一致。")
    components = inventory.get("components")
    if not isinstance(components, list):
        raise GlobalManifestSeedImportError("组件清单缺少components数组。")

    bindings = _token_bindings(context, catalog, project_id)
    expected_counts = Counter(row["moduleToken"] for row in bindings)
    observed_counts: Counter[str] = Counter()
    matched_indexes: set[int] = set()
    for token, required_count in expected_counts.items():
        matches = [
            index
            for index, component in enumerate(components)
            if token.casefold()
            in " ".join(
                [
                    str(component.get("Name") or component.get("name") or ""),
                    str(component.get("Path") or component.get("path") or ""),
                ]
            ).casefold()
        ]
        observed_counts[token] = len(matches)
        if len(matches) != required_count:
            raise GlobalManifestSeedImportError(
                f"种子装配体中的{token}数量为{len(matches)}，期望{required_count}。"
            )
        matched_indexes.update(matches)

    extras = [
        {
            "name": component.get("Name") or component.get("name"),
            "path": component.get("Path") or component.get("path"),
        }
        for index, component in enumerate(components)
        if index not in matched_indexes
    ]
    evidence = {
        "schemaVersion": EXTERNAL_SEED_SCHEMA,
        "success": True,
        "packetId": expected.get("packetId"),
        "packetDigest": expected.get("packetDigest"),
        "moduleToken": expected.get("moduleToken"),
        "outputAssemblyPath": assembly_identity["path"],
        "outputAssemblySha256": assembly_identity["sha256"],
        "manifestPath": plan.get("manifestPath"),
        "manifestDigest": plan.get("manifestDigest"),
        "planDigest": plan.get("planDigest"),
        "contextId": context.get("contextId"),
        "contextDigest": context.get("contextDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "projectId": project_id,
        "sourceExistingAssembly": {
            "matchPolicy": "context-instance-subset-exact-count/v1",
            "assemblyIdentity": assembly_identity,
            "componentInventoryIdentity": inventory_identity,
            "inventorySchemaVersion": inventory.get("schemaVersion"),
            "inventoryComponentCount": len(components),
            "unmatchedTopLevelComponents": extras,
        },
        "instanceTokenBindings": bindings,
        "moduleTokenCounts": dict(sorted(expected_counts.items())),
        "observedRequiredModuleTokenCounts": dict(sorted(observed_counts.items())),
        "collisionStatus": "not_evaluated",
        "statement": (
            "该不可变既有装配体包含当前关系上下文的全部实例；额外顶层组件已显式记录，"
            "不宣称清单前缀由本次执行产生。"
        ),
    }
    evidence["evidenceDigest"] = _digest(evidence)
    return evidence


def build_external_manifest_seed_evidence(
    *,
    plan: dict[str, Any],
    context: dict[str, Any],
    catalog: dict[str, Any],
    historical_import: dict[str, Any],
    historical_import_path: Path,
) -> dict[str, Any]:
    expected = plan.get("expectedSeed") or {}
    if not plan.get("requiresSeedCheckpoint") or not expected:
        raise GlobalManifestSeedImportError("该清单计划不需要外部种子检查点。")
    if context.get("contextId") != plan.get("contextId"):
        raise GlobalManifestSeedImportError("上下文ID与清单计划不一致。")
    if context.get("contextDigest") != plan.get("contextDigest"):
        raise GlobalManifestSeedImportError("上下文摘要与清单计划不一致。")
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalManifestSeedImportError("上下文与目录摘要不一致。")
    if historical_import.get("schemaVersion") != "historical-demo-checkpoint-import/v1":
        raise GlobalManifestSeedImportError("不支持的历史检查点签认版本。")
    if historical_import.get("status") != "ready_for_import":
        raise GlobalManifestSeedImportError("历史检查点尚未通过签认。")
    if not historical_import.get("importedAt"):
        raise GlobalManifestSeedImportError("历史检查点没有已导入时间戳。")
    if historical_import.get("blockers"):
        raise GlobalManifestSeedImportError("历史检查点签认仍含阻塞项。")

    source_context_id = str(historical_import.get("contextId") or "")
    lineage_ids = {
        str(row.get("sourceContextId") or "")
        for row in context.get("history") or []
        if row.get("operation") == "catalog_binding_migration"
    }
    if source_context_id != context.get("contextId") and source_context_id not in lineage_ids:
        raise GlobalManifestSeedImportError("历史检查点不在目标上下文迁移谱系中。")

    project_id = str(historical_import.get("projectId") or "")
    expected_bindings = _token_bindings(context, catalog, project_id)
    observed_bindings = sorted(
        [
            {
                "instanceId": str(row.get("instanceId") or ""),
                "moduleToken": str(row.get("moduleToken") or "").strip().upper(),
            }
            for row in historical_import.get("instanceTokenBindings") or []
        ],
        key=lambda row: row["instanceId"],
    )
    if observed_bindings != expected_bindings:
        raise GlobalManifestSeedImportError("历史检查点实例集合与目标上下文不一致。")
    expected_counts = historical_import.get("expectedModuleTokenCounts") or {}
    observed_counts = historical_import.get("observedModuleTokenCounts") or {}
    if expected_counts != observed_counts:
        raise GlobalManifestSeedImportError("历史检查点的模组计数未闭合。")

    identity = historical_import.get("checkpointAssemblyIdentity") or {}
    assembly = Path(str(identity.get("path") or "")).resolve()
    if not assembly.is_file():
        raise GlobalManifestSeedImportError("历史检查点装配体不存在。")
    actual_sha = sha256_file(assembly)
    if actual_sha != str(identity.get("sha256") or ""):
        raise GlobalManifestSeedImportError("历史检查点装配体SHA-256已变化。")
    if assembly.stat().st_size != int(identity.get("sizeBytes") or -1):
        raise GlobalManifestSeedImportError("历史检查点装配体大小已变化。")

    evidence = {
        "schemaVersion": EXTERNAL_SEED_SCHEMA,
        "success": True,
        "packetId": expected.get("packetId"),
        "packetDigest": expected.get("packetDigest"),
        "moduleToken": expected.get("moduleToken"),
        "outputAssemblyPath": str(assembly),
        "outputAssemblySha256": actual_sha,
        "manifestPath": plan.get("manifestPath"),
        "manifestDigest": plan.get("manifestDigest"),
        "planDigest": plan.get("planDigest"),
        "contextId": context.get("contextId"),
        "contextDigest": context.get("contextDigest"),
        "catalogDigest": catalog.get("catalogDigest"),
        "projectId": project_id,
        "sourceHistoricalImport": {
            "path": str(historical_import_path.resolve()),
            "sha256": sha256_file(historical_import_path.resolve()),
            "contextId": source_context_id,
            "contextRevision": historical_import.get("contextRevision"),
            "assessmentDigest": historical_import.get("assessmentDigest"),
            "importedAt": historical_import.get("importedAt"),
        },
        "instanceTokenBindings": expected_bindings,
        "moduleTokenCounts": expected_counts,
        "collisionStatus": "not_evaluated",
        "statement": (
            "该装配体来自已签认历史检查点，并与当前迁移上下文的实例集合一致；"
            "不宣称当前清单前缀已被重新执行。"
        ),
    }
    evidence["evidenceDigest"] = _digest(evidence)
    return evidence


def validate_external_manifest_seed_evidence(
    evidence: dict[str, Any],
    *,
    plan: dict[str, Any],
) -> None:
    if evidence.get("schemaVersion") != EXTERNAL_SEED_SCHEMA:
        raise GlobalManifestSeedImportError("不支持的外部种子证据版本。")
    expected_digest = str(evidence.get("evidenceDigest") or "")
    actual_digest = _digest(
        {key: value for key, value in evidence.items() if key != "evidenceDigest"}
    )
    if not expected_digest or expected_digest != actual_digest:
        raise GlobalManifestSeedImportError("外部种子证据摘要不一致。")
    if evidence.get("manifestDigest") != plan.get("manifestDigest"):
        raise GlobalManifestSeedImportError("外部种子证据与清单摘要不一致。")
    if evidence.get("planDigest") != plan.get("planDigest"):
        raise GlobalManifestSeedImportError("外部种子证据与任务计划摘要不一致。")
    if evidence.get("contextId") != plan.get("contextId"):
        raise GlobalManifestSeedImportError("外部种子证据与上下文ID不一致。")
    if evidence.get("contextDigest") != plan.get("contextDigest"):
        raise GlobalManifestSeedImportError("外部种子证据与上下文摘要不一致。")
