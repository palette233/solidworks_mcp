"""Execution planning for one generic CAD transaction packet."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .global_cad_base_context_cache import (
    BASE_CONTEXT_WRAPPER_ADAPTER_VERSION,
    build_base_context_cache_descriptor,
)

from .global_relation_catalog_release import (
    GlobalRelationCatalogReleaseError,
    load_bound_relation_catalog_release,
)
from .global_relation_semantics import normalize_template_relation_profile


GLOBAL_CAD_PACKET_EXECUTION_PLAN_SCHEMA = "global-cad-packet-execution-plan/v1"


class GlobalCadPacketExecutionError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _inside(workspace: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalCadPacketExecutionError(f"无法读取JSON证据：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GlobalCadPacketExecutionError(f"JSON证据根节点必须为对象：{path}")
    return value


def validate_cad_manifest_release_authority(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    packets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Revalidate an optional relation release at the CAD execution boundary.

    Historical manifests remain executable without a release binding.  Once a
    manifest declares one, however, every selected packet must carry the same
    immutable binding and may use only explicitly authorized driving templates.
    """

    workspace = workspace.resolve()
    selected = list(packets if packets is not None else manifest.get("packets") or [])
    binding = manifest.get("relationReleaseBinding")
    packet_bindings = [packet.get("relationReleaseBinding") for packet in selected]
    if binding is None:
        if any(value is not None for value in packet_bindings):
            raise GlobalCadPacketExecutionError(
                "数据包声明了关系发布绑定，但CAD事务清单未声明。"
            )
        return {
            "status": "legacy_unbound",
            "binding": None,
            "authorizedDrivingTemplateIds": [],
            "authorizedValidationTemplateIds": [],
            "authorizedTemplateCombinationIds": [],
            "usedDrivingTemplateIds": [],
            "usedValidationTemplateIds": [],
            "usedTemplateIds": [],
            "usedTemplateCombinationIds": [],
        }
    if not isinstance(binding, dict):
        raise GlobalCadPacketExecutionError("CAD事务清单的关系发布绑定必须是对象。")
    try:
        catalog, _release = load_bound_relation_catalog_release(
            binding,
            workspace_root=workspace,
        )
    except GlobalRelationCatalogReleaseError as exc:
        raise GlobalCadPacketExecutionError(f"关系发布授权复核失败：{exc}") from exc
    if manifest.get("catalogDigest") != binding.get("catalogDigest"):
        raise GlobalCadPacketExecutionError("CAD事务清单与关系发布目录摘要不一致。")
    if catalog.get("catalogDigest") != binding.get("catalogDigest"):
        raise GlobalCadPacketExecutionError("现场发布目录与关系发布绑定摘要不一致。")
    authorized = {
        str(value)
        for value in binding.get("authorizedDrivingTemplateIds") or []
        if str(value)
    }
    authorized_combinations = {
        str(value)
        for value in binding.get("authorizedTemplateCombinationIds") or []
        if str(value)
    }
    template_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    authorized_validation = {
        template_id
        for template_id, template in template_by_id.items()
        if normalize_template_relation_profile(template).get("drivesPlacement") is False
        and int(
            normalize_template_relation_profile(template).get(
                "validationMateStepCount"
            )
            or 0
        )
        > 0
    }
    combination_by_id = {
        str(row.get("globalCombinationId") or ""): row
        for row in catalog.get("templateCombinations") or []
    }
    used: set[str] = set()
    used_driving: set[str] = set()
    used_validation: set[str] = set()
    used_combinations: set[str] = set()
    for packet in selected:
        if packet.get("relationReleaseBinding") != binding:
            raise GlobalCadPacketExecutionError(
                f"数据包{packet.get('packetId')}与清单的关系发布绑定不一致。"
            )
        packet_template_ids: set[str] = set()
        read_only_packet = str(packet.get("operation") or "").upper() == "VERIFY_RELATION"
        for connection in packet.get("connections") or []:
            template_id = str(connection.get("globalTemplateId") or "").strip()
            if not template_id:
                raise GlobalCadPacketExecutionError(
                    f"数据包{packet.get('packetId')}包含未登记模板的连接。"
                )
            used.add(template_id)
            packet_template_ids.add(template_id)
            if read_only_packet:
                used_validation.add(template_id)
            else:
                used_driving.add(template_id)
        packet_authorized = authorized | authorized_validation if read_only_packet else authorized
        unauthorized_packet = sorted(packet_template_ids - packet_authorized)
        if unauthorized_packet:
            label = "只读验证" if read_only_packet else "驱动"
            raise GlobalCadPacketExecutionError(
                f"CAD事务数据包使用了未获{label}授权的关系模板："
                + ", ".join(unauthorized_packet)
            )
        if read_only_packet:
            continue
        for combination_id in authorized_combinations:
            combination = combination_by_id.get(combination_id)
            if combination is None:
                raise GlobalCadPacketExecutionError(
                    f"发布绑定引用了目录中不存在的模板组合：{combination_id}"
                )
            members = {
                str(value)
                for value in combination.get("memberGlobalTemplateIds") or []
                if str(value)
            }
            overlap = members & packet_template_ids
            if overlap and not members.issubset(packet_template_ids):
                raise GlobalCadPacketExecutionError(
                    f"数据包{packet.get('packetId')}只使用了模板组合{combination_id}的部分成员。"
                )
            if members and members.issubset(packet_template_ids):
                used_combinations.add(combination_id)
    return {
        "status": "verified",
        "binding": copy.deepcopy(binding),
        "authorizedDrivingTemplateIds": sorted(authorized),
        "authorizedValidationTemplateIds": sorted(authorized_validation),
        "authorizedTemplateCombinationIds": sorted(authorized_combinations),
        "usedDrivingTemplateIds": sorted(used_driving),
        "usedValidationTemplateIds": sorted(used_validation),
        "usedTemplateIds": sorted(used),
        "usedTemplateCombinationIds": sorted(used_combinations),
    }


def _base_context_modules(
    effective_graph: dict[str, Any], target_module_token: str
) -> list[tuple[str, list[float]]]:
    policy = effective_graph.get("BaseGraphPolicy") or effective_graph.get(
        "baseGraphPolicy"
    ) or {}
    declared = policy.get("moduleTokens") or policy.get("ModuleTokens") or []
    tokens = sorted({str(value).strip().upper() for value in declared if str(value).strip()})
    if not tokens:
        modules = effective_graph.get("Modules") or effective_graph.get("modules") or []
        tokens = sorted(
            {
                str(module.get("ModuleToken") or module.get("moduleToken") or "")
                .strip()
                .upper()
                for module in modules
                if str(module.get("ModuleToken") or module.get("moduleToken") or "")
                .strip()
                .upper()
                != target_module_token
            }
        )
    modules = effective_graph.get("Modules") or effective_graph.get("modules") or []
    result: list[tuple[str, list[float]]] = []
    for token in tokens:
        matches = [
            module
            for module in modules
            if str(module.get("ModuleToken") or module.get("moduleToken") or "")
            .strip()
            .upper()
            == token
        ]
        if len(matches) != 1:
            raise GlobalCadPacketExecutionError(
                f"有效配合图未唯一记录基座上下文模组{token}的位姿。"
            )
        raw_transform = matches[0].get("SourceTransform") or matches[0].get(
            "sourceTransform"
        )
        try:
            transform = [float(value) for value in raw_transform]
        except (TypeError, ValueError) as exc:
            raise GlobalCadPacketExecutionError(
                f"基座上下文模组{token}的SourceTransform不可用。"
            ) from exc
        if len(transform) != 16:
            raise GlobalCadPacketExecutionError(
                f"基座上下文模组{token}必须记录16值SourceTransform。"
            )
        result.append((token, transform))
    return result


def _verified_composite_base_context(
    effective_graph_path: Path,
    base_modules: list[tuple[str, list[float]]],
) -> tuple[Path, Path, dict[str, Any]]:
    """Resolve a uniquely attested step00 context for a multi-module base."""

    directory = effective_graph_path.parent
    accepted: list[tuple[Path, Path, dict[str, Any]]] = []
    required_tokens = {token for token, _ in base_modules}
    for assembly in sorted(directory.glob("step00_*_context.SLDASM")):
        evidence_path = assembly.with_suffix(".result.json")
        if not evidence_path.is_file():
            continue
        evidence = _read_json_object(evidence_path)
        tool = evidence.get("toolResult") or {}
        observed_tokens = {
            str(row.get("ModuleToken") or "").strip().upper()
            for row in tool.get("ComponentStatuses") or []
            if str(row.get("ModuleToken") or "").strip()
        }
        output = Path(str(evidence.get("outputAssemblyPath") or "")).resolve()
        if (
            evidence.get("success") is True
            and tool.get("Success") is True
            and tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and output == assembly.resolve()
            and observed_tokens == required_tokens
            and assembly.is_file()
        ):
            accepted.append((assembly.resolve(), evidence_path.resolve(), evidence))
    if len(accepted) != 1:
        raise GlobalCadPacketExecutionError(
            "多模组基座需要唯一的step00上下文装配体及成功的保存/关闭/重开证据；"
            f"当前找到{len(accepted)}个。"
        )
    return accepted[0]


def _graph_target_module_token(
    effective_graph: dict[str, Any], project_alias: str
) -> str:
    tokens = [
        str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        for module in effective_graph.get("Modules")
        or effective_graph.get("modules")
        or []
        if str(module.get("ModuleToken") or module.get("moduleToken") or "").strip()
    ]
    alias = project_alias.strip().upper()
    exact = [token for token in tokens if token == alias]
    if len(exact) == 1:
        return exact[0]
    suffix = [token for token in tokens if token.endswith(alias)]
    if len(suffix) == 1:
        return suffix[0]
    raise GlobalCadPacketExecutionError(
        f"项目别名{project_alias}无法唯一映射到有效配合图中的目标模组令牌。"
    )


def _target_module_alias_from_packet(
    packet: dict[str, Any], *, preferred_project: str | None = None
) -> str:
    """Resolve the inserted module token without confusing slot ownership.

    Cross-project templates are often evidenced by the project that owns the
    provided slot.  That provenance project is not necessarily the project of
    the module being inserted.  A project filter is therefore applied only if
    it matches at least one target alias; otherwise an already unique target
    alias remains authoritative.
    """

    aliases = list(packet.get("targetProjectAliases") or [])
    project = str(preferred_project or "").strip().lower()
    if project:
        matching = [
            row
            for row in aliases
            if str(row.get("projectId") or "").strip().lower() == project
        ]
        if matching:
            aliases = matching
    tokens = sorted(
        {
            str(row.get("moduleToken") or "").strip().upper()
            for row in aliases
            if str(row.get("moduleToken") or "").strip()
        }
    )
    if len(tokens) != 1:
        raise GlobalCadPacketExecutionError("无法从模组证据唯一解析目标模组令牌。")
    return tokens[0]


def _normalized_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 12)
    except (TypeError, ValueError) as exc:
        raise GlobalCadPacketExecutionError(
            f"配合参数{value!r}不是有效数值。"
        ) from exc


def _mate_identity(mate: dict[str, Any]) -> tuple[str, int, int, float | None, float | None]:
    """Return the CAD-significant identity used by packet/graph coverage checks."""

    name = str(mate.get("mateName") or mate.get("MateName") or "").strip()
    if not name:
        raise GlobalCadPacketExecutionError("配合记录缺少mateName/MateName。")
    try:
        mate_type = int(mate.get("mateType", mate.get("MateType")))
        alignment = int(mate.get("alignment", mate.get("Alignment")))
    except (TypeError, ValueError) as exc:
        raise GlobalCadPacketExecutionError(
            f"配合{name}缺少有效的类型或对齐参数。"
        ) from exc
    advanced = mate.get("advancedOptions") or mate.get("AdvancedOptions") or {}
    distance = mate.get("distance", mate.get("Distance"))
    if distance is None:
        distance = advanced.get("distanceMeters")
    angle = mate.get("angle", mate.get("Angle"))
    if angle is None:
        angle = advanced.get("angleRadians")
    if angle is None and advanced.get("angleDegrees") is not None:
        angle = math.radians(float(advanced["angleDegrees"]))
    return (
        name,
        mate_type,
        alignment,
        _normalized_optional_float(distance),
        _normalized_optional_float(angle),
    )


def _mate_identity_record(
    identity: tuple[str, int, int, float | None, float | None]
) -> dict[str, Any]:
    name, mate_type, alignment, distance, angle = identity
    return {
        "mateName": name,
        "mateType": mate_type,
        "alignment": alignment,
        "distance": distance,
        "angle": angle,
    }


def _is_context_insert_rebuildable(mate: dict[str, Any]) -> bool:
    """Match the live context-insert adapter's supported mate surface.

    Historical graphs named the capability flag ``IsBasicTwoFaceRebuildable``.
    A width mate is intentionally four-face and therefore false under that old
    pair-demo flag, while the current context adapter rebuilds it from the two
    width and two tab endpoint indices.  Treat only a structurally complete
    width mate as the explicit exception.
    """

    basic = mate.get(
        "IsBasicTwoFaceRebuildable",
        mate.get("isBasicTwoFaceRebuildable", True),
    )
    if basic is not False:
        return True
    try:
        mate_type = int(mate.get("MateType", mate.get("mateType")))
    except (TypeError, ValueError):
        return False
    endpoints = mate.get("Endpoints") or mate.get("endpoints") or []
    advanced = mate.get("AdvancedOptions") or mate.get("advancedOptions") or {}
    if mate_type == 21:
        # Slot mates were marked non-basic by the historical two-face demo even
        # though the live adapter can rebuild them deterministically once the
        # exported advanced constraint option is present.  Free is a valid
        # value (0), so test key presence rather than truthiness.
        return bool(
            len(endpoints) == 2
            and (
                "SlotConstraint" in advanced
                or "slotConstraint" in advanced
            )
            and advanced.get("SlotConstraint", advanced.get("slotConstraint"))
            is not None
        )
    if mate_type != 11:
        return False
    width_indices = advanced.get("WidthEndpointIndices") or advanced.get(
        "widthEndpointIndices"
    ) or []
    tab_indices = advanced.get("TabEndpointIndices") or advanced.get(
        "tabEndpointIndices"
    ) or []
    return bool(
        len(endpoints) == 4
        and len(width_indices) == 2
        and len(tab_indices) == 2
        and sorted([*width_indices, *tab_indices]) == [0, 1, 2, 3]
    )


def _effective_graph_mate_coverage(
    packet: dict[str, Any],
    effective_graph: dict[str, Any],
    target_module_token: str,
) -> dict[str, Any]:
    """Require the effective graph to rebuild exactly the mates requested by a packet.

    The downstream CAD adapter rebuilds every active, basic two-face mate involving the
    target module in the selected effective graph.  A subset check is therefore unsafe:
    a graph with a hidden extra mate would change the assembly beyond the transaction,
    while a missing mate would silently under-constrain the requested connection set.
    """

    requested_mates = [
        mate
        for connection in packet.get("connections") or []
        for mate in connection.get("mates") or []
    ]
    requested_driving_mates = [
        mate
        for mate in requested_mates
        if str((mate.get("advancedOptions") or {}).get("applicationMode") or "driving")
        != "validate_only"
    ]
    requested_validation_relations = [
        mate
        for mate in requested_mates
        if str((mate.get("advancedOptions") or {}).get("applicationMode") or "driving")
        == "validate_only"
    ]
    graph_mates = []
    for mate in effective_graph.get("Mates") or effective_graph.get("mates") or []:
        tokens = {
            str(value).strip().upper()
            for value in mate.get("ModuleTokens") or mate.get("moduleTokens") or []
            if str(value).strip()
        }
        suppressed = bool(mate.get("IsSuppressed", mate.get("isSuppressed", False)))
        rebuildable = _is_context_insert_rebuildable(mate)
        if target_module_token in tokens and not suppressed and rebuildable:
            graph_mates.append(mate)

    requested = Counter(_mate_identity(mate) for mate in requested_driving_mates)
    observed = Counter(_mate_identity(mate) for mate in graph_mates)
    missing = list((requested - observed).elements())
    unexpected = list((observed - requested).elements())
    if missing or unexpected:
        raise GlobalCadPacketExecutionError(
            "有效配合图与事务请求的目标模组配合覆盖不一致："
            f"缺少{[_mate_identity_record(row) for row in missing]}；"
            f"多出{[_mate_identity_record(row) for row in unexpected]}。"
        )
    validation_remaining = Counter(
        _mate_identity(mate) for mate in requested_validation_relations
    )
    matched_validations: list[dict[str, Any]] = []
    audit = effective_graph.get("SemanticAssemblyPlanAudit") or {}
    validations = audit.get("ValidationRelations") or audit.get("validationRelations") or []
    for relation in validations:
        relation_name = str(
            relation.get("RelationName") or relation.get("relationName") or ""
        ).strip()
        relation_type = int(
            relation.get("RelationType", relation.get("relationType", -1))
        )
        relation_distance = _normalized_optional_float(
            relation.get(
                "ExpectedDistanceMeters", relation.get("expectedDistanceMeters")
            )
        )
        relation_angle = _normalized_optional_float(
            relation.get("ExpectedAngleRadians", relation.get("expectedAngleRadians"))
        )
        identity = next(
            (
                candidate
                for candidate, count in validation_remaining.items()
                if count > 0
                and candidate[0] == relation_name
                and candidate[1] == relation_type
                and candidate[3] == relation_distance
                and candidate[4] == relation_angle
            ),
            None,
        )
        if identity is not None:
            matched_validations.append(copy.deepcopy(relation))
            validation_remaining[identity] -= 1
    missing_validations = list(validation_remaining.elements())
    if missing_validations:
        raise GlobalCadPacketExecutionError(
            "有效配合图缺少事务请求的只读验证关系："
            f"{[_mate_identity_record(row) for row in missing_validations]}。"
        )
    return {
        "status": "exact",
        "targetModuleToken": target_module_token,
        "requestedMateCount": sum(requested.values()),
        "requestedDrivingMateCount": sum(requested.values()),
        "graphTargetMateCount": sum(observed.values()),
        "requestedValidationRelationCount": len(requested_validation_relations),
        "graphMatchedValidationRelationCount": len(matched_validations),
        "requestedMates": [
            _mate_identity_record(row)
            for row in sorted(requested.elements(), key=repr)
        ],
        "graphTargetMates": [
            _mate_identity_record(row)
            for row in sorted(observed.elements(), key=repr)
        ],
        "unmatchedRequested": [],
        "unexpectedGraphMates": [],
        "validationRelations": matched_validations,
    }


def _calibrated_static_snapshot_coverage(
    packet: dict[str, Any],
    effective_graph: dict[str, Any],
    target_module_token: str,
) -> dict[str, Any]:
    """Validate an explicitly selected project-calibrated static snapshot.

    This mode intentionally does not create the portable template's requested
    mates.  It reproduces a versioned case pose and internal leaf state instead,
    so its authority and limitations must be visible in the execution evidence.
    """

    override = packet.get("drivingExecutionOverride") or {}
    if override.get("authority") != "prototype-calibrated-explicit-fallback":
        raise GlobalCadPacketExecutionError("标定静态快照缺少显式回退授权。")
    if override.get("portable") is not False:
        raise GlobalCadPacketExecutionError("标定静态快照不得声明为可迁移端口。")
    policy = (
        (effective_graph.get("SemanticAssemblyPlanAudit") or {}).get(
            "staticSnapshotPolicy"
        )
        or {}
    )
    edit_policy = effective_graph.get("EditPolicy") or {}
    case_anchors = {
        str(value).strip().upper()
        for value in edit_policy.get("caseAnchoredModuleTokens") or []
        if str(value).strip()
    }
    leaf_anchors = list(edit_policy.get("targetLeafPoseAnchors") or [])
    active_mates = [
        mate
        for mate in effective_graph.get("Mates") or effective_graph.get("mates") or []
        if not bool(mate.get("IsSuppressed", mate.get("isSuppressed", False)))
    ]
    if target_module_token not in case_anchors:
        raise GlobalCadPacketExecutionError("静态快照未锚定目标模组顶层位姿。")
    if not leaf_anchors:
        raise GlobalCadPacketExecutionError("静态快照缺少柔性模组内部叶件状态锚点。")
    if active_mates:
        raise GlobalCadPacketExecutionError("静态快照回退不得混入活动驱动配合。")
    if not policy or policy.get("motionSemanticsPreserved") is not False:
        raise GlobalCadPacketExecutionError("静态快照未声明运动语义不保留边界。")
    requested = _requested_mates(packet)
    retained_names = {
        str(value)
        for value in policy.get("sourceDrivingMatesRetainedAsEvidence") or []
    }
    requested_names = {str(mate.get("mateName") or "") for mate in requested}
    if requested_names != retained_names:
        raise GlobalCadPacketExecutionError(
            "静态快照保留的来源配合集与事务模板不一致。"
        )
    return {
        "status": "explicit_project_calibrated_static_snapshot",
        "targetModuleToken": target_module_token,
        "requestedMateCount": len(requested),
        "requestedDrivingMateCount": 0,
        "graphTargetMateCount": 0,
        "requestedValidationRelationCount": 0,
        "graphMatchedValidationRelationCount": 0,
        "requestedMatesRetainedAsProvenance": sorted(requested_names),
        "caseAnchorCount": len(case_anchors),
        "internalLeafPoseAnchorCount": len(leaf_anchors),
        "portable": False,
        "scope": override.get("scope"),
        "strategyId": override.get("strategyId"),
        "unmatchedRequested": [],
        "unexpectedGraphMates": [],
        "validationRelations": [],
    }


def _transaction_effective_graph_view(
    effective_graph: dict[str, Any],
    target_module_token: str,
) -> dict[str, Any]:
    """Project an authoritative graph onto the modules used by this insertion.

    Exact mate coverage has already been checked before this function is called.
    The projection prevents the live adapter from trying to resolve unrelated
    prototype modules that are not yet present in the cumulative checkpoint.
    """

    module_key = "Modules" if "Modules" in effective_graph else "modules"
    mate_key = "Mates" if "Mates" in effective_graph else "mates"
    target_mates: list[dict[str, Any]] = []
    execution_tokens = {target_module_token}
    for mate in effective_graph.get(mate_key) or []:
        tokens = {
            str(value).strip().upper()
            for value in mate.get("ModuleTokens") or mate.get("moduleTokens") or []
            if str(value).strip()
        }
        suppressed = bool(mate.get("IsSuppressed", mate.get("isSuppressed", False)))
        rebuildable = _is_context_insert_rebuildable(mate)
        if target_module_token in tokens and not suppressed and rebuildable:
            target_mates.append(copy.deepcopy(mate))
            execution_tokens.update(tokens)

    modules = [
        copy.deepcopy(module)
        for module in effective_graph.get(module_key) or []
        if str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        in execution_tokens
    ]
    observed_tokens = {
        str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        for module in modules
    }
    if observed_tokens != execution_tokens:
        raise GlobalCadPacketExecutionError(
            "有效配合图无法为事务执行投影提供完整模组记录："
            f"缺少{sorted(execution_tokens - observed_tokens)}。"
        )

    view = copy.deepcopy(effective_graph)
    view[module_key] = modules
    view[mate_key] = target_mates
    if "ModuleCount" in view:
        view["ModuleCount"] = len(modules)
    if "moduleCount" in view:
        view["moduleCount"] = len(modules)
    if "InterModuleMateCount" in view:
        view["InterModuleMateCount"] = len(target_mates)
    if "interModuleMateCount" in view:
        view["interModuleMateCount"] = len(target_mates)
    policy_key = (
        "BaseGraphPolicy"
        if "BaseGraphPolicy" in view
        else "baseGraphPolicy"
        if "baseGraphPolicy" in view
        else None
    )
    if policy_key:
        policy = copy.deepcopy(view.get(policy_key) or {})
        token_key = "moduleTokens" if "moduleTokens" in policy else "ModuleTokens"
        policy[token_key] = sorted(execution_tokens - {target_module_token})
        view[policy_key] = policy
    else:
        view["BaseGraphPolicy"] = {
            "moduleTokens": sorted(execution_tokens - {target_module_token}),
            "source": "transaction_execution_projection",
        }
    view["TransactionExecutionProjection"] = {
        "targetModuleToken": target_module_token,
        "moduleTokens": sorted(execution_tokens),
        "mateNames": sorted(
            str(mate.get("MateName") or mate.get("mateName") or "")
            for mate in target_mates
        ),
        "sourceGraphDigest": _digest(effective_graph),
        "reason": "仅保留本事务目标模组及其本次配合上下文，避免解析尚未装入的原型模组。",
    }
    return view


def _resolve_effective_graph(workspace: Path, candidate: str) -> Path:
    """Resolve legacy and current semantic-port graph naming conventions."""

    path = _inside(workspace, candidate)
    if path.is_file():
        return path
    if path.name == "assembly_plan_effective.json":
        # Non-prototype CAD closures deliberately use a distinct filename so
        # they cannot be confused with a graph that inherited the prototype's
        # top-level pose.  Older packages use ``effective_graph.json``.  Keep
        # the fallback order explicit and deterministic; never glob for an
        # arbitrary JSON file in an evidence directory.
        for fallback_name in (
            "assembly_plan_effective.nonprototype.json",
            "effective_graph.json",
        ):
            fallback = path.with_name(fallback_name)
            if fallback.is_file():
                return fallback
    raise GlobalCadPacketExecutionError(f"有效配合图不存在：{path}")


def _requested_mates(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        mate
        for connection in packet.get("connections") or []
        for mate in connection.get("mates") or []
    ]


def _relation_effective_graph_view(
    packet: dict[str, Any],
    effective_graph: dict[str, Any],
    *,
    mutating: bool,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Build a target-local graph for a relation between existing components.

    Relation packets do not insert a component.  Their execution graph therefore
    contains only the requested relation and its two already-installed modules.
    For a mutating transaction, PatchAudit is rewritten to addMate operations;
    any historical addModule operation belongs to the old isolated rebuild demo
    and must never be replayed against a cumulative checkpoint.
    """

    requested = Counter(_mate_identity(mate) for mate in _requested_mates(packet))
    if not requested:
        raise GlobalCadPacketExecutionError("关系事务未包含任何配合步骤。")
    graph_mates = effective_graph.get("Mates") or effective_graph.get("mates") or []
    matching: list[dict[str, Any]] = []
    remaining = requested.copy()
    for mate in graph_mates:
        if bool(mate.get("IsSuppressed", mate.get("isSuppressed", False))):
            continue
        identity = _mate_identity(mate)
        if remaining[identity] > 0:
            matching.append(copy.deepcopy(mate))
            remaining[identity] -= 1
    validation_matches: list[dict[str, Any]] = []
    if not mutating and remaining:
        audit = effective_graph.get("SemanticAssemblyPlanAudit") or {}
        validations = audit.get("ValidationRelations") or audit.get("validationRelations") or []
        for relation in validations:
            relation_name = str(
                relation.get("RelationName") or relation.get("relationName") or ""
            ).strip()
            relation_type = int(
                relation.get("RelationType", relation.get("relationType", -1))
            )
            relation_distance = _normalized_optional_float(
                relation.get(
                    "ExpectedDistanceMeters",
                    relation.get("expectedDistanceMeters"),
                )
            )
            relation_angle = _normalized_optional_float(
                relation.get(
                    "ExpectedAngleRadians",
                    relation.get("expectedAngleRadians"),
                )
            )
            # ValidationRelations in historical effective graphs do not always
            # persist Alignment.  For a read-only dimensional observation,
            # alignment is not part of the measured scalar identity; preserve
            # the alignment declared by the current packet instead of inventing
            # a value in the source audit.
            identity = next(
                (
                    candidate
                    for candidate, count in remaining.items()
                    if count > 0
                    and candidate[0] == relation_name
                    and candidate[1] == relation_type
                    and candidate[3] == relation_distance
                    and candidate[4] == relation_angle
                ),
                None,
            )
            if identity is not None:
                validation_matches.append(copy.deepcopy(relation))
                remaining[identity] -= 1
    missing = list(remaining.elements())
    if missing:
        raise GlobalCadPacketExecutionError(
            "有效配合图缺少关系事务请求的配合："
            f"{[_mate_identity_record(row) for row in missing]}。"
        )

    module_tokens: set[str] = set()
    endpoint_sources = matching + validation_matches
    for relation in endpoint_sources:
        direct_tokens = relation.get("ModuleTokens") or relation.get("moduleTokens") or []
        endpoint_tokens = [
            endpoint.get("ModuleToken", endpoint.get("moduleToken"))
            for endpoint in relation.get("Endpoints") or relation.get("endpoints") or []
        ]
        module_tokens.update(
            str(value).strip().upper()
            for value in list(direct_tokens) + endpoint_tokens
            if str(value or "").strip()
        )
    if len(module_tokens) != 2:
        raise GlobalCadPacketExecutionError(
            "当前关系执行器要求请求关系唯一落在两个既有模组之间。"
        )
    module_key = "Modules" if "Modules" in effective_graph else "modules"
    mate_key = "Mates" if "Mates" in effective_graph else "mates"
    modules = [
        copy.deepcopy(module)
        for module in effective_graph.get(module_key) or []
        if str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        in module_tokens
    ]
    observed_tokens = {
        str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        for module in modules
    }
    if observed_tokens != module_tokens:
        raise GlobalCadPacketExecutionError(
            f"关系执行图缺少模组记录：{sorted(module_tokens - observed_tokens)}。"
        )

    view = copy.deepcopy(effective_graph)
    view[module_key] = modules
    view[mate_key] = matching if mutating else []
    projected_mates = view[mate_key]
    if "ModuleCount" in view:
        view["ModuleCount"] = len(modules)
    if "moduleCount" in view:
        view["moduleCount"] = len(modules)
    if "InterModuleMateCount" in view:
        view["InterModuleMateCount"] = len(projected_mates)
    if "interModuleMateCount" in view:
        view["interModuleMateCount"] = len(projected_mates)
    if "MateBundleCount" in view:
        view["MateBundleCount"] = 0
    if "mateBundleCount" in view:
        view["mateBundleCount"] = 0
    if "MateBundles" in view:
        view["MateBundles"] = []
    if "mateBundles" in view:
        view["mateBundles"] = []
    first_relation = endpoint_sources[0]
    target_token = str(
        (first_relation.get("Endpoints") or first_relation.get("endpoints") or [{}])[0].get(
            "ModuleToken", ""
        )
    ).strip().upper()
    if target_token not in module_tokens:
        target_token = sorted(module_tokens)[0]
    if mutating:
        view["PatchAudit"] = {
            "patchSchemaVersion": "mate-graph-patch/v1",
            "operationCount": len(matching),
            "operations": [
                {
                    "index": index,
                    "operation": "addMate",
                    "mateName": str(mate.get("MateName") or mate.get("mateName") or ""),
                }
                for index, mate in enumerate(matching)
            ],
            "warnings": [],
            "projectionReason": (
                "关系两端已存在于累计检查点；仅新增请求配合，不重插模组。"
            ),
        }
        policy = copy.deepcopy(view.get("EditPolicy") or {})
        policy["initialPlacementMode"] = "existing_component_pose"
        policy["sourceGraphImmutable"] = True
        view["EditPolicy"] = policy
    else:
        if not validation_matches:
            validation_matches = [
                {
                    "relationName": str(
                        mate.get("MateName") or mate.get("mateName") or ""
                    ),
                    "relationType": int(
                        mate.get("MateType", mate.get("mateType", -1))
                    ),
                    "relationTypeName": str(
                        mate.get("MateTypeName")
                        or mate.get("mateTypeName")
                        or ""
                    ),
                    "endpointIds": [
                        str(endpoint.get("EndpointId") or endpoint.get("endpointId") or "")
                        for endpoint in mate.get("Endpoints") or mate.get("endpoints") or []
                    ],
                    "endpoints": copy.deepcopy(
                        mate.get("Endpoints") or mate.get("endpoints") or []
                    ),
                    "expectedDistanceMeters": mate.get(
                        "Distance", mate.get("distance")
                    ),
                    "expectedAngleRadians": mate.get("Angle", mate.get("angle")),
                    "tolerance": {"distanceMeters": 0.0001, "angleRadians": 1e-6},
                    "status": "requires_cad_measurement",
                }
                for mate in matching
            ]
        view["SemanticAssemblyPlanAudit"] = {
            "ValidationRelations": validation_matches
        }
        view["PatchAudit"] = {
            "patchSchemaVersion": "mate-graph-patch/v1",
            "operationCount": 0,
            "operations": [],
            "warnings": [],
            "projectionReason": "只读验证关系，不创建、更新或删除配合。",
        }
        policy = copy.deepcopy(view.get("EditPolicy") or {})
        policy["initialPlacementMode"] = "existing_component_pose"
        policy["sourceGraphImmutable"] = True
        view["EditPolicy"] = policy
    view["TransactionExecutionProjection"] = {
        "operation": packet.get("operation"),
        "targetModuleToken": target_token,
        "moduleTokens": sorted(module_tokens),
        "mateNames": sorted(
            str(
                mate.get("MateName")
                or mate.get("mateName")
                or mate.get("RelationName")
                or mate.get("relationName")
                or ""
            )
            for mate in endpoint_sources
        ),
        "sourceGraphDigest": _digest(effective_graph),
        "reason": "仅保留本关系事务的两个既有模组与请求关系。",
    }
    coverage = {
        "status": "exact_requested_relation_present",
        "requestedMateCount": sum(requested.values()),
        "requestedDrivingMateCount": sum(requested.values()) if mutating else 0,
        "requestedValidationRelationCount": 0 if mutating else sum(requested.values()),
        "graphMatchedMateCount": len(matching),
        "graphMatchedValidationRelationCount": len(validation_matches),
        "requestedMates": [
            _mate_identity_record(row) for row in sorted(requested.elements(), key=repr)
        ],
        "unmatchedRequested": [],
    }
    return view, target_token, coverage


def build_global_cad_packet_execution_plan(
    workspace: Path,
    manifest: dict[str, Any],
    packet_id: str,
    *,
    output_path: Path,
    input_checkpoint: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    if manifest.get("schemaVersion") != "global-cad-transaction-manifest/v1":
        raise GlobalCadPacketExecutionError("不支持的CAD事务清单版本。")
    expected_manifest_digest = str(manifest.get("manifestDigest") or "")
    actual_manifest_digest = _digest(
        {key: value for key, value in manifest.items() if key != "manifestDigest"}
    )
    if expected_manifest_digest != actual_manifest_digest:
        raise GlobalCadPacketExecutionError("CAD事务清单摘要不一致。")
    matches = [
        packet
        for packet in manifest.get("packets") or []
        if str(packet.get("packetId")) == packet_id
    ]
    if len(matches) != 1:
        raise GlobalCadPacketExecutionError(
            f"数据包{packet_id!r}解析到{len(matches)}条，要求唯一。"
        )
    packet = matches[0]
    expected_packet_digest = str(packet.get("packetDigest") or "")
    actual_packet_digest = _digest(
        {key: value for key, value in packet.items() if key != "packetDigest"}
    )
    if expected_packet_digest != actual_packet_digest:
        raise GlobalCadPacketExecutionError("CAD事务数据包摘要不一致。")
    if packet.get("status") != "ready_for_executor_implementation":
        raise GlobalCadPacketExecutionError(
            "数据包尚未满足执行条件："
            + ", ".join(
                str(row.get("code")) for row in packet.get("blockers") or []
            )
        )
    release_authority = validate_cad_manifest_release_authority(
        workspace,
        manifest,
        packets=[packet],
    )

    cumulative_input = packet.get("cumulativeInput") or {}
    cumulative_input_kind = str(cumulative_input.get("kind") or "")
    if cumulative_input_kind == "base_module_source":
        if input_checkpoint is not None:
            raise GlobalCadPacketExecutionError("首包不得用外部检查点替换已签认基座。")
        sources = list(cumulative_input.get("cadSources") or [])
        if not sources:
            raise GlobalCadPacketExecutionError("基座CAD源未登记。")
        source = Path(str(sources[0].get("path") or "")).resolve()
    elif cumulative_input_kind == "previous_transaction_checkpoint":
        if input_checkpoint is None:
            raise GlobalCadPacketExecutionError("后续数据包必须显式提供上一事务检查点。")
        source = input_checkpoint.resolve()
    else:
        raise GlobalCadPacketExecutionError("不支持的累计输入策略。")
    if not source.is_file():
        raise GlobalCadPacketExecutionError(f"累计输入装配体不存在：{source}")

    graph_candidates = {
        str(connection.get("effectiveMateGraphCandidate") or "")
        for connection in packet.get("connections") or []
        if connection.get("effectiveMateGraphCandidate")
    }
    if len(graph_candidates) != 1:
        raise GlobalCadPacketExecutionError(
            "当前执行器要求一个数据包唯一对应一个有效配合图。"
        )
    effective_graph = _resolve_effective_graph(workspace, graph_candidates.pop())
    effective_graph_value = _read_json_object(effective_graph)

    operation = str(packet.get("operation") or "INSERT_AND_CONNECT")
    strategy = str(packet.get("executionStrategy") or "")
    if not strategy:
        strategy = (
            "direct_existing_component_mate_edit"
            if operation == "ADD_RELATION"
            else "read_only_existing_relation_verification"
            if operation == "VERIFY_RELATION"
            else "incremental_component_insert"
        )
    execution_override = packet.get("drivingExecutionOverride") or {}
    if strategy == "calibrated_static_snapshot_insert":
        expected_graph_sha = str(
            execution_override.get("effectiveMateGraphSha256") or ""
        ).lower()
        if not expected_graph_sha or sha256_file(effective_graph).lower() != expected_graph_sha:
            raise GlobalCadPacketExecutionError("标定静态快照图摘要与安全目录不一致。")
        evidence_path = _inside(
            workspace, str(execution_override.get("validationEvidencePath") or "")
        )
        expected_evidence_sha = str(
            execution_override.get("validationEvidenceSha256") or ""
        ).lower()
        if (
            not evidence_path.is_file()
            or not expected_evidence_sha
            or sha256_file(evidence_path).lower() != expected_evidence_sha
        ):
            raise GlobalCadPacketExecutionError("标定静态快照验证证据缺失或摘要不一致。")

    if operation in {"ADD_RELATION", "VERIFY_RELATION"}:
        if cumulative_input_kind != "previous_transaction_checkpoint":
            raise GlobalCadPacketExecutionError("既有模组关系事务必须基于累计检查点。")
        execution_graph_view, target_module_token, graph_mate_coverage = (
            _relation_effective_graph_view(
                packet,
                effective_graph_value,
                mutating=operation == "ADD_RELATION",
            )
        )
        target_module_alias = target_module_token
        source_preparation = {
            "mode": "use_previous_committed_checkpoint",
            "required": False,
        }
    elif strategy == "calibrated_static_snapshot_insert":
        evidence_projects = {
            str(
                (connection.get("templateEvidenceSource") or {}).get("projectId")
                or ""
            ).lower()
            for connection in packet.get("connections") or []
        }
        evidence_projects.discard("")
        if evidence_projects != {"project02"}:
            raise GlobalCadPacketExecutionError("当前标定静态快照仅授权Project02。")
        target_module_alias = _target_module_alias_from_packet(
            packet, preferred_project="project02"
        )
        target_module_token = _graph_target_module_token(
            effective_graph_value, target_module_alias
        )
        graph_mate_coverage = _calibrated_static_snapshot_coverage(
            packet,
            effective_graph_value,
            target_module_token,
        )
        execution_graph_view = copy.deepcopy(effective_graph_value)
        execution_graph_view["CalibratedFallbackExecution"] = {
            "strategyId": execution_override.get("strategyId"),
            "scope": execution_override.get("scope"),
            "portable": False,
            "authority": execution_override.get("authority"),
            "sourceGraphDigest": _digest(effective_graph_value),
        }
        source_preparation = {
            "mode": "use_previous_committed_checkpoint",
            "required": False,
        }
    else:

        evidence_projects = {
        str(
            (connection.get("templateEvidenceSource") or {}).get("projectId")
            or ""
        ).lower()
        for connection in packet.get("connections") or []
    }
        evidence_projects.discard("")
        if len(evidence_projects) != 1:
            raise GlobalCadPacketExecutionError("数据包模板证据来源项目不唯一。")
        evidence_project = evidence_projects.pop()
        target_module_alias = _target_module_alias_from_packet(
            packet, preferred_project=evidence_project
        )
        target_module_token = _graph_target_module_token(
            effective_graph_value, target_module_alias
        )
        graph_mate_coverage = _effective_graph_mate_coverage(
            packet,
            effective_graph_value,
            target_module_token,
        )
        execution_graph_view = _transaction_effective_graph_view(
            effective_graph_value,
            target_module_token,
        )
        source_preparation = {
            "mode": "use_previous_committed_checkpoint",
            "required": False,
        }
    if operation == "INSERT_AND_CONNECT" and cumulative_input_kind == "base_module_source":
        base_context_modules = _base_context_modules(
            effective_graph_value, target_module_token
        )
        if len(base_context_modules) == 1:
            base_context_token, base_context_transform = base_context_modules[0]
            source_preparation = {
                "mode": "wrap_root_module_as_top_level_context",
                "required": True,
                "baseContextModuleToken": base_context_token,
                "baseContextTransform": base_context_transform,
                "reason": (
                    "上下文插入器在父装配体顶层解析基座模组；原始根模组文件必须先包装为"
                    "单组件累计基座，不能直接当作其自身的子组件。"
                ),
            }
        else:
            composite, composite_evidence, evidence = _verified_composite_base_context(
                effective_graph,
                base_context_modules,
            )
            source = composite
            source_preparation = {
                "mode": "use_verified_composite_base_context",
                "required": False,
                "baseContextModuleTokens": [token for token, _ in base_context_modules],
                "evidencePath": str(composite_evidence),
                "evidenceSha256": sha256_file(composite_evidence),
                "evidenceSchemaVersion": evidence.get("schemaVersion"),
                "reason": (
                    "有效配合图声明多个固定基座模组；复用已有保存/关闭/重开验证的"
                    "step00累计上下文，避免错误地把单个原始模组当作完整基座。"
                ),
            }

    source_sha256 = sha256_file(source)
    if source_preparation.get("mode") == "wrap_root_module_as_top_level_context":
        source_preparation = {
            **source_preparation,
            "cachePolicy": "content_addressed_read_only_reuse",
            "cacheRootRelativePath": (
                "demo/global_assembly_contexts/base_wrapper_cache"
            ),
            "cacheDescriptor": build_base_context_cache_descriptor(
                source_assembly_path=source,
                source_assembly_sha256=source_sha256,
                base_context_module_token=str(
                    source_preparation["baseContextModuleToken"]
                ),
                base_context_transform=list(
                    source_preparation["baseContextTransform"]
                ),
                adapter_version=BASE_CONTEXT_WRAPPER_ADAPTER_VERSION,
            ),
        }

    output = output_path.resolve()
    if output.exists():
        raise GlobalCadPacketExecutionError(f"拒绝覆盖既有输出：{output}")
    plan = {
        "schemaVersion": GLOBAL_CAD_PACKET_EXECUTION_PLAN_SCHEMA,
        "contextId": manifest.get("contextId"),
        "contextDigest": manifest.get("contextDigest"),
        "manifestDigest": expected_manifest_digest,
        "packetId": packet_id,
        "packetDigest": expected_packet_digest,
        "relationReleaseBinding": release_authority["binding"],
        "releaseAuthority": release_authority,
        "projectSequenceRequired": False,
        "cumulativeInputKind": cumulative_input_kind,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": source_sha256,
        "sourcePreparation": source_preparation,
        "effectiveMateGraphPath": str(effective_graph),
        "effectiveMateGraphSha256": sha256_file(effective_graph),
        "effectiveMateGraphExecutionView": execution_graph_view,
        "effectiveMateGraphExecutionDigest": _digest(execution_graph_view),
        "targetModuleToken": target_module_token,
        "targetModuleAlias": target_module_alias,
        "targetInstanceId": packet.get("targetInstanceId"),
        "operation": packet.get("operation"),
        "executionStrategy": strategy,
        "drivingExecutionOverride": execution_override or None,
        "connectionCount": len(packet.get("connections") or []),
        "requestedMateCount": graph_mate_coverage["requestedDrivingMateCount"],
        "requestedDrivingMateCount": graph_mate_coverage[
            "requestedDrivingMateCount"
        ],
        "requestedValidationRelationCount": graph_mate_coverage[
            "requestedValidationRelationCount"
        ],
        "requestedRelationCount": (
            graph_mate_coverage["requestedDrivingMateCount"]
            + graph_mate_coverage["requestedValidationRelationCount"]
        ),
        "effectiveGraphMateCoverage": graph_mate_coverage,
        "outputAssemblyPath": str(output),
        "verificationRequirements": packet.get("verificationRequirements") or [],
        "collisionStatus": "not_evaluated",
        "executionBoundary": {
            "solidWorksExecuted": False,
            "statement": "计划已绑定输入、数据包与有效图摘要；执行需显式调用现场CAD脚本。",
        },
    }
    plan["planDigest"] = _digest(plan)
    return plan

