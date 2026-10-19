"""Application service for natural-language, cumulative semantic assembly.

The workbench joins module retrieval, user disambiguation, semantic-port and
template selection, editable assembly context, release policy, transaction DAG
compilation, and CAD-manifest generation.  It must fail closed when a requested
module or relation is ambiguous or lacks authorized evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
import hashlib
from pathlib import Path
import re
from typing import Any

from .global_assembly_context import (
    GlobalAssemblyContextError,
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
    search_global_modules,
    validate_global_assembly_context,
)
from .global_module_catalog import GlobalModuleCatalogError, validate_global_module_catalog
from .global_module_port_coverage import (
    assess_module_selection_readiness,
    build_global_module_port_coverage_matrix,
)
from .global_assembly_compiler import (
    GlobalAssemblyCompilerError,
    compile_global_assembly_execution_manifest,
)
from .global_assembly_transactions import (
    GlobalAssemblyTransactionError,
    build_global_command_ir,
    compile_global_assembly_transaction_dag,
)
from .global_cad_transaction_packets import compile_global_cad_transaction_manifest
from .project02_positioning_standard import load_project02_positioning_standard
from .global_project_adapter_plan import (
    GlobalProjectAdapterPlanError,
    compile_global_project_adapter_plan,
)
from .assembly_conversation import (
    record_graph_turn,
    reset_conversation,
    rollback_latest_graph_turn,
)
from .temporary_semantic_ports import reset_temporary_ports
from .global_catalog_migration import (
    GlobalCatalogMigrationError,
    build_catalog_migration_plan,
    migrate_context_catalog_binding,
)
from .global_relation_edits import (
    GlobalRelationEditError,
    apply_global_relation_edit,
    preview_global_relation_edit,
)
from .global_relation_catalog_release import (
    GlobalRelationCatalogReleaseError,
    load_relation_catalog_release,
    relation_catalog_release_binding,
)
from .global_relation_semantics import (
    assess_template_for_relation_intent,
    normalize_template_relation_profile,
    parse_relation_intent,
)
from .mate_transaction_preflight import preflight_direct_mate_transaction
from .relation_driving_preflight import classify_relation_driving_preflight
from .assembly_user_failure import build_assembly_user_failure
from .portable_release_recommendation import (
    PortableReleaseRecommendationError,
    build_portable_release_context,
    recommend_portable_relation_release,
)
from .cross_project_module_substitution import (
    build_module_role_overlay,
    compile_substitution_preview,
)


DEFAULT_CATALOG = Path("demo/global_assembly_catalog/v1/global_module_catalog.json")
DEFAULT_CONTEXT_DIR = Path("demo/global_assembly_contexts")
DEFAULT_CATALOG_MIGRATION_DIR = Path("demo/global_assembly_catalog/migrations")
DEFAULT_RELATION_RELEASE_MANIFEST = Path(
    "demo/global_assembly_catalog/releases/relation-v5-20261011/release-manifest.json"
)
DEFAULT_RELATION_VALIDATION_PRECONDITION_REGISTRY = Path(
    "demo/global_assembly_catalog/relation-validation-preconditions-v1.json"
)
DEFAULT_RELATION_DRIVING_SAFETY_REGISTRY = Path(
    "demo/global_assembly_catalog/relation-driving-safety-v1.json"
)


class GlobalAssemblyWorkbenchError(ValueError):
    pass


def _load_selected_positioning_standard(
    positioning_standard_id: str | None,
) -> dict[str, Any] | None:
    selected = str(positioning_standard_id or "").strip().lower()
    if not selected:
        return None
    if selected != "project02-inferred-v1":
        raise GlobalAssemblyWorkbenchError(
            f"不支持的定位标准：{positioning_standard_id}"
        )
    return load_project02_positioning_standard()


def _inside(workspace: Path, path: Path) -> Path:
    root = workspace.resolve()
    result = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        result.relative_to(root)
    except ValueError as exc:
        raise GlobalAssemblyWorkbenchError("全局装配工作台文件必须位于工作区内。") from exc
    return result


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalAssemblyWorkbenchError(f"无法读取JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GlobalAssemblyWorkbenchError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_global_catalog(workspace: Path, catalog_path: str | None = None) -> dict[str, Any]:
    path = _inside(workspace, Path(catalog_path) if catalog_path else DEFAULT_CATALOG)
    if not path.is_file():
        raise GlobalAssemblyWorkbenchError(f"全局模组目录不存在：{path}")
    catalog = _read(path)
    try:
        validate_global_module_catalog(catalog)
    except GlobalModuleCatalogError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
    return catalog


def load_released_relation_catalog(
    workspace: Path, release_manifest_path: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _inside(
        workspace,
        Path(release_manifest_path)
        if release_manifest_path
        else DEFAULT_RELATION_RELEASE_MANIFEST,
    )
    try:
        return load_relation_catalog_release(path, workspace_root=workspace)
    except GlobalRelationCatalogReleaseError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def _relation_release_binding(
    workspace: Path,
    manifest: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        return relation_catalog_release_binding(
            manifest,
            manifest_path=manifest_path,
            workspace_root=workspace,
        )
    except GlobalRelationCatalogReleaseError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def _load_context_catalog_authority(
    workspace: Path,
    context: dict[str, Any],
    *,
    explicit_catalog_path: str | None = None,
) -> tuple[dict[str, Any], list[str] | None]:
    """Load the immutable catalog authority recorded by the context itself."""

    binding = context.get("relationReleaseBinding")
    if binding is None:
        catalog = load_global_catalog(workspace, explicit_catalog_path)
        return catalog, None
    if str(explicit_catalog_path or "").strip():
        raise GlobalAssemblyWorkbenchError(
            "上下文已绑定关系发布清单，不能再通过catalogPath替换目录。"
        )
    manifest_path = _inside(workspace, Path(binding["releaseManifestPath"]))
    catalog, manifest = load_released_relation_catalog(
        workspace, str(manifest_path)
    )
    expected = _relation_release_binding(workspace, manifest, manifest_path)
    if expected != binding:
        raise GlobalAssemblyWorkbenchError(
            "关系发布清单已变化或上下文绑定被修改，拒绝继续编译。"
        )
    if catalog.get("catalogDigest") != context.get("catalogDigest"):
        raise GlobalAssemblyWorkbenchError("上下文与绑定发布目录摘要不一致。")
    return catalog, list(binding["authorizedDrivingTemplateIds"])


def _relation_operation_for_command(command: dict[str, Any]) -> str:
    """Resolve add versus read-only verification for an existing-instance relation."""

    explicit = str(
        command.get("operation") or command.get("executionMode") or ""
    ).strip().lower()
    aliases = {
        "add": "add",
        "drive": "add",
        "add_relation": "add",
        "verify": "verify",
        "validate": "verify",
        "verify_relation": "verify",
    }
    if explicit:
        if explicit not in aliases:
            raise GlobalAssemblyWorkbenchError(
                "关系命令operation/executionMode只能表达add/drive或verify/validate。"
            )
        return aliases[explicit]
    requirement = str(command.get("requirement") or "").lower()
    verification_markers = (
        "验证",
        "校验",
        "检查",
        "核对",
        "测量",
        "verify",
        "validate",
        "check",
        "measure",
    )
    return "verify" if any(marker in requirement for marker in verification_markers) else "add"


def _released_relation_template_ids_for_operation(
    catalog: dict[str, Any],
    authorized_driving_template_ids: list[str] | None,
    operation: str,
) -> list[str] | None:
    """Keep driving authorization strict while permitting immutable read-only checks."""

    if authorized_driving_template_ids is None:
        return None
    allowed = set(authorized_driving_template_ids)
    if operation == "verify":
        for template in catalog.get("connectionTemplates") or []:
            profile = normalize_template_relation_profile(template)
            if (
                profile.get("drivesPlacement") is False
                and int(profile.get("validationMateStepCount") or 0) > 0
            ):
                allowed.add(str(template.get("globalTemplateId") or ""))
    allowed.discard("")
    return sorted(allowed)


def describe_released_relation_catalog(
    workspace: Path, release_manifest_path: str | None = None
) -> dict[str, Any]:
    catalog, manifest = load_released_relation_catalog(
        workspace, release_manifest_path
    )
    template_ids = set(manifest["derivedTemplateIds"])
    return {
        "success": True,
        "releaseId": manifest["releaseId"],
        "status": manifest["status"],
        "productionReady": manifest["productionReady"],
        "catalogDigest": catalog["catalogDigest"],
        "releaseDigest": manifest["releaseDigest"],
        "releasedCatalogRelativePath": manifest["releasedCatalogRelativePath"],
        "releasedTemplateCount": len(template_ids),
        "releasedTemplateIds": sorted(template_ids),
        "authorizedDrivingTemplateIds": sorted(
            manifest.get("scope", {}).get("authorizedDrivingTemplateIds") or []
        ),
        "scope": manifest["scope"],
        "validationEvidenceCount": len(manifest.get("validationEvidence") or []),
    }


def preview_released_relation_intent(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    """Resolve relation language only against explicitly released templates."""

    explicit_catalog = str(payload.get("catalogPath") or "").strip()
    explicit_release = str(payload.get("releaseManifestPath") or "").strip()
    if explicit_catalog and explicit_release:
        raise GlobalAssemblyWorkbenchError(
            "catalogPath与releaseManifestPath不能同时指定。"
        )
    if explicit_catalog:
        catalog = load_global_catalog(workspace, explicit_catalog)
        manifest = None
        allowed_ids = {
            str(row.get("globalTemplateId") or "")
            for row in catalog.get("connectionTemplates") or []
        }
    else:
        catalog, manifest = load_released_relation_catalog(
            workspace, explicit_release or None
        )
        allowed_ids = set(manifest.get("derivedTemplateIds") or [])

    execution_mode = str(payload.get("executionMode") or "verify").strip().lower()
    if execution_mode not in {"verify", "drive"}:
        raise GlobalAssemblyWorkbenchError("executionMode只能为verify或drive。")
    intent = parse_relation_intent(str(payload.get("requirement") or ""))
    assessments: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for template in catalog.get("connectionTemplates") or []:
        template_id = str(template.get("globalTemplateId") or "")
        if template_id not in allowed_ids:
            continue
        assessment = assess_template_for_relation_intent(
            template,
            intent,
            allow_validation_only=execution_mode == "verify",
        )
        row = {
            "globalTemplateId": template_id,
            "legacyTemplateId": template.get("legacyTemplateId"),
            "compatible": assessment["compatible"],
            "reasons": assessment["reasons"],
            "templateProfile": assessment["templateProfile"],
        }
        assessments.append(row)
        if row["compatible"]:
            matches.append(row)

    blockers = list(intent.get("blockers") or [])
    if execution_mode == "drive" and manifest is not None:
        scope = manifest.get("scope", {})
        authorized_ids = set(scope.get("authorizedDrivingTemplateIds") or [])
        if scope.get("drivingRelationRelease") is not True or not authorized_ids:
            blockers.append(
                {
                    "code": "RELEASE_SCOPE_FORBIDS_DRIVING_RELATION",
                    "detail": "当前发布版只允许检查已有关系，不允许用该关系驱动模组位姿。",
                }
            )
            matches = []
        else:
            unauthorized_matches = [
                row for row in matches if row["globalTemplateId"] not in authorized_ids
            ]
            matches = [
                row for row in matches if row["globalTemplateId"] in authorized_ids
            ]
            if unauthorized_matches and not matches:
                blockers.append(
                    {
                        "code": "MATCHED_RELATION_TEMPLATE_NOT_AUTHORIZED_FOR_DRIVING",
                        "detail": "匹配到的关系模板尚未获得逐模板驱动授权。",
                        "matchedButUnauthorizedTemplateIds": [
                            row["globalTemplateId"] for row in unauthorized_matches
                        ],
                    }
                )
    if intent.get("primaryRelation") == "unspecified":
        blockers.append(
            {
                "code": "RELATION_KIND_REQUIRED",
                "detail": "请明确重合、平行、距离等关系类型。",
            }
        )
        matches = []
    elif not blockers and not matches:
        blockers.append(
            {
                "code": "NO_RELEASED_RELATION_TEMPLATE_MATCHED",
                "detail": "已发布关系目录中没有与该自然语言要求匹配的模板。",
            }
        )
    status = (
        "blocked"
        if blockers
        else "ready_for_endpoint_selection"
        if len(matches) == 1
        else "needs_template_selection"
    )
    result = {
        "success": not blockers,
        "status": status,
        "requestedExecutionMode": execution_mode,
        "intent": intent,
        "catalogDigest": catalog["catalogDigest"],
        "release": (
            {
                "releaseId": manifest["releaseId"],
                "releaseDigest": manifest["releaseDigest"],
                "scope": manifest["scope"],
            }
            if manifest is not None
            else None
        ),
        "matchingTemplates": matches,
        "templateAssessments": assessments,
        "blockers": blockers,
        "userFailureExplanation": (
            build_assembly_user_failure(
                blockers=blockers,
                status=status,
                stage="natural_language_relation_preview",
            )
            if blockers
            else None
        ),
        "nextAction": (
            "选择两个模组实例及其已登记语义端口，再创建verify关系预览。"
            if status == "ready_for_endpoint_selection"
            else "先消除阻塞项或明确选择关系模板。"
        ),
        "cadExecution": {
            "status": "not_executed",
            "statement": "该步骤只解析自然语言并选择已发布模板，不启动SolidWorks。",
        },
    }
    result["previewDigest"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return result


def preflight_released_driving_relation(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    """Join released relation semantics with strict pre-CAD DOF evidence."""

    requirement = str(payload.get("requirement") or "").strip()
    if not requirement:
        raise GlobalAssemblyWorkbenchError("requirement不能为空。")
    graph_value = str(payload.get("effectiveGraphPath") or "").strip()
    if not graph_value:
        raise GlobalAssemblyWorkbenchError("effectiveGraphPath不能为空。")
    target = str(payload.get("targetModuleToken") or "").strip()
    if not target:
        raise GlobalAssemblyWorkbenchError("targetModuleToken不能为空。")

    graph_path = _inside(workspace, Path(graph_value))
    if not graph_path.is_file():
        raise GlobalAssemblyWorkbenchError(f"有效配合图不存在：{graph_path}")
    graph = _read(graph_path)
    transaction = preflight_direct_mate_transaction(
        graph,
        target,
        require_closed_dof=bool(payload.get("requireClosedDof", False)),
        reject_redundant_mutations=True,
    )
    release_manifest_path = str(payload.get("releaseManifestPath") or "").strip()
    verification_payload = {"requirement": requirement, "executionMode": "verify"}
    if release_manifest_path:
        verification_payload["releaseManifestPath"] = release_manifest_path
    verification = preview_released_relation_intent(workspace, verification_payload)
    release = describe_released_relation_catalog(
        workspace, release_manifest_path or None
    )
    result = classify_relation_driving_preflight(
        requirement=requirement,
        released_verification_preview=verification,
        transaction_preflight=transaction,
        release=release,
    )
    result["effectiveGraphPath"] = str(graph_path)
    result["targetModuleToken"] = target.upper()
    result["preflightDigest"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in result.items() if key != "preflightDigest"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return result


def context_path(workspace: Path, context_id: str) -> Path:
    candidate = DEFAULT_CONTEXT_DIR / f"{context_id}.json"
    return _inside(workspace, candidate)


def _revision_snapshot_path(path: Path, revision: int) -> Path:
    return path.parent / f"{path.stem}.revisions" / f"revision-{revision:06d}.json"


def _revision_snapshot_variant_path(
    path: Path, revision: int, context_digest: str
) -> Path:
    digest = str(context_digest or "").strip()
    suffix = digest[:16] if digest else "unknown"
    return (
        path.parent
        / f"{path.stem}.revisions"
        / f"revision-{revision:06d}-{suffix}.json"
    )


def _revision_snapshot_candidates(path: Path, revision: int) -> list[Path]:
    directory = path.parent / f"{path.stem}.revisions"
    candidates = sorted(directory.glob(f"revision-{revision:06d}-*.json"))
    legacy = _revision_snapshot_path(path, revision)
    if legacy.is_file():
        candidates.append(legacy)
    return candidates


def _archive_context_revision(
    path: Path, context: dict[str, Any], *, replace: bool = False
) -> Path:
    """Persist one immutable-by-convention graph revision before mutation."""

    revision = int(context.get("revision") or 0)
    snapshot = _revision_snapshot_path(path, revision)
    if replace:
        _write(snapshot, context)
        return snapshot
    if snapshot.is_file():
        existing = _read(snapshot)
        if existing.get("contextDigest") != context.get("contextDigest"):
            # A graph-only undo may legitimately create another branch that
            # reuses the same integer revision.  Keep both immutable snapshots
            # instead of overwriting the older branch or rejecting the new one.
            variant = _revision_snapshot_variant_path(
                path, revision, str(context.get("contextDigest") or "")
            )
            if variant.is_file():
                variant_existing = _read(variant)
                if variant_existing.get("contextDigest") != context.get(
                    "contextDigest"
                ):
                    raise GlobalAssemblyWorkbenchError(
                        f"修订快照{revision}的摘要短标识发生冲突。"
                    )
                return variant
            _write(variant, context)
            return variant
        return snapshot
    _write(snapshot, context)
    return snapshot


def _load_parent_revision_snapshot(
    path: Path, current: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    revision = int(current.get("revision") or 0)
    target_revision = revision - 1
    history = current.get("history") or []
    expected_digest = ""
    if history and isinstance(history[-1], dict):
        expected_digest = str(history[-1].get("sourceContextDigest") or "")

    valid: list[tuple[Path, dict[str, Any]]] = []
    for candidate in _revision_snapshot_candidates(path, target_revision):
        try:
            snapshot = _read(candidate)
        except (OSError, json.JSONDecodeError):
            continue
        if expected_digest and snapshot.get("contextDigest") != expected_digest:
            continue
        snapshot_history = snapshot.get("history") or []
        if not expected_digest and snapshot_history != history[:-1]:
            continue
        valid.append((candidate, snapshot))

    if len(valid) == 1:
        return valid[0]
    if not valid:
        detail = "且找不到父摘要" if expected_digest else "且历史前缀不匹配"
        raise GlobalAssemblyWorkbenchError(
            f"缺少上一修订{target_revision}的恢复快照{detail}，不能安全撤销。"
        )
    raise GlobalAssemblyWorkbenchError(
        f"上一修订{target_revision}存在多个匹配快照，不能安全判定撤销分支。"
    )


def create_context(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    explicit_catalog = str(payload.get("catalogPath") or "").strip()
    explicit_release = str(payload.get("releaseManifestPath") or "").strip()
    if explicit_catalog and explicit_release:
        raise GlobalAssemblyWorkbenchError(
            "catalogPath与releaseManifestPath不能同时指定。"
        )
    relation_release_binding = None
    if explicit_release:
        manifest_path = _inside(workspace, Path(explicit_release))
        catalog, manifest = load_released_relation_catalog(
            workspace, str(manifest_path)
        )
        relation_release_binding = _relation_release_binding(
            workspace, manifest, manifest_path
        )
    else:
        catalog = load_global_catalog(workspace, explicit_catalog or None)
    context = create_global_assembly_context(
        str(payload.get("contextId") or ""),
        display_name=payload.get("displayName"),
        catalog_digest=catalog["catalogDigest"],
        relation_release_binding=relation_release_binding,
    )
    path = context_path(workspace, context["contextId"])
    if path.exists() and not bool(payload.get("overwrite")):
        raise GlobalAssemblyWorkbenchError("装配上下文已存在；如需覆盖必须显式overwrite=true。")
    _write(path, context)
    _archive_context_revision(path, context, replace=bool(payload.get("overwrite")))
    reset_conversation(path, context)
    reset_temporary_ports(path, context)
    return {"success": True, "contextPath": str(path), "context": context}


def load_context(workspace: Path, context_id: str) -> dict[str, Any]:
    path = context_path(workspace, context_id)
    if not path.is_file():
        raise GlobalAssemblyWorkbenchError(f"装配上下文不存在：{path}")
    context = _read(path)
    try:
        validate_global_assembly_context(context)
    except GlobalAssemblyContextError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
    return context


def preview_portable_release_upgrade(
    workspace: Path, context_id: str
) -> dict[str, Any]:
    """Recommend a single immutable release without mutating the source graph."""

    return recommend_portable_relation_release(
        workspace.resolve(), load_context(workspace, context_id)
    )


def commit_portable_release_upgrade(
    workspace: Path, context_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Create a new release-bound context after explicit user confirmation."""

    if payload.get("confirmed") is not True:
        raise GlobalAssemblyWorkbenchError(
            "必须显式confirmed=true才能创建便携发布上下文。"
        )
    source_path = context_path(workspace, context_id)
    source_bytes_before = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes_before).hexdigest()
    source = load_context(workspace, context_id)
    try:
        upgraded, evidence = build_portable_release_context(
            workspace.resolve(),
            source,
            expected_preview_digest=str(payload.get("previewDigest") or ""),
            release_id=str(payload.get("releaseId") or ""),
            target_context_id=str(payload.get("targetContextId") or ""),
        )
    except (PortableReleaseRecommendationError, GlobalRelationCatalogReleaseError) as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
    target_path = context_path(workspace, upgraded["contextId"])
    if target_path.exists():
        raise GlobalAssemblyWorkbenchError(
            "便携发布目标上下文已存在；为保护历史记录，禁止覆盖。"
        )
    _write(target_path, upgraded)
    _archive_context_revision(target_path, upgraded)
    reset_conversation(target_path, upgraded)
    reset_temporary_ports(target_path, upgraded)
    evidence_path = target_path.with_suffix(".portable-release-binding.json")
    if source_path.read_bytes() != source_bytes_before:
        raise GlobalAssemblyWorkbenchError(
            "创建便携上下文时检测到源会话被修改，拒绝报告成功。"
        )
    evidence["sourceContextFileSha256"] = source_sha256
    evidence["sourceContextFileUnchanged"] = True
    evidence["evidenceDigest"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in evidence.items() if key != "evidenceDigest"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _write(evidence_path, evidence)
    return {
        "success": True,
        "sourcePreserved": True,
        "solidWorksExecuted": False,
        "sourceContextId": context_id,
        "targetContextPath": str(target_path),
        "evidencePath": str(evidence_path),
        "context": upgraded,
        "bindingEvidence": evidence,
        "message": "已创建便携关系发布上下文；源会话保持不变，尚未执行SolidWorks。",
    }


def preview_catalog_migration(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    source_path = _inside(
        workspace,
        Path(payload.get("sourceCatalogPath") or DEFAULT_CATALOG),
    )
    candidate_value = str(payload.get("candidateCatalogPath") or "").strip()
    if not candidate_value:
        raise GlobalAssemblyWorkbenchError("candidateCatalogPath不能为空。")
    candidate_path = _inside(workspace, Path(candidate_value))
    source_catalog = load_global_catalog(workspace, str(source_path))
    candidate_catalog = load_global_catalog(workspace, str(candidate_path))
    context_ids = payload.get("contextIds")
    if not isinstance(context_ids, list) or not context_ids:
        raise GlobalAssemblyWorkbenchError("contextIds必须是非空数组。")
    contexts = [load_context(workspace, str(context_id)) for context_id in context_ids]
    return build_catalog_migration_plan(
        source_catalog,
        candidate_catalog,
        contexts,
        source_catalog_path=str(source_path),
        candidate_catalog_path=str(candidate_path),
    )


def commit_catalog_migration(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    source_path = _inside(
        workspace,
        Path(payload.get("sourceCatalogPath") or DEFAULT_CATALOG),
    )
    candidate_value = str(payload.get("candidateCatalogPath") or "").strip()
    if not candidate_value:
        raise GlobalAssemblyWorkbenchError("candidateCatalogPath不能为空。")
    candidate_path = _inside(workspace, Path(candidate_value))
    source_catalog = load_global_catalog(workspace, str(source_path))
    candidate_catalog = load_global_catalog(workspace, str(candidate_path))
    source_context_id = str(payload.get("sourceContextId") or "").strip()
    target_context_id = str(payload.get("targetContextId") or "").strip()
    source_context_file = context_path(workspace, source_context_id)
    source_bytes_before = source_context_file.read_bytes()
    source_file_sha256 = hashlib.sha256(source_bytes_before).hexdigest()
    context = load_context(workspace, source_context_id)
    try:
        migrated, binding = migrate_context_catalog_binding(
            source_catalog,
            candidate_catalog,
            context,
            target_context_id=target_context_id,
            expected_assessment_digest=str(payload.get("expectedAssessmentDigest") or ""),
            confirmed=bool(payload.get("confirmed")),
        )
    except GlobalCatalogMigrationError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc

    target_path = context_path(workspace, target_context_id)
    if target_path.exists():
        raise GlobalAssemblyWorkbenchError("迁移目标上下文已存在；迁移禁止覆盖已有文件。")
    migration_dir = _inside(
        workspace,
        DEFAULT_CATALOG_MIGRATION_DIR
        / (
            f"{source_catalog['catalogDigest'][:12]}-to-"
            f"{candidate_catalog['catalogDigest'][:12]}"
        ),
    )
    binding_path = migration_dir / f"{target_context_id}.binding.json"
    if binding_path.exists():
        raise GlobalAssemblyWorkbenchError("迁移绑定证据已存在；请更换targetContextId。")

    _write(target_path, migrated)
    reset_conversation(target_path, migrated)
    reset_temporary_ports(target_path, migrated)
    binding.update(
        {
            "sourceCatalogPath": str(source_path),
            "candidateCatalogPath": str(candidate_path),
            "sourceContextPath": str(source_context_file),
            "targetContextPath": str(target_path),
            "sourceContextFileSha256": source_file_sha256,
        }
    )
    _write(binding_path, binding)

    if source_context_file.read_bytes() != source_bytes_before:
        raise GlobalAssemblyWorkbenchError("迁移后检测到源上下文被修改，已拒绝报告成功。")
    return {
        "success": True,
        "status": "committed",
        "sourcePreserved": True,
        "sourceContextPath": str(source_context_file),
        "targetContextPath": str(target_path),
        "bindingPath": str(binding_path),
        "context": migrated,
        "binding": binding,
        "message": "已创建新目录绑定上下文；源目录和源上下文均未覆盖。",
    }


def preview_relation_edit(
    workspace: Path, context_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    catalog, allowed_template_ids = _load_context_catalog_authority(
        workspace,
        context,
        explicit_catalog_path=payload.get("catalogPath"),
    )
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyWorkbenchError("上下文使用的目录版本已过期，请迁移或新建上下文。")
    try:
        effective_payload = dict(payload)
        if allowed_template_ids is not None:
            effective_payload["allowedTemplateIds"] = allowed_template_ids
        return preview_global_relation_edit(catalog, context, effective_payload)
    except GlobalRelationEditError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def apply_relation_edit(
    workspace: Path, context_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    preview = payload.get("preview")
    if not isinstance(preview, dict):
        raise GlobalAssemblyWorkbenchError("preview必须是对象。")
    try:
        updated = apply_global_relation_edit(
            context,
            preview,
            preview_digest=str(payload.get("previewDigest") or ""),
            confirmed=bool(payload.get("confirmed")),
        )
    except GlobalRelationEditError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
    path = context_path(workspace, context_id)
    _write(path, updated)
    return {
        "success": True,
        "contextPath": str(path),
        "context": updated,
        "message": "关系编辑已写入配合语义图；尚未执行SolidWorks。",
    }


def search_modules(workspace: Path, query: str, *, limit: int = 20) -> dict[str, Any]:
    catalog = load_global_catalog(workspace)
    results = search_global_modules(catalog, query, limit=limit)
    return {
        "success": True,
        "query": query,
        "resultCount": len(results),
        "results": results,
        "catalogDigest": catalog["catalogDigest"],
    }


def load_module_port_coverage(
    workspace: Path, catalog_path: str | None = None
) -> dict[str, Any]:
    catalog = load_global_catalog(workspace, catalog_path)
    return build_global_module_port_coverage_matrix(catalog)


def assess_module_selection(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    matrix = load_module_port_coverage(workspace, payload.get("catalogPath"))
    references = payload.get("moduleReferences")
    if not isinstance(references, list):
        raise GlobalAssemblyWorkbenchError("moduleReferences必须是数组。")
    return assess_module_selection_readiness(matrix, references)


def _rehash_command_preview(preview: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the canonical command IR and digest after a trusted enrichment."""

    preview.pop("previewDigest", None)
    preview["commandIr"] = build_global_command_ir(preview)
    preview["previewDigest"] = hashlib.sha256(
        json.dumps(
            preview,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return preview


def _enrich_first_connection_with_portable_release(
    workspace: Path,
    context: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    """Bind the first real connection to one verified portable release.

    The enrichment is intentionally narrow: it only runs for an unbound
    context and only when the command already has a ready connection.  The
    user's existing confirmation therefore covers both adding the module and
    accepting the immutable relation release; no hidden graph mutation occurs.
    """

    patch = preview.get("proposedPatch") or {}
    if (
        context.get("relationReleaseBinding") is not None
        or preview.get("status") != "ready"
        or not isinstance(patch.get("connection"), dict)
    ):
        return preview
    try:
        hypothetical = apply_global_command_preview(
            context,
            preview,
            preview_digest=str(preview.get("previewDigest") or ""),
            confirmed=True,
        )
        recommendation = recommend_portable_relation_release(workspace, hypothetical)
        selected = recommendation.get("recommendation")
        if recommendation.get("status") != "ready" or not isinstance(selected, dict):
            return preview
        upgraded, _ = build_portable_release_context(
            workspace,
            hypothetical,
            expected_preview_digest=str(recommendation.get("previewDigest") or ""),
            release_id=str(selected.get("releaseId") or ""),
            target_context_id=str(hypothetical.get("contextId") or ""),
        )
    except (GlobalAssemblyContextError, PortableReleaseRecommendationError):
        return preview

    connection_id = str(patch["connection"].get("connectionId") or "")
    upgraded_connection = next(
        (
            row
            for row in upgraded.get("connections") or []
            if str(row.get("connectionId") or "") == connection_id
        ),
        None,
    )
    if not isinstance(upgraded_connection, dict):
        return preview

    enriched = dict(preview)
    enriched_patch = dict(patch)
    enriched_patch["connection"] = upgraded_connection
    enriched["proposedPatch"] = enriched_patch
    enriched["portableReleaseTransition"] = {
        "transitionKind": "first_bind",
        "discoveryMode": "active_catalog_rebinding",
        "sourceCatalogDigest": context.get("catalogDigest"),
        "sourceRelationReleaseBinding": deepcopy(
            context.get("relationReleaseBinding")
        ),
        "releaseId": selected.get("releaseId"),
        "catalogDigest": upgraded.get("catalogDigest"),
        "relationReleaseBinding": upgraded.get("relationReleaseBinding"),
        "replacements": selected.get("replacements") or [],
        "selectionPolicy": recommendation.get("selectionPolicy"),
        "solidWorksExecuted": False,
        "requiresExplicitConfirmation": True,
    }
    return _rehash_command_preview(enriched)


def _release_version(release_id: str) -> int:
    match = re.search(r"(?:^|-)v(\d+)(?:-|$)", release_id.casefold())
    return int(match.group(1)) if match else 0


def _enrich_unbound_blocked_command_from_portable_releases(
    workspace: Path,
    context: dict[str, Any],
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    """Resolve a first cross-project connection from immutable releases.

    The active catalog intentionally remains small and cannot know every
    cross-project port pair.  When an unbound context is blocked *only after*
    choosing a concrete module, inspect immutable driving releases and accept
    the smallest/latest release that can compile the same natural-language
    command as one fully locating connection.  No prototype pose is consulted.
    """

    if (
        context.get("relationReleaseBinding") is not None
        or context.get("connections")
        or preview.get("status") != "blocked"
        or not preview.get("selectedModuleDefinitionId")
    ):
        return preview
    blocker_codes = {
        str(row.get("code") or "") for row in preview.get("blockers") or []
    }
    if "NO_COMPATIBLE_PORT_PAIR" not in blocker_codes:
        return preview

    required_definition_ids = {
        str(row.get("moduleDefinitionId") or "")
        for row in context.get("instances") or []
    }
    required_definition_ids.add(str(preview.get("selectedModuleDefinitionId") or ""))
    required_definition_ids.discard("")
    candidates: list[dict[str, Any]] = []
    release_root = workspace.resolve() / "demo/global_assembly_catalog/releases"
    for manifest_path in sorted(release_root.glob("*/release-manifest.json")):
        try:
            candidate_catalog, manifest = load_released_relation_catalog(
                workspace, str(manifest_path)
            )
            binding = _relation_release_binding(workspace, manifest, manifest_path)
            definition_ids = {
                str(row.get("moduleDefinitionId") or "")
                for row in candidate_catalog.get("moduleDefinitions") or []
            }
            if not required_definition_ids.issubset(definition_ids):
                continue
            authorized_ids = list(binding.get("authorizedDrivingTemplateIds") or [])
            if not authorized_ids:
                continue
            effective_payload = dict(payload)
            effective_payload["allowedTemplateIds"] = authorized_ids
            candidate_preview = preview_global_assembly_command(
                candidate_catalog, context, effective_payload
            )
        except (
            GlobalAssemblyContextError,
            GlobalAssemblyWorkbenchError,
            GlobalRelationCatalogReleaseError,
            OSError,
            ValueError,
            TypeError,
        ):
            continue
        connection = (candidate_preview.get("proposedPatch") or {}).get("connection")
        if candidate_preview.get("status") != "ready" or not isinstance(
            connection, dict
        ):
            continue
        template_id = str(connection.get("globalTemplateId") or "")
        if template_id not in set(authorized_ids):
            continue
        template = next(
            (
                row
                for row in candidate_catalog.get("connectionTemplates") or []
                if str(row.get("globalTemplateId") or "") == template_id
            ),
            None,
        )
        if not isinstance(template, dict) or (template.get("constraintEffect") or {}).get(
            "fullyLocatesAddedComponent"
        ) is not True:
            continue
        candidates.append(
            {
                "preview": candidate_preview,
                "binding": binding,
                "releaseId": str(manifest.get("releaseId") or ""),
                "authorizedTemplateCount": len(authorized_ids),
                "releaseVersion": _release_version(str(manifest.get("releaseId") or "")),
                "mateStepCount": len(template.get("mateSteps") or []),
            }
        )

    if not candidates:
        return preview
    candidates.sort(
        key=lambda row: (
            int(row["authorizedTemplateCount"]),
            -int(row["releaseVersion"]),
            str(row["releaseId"]),
        )
    )
    selected = candidates[0]
    enriched = dict(selected["preview"])
    connection = enriched["proposedPatch"]["connection"]
    replacement = {
        "connectionId": connection.get("connectionId"),
        "sourceTemplateId": None,
        "portableTemplateId": connection.get("globalTemplateId"),
        "orientation": "same",
        "mateStepCount": selected["mateStepCount"],
    }
    enriched["sourceContextDigest"] = context.get("contextDigest")
    enriched["relationReleaseBinding"] = deepcopy(
        context.get("relationReleaseBinding")
    )
    enriched["portableReleaseTransition"] = {
        "transitionKind": "first_bind",
        "discoveryMode": "immutable_release_port_discovery",
        "sourceCatalogDigest": context.get("catalogDigest"),
        "sourceRelationReleaseBinding": deepcopy(
            context.get("relationReleaseBinding")
        ),
        "releaseId": selected["releaseId"],
        "catalogDigest": selected["preview"].get("catalogDigest"),
        "relationReleaseBinding": deepcopy(selected["binding"]),
        "replacements": [replacement],
        "selectionPolicy": (
            "活动目录无兼容端口时，在能按同一自然语言完整定位首次连接的"
            "不可变发布中，先选授权模板数最少者，再选最高版本。"
        ),
        "solidWorksExecuted": False,
        "requiresExplicitConfirmation": True,
    }
    return _rehash_command_preview(enriched)


def _enrich_blocked_command_with_portable_release_expansion(
    workspace: Path,
    context: dict[str, Any],
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    """Try one larger immutable release when the current release lacks a relation.

    Existing connections are re-bound in memory by their stable semantic port
    pairs.  A candidate is accepted only if its single catalog can both cover
    every existing connection and compile the new command as ready.
    """

    current_binding = context.get("relationReleaseBinding")
    if (
        not isinstance(current_binding, dict)
        or preview.get("status") != "blocked"
        or not preview.get("selectedModuleDefinitionId")
    ):
        return preview
    blocker_codes = {
        str(row.get("code") or "") for row in preview.get("blockers") or []
    }
    if "NO_COMPATIBLE_PORT_PAIR" not in blocker_codes:
        return preview

    try:
        recommendation = recommend_portable_relation_release(workspace, context)
    except PortableReleaseRecommendationError:
        return preview
    rows = [
        row
        for row in [
            recommendation.get("recommendation"),
            *(recommendation.get("alternatives") or []),
        ]
        if isinstance(row, dict)
        and row.get("releaseId") != current_binding.get("releaseId")
    ]
    for selected in rows:
        try:
            upgraded, _ = build_portable_release_context(
                workspace,
                context,
                expected_preview_digest=str(
                    recommendation.get("previewDigest") or ""
                ),
                release_id=str(selected.get("releaseId") or ""),
                target_context_id=str(context.get("contextId") or ""),
            )
            target_binding = upgraded.get("relationReleaseBinding") or {}
            manifest_path = _inside(
                workspace, Path(str(target_binding.get("releaseManifestPath") or ""))
            )
            candidate_catalog, candidate_manifest = load_released_relation_catalog(
                workspace, str(manifest_path)
            )
            expected_binding = _relation_release_binding(
                workspace, candidate_manifest, manifest_path
            )
            if expected_binding != target_binding:
                continue
            effective_payload = dict(payload)
            effective_payload["allowedTemplateIds"] = list(
                expected_binding.get("authorizedDrivingTemplateIds") or []
            )
            candidate_preview = preview_global_assembly_command(
                candidate_catalog, upgraded, effective_payload
            )
        except (
            GlobalAssemblyContextError,
            GlobalAssemblyWorkbenchError,
            PortableReleaseRecommendationError,
        ):
            continue
        if candidate_preview.get("status") != "ready" or not isinstance(
            (candidate_preview.get("proposedPatch") or {}).get("connection"), dict
        ):
            continue

        enriched = dict(candidate_preview)
        enriched["sourceContextDigest"] = context.get("contextDigest")
        enriched["relationReleaseBinding"] = deepcopy(current_binding)
        enriched["portableReleaseTransition"] = {
            "transitionKind": "expand",
            "discoveryMode": "bound_release_expansion",
            "sourceCatalogDigest": context.get("catalogDigest"),
            "sourceRelationReleaseBinding": deepcopy(current_binding),
            "sourceReleaseId": current_binding.get("releaseId"),
            "releaseId": selected.get("releaseId"),
            "catalogDigest": upgraded.get("catalogDigest"),
            "relationReleaseBinding": deepcopy(target_binding),
            "replacements": deepcopy(selected.get("replacements") or []),
            "upgradedConnections": deepcopy(upgraded.get("connections") or []),
            "selectionPolicy": (
                "在能够覆盖全部既有连接的发布中，选择首个还能编译本次新增连接的最小发布。"
            ),
            "solidWorksExecuted": False,
            "requiresExplicitConfirmation": True,
        }
        return _rehash_command_preview(enriched)
    return preview


def _definition_reference(
    definition: dict[str, Any], *, preferred_project_id: str | None = None
) -> str | None:
    aliases = list(definition.get("projectAliases") or [])
    if preferred_project_id:
        preferred = next(
            (
                row
                for row in aliases
                if str(row.get("projectId") or "").casefold()
                == preferred_project_id.casefold()
            ),
            None,
        )
        if preferred is not None:
            return (
                f"{preferred.get('projectId')}:{preferred.get('moduleToken')}"
            )
    if len(aliases) == 1:
        alias = aliases[0]
        return f"{alias.get('projectId')}:{alias.get('moduleToken')}"
    return None


def _native_role_modules_for_context(
    catalog: dict[str, Any],
    context: dict[str, Any],
    *,
    selected_definition_id: str,
) -> list[dict[str, Any]]:
    """Find native same-role modules already associated with context slots.

    A blocked request normally contains only the base/frame instance, not the
    native module that originally occupied its slot.  Existing installation
    templates provide the auditable bridge: if a context module exposes one
    endpoint of a complete installation template, the opposite module is a
    native occupant candidate.  No geometric interface is invented here.
    """

    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    ports = {
        str(row.get("globalPortId") or ""): row
        for row in catalog.get("semanticPorts") or []
    }
    role_overlay = build_module_role_overlay(catalog)
    roles = {
        str(row.get("moduleDefinitionId") or ""): str(row.get("primaryRole") or "")
        for row in role_overlay.get("modules") or []
    }
    selected_role = roles.get(selected_definition_id)
    if not selected_role:
        return []
    context_definition_ids = {
        str(row.get("moduleDefinitionId") or "")
        for row in context.get("instances") or []
    }
    result: dict[str, dict[str, Any]] = {}
    for template in catalog.get("connectionTemplates") or []:
        if "installation" not in set(template.get("purposes") or []):
            continue
        if (template.get("constraintEffect") or {}).get(
            "fullyLocatesAddedComponent"
        ) is not True:
            continue
        port_ids = {
            str(port_id)
            for field in ("candidatePortIdsA", "candidatePortIdsB")
            for port_id in template.get(field) or []
            if str(port_id)
        }
        definition_ids = {
            str((ports.get(port_id) or {}).get("moduleDefinitionId") or "")
            for port_id in port_ids
        }
        definition_ids.discard("")
        if not (definition_ids & context_definition_ids):
            continue
        for definition_id in definition_ids - context_definition_ids:
            if (
                definition_id != selected_definition_id
                and roles.get(definition_id) == selected_role
                and definition_id in definitions
            ):
                result[definition_id] = definitions[definition_id]
    return [result[key] for key in sorted(result)]


def _enrich_blocked_command_with_engineering_fallbacks(
    catalog: dict[str, Any],
    context: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    """Explain physical fallback choices when no direct port pair exists.

    This is deliberately read-only.  It never changes the proposed graph,
    authorizes a mate template, creates an adapter, or starts SolidWorks.
    """

    blocker_codes = {
        str(row.get("code") or "") for row in preview.get("blockers") or []
    }
    selected_definition_id = str(
        preview.get("selectedModuleDefinitionId") or ""
    )
    if (
        preview.get("status") != "blocked"
        or "NO_COMPATIBLE_PORT_PAIR" not in blocker_codes
        or not selected_definition_id
    ):
        return preview

    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    selected = definitions.get(selected_definition_id)
    if selected is None:
        return preview
    source_reference = _definition_reference(selected)
    if source_reference is None:
        return preview

    fallbacks: list[dict[str, Any]] = []
    requirement = str(preview.get("requirement") or "")
    for native in _native_role_modules_for_context(
        catalog,
        context,
        selected_definition_id=selected_definition_id,
    ):
        native_projects = {
            str(row.get("projectId") or "").casefold()
            for row in native.get("projectAliases") or []
        }
        context_projects = {
            str(alias.get("projectId") or "").casefold()
            for instance in context.get("instances") or []
            for alias in (
                definitions.get(str(instance.get("moduleDefinitionId") or ""), {}).get(
                    "projectAliases"
                )
                or []
            )
        }
        preferred_project = next(iter(native_projects & context_projects), None)
        target_reference = _definition_reference(
            native, preferred_project_id=preferred_project
        )
        if target_reference is None:
            continue
        try:
            substitution = compile_substitution_preview(
                catalog,
                build_module_role_overlay(catalog),
                source_module=source_reference,
                replaced_module=target_reference,
                requirement=requirement,
            )
        except (ValueError, TypeError):
            continue
        disposition = substitution.get("engineeringDisposition")
        if not isinstance(disposition, dict):
            continue
        fallbacks.append(
            {
                "kind": (
                    "physical_adapter_required"
                    if disposition.get("classification")
                    == "known_pattern_mismatch_adapter_candidate"
                    else "mechanical_interface_review_required"
                ),
                "sourceModule": source_reference,
                "sourceModuleDefinitionId": selected_definition_id,
                "nativeSlotModule": target_reference,
                "nativeSlotModuleDefinitionId": native.get("moduleDefinitionId"),
                "directCombinationAllowed": False,
                "cadLaunchDecision": "fail_closed_before_cad",
                "engineeringDisposition": deepcopy(disposition),
                "userFailureExplanation": deepcopy(
                    substitution.get("userFailureExplanation")
                ),
                "substitutionReport": deepcopy(
                    substitution.get("substitutionReport")
                ),
            }
        )
    if not fallbacks:
        return preview
    enriched = dict(preview)
    enriched["engineeringFallbacks"] = fallbacks
    enriched["fallbackPolicy"] = {
        "automaticFallbackExecutionAllowed": False,
        "requiresEngineerSelection": True,
        "solidWorksExecuted": False,
        "statement": (
            "直接接口不兼容；系统仅给出可审计的转接或接口评审路线，"
            "不得以原型位姿或近似孔位强行装配。"
        ),
    }
    return _rehash_command_preview(enriched)


def _preview_command_for_context(
    workspace: Path,
    context: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str] | None]:
    catalog, allowed_template_ids = _load_context_catalog_authority(
        workspace,
        context,
        explicit_catalog_path=payload.get("catalogPath"),
    )
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyWorkbenchError("上下文使用的目录版本已过期，请迁移或新建上下文。")
    try:
        effective_payload = dict(payload)
        if allowed_template_ids is not None:
            effective_payload["allowedTemplateIds"] = allowed_template_ids
        preview = preview_global_assembly_command(catalog, context, effective_payload)
        preview = _enrich_first_connection_with_portable_release(
            workspace, context, preview
        )
        preview = _enrich_unbound_blocked_command_from_portable_releases(
            workspace, context, effective_payload, preview
        )
        preview = _enrich_blocked_command_with_portable_release_expansion(
            workspace, context, effective_payload, preview
        )
        preview = _enrich_blocked_command_with_engineering_fallbacks(
            catalog, context, preview
        )
        return preview, catalog, allowed_template_ids
    except GlobalAssemblyContextError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def preview_command(workspace: Path, context_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    preview, _, _ = _preview_command_for_context(workspace, context, payload)
    return preview


def apply_command(workspace: Path, context_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    preview = payload.get("preview")
    if not isinstance(preview, dict):
        raise GlobalAssemblyWorkbenchError("preview必须是对象。")
    transition = preview.get("portableReleaseTransition")
    if transition is not None:
        if not isinstance(transition, dict):
            raise GlobalAssemblyWorkbenchError("portableReleaseTransition必须是对象。")
        binding = transition.get("relationReleaseBinding")
        if not isinstance(binding, dict):
            raise GlobalAssemblyWorkbenchError("便携发布切换缺少关系发布绑定。")
        manifest_path = _inside(workspace, Path(str(binding.get("releaseManifestPath") or "")))
        released_catalog, manifest = load_released_relation_catalog(
            workspace, str(manifest_path)
        )
        expected_binding = _relation_release_binding(
            workspace, manifest, manifest_path
        )
        if expected_binding != binding:
            raise GlobalAssemblyWorkbenchError(
                "便携发布清单已变化或预览绑定被修改，请重新预览。"
            )
        if transition.get("releaseId") != expected_binding.get("releaseId"):
            raise GlobalAssemblyWorkbenchError("便携发布编号与不可变绑定不一致。")
        if transition.get("catalogDigest") != released_catalog.get("catalogDigest"):
            raise GlobalAssemblyWorkbenchError("便携发布目录摘要与预览不一致。")
        connection = (preview.get("proposedPatch") or {}).get("connection") or {}
        template_id = str(connection.get("globalTemplateId") or "")
        if template_id not in set(
            expected_binding.get("authorizedDrivingTemplateIds") or []
        ):
            raise GlobalAssemblyWorkbenchError(
                "本次连接模板未获得所选便携发布的驱动授权。"
            )
        templates_by_id = {
            str(row.get("globalTemplateId") or ""): row
            for row in released_catalog.get("connectionTemplates") or []
        }
        template = templates_by_id.get(template_id)
        if not isinstance(template, dict):
            raise GlobalAssemblyWorkbenchError("便携发布中找不到本次连接模板。")
        port_a = str(connection.get("portAId") or "")
        port_b = str(connection.get("portBId") or "")
        candidates_a = {str(value) for value in template.get("candidatePortIdsA") or []}
        candidates_b = {str(value) for value in template.get("candidatePortIdsB") or []}
        port_pair_matches = (
            port_a in candidates_a and port_b in candidates_b
        ) or (
            port_a in candidates_b and port_b in candidates_a
        )
        if not port_pair_matches:
            raise GlobalAssemblyWorkbenchError("便携模板与本次语义端口对不匹配。")
        if (template.get("constraintEffect") or {}).get(
            "fullyLocatesAddedComponent"
        ) is not True:
            raise GlobalAssemblyWorkbenchError("便携模板没有完整定位声明。")
        replacements = transition.get("replacements") or []
        replacement_by_connection = {
            str(row.get("connectionId") or ""): row
            for row in replacements
            if isinstance(row, dict)
        }
        if transition.get("transitionKind") == "first_bind":
            replacement = replacement_by_connection.get(
                str(connection.get("connectionId") or "")
            )
            if not isinstance(replacement, dict) or str(
                replacement.get("portableTemplateId") or ""
            ) != template_id:
                raise GlobalAssemblyWorkbenchError(
                    "便携发布替换证据与本次连接不一致。"
                )
        elif transition.get("transitionKind") == "expand":
            upgraded_connections = transition.get("upgradedConnections")
            if not isinstance(upgraded_connections, list):
                raise GlobalAssemblyWorkbenchError("发布扩展缺少既有连接重映射结果。")
            if len(upgraded_connections) != len(context.get("connections") or []):
                raise GlobalAssemblyWorkbenchError("发布扩展的既有连接数量不一致。")
            for upgraded_connection in upgraded_connections:
                if not isinstance(upgraded_connection, dict):
                    raise GlobalAssemblyWorkbenchError("发布扩展连接格式非法。")
                upgraded_id = str(upgraded_connection.get("connectionId") or "")
                upgraded_template_id = str(
                    upgraded_connection.get("globalTemplateId") or ""
                )
                upgraded_template = templates_by_id.get(upgraded_template_id)
                upgraded_replacement = replacement_by_connection.get(upgraded_id)
                if (
                    not isinstance(upgraded_template, dict)
                    or upgraded_template_id
                    not in set(expected_binding.get("authorizedDrivingTemplateIds") or [])
                    or (upgraded_template.get("constraintEffect") or {}).get(
                        "fullyLocatesAddedComponent"
                    )
                    is not True
                    or not isinstance(upgraded_replacement, dict)
                    or str(upgraded_replacement.get("portableTemplateId") or "")
                    != upgraded_template_id
                ):
                    raise GlobalAssemblyWorkbenchError(
                        f"既有连接{upgraded_id}没有有效的便携发布替换证据。"
                    )
                upgraded_port_a = str(upgraded_connection.get("portAId") or "")
                upgraded_port_b = str(upgraded_connection.get("portBId") or "")
                upgraded_candidates_a = {
                    str(value)
                    for value in upgraded_template.get("candidatePortIdsA") or []
                }
                upgraded_candidates_b = {
                    str(value)
                    for value in upgraded_template.get("candidatePortIdsB") or []
                }
                if not (
                    (
                        upgraded_port_a in upgraded_candidates_a
                        and upgraded_port_b in upgraded_candidates_b
                    )
                    or (
                        upgraded_port_a in upgraded_candidates_b
                        and upgraded_port_b in upgraded_candidates_a
                    )
                ):
                    raise GlobalAssemblyWorkbenchError(
                        f"既有连接{upgraded_id}与扩展发布端口对不匹配。"
                    )
        else:
            raise GlobalAssemblyWorkbenchError("未知的便携发布切换类型。")
    try:
        updated = apply_global_command_preview(
            context,
            preview,
            preview_digest=str(payload.get("previewDigest") or ""),
            confirmed=bool(payload.get("confirmed")),
        )
    except GlobalAssemblyContextError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
    path = context_path(workspace, context_id)
    _archive_context_revision(path, context)
    _write(path, updated)
    record_graph_turn(path, updated, preview)
    return {
        "success": True,
        "contextPath": str(path),
        "context": updated,
        "message": "装配图补丁已写入上下文；尚未执行SolidWorks，也未进行碰撞评估。",
    }


def apply_command_sequence(
    workspace: Path, context_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Atomically apply an ordered natural-language command sequence.

    All previews are compiled against the preceding in-memory revision.  If any
    turn is ambiguous or blocked, no context or conversation file is changed.
    """

    if not bool(payload.get("confirmed")):
        raise GlobalAssemblyWorkbenchError("必须显式confirmed=true才能提交命令序列。")
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        raise GlobalAssemblyWorkbenchError("commands必须是非空数组。")
    original = load_context(workspace, context_id)
    current = original
    staged: list[tuple[dict[str, Any], dict[str, Any]]] = []
    turns: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        if not isinstance(command, dict):
            raise GlobalAssemblyWorkbenchError(f"第{index}条命令必须是对象。")
        try:
            effective_command = dict(command)
            if (
                "relationExecutionMode" not in effective_command
                and payload.get("relationExecutionMode") is not None
            ):
                effective_command["relationExecutionMode"] = payload.get(
                    "relationExecutionMode"
                )
            if (
                current.get("relationReleaseBinding") is None
                and payload.get("catalogPath")
            ):
                effective_command["catalogPath"] = payload.get("catalogPath")
            preview, catalog, allowed_template_ids = _preview_command_for_context(
                workspace, current, effective_command
            )
        except (GlobalAssemblyContextError, GlobalAssemblyWorkbenchError) as exc:
            raise GlobalAssemblyWorkbenchError(f"第{index}条命令解析失败：{exc}") from exc
        relation_preview = None
        relation_intent = preview.get("relationIntent") or {}
        if (
            preview.get("status") != "ready"
            and relation_intent.get("primaryRelation")
            not in {None, "unspecified", "installation"}
        ):
            instance_by_definition: dict[str, list[str]] = {}
            for instance in current.get("instances") or []:
                instance_by_definition.setdefault(
                    str(instance.get("moduleDefinitionId") or ""), []
                ).append(str(instance.get("instanceId") or ""))
            mentioned_definitions = []
            for alternative in preview.get("moduleAlternatives") or []:
                definition_id = str(
                    alternative.get("moduleDefinitionId") or ""
                )
                if (
                    definition_id in instance_by_definition
                    and definition_id not in mentioned_definitions
                ):
                    mentioned_definitions.append(definition_id)
            if (
                len(mentioned_definitions) == 2
                and all(
                    len(instance_by_definition[definition_id]) == 1
                    for definition_id in mentioned_definitions
                )
            ):
                relation_operation = _relation_operation_for_command(command)
                relation_payload = {
                    "operation": relation_operation,
                    "requirement": command.get("requirement"),
                    "instanceAId": instance_by_definition[
                        mentioned_definitions[0]
                    ][0],
                    "instanceBId": instance_by_definition[
                        mentioned_definitions[1]
                    ][0],
                }
                if allowed_template_ids is not None:
                    relation_payload["allowedTemplateIds"] = (
                        _released_relation_template_ids_for_operation(
                            catalog,
                            allowed_template_ids,
                            relation_operation,
                        )
                    )
                try:
                    relation_preview = preview_global_relation_edit(
                        catalog, current, relation_payload
                    )
                except GlobalRelationEditError as exc:
                    raise GlobalAssemblyWorkbenchError(
                        f"第{index}条关系命令解析失败：{exc}"
                    ) from exc
        effective_preview = relation_preview or preview
        turn = {
            "order": index,
            "requirement": command.get("requirement"),
            "status": effective_preview.get("status"),
            "previewDigest": effective_preview.get("previewDigest"),
            "resolution": (
                "existing_instance_relation_edit"
                if relation_preview is not None
                else preview.get("resolution")
            ),
            "selectedModuleDefinitionId": (
                None
                if relation_preview is not None
                else preview.get("selectedModuleDefinitionId")
            ),
            "blockers": effective_preview.get("blockers") or [],
        }
        turns.append(turn)
        if effective_preview.get("status") != "ready":
            return {
                "success": False,
                "status": "needs_confirmation"
                if effective_preview.get("status") == "needs_confirmation"
                else "blocked",
                "failedAtOrder": index,
                "contextModified": False,
                "sourceContextRevision": original.get("revision"),
                "sourceContextDigest": original.get("contextDigest"),
                "turns": turns,
                "preview": effective_preview,
                "message": "命令序列未写入；请先消除当前轮次的歧义或阻塞。",
            }
        try:
            if relation_preview is not None:
                updated = apply_global_relation_edit(
                    current,
                    relation_preview,
                    preview_digest=str(relation_preview["previewDigest"]),
                    confirmed=True,
                )
            else:
                updated = apply_global_command_preview(
                    current,
                    preview,
                    preview_digest=str(preview["previewDigest"]),
                    confirmed=True,
                )
        except (GlobalAssemblyContextError, GlobalRelationEditError) as exc:
            raise GlobalAssemblyWorkbenchError(f"第{index}条命令应用失败：{exc}") from exc
        staged.append((updated, effective_preview))
        current = updated

    path = context_path(workspace, context_id)
    _archive_context_revision(path, original)
    for intermediate, _ in staged[:-1]:
        _archive_context_revision(path, intermediate)
    _write(path, current)
    for intermediate, preview in staged:
        record_graph_turn(path, intermediate, preview)
    return {
        "success": True,
        "status": "committed",
        "contextModified": True,
        "sourceContextRevision": original.get("revision"),
        "finalContextRevision": current.get("revision"),
        "finalContextDigest": current.get("contextDigest"),
        "turnCount": len(turns),
        "turns": turns,
        "contextPath": str(path),
        "context": current,
        "message": "有序自然语言命令已原子写入装配图；CAD执行仍由后续任务显式触发。",
    }


def undo_latest_command(
    workspace: Path, context_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Restore the graph revision preceding the latest unexecuted command."""

    if not bool(payload.get("confirmed")):
        raise GlobalAssemblyWorkbenchError("必须显式confirmed=true才能撤销上一轮。")
    current = load_context(workspace, context_id)
    path = context_path(workspace, context_id)
    revision = int(current.get("revision") or 0)
    snapshot_path, restored = _load_parent_revision_snapshot(path, current)
    try:
        validate_global_assembly_context(restored)
    except GlobalAssemblyContextError as exc:
        raise GlobalAssemblyWorkbenchError(f"上一修订快照无效：{exc}") from exc
    if restored.get("contextId") != current.get("contextId"):
        raise GlobalAssemblyWorkbenchError("恢复快照属于其他装配上下文。")
    restored_revision = restored.get("revision")
    if restored_revision is None or int(restored_revision) != revision - 1:
        raise GlobalAssemblyWorkbenchError("恢复快照修订号与预期不一致。")

    try:
        ledger, removed_turn = rollback_latest_graph_turn(
            path,
            current,
            expected_revision=int(payload.get("expectedRevision") or -1),
            expected_context_digest=str(payload.get("expectedContextDigest") or ""),
        )
    except (ValueError, TypeError) as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc

    _archive_context_revision(path, current)
    _write(path, restored)
    reset_temporary_ports(path, restored)
    return {
        "success": True,
        "status": "rolled_back",
        "contextPath": str(path),
        "snapshotPath": str(snapshot_path),
        "context": restored,
        "conversation": ledger,
        "rolledBackTurn": removed_turn,
        "message": "已撤销上一轮尚未执行CAD的装配图修改；更早历史与恢复证据均保留。",
    }


def compile_execution_manifest(workspace: Path, context_id: str) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    catalog, _ = _load_context_catalog_authority(workspace, context)
    try:
        return compile_global_assembly_execution_manifest(workspace, catalog, context)
    except GlobalAssemblyCompilerError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def compile_project_adapter_plan(
    workspace: Path,
    context_id: str,
    *,
    assembly_mode: str = "mate_driven_port_assembly",
) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    catalog, _ = _load_context_catalog_authority(workspace, context)
    try:
        manifest = compile_global_assembly_execution_manifest(workspace, catalog, context)
        return compile_global_project_adapter_plan(
            workspace,
            catalog,
            context,
            manifest,
            assembly_mode=assembly_mode,
        )
    except (GlobalAssemblyCompilerError, GlobalProjectAdapterPlanError) as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def compile_transaction_dag(
    workspace: Path,
    context_id: str,
    *,
    base_instance_id: str | None = None,
    positioning_standard_id: str | None = None,
    catalog_path: str | None = None,
) -> dict[str, Any]:
    """Compile a context without consulting a project-specific fixed sequence."""

    context = load_context(workspace, context_id)
    catalog, _ = _load_context_catalog_authority(
        workspace, context, explicit_catalog_path=catalog_path
    )
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyWorkbenchError("上下文使用的目录版本与请求目录不一致。")
    try:
        return compile_global_assembly_transaction_dag(
            catalog,
            context,
            base_instance_id=base_instance_id,
            positioning_standard=_load_selected_positioning_standard(
                positioning_standard_id
            ),
        )
    except GlobalAssemblyTransactionError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc


def compile_cad_transaction_manifest(
    workspace: Path,
    context_id: str,
    *,
    base_instance_id: str | None = None,
    positioning_standard_id: str | None = None,
    catalog_path: str | None = None,
    driving_strategy_selections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile endpoint-complete CAD packets without running SolidWorks."""

    context = load_context(workspace, context_id)
    catalog, _ = _load_context_catalog_authority(
        workspace, context, explicit_catalog_path=catalog_path
    )
    if context.get("catalogDigest") != catalog.get("catalogDigest"):
        raise GlobalAssemblyWorkbenchError("上下文使用的目录版本与请求目录不一致。")
    registry_path = _inside(
        workspace, DEFAULT_RELATION_VALIDATION_PRECONDITION_REGISTRY
    )
    validation_precondition_registry = (
        _read(registry_path) if registry_path.is_file() else None
    )
    driving_safety_registry_path = _inside(
        workspace, DEFAULT_RELATION_DRIVING_SAFETY_REGISTRY
    )
    driving_safety_registry = (
        _read(driving_safety_registry_path)
        if driving_safety_registry_path.is_file()
        else None
    )
    try:
        return compile_global_cad_transaction_manifest(
            catalog,
            context,
            base_instance_id=base_instance_id,
            positioning_standard=_load_selected_positioning_standard(
                positioning_standard_id
            ),
            validation_precondition_registry=validation_precondition_registry,
            validation_precondition_registry_path=(
                str(DEFAULT_RELATION_VALIDATION_PRECONDITION_REGISTRY)
                if validation_precondition_registry is not None
                else None
            ),
            driving_safety_registry=driving_safety_registry,
            driving_safety_registry_path=(
                str(DEFAULT_RELATION_DRIVING_SAFETY_REGISTRY)
                if driving_safety_registry is not None
                else None
            ),
            driving_strategy_selections=driving_strategy_selections,
        )
    except GlobalAssemblyTransactionError as exc:
        raise GlobalAssemblyWorkbenchError(str(exc)) from exc
