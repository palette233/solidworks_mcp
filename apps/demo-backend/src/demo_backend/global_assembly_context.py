from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .relation_execution_policy import (
    RelationExecutionPolicyError,
    filter_connection_candidates_by_execution_policy,
    normalize_relation_execution_mode,
)

from .global_module_catalog import validate_global_module_catalog
from .global_relation_semantics import (
    evaluate_connection_candidates_for_relation,
    parse_relation_intent,
)


GLOBAL_ASSEMBLY_CONTEXT_SCHEMA = "global-assembly-context/v1"
GLOBAL_COMMAND_PREVIEW_SCHEMA = "global-assembly-command-preview/v1"


_CATEGORY_SELECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "frame": ("设备机架", "固定安装环境", "设备箱体", "箱体", "基座"),
    "transport": ("产品传输", "传输模组", "输送模组", "传输", "输送"),
    "scanner": ("条码扫描", "扫码模组", "扫描模组", "扫码", "扫描"),
    "calibration": ("喷嘴校准", "校准模组", "标定模组", "对针模组", "校准", "标定"),
    "ccd": ("产品定位ccd", "ccd模组", "视觉定位", "视觉模组", "ccd"),
    "cleaning_weighing": ("清洁称重", "清洁模组", "称重模组", "排胶模组"),
    "gantry": ("点胶龙门", "龙门模组", "点胶执行模组", "龙门"),
    "positioning": ("产品定位模组", "定位模组", "双工位定位"),
    "glue_supply": ("供胶系统", "供胶模组", "胶桶模组", "供胶"),
}


class GlobalAssemblyContextError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result[:40] or "module"


def create_global_assembly_context(
    context_id: str,
    *,
    display_name: str | None = None,
    catalog_digest: str,
    relation_release_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = str(context_id or "").strip()
    if not normalized or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", normalized):
        raise GlobalAssemblyContextError("contextId只能包含字母、数字、点、下划线和连字符。")
    timestamp = _now()
    context = {
        "schemaVersion": GLOBAL_ASSEMBLY_CONTEXT_SCHEMA,
        "contextId": normalized,
        "displayName": str(display_name or normalized),
        "catalogDigest": str(catalog_digest),
        "relationReleaseBinding": deepcopy(relation_release_binding),
        "revision": 0,
        "instances": [],
        "connections": [],
        "history": [],
        "collisionAssessment": {
            "status": "not_evaluated",
            "reason": "collision_gate_development_deferred_by_user_scope",
        },
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    context["contextDigest"] = context_digest(context)
    return context


def context_digest(context: dict[str, Any]) -> str:
    return _digest({key: value for key, value in context.items() if key != "contextDigest"})


def validate_global_assembly_context(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("schemaVersion") != GLOBAL_ASSEMBLY_CONTEXT_SCHEMA:
        raise GlobalAssemblyContextError("不支持的装配上下文版本。")
    if not str(context.get("contextId") or "").strip():
        raise GlobalAssemblyContextError("装配上下文缺少contextId。")
    instances = context.get("instances")
    connections = context.get("connections")
    if not isinstance(instances, list) or not isinstance(connections, list):
        raise GlobalAssemblyContextError("装配上下文缺少instances或connections数组。")
    binding = context.get("relationReleaseBinding")
    if binding is not None:
        if not isinstance(binding, dict):
            raise GlobalAssemblyContextError("relationReleaseBinding必须是对象或null。")
        required = {
            "releaseId",
            "releaseDigest",
            "releaseManifestPath",
            "catalogDigest",
            "authorizedDrivingTemplateIds",
        }
        missing = sorted(required - set(binding))
        if missing:
            raise GlobalAssemblyContextError(
                f"关系发布绑定缺少字段：{', '.join(missing)}。"
            )
        if binding.get("catalogDigest") != context.get("catalogDigest"):
            raise GlobalAssemblyContextError("关系发布绑定与上下文目录摘要不一致。")
        authorized = binding.get("authorizedDrivingTemplateIds")
        if not isinstance(authorized, list) or not authorized:
            raise GlobalAssemblyContextError("关系发布绑定没有逐模板驱动授权。")
        if len(authorized) != len(set(str(item) for item in authorized)):
            raise GlobalAssemblyContextError("关系发布绑定含重复的驱动模板编号。")
        authorized_combinations = binding.get("authorizedTemplateCombinationIds")
        if authorized_combinations is not None:
            if not isinstance(authorized_combinations, list) or not all(
                str(item).strip() for item in authorized_combinations
            ):
                raise GlobalAssemblyContextError("模板组合授权必须是非空编号数组。")
            if len(authorized_combinations) != len(
                set(str(item) for item in authorized_combinations)
            ):
                raise GlobalAssemblyContextError("关系发布绑定含重复的模板组合编号。")
    instance_ids = [str(item.get("instanceId") or "") for item in instances]
    if any(not item for item in instance_ids) or len(instance_ids) != len(set(instance_ids)):
        raise GlobalAssemblyContextError("instanceId必须非空且唯一。")
    known = set(instance_ids)
    for connection in connections:
        if connection.get("instanceAId") not in known or connection.get("instanceBId") not in known:
            raise GlobalAssemblyContextError("连接引用了不存在的模组实例。")
    expected = context_digest(context)
    if context.get("contextDigest") != expected:
        raise GlobalAssemblyContextError("装配上下文摘要不匹配。")
    return {
        "success": True,
        "contextId": context["contextId"],
        "revision": context.get("revision", 0),
        "instanceCount": len(instances),
        "connectionCount": len(connections),
        "contextDigest": expected,
    }


def search_global_modules(catalog: dict[str, Any], query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    validate_global_module_catalog(catalog)
    normalized = str(query or "").strip().casefold()
    rows: list[tuple[int, str, dict[str, Any], list[str]]] = []
    for definition in catalog.get("moduleDefinitions") or []:
        terms = [
            str(definition.get("moduleDefinitionId") or ""),
            str(definition.get("displayName") or ""),
            str(definition.get("category") or ""),
            *(str(item) for item in definition.get("aliases") or []),
            *(str(item) for item in definition.get("componentNames") or []),
        ]
        for alias in definition.get("projectAliases") or []:
            terms.extend([str(alias.get("projectId") or ""), str(alias.get("moduleToken") or "")])
        matched: list[str] = []
        score = 0
        if not normalized:
            score = 1
        else:
            for term in terms:
                folded = term.casefold()
                if folded == normalized:
                    score = max(score, 1000)
                    matched.append(term)
                elif normalized in folded:
                    score = max(score, 500 + min(len(normalized), 100))
                    matched.append(term)
                elif all(part in folded for part in normalized.split() if part):
                    score = max(score, 200)
                    matched.append(term)
        if score:
            rows.append((score, str(definition["moduleDefinitionId"]), definition, sorted(set(matched))))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "score": score,
            "matchedTerms": matches,
            "moduleDefinitionId": definition["moduleDefinitionId"],
            "displayName": definition["displayName"],
            "category": definition["category"],
            "componentNames": definition.get("componentNames") or [],
            "projectAliases": definition.get("projectAliases") or [],
            "portCoverage": definition.get("portCoverage"),
            "portablePortCount": sum(
                1
                for port_id in definition.get("portIds") or []
                if next(
                    (
                        port.get("portable")
                        for port in catalog.get("semanticPorts") or []
                        if port.get("globalPortId") == port_id
                    ),
                    False,
                )
            ),
        }
        for score, _, definition, matches in rows[: max(1, min(int(limit), 100))]
    ]


def _mentioned_definitions(catalog: dict[str, Any], requirement: str) -> list[dict[str, Any]]:
    text = str(requirement or "").casefold()
    requested_project_ids: set[str] = set()
    for project in catalog.get("projects") or []:
        project_id = str(project.get("projectId") or "").casefold()
        project_number = re.sub(r"\D+", "", project_id)
        if project_id and project_id in text:
            requested_project_ids.add(project_id)
        elif project_number and re.search(
            rf"(?:项目|project)\s*0*{re.escape(str(int(project_number)))}(?!\d)",
            text,
        ):
            requested_project_ids.add(project_id)
    candidates: list[tuple[int, str, dict[str, Any], str]] = []
    for definition in catalog.get("moduleDefinitions") or []:
        definition_project_ids = {
            str(alias.get("projectId") or "").casefold()
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").strip()
        }
        if requested_project_ids and requested_project_ids.isdisjoint(
            definition_project_ids
        ):
            continue
        terms: list[tuple[str, int]] = [
            (str(definition.get("displayName") or ""), 1000),
            *((str(item), 1000) for item in definition.get("aliases") or []),
            *((str(item), 3000) for item in definition.get("componentNames") or []),
            *(
                (term, 900)
                for term in _CATEGORY_SELECTION_ALIASES.get(
                    str(definition.get("category") or "").casefold(), ()
                )
            ),
        ]
        project_boost = 0
        for alias in definition.get("projectAliases") or []:
            project_id = str(alias.get("projectId") or "").casefold()
            project_number = re.sub(r"\D+", "", project_id)
            project_mentioned = bool(project_id and project_id in text)
            if project_number:
                normalized_number = str(int(project_number))
                project_mentioned = project_mentioned or bool(
                    re.search(
                        rf"(?:项目|project)\s*0*{re.escape(normalized_number)}(?!\d)",
                        text,
                    )
                )
            if project_mentioned:
                project_boost = 500
            terms.append((str(alias.get("moduleToken") or ""), 2000))
        best = ""
        best_score = 0
        for term, base_score in terms:
            folded = term.strip().casefold()
            if not folded:
                continue
            if re.fullmatch(r"[a-z0-9_.-]+", folded):
                matched = re.search(rf"(?<![a-z0-9]){re.escape(folded)}(?![a-z0-9])", text)
            else:
                matched = folded in text
            score = base_score + project_boost + len(folded)
            if matched and score > best_score:
                best = folded
                best_score = score
        if best:
            candidates.append((best_score, definition["moduleDefinitionId"], definition, best))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"definition": item[2], "matchedTerm": item[3], "matchScore": item[0]}
        for item in candidates
    ]


def _module_selection_text(requirement: str) -> tuple[str, str]:
    """Focus module selection on the object being added, not its context target.

    Engineering commands normally mention both sides of an installation, for
    example ``在当前固定环境上安装一套产品传输模组``. Searching the entire
    sentence makes ``固定环境`` compete with ``传输模组`` even though the former
    is only the already-present target. Keep the full sentence for relation
    target discovery, but use the action object for selecting the new module.

    The ``把/将 X 安装到 Y`` form places the object before the action verb and is
    handled separately. If no reliable action object can be isolated, the
    caller falls back to the original sentence.
    """

    text = str(requirement or "").strip()
    front_object = re.search(
        r"(?:^|[，,。；;])\s*(?:(?:请|随后|然后|接着|最后|再|下一步)\s*)*"
        r"(?:将|把)\s*(.+?)\s*"
        r"(?:安装|装配|连接|固定)(?:到|至|在|于)",
        text,
    )
    if front_object and front_object.group(1).strip():
        return front_object.group(1).strip(), "fronted_action_object"

    actions = list(
        re.finditer(
            r"(?:添加|增加|安装|装入|放置|布置|建立|加入|选用|采用)\s*",
            text,
        )
    )
    if actions:
        # A preview command adds one module. The final explicit action is the
        # most local instruction in sentences that also contain history/context.
        fragment = text[actions[-1].end() :]
        fragment = re.split(r"[。；;]", fragment, maxsplit=1)[0]
        fragment = re.split(r"(?:，|,)\s*(?:用于|以便|方便|从而)", fragment, maxsplit=1)[0]
        if fragment.strip():
            return fragment.strip(), "post_action_object"
    return text, "full_requirement_fallback"


def _port_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(port["globalPortId"]): port for port in catalog.get("semanticPorts") or []}


def _compatible_connections(
    catalog: dict[str, Any],
    context: dict[str, Any],
    new_definition_id: str,
) -> list[dict[str, Any]]:
    ports = _port_map(catalog)
    release_binding = context.get("relationReleaseBinding") or {}
    authorized_template_ids = {
        str(value)
        for value in release_binding.get("authorizedDrivingTemplateIds") or []
        if str(value)
    }
    release_bound = bool(release_binding)
    new_ports = {
        port_id for port_id, port in ports.items() if port.get("moduleDefinitionId") == new_definition_id
    }
    instances_by_definition: dict[str, list[dict[str, Any]]] = {}
    for instance in context.get("instances") or []:
        instances_by_definition.setdefault(str(instance.get("moduleDefinitionId")), []).append(instance)
    result: list[dict[str, Any]] = []
    for compatibility in catalog.get("compatibility") or []:
        # A released context is an execution authority, not merely a catalog
        # selection hint.  Unauthorised historical/native templates may still
        # be present in the immutable catalog for traceability, but must not
        # compete in natural-language candidate selection.
        if release_bound and str(
            compatibility.get("globalTemplateId") or ""
        ) not in authorized_template_ids:
            continue
        port_a_id = str(compatibility.get("portAId") or "")
        port_b_id = str(compatibility.get("portBId") or "")
        side = None
        if port_a_id in new_ports:
            side = "A"
            new_port_id, existing_port_id = port_a_id, port_b_id
        elif port_b_id in new_ports:
            side = "B"
            new_port_id, existing_port_id = port_b_id, port_a_id
        else:
            continue
        existing_port = ports.get(existing_port_id) or {}
        existing_definition_id = str(existing_port.get("moduleDefinitionId") or "")
        for instance in instances_by_definition.get(existing_definition_id) or []:
            result.append(
                {
                    "newSide": side,
                    "newPortId": new_port_id,
                    "existingPortId": existing_port_id,
                    "existingInstanceId": instance["instanceId"],
                    "globalTemplateId": compatibility.get("globalTemplateId"),
                    "purpose": compatibility.get("purpose"),
                    "portable": bool(
                        compatibility.get("portableForTemplate")
                    ),
                }
            )
    templates = {
        str(item.get("globalTemplateId") or ""): item
        for item in catalog.get("connectionTemplates") or []
    }

    def interchangeable_side(item: dict[str, Any]) -> bool:
        """Return true only when swapping template sides has identical semantics.

        Some migrated catalogs intentionally list the same two ports on both
        template sides.  That representation is useful for discovery, but it
        used to turn one physical installation into two indistinguishable
        natural-language candidates.  Side collapse is safe only when the two
        interface types and every mate endpoint role are symmetric.
        """

        template = templates.get(str(item.get("globalTemplateId") or "")) or {}
        if "installation" not in (template.get("purposes") or []):
            return False
        if template.get("interfaceTypeA") != template.get("interfaceTypeB"):
            return False
        steps = template.get("mateSteps") or []
        return bool(steps) and all(
            step.get("endpointRoleA") == step.get("endpointRoleB") for step in steps
        )

    unique: dict[str, dict[str, Any]] = {}
    for item in result:
        key_item = dict(item)
        if interchangeable_side(item):
            key_item.pop("newSide", None)
            # Bidirectional compatibility rows describe the same physical
            # installation when the template is side-symmetric.  Portability
            # is evidence quality for that direction, not a second mechanical
            # choice, so it must not keep a duplicate candidate alive.
            key_item.pop("portable", None)
        key = json.dumps(key_item, ensure_ascii=False, sort_keys=True)
        existing = unique.get(key)
        if existing is None or (
            interchangeable_side(item)
            and item.get("portable") is True
            and existing.get("portable") is not True
        ):
            unique[key] = item
    return sorted(
        unique.values(),
        key=lambda item: (
            not item["portable"],
            item["existingInstanceId"],
            item["newPortId"],
            item["existingPortId"],
        ),
    )


def _next_instance_id(context: dict[str, Any], definition_id: str) -> str:
    base = _slug(definition_id.split("/")[-2] if "/" in definition_id else definition_id)
    existing = {str(item.get("instanceId")) for item in context.get("instances") or []}
    index = 1
    while f"{base}-{index:03d}" in existing:
        index += 1
    return f"{base}-{index:03d}"


def _definition_instance_capacity(definition: dict[str, Any]) -> int:
    """Return the largest declared per-project occurrence count.

    A global definition can be shared by several project profiles.  The profile
    occurrence count is the only current evidence that two identical CAD sources
    are intentionally used more than once (Project02 T401 is the first case).
    """

    # A definition backed by several different component names represents one
    # composite module group (for example Project05 A000+E000 or B000+Z000), not
    # several interchangeable occurrences of the same CAD source.
    if len(definition.get("componentNames") or []) > 1:
        return 1
    declared: list[int] = []
    for alias in definition.get("projectAliases") or []:
        try:
            declared.append(max(1, int(alias.get("instanceCount", 1))))
        except (TypeError, ValueError):
            declared.append(1)
    return max(declared, default=1)


def _mentioned_existing_definition_ids(
    catalog: dict[str, Any], context: dict[str, Any], requirement: str, new_definition_id: str
) -> set[str]:
    """Extract already-present module mentions used as a connection target hint."""

    present = {
        str(item.get("moduleDefinitionId") or "")
        for item in context.get("instances") or []
    }
    return {
        str(item["definition"]["moduleDefinitionId"])
        for item in _mentioned_definitions(catalog, requirement)
        if str(item["definition"]["moduleDefinitionId"]) in present
        and str(item["definition"]["moduleDefinitionId"]) != new_definition_id
    }


def preview_global_assembly_command(
    catalog: dict[str, Any], context: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    requirement = str(payload.get("requirement") or "").strip()
    if not requirement:
        raise GlobalAssemblyContextError("requirement不能为空。")
    try:
        relation_execution_mode = normalize_relation_execution_mode(
            payload.get("relationExecutionMode")
        )
    except RelationExecutionPolicyError as exc:
        raise GlobalAssemblyContextError(str(exc)) from exc
    relation_intent = parse_relation_intent(requirement)
    explicit_definition_id = str(payload.get("moduleDefinitionId") or "").strip()
    definitions = {
        str(item["moduleDefinitionId"]): item for item in catalog.get("moduleDefinitions") or []
    }
    if explicit_definition_id:
        if explicit_definition_id not in definitions:
            raise GlobalAssemblyContextError("指定的moduleDefinitionId不存在。")
        selected_definition = definitions[explicit_definition_id]
        resolution = "explicit_definition_id"
        alternatives: list[dict[str, Any]] = []
        selection_text = requirement
        selection_basis = "explicit_definition_id"
    else:
        selection_text, selection_basis = _module_selection_text(requirement)
        mentions = _mentioned_definitions(catalog, selection_text)
        # A focused fragment is useful only if it actually contains a known
        # module term. Preserve whole-sentence behaviour for unusual commands.
        if not mentions and selection_text != requirement:
            selection_text = requirement
            selection_basis = "full_requirement_fallback"
            mentions = _mentioned_definitions(catalog, requirement)
        # Keep all equally specific matches. Cross-project generic aliases should ask for confirmation.
        if not mentions:
            selected_definition = None
            alternatives = []
            resolution = "no_module_match"
        else:
            best_score = mentions[0]["matchScore"]
            best = [item for item in mentions if item["matchScore"] == best_score]
            alternatives = [
                {
                    "moduleDefinitionId": item["definition"]["moduleDefinitionId"],
                    "displayName": item["definition"]["displayName"],
                    "matchedTerm": item["matchedTerm"],
                }
                for item in best
            ]
            if len(best) == 1:
                selected_definition = best[0]["definition"]
                selected_definition_id = str(
                    selected_definition["moduleDefinitionId"]
                )
                instance_counts: dict[str, int] = {}
                for instance in context.get("instances") or []:
                    definition_id = str(instance.get("moduleDefinitionId") or "")
                    instance_counts[definition_id] = (
                        instance_counts.get(definition_id, 0) + 1
                    )
                if (
                    instance_counts.get(selected_definition_id, 0) > 0
                    and instance_counts.get(selected_definition_id, 0)
                    < _definition_instance_capacity(selected_definition)
                ):
                    # Focusing on the action object can make a repeated module
                    # unambiguous, but its explainability contract still needs
                    # to state why another occurrence is legal.
                    resolution = "unique_definition_with_remaining_instance_capacity"
                else:
                    mentioned_existing_targets = _mentioned_existing_definition_ids(
                        catalog,
                        context,
                        requirement,
                        selected_definition_id,
                    )
                    resolution = (
                        "unique_new_module_with_existing_target_hint"
                        if mentioned_existing_targets
                        else "unique_natural_language_match"
                    )
            else:
                present_definition_ids = {
                    str(item.get("moduleDefinitionId") or "")
                    for item in context.get("instances") or []
                }
                new_mentions = [
                    item
                    for item in best
                    if str(item["definition"]["moduleDefinitionId"])
                    not in present_definition_ids
                ]
                selected_definition = (
                    new_mentions[0]["definition"] if len(new_mentions) == 1 else None
                )
                if selected_definition is not None:
                    resolution = "unique_new_module_with_existing_target_hint"
                else:
                    # When a command mentions two definitions that are both
                    # already present, one of them can still be the requested
                    # *new occurrence*.  Prefer it only when exactly one
                    # definition has unused, profile-declared instance
                    # capacity.  This keeps the rule project-neutral while
                    # supporting commands such as "在A200上安装第二套T401".
                    instance_counts: dict[str, int] = {}
                    for instance in context.get("instances") or []:
                        definition_id = str(instance.get("moduleDefinitionId") or "")
                        instance_counts[definition_id] = (
                            instance_counts.get(definition_id, 0) + 1
                        )
                    capacity_candidates = [
                        item
                        for item in best
                        if instance_counts.get(
                            str(item["definition"]["moduleDefinitionId"]), 0
                        )
                        < _definition_instance_capacity(item["definition"])
                    ]
                    selected_definition = (
                        capacity_candidates[0]["definition"]
                        if len(capacity_candidates) == 1
                        else None
                    )
                    resolution = (
                        "unique_definition_with_remaining_instance_capacity"
                        if selected_definition is not None
                        else "ambiguous_module_match"
                    )

    status = "blocked"
    blockers: list[dict[str, Any]] = []
    proposed_patch: dict[str, Any] | None = None
    connection_candidates: list[dict[str, Any]] = []
    relation_candidate_assessments: list[dict[str, Any]] = []
    execution_policy_assessments: list[dict[str, Any]] = []
    relation_parse_blocked = relation_intent.get("status") == "blocked"
    if relation_parse_blocked:
        blockers.extend(
            {"source": "relation_intent", **item}
            for item in relation_intent.get("blockers") or []
        )
    if selected_definition is None:
        blockers.append(
            {
                "code": "MODULE_SELECTION_REQUIRED",
                "detail": "自然语言未唯一确定一个CAD模组定义，请从候选项中确认。",
            }
        )
        status = "needs_confirmation" if alternatives else "blocked"
    else:
        existing_definition_instances = [
            item
            for item in context.get("instances") or []
            if item.get("moduleDefinitionId") == selected_definition["moduleDefinitionId"]
        ]
        instance_capacity = _definition_instance_capacity(selected_definition)
    if selected_definition is not None and len(existing_definition_instances) >= instance_capacity:
        blockers.append(
            {
                "code": "MODULE_INSTANCE_CAPACITY_REACHED",
                "detail": (
                    f"该模组定义已达到目录声明的实例上限 {instance_capacity}；"
                    "如需更多实例，必须先更新项目配置或显式工程确认。"
                ),
            }
        )
    elif selected_definition is not None:
        new_instance_id = str(payload.get("instanceId") or "").strip() or _next_instance_id(
            context, selected_definition["moduleDefinitionId"]
        )
        if not context.get("instances"):
            relation_target_required = relation_intent.get("primaryRelation") not in {
                "unspecified",
                "installation",
            } or bool((relation_intent.get("parameters") or {}).get("sideQualifier"))
            if relation_parse_blocked:
                status = "blocked"
            elif relation_target_required:
                status = "blocked"
                blockers.append(
                    {
                        "code": "RELATION_TARGET_REQUIRED",
                        "detail": "当前上下文为空，基础关系或方位关系缺少目标模组。",
                    }
                )
            else:
                status = "ready"
                proposed_patch = {
                    "operation": "add_base_instance",
                    "instance": {
                        "instanceId": new_instance_id,
                        "moduleDefinitionId": selected_definition["moduleDefinitionId"],
                        "displayName": selected_definition["displayName"],
                        "instanceOrdinal": len(existing_definition_instances) + 1,
                        "declaredInstanceCapacity": instance_capacity,
                        "placementStatus": "base_context_unlocated",
                    },
                    "connection": None,
                }
        else:
            all_connection_candidates = _compatible_connections(
                catalog, context, selected_definition["moduleDefinitionId"]
            )
            (
                connection_candidates,
                execution_policy_assessments,
            ) = filter_connection_candidates_by_execution_policy(
                catalog,
                all_connection_candidates,
                requested_mode=relation_execution_mode,
            )
            allowed_template_ids = payload.get("allowedTemplateIds")
            if allowed_template_ids is not None:
                if not isinstance(allowed_template_ids, list):
                    raise GlobalAssemblyContextError("allowedTemplateIds必须是数组。")
                allowed = {str(item) for item in allowed_template_ids if str(item)}
                connection_candidates = [
                    row
                    for row in connection_candidates
                    if str(row.get("globalTemplateId") or "") in allowed
                ]
            selected_new_port = str(payload.get("newPortId") or "").strip()
            selected_existing_port = str(payload.get("existingPortId") or "").strip()
            selected_existing_instance = str(payload.get("existingInstanceId") or "").strip()
            selected_template = str(payload.get("globalTemplateId") or "").strip()
            selected_new_side = str(payload.get("newSide") or "").strip().upper()
            if selected_new_side and selected_new_side not in {"A", "B"}:
                raise GlobalAssemblyContextError("newSide只能为A或B。")
            if any(
                [
                    selected_new_port,
                    selected_existing_port,
                    selected_existing_instance,
                    selected_template,
                    selected_new_side,
                ]
            ):
                connection_candidates = [
                    row
                    for row in connection_candidates
                    if (not selected_new_port or row["newPortId"] == selected_new_port)
                    and (not selected_existing_port or row["existingPortId"] == selected_existing_port)
                    and (
                        not selected_existing_instance
                        or row["existingInstanceId"] == selected_existing_instance
                    )
                    and (not selected_template or row["globalTemplateId"] == selected_template)
                    and (not selected_new_side or row["newSide"] == selected_new_side)
                ]
            else:
                mentioned_existing = _mentioned_existing_definition_ids(
                    catalog,
                    context,
                    requirement,
                    selected_definition["moduleDefinitionId"],
                )
                if mentioned_existing:
                    instance_definition = {
                        str(item.get("instanceId") or ""): str(
                            item.get("moduleDefinitionId") or ""
                        )
                        for item in context.get("instances") or []
                    }
                    hinted = [
                        row
                        for row in connection_candidates
                        if instance_definition.get(row["existingInstanceId"])
                        in mentioned_existing
                    ]
                    if hinted:
                        connection_candidates = hinted
            raw_connection_candidates = connection_candidates
            (
                relation_matches,
                relation_candidate_assessments,
            ) = evaluate_connection_candidates_for_relation(
                catalog,
                raw_connection_candidates,
                relation_intent,
            )
            connection_candidates = relation_matches
            if len(connection_candidates) == 1:
                candidate = connection_candidates[0]
                status = "ready" if candidate["portable"] else "needs_confirmation"
                if not candidate["portable"]:
                    blockers.append(
                        {
                            "code": "PORT_EVIDENCE_NOT_PORTABLE",
                            "detail": "端口仍含项目实例依赖；可保存草案，但不能直接声明可跨装配体自动恢复。",
                        }
                    )
                connection_id = f"connection-{len(context.get('connections') or []) + 1:03d}"
                proposed_patch = {
                    "operation": "add_connected_instance",
                    "instance": {
                        "instanceId": new_instance_id,
                        "moduleDefinitionId": selected_definition["moduleDefinitionId"],
                        "displayName": selected_definition["displayName"],
                        "instanceOrdinal": len(existing_definition_instances) + 1,
                        "declaredInstanceCapacity": instance_capacity,
                        "placementStatus": "semantic_connection_planned",
                    },
                    "connection": {
                        "connectionId": connection_id,
                        "instanceAId": new_instance_id
                        if candidate["newSide"] == "A"
                        else candidate["existingInstanceId"],
                        "portAId": candidate["newPortId"]
                        if candidate["newSide"] == "A"
                        else candidate["existingPortId"],
                        "instanceBId": candidate["existingInstanceId"]
                        if candidate["newSide"] == "A"
                        else new_instance_id,
                        "portBId": candidate["existingPortId"]
                        if candidate["newSide"] == "A"
                        else candidate["newPortId"],
                        "globalTemplateId": candidate["globalTemplateId"],
                        "purpose": candidate["purpose"],
                        "relationExecutionMode": relation_execution_mode,
                        "templateEvidenceClass": (
                            candidate.get("executionPolicyAssessment") or {}
                        ).get("templateEvidenceClass"),
                        "relationIntent": relation_intent,
                        "relationProfile": (
                            candidate.get("relationAssessment") or {}
                        ).get("templateProfile"),
                        "executionStatus": "planned_not_executed_in_cad",
                    },
                }
            elif not connection_candidates:
                if relation_parse_blocked:
                    status = "blocked"
                elif (
                    all_connection_candidates
                    and not raw_connection_candidates
                    and execution_policy_assessments
                ):
                    blockers.append(
                        {
                            "code": "RELATION_EXECUTION_MODE_MISMATCH",
                            "detail": (
                                "存在语义端口候选，但其证据等级不允许在当前模式执行。"
                            ),
                            "requestedMode": relation_execution_mode,
                            "candidateAssessments": [
                                {
                                    "globalTemplateId": item.get(
                                        "globalTemplateId"
                                    ),
                                    "assessment": item.get(
                                        "executionPolicyAssessment"
                                    ),
                                }
                                for item in execution_policy_assessments
                            ],
                        }
                    )
                elif raw_connection_candidates:
                    blockers.append(
                        {
                            "code": "REQUESTED_RELATION_TEMPLATE_NOT_AVAILABLE",
                            "detail": (
                                "模组之间存在端口，但没有与本次自然语言关系精确匹配的模板。"
                            ),
                            "primaryRelation": relation_intent.get("primaryRelation"),
                            "candidateTemplateAssessments": [
                                {
                                    "globalTemplateId": item.get("globalTemplateId"),
                                    "reasons": (
                                        item.get("relationAssessment") or {}
                                    ).get("reasons")
                                    or [],
                                }
                                for item in relation_candidate_assessments
                            ],
                        }
                    )
                else:
                    blockers.append(
                        {
                            "code": "NO_COMPATIBLE_PORT_PAIR",
                            "detail": "当前上下文与待添加模组之间没有已登记的兼容语义端口。",
                        }
                    )
            else:
                status = "needs_confirmation"
                if not any(candidate.get("portable") for candidate in connection_candidates):
                    blockers.append(
                        {
                            "code": "PORT_EVIDENCE_NOT_PORTABLE",
                            "detail": (
                                "候选关系都缺少可跨装配恢复的端点证据；"
                                "需迁移签名目录或人工确认端点。"
                            ),
                        }
                    )
                blockers.append(
                    {
                        "code": "CONNECTION_SELECTION_REQUIRED",
                        "detail": "存在多个兼容端口组合，请确认目标实例与端口。",
                    }
                )

    preview = {
        "schemaVersion": GLOBAL_COMMAND_PREVIEW_SCHEMA,
        "status": status,
        "requirement": requirement,
        "resolution": resolution,
        "moduleSelectionEvidence": {
            "basis": selection_basis,
            "text": selection_text,
        },
        "relationIntent": relation_intent,
        "relationExecutionPolicy": {
            "requestedMode": relation_execution_mode,
            "defaulted": "relationExecutionMode" not in payload,
            "candidateAssessments": execution_policy_assessments,
        },
        "catalogDigest": catalog["catalogDigest"],
        "sourceContextDigest": context["contextDigest"],
        "relationReleaseBinding": deepcopy(context.get("relationReleaseBinding")),
        "selectedModuleDefinitionId": (
            selected_definition["moduleDefinitionId"] if selected_definition else None
        ),
        "moduleAlternatives": alternatives,
        "connectionCandidates": connection_candidates,
        "relationCandidateAssessments": relation_candidate_assessments,
        "proposedPatch": proposed_patch,
        "blockers": blockers,
        "collisionAssessment": {
            "status": "not_evaluated",
            "reason": "collision_gate_development_deferred_by_user_scope",
        },
        "cadExecution": {
            "status": "not_executed",
            "statement": "本步骤只生成可审计的装配图补丁预览，不修改SolidWorks。",
        },
    }
    # Import locally to keep the command parser independent from the optional
    # transaction-DAG compiler while still exposing one canonical command IR.
    from .global_assembly_transactions import build_global_command_ir

    preview["commandIr"] = build_global_command_ir(preview)
    preview["previewDigest"] = _digest(preview)
    return preview


def apply_global_command_preview(
    context: dict[str, Any], preview: dict[str, Any], *, preview_digest: str, confirmed: bool
) -> dict[str, Any]:
    validate_global_assembly_context(context)
    if not confirmed:
        raise GlobalAssemblyContextError("必须显式confirmed=true才能写入装配上下文。")
    if str(preview.get("previewDigest") or "") != str(preview_digest):
        raise GlobalAssemblyContextError("previewDigest与预览不一致。")
    if _digest({key: value for key, value in preview.items() if key != "previewDigest"}) != preview_digest:
        raise GlobalAssemblyContextError("预览内容已被修改。")
    if preview.get("sourceContextDigest") != context.get("contextDigest"):
        raise GlobalAssemblyContextError("装配上下文在预览后已发生变化，请重新预览。")
    release_transition = preview.get("portableReleaseTransition")
    if release_transition is not None:
        source_binding = release_transition.get("sourceRelationReleaseBinding")
        if source_binding != context.get("relationReleaseBinding"):
            raise GlobalAssemblyContextError("发布切换预览的源发布绑定已过期。")
        if preview.get("relationReleaseBinding") != context.get(
            "relationReleaseBinding"
        ):
            raise GlobalAssemblyContextError("发布切换预览的源发布状态不一致。")
        if release_transition.get("sourceCatalogDigest") != context.get("catalogDigest"):
            raise GlobalAssemblyContextError("发布绑定预览的源目录摘要已过期。")
        binding = release_transition.get("relationReleaseBinding")
        if not isinstance(binding, dict) or not binding.get("releaseId"):
            raise GlobalAssemblyContextError("发布绑定预览缺少不可变发布证据。")
    elif preview.get("relationReleaseBinding") != context.get("relationReleaseBinding"):
        raise GlobalAssemblyContextError("预览使用的关系发布绑定与当前上下文不一致。")
    if preview.get("status") != "ready" or not preview.get("proposedPatch"):
        raise GlobalAssemblyContextError("只有status=ready的预览可以写入。")
    patch = preview["proposedPatch"]
    result = deepcopy(context)
    if release_transition is not None:
        result["catalogDigest"] = release_transition["catalogDigest"]
        result["relationReleaseBinding"] = deepcopy(
            release_transition["relationReleaseBinding"]
        )
        upgraded_connections = release_transition.get("upgradedConnections")
        if upgraded_connections is not None:
            if not isinstance(upgraded_connections, list):
                raise GlobalAssemblyContextError("发布扩展后的既有连接必须为数组。")
            source_ids = {
                str(row.get("connectionId") or "")
                for row in context.get("connections") or []
            }
            upgraded_ids = {
                str(row.get("connectionId") or "")
                for row in upgraded_connections
                if isinstance(row, dict)
            }
            if source_ids != upgraded_ids or len(upgraded_ids) != len(
                upgraded_connections
            ):
                raise GlobalAssemblyContextError(
                    "发布扩展必须一一保留全部既有连接，不能增删连接。"
                )
            result["connections"] = deepcopy(upgraded_connections)
    result["instances"].append(deepcopy(patch["instance"]))
    if patch.get("connection"):
        result["connections"].append(deepcopy(patch["connection"]))
    result["revision"] = int(result.get("revision", 0)) + 1
    result["updatedAt"] = _now()
    result["history"].append(
        {
            "revision": result["revision"],
            "sourceContextDigest": context.get("contextDigest"),
            "requirement": preview.get("requirement"),
            "previewDigest": preview_digest,
            "operation": patch.get("operation"),
            "portableReleaseTransition": (
                {
                    "transitionKind": release_transition.get("transitionKind"),
                    "sourceReleaseId": release_transition.get("sourceReleaseId"),
                    "releaseId": release_transition.get("releaseId"),
                    "replacementCount": len(
                        release_transition.get("replacements") or []
                    ),
                }
                if release_transition is not None
                else None
            ),
            "timestamp": result["updatedAt"],
        }
    )
    result["contextDigest"] = context_digest(result)
    validate_global_assembly_context(result)
    return result
