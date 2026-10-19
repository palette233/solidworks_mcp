from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from .assembly_contracts import (
    build_assembly_intent_contract,
    build_assembly_plan_contract,
)
from .project_assembly_profile import (
    load_project_assembly_profile,
    module_alias_map,
    module_policy_map,
)
from .project03_dynamic_release_gate import (
    evaluate_project03_ad20_process_request,
    load_project03_ad20_dynamic_closure,
    parse_project03_ad20_process_request,
)


COMMAND_SCHEMA = "ordered-assembly-command/v2"
PLAN_SCHEMA = "ordered-assembly-plan/v2"


class OrderedAssemblyPlannerError(ValueError):
    pass


def _normalize_project_id(project_id: str) -> str:
    value = str(project_id or "").strip().lower()
    if value.isdigit():
        value = f"project{value.zfill(2)}"
    if not value.startswith("project"):
        raise OrderedAssemblyPlannerError(f"非法项目编号：{project_id!r}")
    return value


def parse_ordered_assembly_command(project_id: str, requirement: str) -> dict[str, Any]:
    project_id = _normalize_project_id(project_id)
    profile = load_project_assembly_profile(project_id)
    text = " ".join(str(requirement or "").strip().split())
    if not text:
        raise OrderedAssemblyPlannerError("装配命令不能为空。")
    suffix = project_id.removeprefix("project")
    if f"项目{suffix}" not in text and project_id.upper() not in text.upper():
        raise OrderedAssemblyPlannerError(f"命令必须明确指定项目{suffix}。")

    aliases = module_alias_map(profile)
    canonical_by_fold = {str(alias).casefold(): token for alias, token in aliases.items()}
    alias_pattern = "|".join(
        re.escape(value) for value in sorted(aliases, key=len, reverse=True)
    )
    add_pattern = re.compile(
        rf"(?P<marker>先|再|然后|接着|随后|最后)?\s*"
        rf"(?P<verb>添加|加入|装入|安装)\s*(?P<module>{alias_pattern})",
        flags=re.IGNORECASE,
    )
    matches = list(add_pattern.finditer(text))
    if not matches:
        raise OrderedAssemblyPlannerError("没有识别到任何添加步骤。")

    base = str(profile["baseModule"])
    seen: set[str] = set()
    warnings: list[str] = []
    steps = []
    for match in matches:
        raw_module = match.group("module")
        token = canonical_by_fold.get(raw_module.casefold())
        if token is None:
            raise OrderedAssemblyPlannerError(f"无法识别模组：{raw_module}")
        if token in seen:
            raise OrderedAssemblyPlannerError(f"模组{token}在装配顺序中重复出现。")
        seen.add(token)
        if token == base:
            if steps:
                raise OrderedAssemblyPlannerError(
                    f"{base}必须作为初始基座，不能在其他模组之后添加。"
                )
            warnings.append(f"{base}被解释为初始固定上下文，不作为普通插入步骤。")
            continue
        row = profile["modules"][token]
        steps.append(
            {
                "order": len(steps) + 1,
                "moduleToken": token,
                "moduleLabel": row["label"],
                "orderMarker": match.group("marker") or None,
                "sourceVerb": match.group("verb"),
                "sourceText": match.group(0).strip(),
                "sourceSpan": [match.start(), match.end()],
            }
        )
    if not steps:
        raise OrderedAssemblyPlannerError("至少需要一个待添加模组。")
    if not any(match.group("marker") for match in matches):
        warnings.append("未检测到顺序词，按文本出现顺序执行。")
    if base not in text.upper() and not any(
        alias in text
        for alias, token in aliases.items()
        if token == base and alias != base
    ):
        warnings.append(f"未显式指定基座，安全默认使用固定{base}上下文。")

    process_requests: dict[str, Any] = {}
    if project_id == "project03":
        process_requests["ad20"] = parse_project03_ad20_process_request(text)

    return {
        "schemaVersion": COMMAND_SCHEMA,
        "projectId": project_id,
        "projectProfile": {
            "schemaVersion": profile["schemaVersion"],
            "profileVersion": profile["profileVersion"],
            "profileDigest": profile["profileDigest"],
            "profilePath": profile["profilePath"],
        },
        "operation": "ordered_add_modules",
        "sourceRequirement": requirement,
        "normalizedRequirement": text,
        "initialContextModules": [base],
        "steps": steps,
        "processRequests": process_requests,
        "outputPolicy": {
            "modifyPrototype": False,
            "createIndependentAssemblyPerAcceptedStep": True,
            "stopOnFailure": True,
        },
        "parser": {
            "mode": "controlled-versioned-project-profile",
            "geometricEntitiesGenerated": False,
            "warnings": warnings,
        },
    }


def build_ordered_assembly_plan(intent: dict[str, Any]) -> dict[str, Any]:
    if intent.get("schemaVersion") != COMMAND_SCHEMA:
        raise OrderedAssemblyPlannerError("不支持的有序装配命令版本。")
    project_id = _normalize_project_id(str(intent.get("projectId") or ""))
    profile = load_project_assembly_profile(project_id)
    policies = module_policy_map(profile)
    available = list(
        dict.fromkeys(str(value).upper() for value in intent.get("initialContextModules") or [])
    )
    planned_steps = []
    blockers: list[str] = []
    missing_implementations: list[dict[str, str]] = []
    for raw_step in intent.get("steps") or []:
        token = str(raw_step.get("moduleToken") or "").upper()
        policy = policies.get(token)
        if policy is None:
            raise OrderedAssemblyPlannerError(f"缺少模组{token}的装配策略。")
        required = [str(value).upper() for value in policy.get("requires") or []]
        missing = [value for value in required if value not in available]
        dependencies_satisfied = not missing
        implementation_status = str(policy.get("implementationStatus") or "")
        cad_ready = dependencies_satisfied and implementation_status in {
            "single_module_cad_validated",
            "single_module_static_cad_validated_dynamic_missing",
            "full_static_cad_validated_hybrid_snapshot",
            "full_static_cad_validated_parent_context_snapshot",
        }
        if missing:
            blockers.append(
                f"步骤{raw_step['order']}添加{token}前缺少：{'、'.join(missing)}"
            )
            status = "blocked_by_order"
        elif cad_ready:
            status = "cad_validated_single_step"
        else:
            status = "preview_ready_implementation_missing"
            missing_implementations.append(
                {
                    "moduleToken": token,
                    "reason": str(
                        policy.get("missingImplementation") or "尚未实现CAD增量执行。"
                    ),
                }
            )
        planned_steps.append(
            {
                **raw_step,
                "stepId": f"step-{int(raw_step['order']):02d}-{token.lower()}",
                "availableBefore": list(available),
                "requiredModules": required,
                "missingRequiredModules": missing,
                "dependenciesSatisfied": dependencies_satisfied,
                "placementKind": policy["placementKind"],
                "ruleSummary": policy["ruleSummary"],
                "acceptanceChecks": list(policy["acceptanceChecks"]),
                "implementationStatus": implementation_status,
                "missingImplementation": policy.get("missingImplementation"),
                "engineeringLimitations": list(policy.get("engineeringLimitations") or []),
                "cadExecutableNow": cad_ready,
                "status": status,
                "checkpointPolicy": {
                    "saveIndependentAssembly": True,
                    "reopenAndVerify": True,
                    "runFastAabbAfterStep": True,
                    "runConditionalBrepAfterStep": cad_ready,
                    "stopOnFailure": True,
                },
            }
        )
        if dependencies_satisfied:
            available.append(token)

    order_valid = not blockers
    cad_ready_count = sum(1 for row in planned_steps if row["cadExecutableNow"])
    dynamic_process_gate: dict[str, Any] | None = None
    if project_id == "project03":
        relative_path = str(
            (profile.get("artifacts") or {}).get("ad20ContextRebasedDynamicClosure")
            or ""
        )
        if not relative_path:
            raise OrderedAssemblyPlannerError("项目03配置缺少AD20上下文校正动态闭包。")
        workspace = Path(__file__).resolve().parents[4]
        closure = load_project03_ad20_dynamic_closure(workspace / relative_path)
        dynamic_process_gate = evaluate_project03_ad20_process_request(
            dict((intent.get("processRequests") or {}).get("ad20") or {}),
            closure,
        )
    dynamic_request_accepted = (
        dynamic_process_gate is None or dynamic_process_gate.get("accepted") is True
    )
    execution_ready = (
        order_valid
        and cad_ready_count == len(planned_steps)
        and dynamic_request_accepted
    )
    return {
        "schemaVersion": PLAN_SCHEMA,
        "projectId": project_id,
        "projectProfile": dict(intent.get("projectProfile") or {}),
        "sourceRequirement": intent.get("sourceRequirement"),
        "initialContextModules": intent.get("initialContextModules") or [],
        "steps": planned_steps,
        "processRequests": intent.get("processRequests") or {},
        "dynamicProcessGate": dynamic_process_gate,
        "summary": {
            "stepCount": len(planned_steps),
            "orderValid": order_valid,
            "previewReady": order_valid,
            "cadExecutableStepCount": cad_ready_count,
            "allStepsCadExecutableNow": execution_ready,
            "dynamicProcessRequestAccepted": dynamic_request_accepted,
            "finalPlannedModuleTokens": available,
            "orderBlockerCount": len(blockers),
            "missingImplementationCount": len(missing_implementations),
        },
        "orderBlockers": blockers,
        "missingImplementations": missing_implementations,
        "executionBoundary": {
            "mode": "preview_only_multi_step",
            "modifiesPrototype": False,
            "safeToStartCad": execution_ready,
            "reason": (
                "所有步骤均具备已验证的单模组CAD执行能力，且显式动态请求已通过证据门禁。"
                if execution_ready
                else str(dynamic_process_gate.get("message"))
                if order_valid
                and cad_ready_count == len(planned_steps)
                and dynamic_process_gate is not None
                and dynamic_process_gate.get("accepted") is not True
                else "顺序计划可审核，但仍有项目专属CAD动作和逐步证据未实现。"
                if order_valid
                else "装配顺序缺少前置模组，必须先调整命令。"
            ),
        },
    }


def preview_ordered_assembly(project_id: str, requirement: str) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()
    intent = parse_ordered_assembly_command(project_id, requirement)
    parsed_clock = perf_counter()
    plan = build_ordered_assembly_plan(intent)
    intent_contract = build_assembly_intent_contract(intent)
    plan_contract = build_assembly_plan_contract(plan, intent_contract)
    intent["intentDigest"] = intent_contract["intentDigest"]
    plan["intentDigest"] = intent_contract["intentDigest"]
    plan["planDigest"] = plan_contract["planDigest"]
    completed_clock = perf_counter()
    return {
        "success": True,
        "message": (
            "跨项目有序装配计划已生成，可审核顺序、依赖和CAD实现缺口。"
            if plan["summary"]["orderValid"]
            else "计划已生成，但顺序依赖检查未通过。"
        ),
        "intent": intent,
        "plan": plan,
        "contracts": {"intent": intent_contract, "plan": plan_contract},
        "audit": {
            "runId": f"{intent['projectId']}-ordered-{uuid4().hex[:12]}",
            "startedAt": started_at.isoformat().replace("+00:00", "Z"),
            "completedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "timingSeconds": {
                "parseCommand": round(parsed_clock - started_clock, 9),
                "buildPlan": round(completed_clock - parsed_clock, 9),
                "total": round(completed_clock - started_clock, 9),
            },
        },
    }
