from __future__ import annotations

import copy
import re
from typing import Any


SEMANTIC_ASSEMBLY_INTENT_SCHEMA = "semantic-assembly-intent/v1"
SUPPORTED_PROJECT = "project02"
SUPPORTED_PURPOSES = {"installation", "spacing"}
SUPPORTED_APPLICATION_MODES = {"driving", "validate_only"}
SOLVING_STATE_VALUES = {
    "rigid": (0, "swComponentRigidSolving"),
    "flexible": (1, "swComponentFlexibleSolving"),
}


class SemanticAssemblyIntentError(ValueError):
    pass


def _module_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"A\d{3}", text.upper())))


def _solving_states(text: str, module_tokens: list[str]) -> dict[str, str]:
    states: dict[str, str] = {}
    for token in module_tokens:
        rigid = bool(
            re.search(
                rf"{re.escape(token)}[^，。；;]{{0,12}}(?:保持|设为|设置为|按|作为)?\s*刚性",
                text,
                flags=re.IGNORECASE,
            )
        )
        flexible = bool(
            re.search(
                rf"{re.escape(token)}[^，。；;]{{0,12}}(?:保持|设为|设置为|按|作为)?\s*柔性",
                text,
                flags=re.IGNORECASE,
            )
        )
        if rigid and flexible:
            raise SemanticAssemblyIntentError(f"{token}同时被描述为刚性和柔性。")
        if rigid:
            states[token] = "rigid"
        elif flexible:
            states[token] = "flexible"
    return states


def parse_project02_semantic_assembly_intent(requirement: str) -> dict[str, Any]:
    """Parse a deliberately bounded Project02 installation command.

    The parser never emits geometric entities.  It only extracts engineering
    intent that can later be grounded against the semantic-port catalog.
    Unsupported or ambiguous wording is rejected instead of guessed.
    """

    text = str(requirement or "").strip()
    if not text:
        raise SemanticAssemblyIntentError("自然语言需求不能为空。")
    if "项目02" not in text and "PROJECT02" not in text.upper():
        raise SemanticAssemblyIntentError("当前受控解析器只支持明确指定项目02。")

    tokens = _module_tokens(text)
    unsupported = sorted(set(tokens) - {"A500", "A600", "A700"})
    if unsupported:
        raise SemanticAssemblyIntentError(
            "当前项目02 Demo 尚不支持这些模组：" + "、".join(unsupported)
        )

    add_match = re.search(r"(?:新增|加入|添加|装入)\s*(A\d{3})", text, re.IGNORECASE)
    if add_match:
        module_to_add = add_match.group(1).upper()
    elif "A500" in tokens and "安装" in text:
        module_to_add = "A500"
    else:
        raise SemanticAssemblyIntentError("无法确定需要新增的模组；请使用“新增A500”。")
    if module_to_add != "A500":
        raise SemanticAssemblyIntentError("当前受控解析器只支持新增A500。")

    if not ({"A500", "A600"} <= set(tokens) and "安装" in text):
        raise SemanticAssemblyIntentError("需求必须明确说明将A500安装到A600。")

    fixed_context: list[str] = []
    if "固定上下文" in text or "固定的上下文" in text:
        fixed_context = [token for token in ("A600", "A700") if token in tokens]
    elif "固定" in text:
        fixed_context = [token for token in ("A600", "A700") if token in tokens]
    if "A600" not in fixed_context:
        raise SemanticAssemblyIntentError("A600必须明确作为固定上下文。")

    relationships: list[dict[str, Any]] = [
        {
            "relationshipId": "install-A500-on-A600",
            "sourceModule": "A500",
            "targetModule": "A600",
            "purpose": "installation",
            "applicationMode": "driving",
            "evidence": "自然语言同时包含A500、A600和安装意图。",
        }
    ]

    spacing_requested = {"A500", "A700"} <= set(tokens) and any(
        keyword in text for keyword in ("间距", "距离", "50 mm", "50mm")
    )
    if spacing_requested:
        distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:毫米|mm)", text, re.IGNORECASE)
        distance_mm = float(distance_match.group(1)) if distance_match else 50.0
        explicitly_driving = bool(
            re.search(r"(?:作为|设为|用作)[^，。；;]{0,8}驱动", text)
        ) and not bool(re.search(r"不要[^，。；;]{0,8}驱动", text))
        validate_only = any(
            keyword in text
            for keyword in ("验证", "检查", "校验", "只核验", "只验证", "不要将")
        )
        mode = "driving" if explicitly_driving else "validate_only" if validate_only else "validate_only"
        relationships.append(
            {
                "relationshipId": "check-A500-A700-spacing",
                "sourceModule": "A500",
                "targetModule": "A700",
                "purpose": "spacing",
                "applicationMode": mode,
                "parameters": {"distanceMillimeters": distance_mm},
                "evidence": "自然语言包含A500、A700和距离/间距要求。",
            }
        )

    states = _solving_states(text, tokens)
    independent = any(keyword in text for keyword in ("独立装配体", "另存", "新装配体"))
    warnings: list[str] = []
    if "A500" not in states:
        warnings.append("未显式指定A500刚柔性；后续将核对目录中的组件语义。")
    if "A700" in tokens and "A700" not in states:
        warnings.append("未显式指定A700刚柔性；后续将核对既有上下文状态。")
    if not independent:
        warnings.append("未明确输出策略；安全默认仍为独立装配体且不修改原型。")

    return {
        "schemaVersion": SEMANTIC_ASSEMBLY_INTENT_SCHEMA,
        "projectId": SUPPORTED_PROJECT,
        "operation": "add_module",
        "sourceRequirement": text,
        "moduleToAdd": module_to_add,
        "mentionedModules": tokens,
        "fixedContextModules": fixed_context,
        "componentSolvingStates": states,
        "relationships": relationships,
        "outputPolicy": {
            "modifyPrototype": False,
            "createIndependentAssembly": True,
        },
        "parser": {
            "mode": "controlled-project02-rules",
            "geometricEntitiesGenerated": False,
            "warnings": warnings,
        },
    }


def _port_capabilities(port: dict[str, Any]) -> set[str]:
    return {str(value).strip() for value in port.get("capabilities") or [] if str(value).strip()}


def _compatible_templates(
    catalog: dict[str, Any], port_a: dict[str, Any], port_b: dict[str, Any]
) -> list[dict[str, Any]]:
    type_a = str(port_a.get("interfaceType") or "")
    type_b = str(port_b.get("interfaceType") or "")
    result = []
    for template in catalog.get("connectionTemplates") or []:
        left = str(template.get("interfaceTypeA") or "")
        right = str(template.get("interfaceTypeB") or "")
        if (type_a, type_b) in {(left, right), (right, left)}:
            result.append(template)
    return result


def _candidate_score(port_a: dict[str, Any], port_b: dict[str, Any]) -> int:
    return sum(
        100 if str(port.get("status") or "") == "confirmed" else 0
        for port in (port_a, port_b)
    ) + sum(10 if port.get("evidence") else 0 for port in (port_a, port_b))


def _select_connection(
    catalog: dict[str, Any], relationship: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = str(relationship["sourceModule"])
    target = str(relationship["targetModule"])
    purpose = str(relationship["purpose"])
    candidates: list[dict[str, Any]] = []
    source_ports = [
        item
        for item in catalog.get("ports") or []
        if str(item.get("moduleToken") or "").upper() == source
        and purpose in _port_capabilities(item)
    ]
    target_ports = [
        item
        for item in catalog.get("ports") or []
        if str(item.get("moduleToken") or "").upper() == target
        and purpose in _port_capabilities(item)
    ]
    for port_a in source_ports:
        for port_b in target_ports:
            for template in _compatible_templates(catalog, port_a, port_b):
                template_purposes = {
                    str(value) for value in template.get("purposes") or []
                }
                if template_purposes and purpose not in template_purposes:
                    continue
                candidates.append(
                    {
                        "portAId": port_a["portId"],
                        "portBId": port_b["portId"],
                        "templateId": template["templateId"],
                        "score": _candidate_score(port_a, port_b),
                        "portAStatus": port_a.get("status"),
                        "portBStatus": port_b.get("status"),
                        "reason": (
                            f"{source}/{target}模组匹配，双方端口均声明{purpose}能力，"
                            "且接口类型存在兼容模板。"
                        ),
                        "template": template,
                    }
                )
    candidates.sort(
        key=lambda item: (-int(item["score"]), item["portAId"], item["portBId"], item["templateId"])
    )
    if not candidates:
        raise SemanticAssemblyIntentError(
            f"没有找到{source}到{target}的{purpose}兼容语义端口。"
        )
    best_score = candidates[0]["score"]
    top = [item for item in candidates if item["score"] == best_score]
    if len(top) != 1:
        raise SemanticAssemblyIntentError(
            f"{source}到{target}的{purpose}端口存在{len(top)}个同分候选，需要人工消歧。"
        )
    selected = copy.deepcopy(top[0])
    template = selected.pop("template")
    requested_mode = str(relationship["applicationMode"])
    step_modes = {
        str(step.get("applicationMode") or "driving")
        for step in template.get("mateSteps") or []
    }
    if requested_mode not in SUPPORTED_APPLICATION_MODES:
        raise SemanticAssemblyIntentError(f"不支持应用模式：{requested_mode}")
    if requested_mode == "driving" and step_modes == {"validate_only"}:
        raise SemanticAssemblyIntentError(
            f"关系{relationship['relationshipId']}被要求作为驱动，但已验证模板仅允许validate_only；"
            "这会重复约束并可能造成过约束。"
        )
    if requested_mode == "validate_only" and "driving" in step_modes:
        raise SemanticAssemblyIntentError(
            f"关系{relationship['relationshipId']}被要求只验证，但模板会生成驱动配合。"
        )
    return selected, [{key: value for key, value in item.items() if key != "template"} for item in candidates]


def _state_name(module: dict[str, Any]) -> str | None:
    value = module.get("SolvingState")
    if value == 0:
        return "rigid"
    if value == 1:
        return "flexible"
    return None


def resolve_semantic_assembly_intent(
    intent: dict[str, Any],
    semantic_catalog: dict[str, Any],
    source_graph: dict[str, Any],
    plan_template: dict[str, Any],
) -> dict[str, Any]:
    """Ground an intent to catalog ports and a deterministic assembly plan."""

    if intent.get("schemaVersion") != SEMANTIC_ASSEMBLY_INTENT_SCHEMA:
        raise SemanticAssemblyIntentError("不支持的语义装配意图版本。")
    if intent.get("projectId") != semantic_catalog.get("projectId"):
        raise SemanticAssemblyIntentError("意图项目与语义端口目录不一致。")
    module_to_add = str(intent.get("moduleToAdd") or "").upper()
    template_component = copy.deepcopy(plan_template.get("componentToAdd") or {})
    if str(template_component.get("ModuleToken") or "").upper() != module_to_add:
        raise SemanticAssemblyIntentError("安装计划模板中找不到待新增模组。")

    requested_states = intent.get("componentSolvingStates") or {}
    state_checks: list[dict[str, Any]] = []
    modules = [*list(source_graph.get("Modules") or []), template_component]
    by_token = {str(item.get("ModuleToken") or "").upper(): item for item in modules}
    blocking_issues: list[str] = []
    for token, requested in requested_states.items():
        normalized_token = str(token).upper()
        module = by_token.get(normalized_token)
        if module is None:
            blocking_issues.append(f"刚柔性要求引用未知模组{normalized_token}。")
            continue
        actual = _state_name(module)
        matched = actual == requested
        state_checks.append(
            {
                "moduleToken": normalized_token,
                "requested": requested,
                "catalogState": actual,
                "matched": matched,
            }
        )
        if not matched:
            blocking_issues.append(
                f"{normalized_token}要求{requested}，但目录/源图记录为{actual or 'unknown'}。"
            )

    fixed_context = [str(value).upper() for value in intent.get("fixedContextModules") or []]
    source_tokens = {str(item.get("ModuleToken") or "").upper() for item in source_graph.get("Modules") or []}
    missing_context = sorted(set(fixed_context) - source_tokens)
    if missing_context:
        blocking_issues.append("固定上下文不存在于源图：" + "、".join(missing_context))

    selected_connections: list[dict[str, Any]] = []
    candidate_audit: list[dict[str, Any]] = []
    for relationship in intent.get("relationships") or []:
        selected, candidates = _select_connection(semantic_catalog, relationship)
        relationship_parameters = copy.deepcopy(relationship.get("parameters") or {})
        connection_parameters: dict[str, Any] = {}
        if relationship_parameters.get("distanceMillimeters") is not None:
            connection_parameters["distanceMeters"] = (
                float(relationship_parameters["distanceMillimeters"]) / 1000.0
            )
        selected_connections.append(
            {
                "connectionId": relationship["relationshipId"],
                "portAId": selected["portAId"],
                "portBId": selected["portBId"],
                "templateId": selected["templateId"],
                "parameters": connection_parameters,
            }
        )
        candidate_audit.append(
            {
                "relationshipId": relationship["relationshipId"],
                "purpose": relationship["purpose"],
                "selected": selected,
                "candidates": candidates,
            }
        )

    if blocking_issues:
        raise SemanticAssemblyIntentError("；".join(blocking_issues))

    plan = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": f"{intent['projectId']}-nl-add-{module_to_add.lower()}-v1",
        "baseModuleToken": plan_template.get("baseModuleToken") or "A600",
        "initialPlacementMode": plan_template.get("initialPlacementMode") or "deterministic",
        "fixedContextModuleTokens": fixed_context,
        "componentSolvingStates": copy.deepcopy(requested_states),
        "componentToAdd": template_component,
        "connections": selected_connections,
        "intentProvenance": {
            "schemaVersion": intent["schemaVersion"],
            "sourceRequirement": intent["sourceRequirement"],
            "parserMode": (intent.get("parser") or {}).get("mode"),
        },
    }
    if isinstance(plan_template.get("cadVerificationEvidence"), dict):
        plan["cadVerificationEvidence"] = copy.deepcopy(
            plan_template["cadVerificationEvidence"]
        )
    return {
        "success": True,
        "intent": intent,
        "assemblyPlan": plan,
        "selectionAudit": candidate_audit,
        "solvingStateChecks": state_checks,
        "blockingIssues": [],
        "requiresHumanConfirmation": True,
        "message": "自然语言需求已解析并确定性绑定到已注册语义端口；尚未修改SolidWorks。",
    }
