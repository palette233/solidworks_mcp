from __future__ import annotations

import json
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
from .project02_requirements import PROJECT02_MODULES


ORDERED_ASSEMBLY_SCHEMA = "project02-ordered-assembly-command/v1"
ORDERED_PLAN_SCHEMA = "project02-ordered-assembly-plan/v1"
ORDERED_CLOSURE_RELATIVE_PATH = Path(
    "demo/semantic_ports/project02_ordered_true_increment_v1/"
    "project02_ordered_true_increment_closure.json"
)
FULL_MACHINE_CLOSURE_RELATIVE_PATH = Path(
    "demo/semantic_ports/project02_full_machine_increment_v1/"
    "project02_full_machine_closure.json"
)


class SemanticAssemblySequenceError(ValueError):
    pass


def load_project02_ordered_assembly_closure(workspace: Path) -> dict[str, Any]:
    full_path = (workspace / FULL_MACHINE_CLOSURE_RELATIVE_PATH).resolve()
    full_payload = json.loads(full_path.read_text(encoding="utf-8")) if full_path.is_file() else {}
    full_release = full_payload.get("releaseDecision") or {}
    if full_release.get("staticTenObjectDemoReleaseAllowed") is True:
        path = full_path
        payload = full_payload
    else:
        path = (workspace / ORDERED_CLOSURE_RELATIVE_PATH).resolve()
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not path.is_file():
        return {
            "available": False,
            "status": "NOT_RUN",
            "message": "尚未生成项目02真正累计装配闭环证据。",
            "evidencePath": str(path),
        }
    release = payload.get("releaseDecision") or {}
    gate = dict(payload.get("interferenceGate") or {})
    template_evidence_path = path
    live_index_path = (
        workspace
        / "demo/semantic_ports/project02_full_machine_increment_v1/latest_live_full_chain.json"
    ).resolve()
    live_job_id = None
    live_timing_path = None
    if live_index_path.is_file():
        live_index = json.loads(live_index_path.read_text(encoding="utf-8"))
        live_closure_path = Path(str(live_index.get("staticClosurePath") or "")).resolve()
        if live_closure_path.is_file():
            live_closure = json.loads(live_closure_path.read_text(encoding="utf-8"))
            if live_closure.get("staticFullChainAccepted") is True:
                live_job_id = live_index.get("jobId")
                live_timing_path = Path(str(live_index.get("timingReportPath") or "")).resolve()
                path = live_closure_path
                gate = {
                    "expectedPairCount": live_closure.get("expectedPairCount"),
                    "evaluatedPairCount": live_closure.get("evaluatedUniquePairCount"),
                    "checkedPairCount": live_closure.get("evaluatedUniquePairCount"),
                    "acceptedPairCount": live_closure.get("acceptedPairCount"),
                    "rejectedPairCount": len(live_closure.get("rejectedEvidence") or []),
                    "pairCoverageComplete": (
                        live_closure.get("evaluatedUniquePairCount")
                        == live_closure.get("expectedPairCount")
                    ),
                }
                release = {
                    "staticTenObjectDemoReleaseAllowed": True,
                    "productionReleaseAllowed": False,
                    "reason": live_closure.get("releaseReason"),
                }
                payload = {
                    **payload,
                    "status": "LIVE_FULL_CHAIN_STATIC_ACCEPTED",
                    "allCadStepsPassed": True,
                    "finalAssemblyPath": live_closure.get("finalAssemblyPath"),
                    "interferenceGate": gate,
                    "releaseDecision": release,
                    "blockingIssues": [],
                }
    if "checkedPairCount" not in gate and "evaluatedPairCount" in gate:
        gate["checkedPairCount"] = gate["evaluatedPairCount"]
    static_release_allowed = (
        release.get("staticTenObjectDemoReleaseAllowed") is True
        or release.get("staticSevenModuleDemoReleaseAllowed") is True
    )
    all_cad_steps_passed = payload.get("allCadStepsPassed")
    if all_cad_steps_passed is None:
        all_cad_steps_passed = bool(
            static_release_allowed
            and gate.get("acceptedPairCount") == gate.get("expectedPairCount")
            and not (payload.get("blockingIssues") or [])
        )
    return {
        "available": True,
        "status": payload.get("status"),
        "allCadStepsPassed": all_cad_steps_passed,
        "finalAssemblyPath": payload.get("finalAssemblyPath"),
        "sequence": payload.get("sequence") or [],
        "steps": payload.get("steps") or [],
        "interferenceGate": gate,
        "blockingIssues": payload.get("blockingIssues") or [],
        "knownLimitations": payload.get("knownLimitations") or [],
        "releaseDecision": payload.get("releaseDecision") or {},
        "timingSeconds": (
            json.loads(live_timing_path.read_text(encoding="utf-8"))
            if live_timing_path and live_timing_path.is_file()
            else payload.get("timingSeconds") or {}
        ),
        "evidencePath": str(path),
        "templateClosureEvidencePath": str(template_evidence_path),
        "liveJobId": live_job_id,
    }


MODULE_ALIASES: dict[str, str] = {
    "A100": "A100",
    "龙门模组": "A100",
    "点胶龙门": "A100",
    "A180": "A180",
    "扫描模组": "A180",
    "扫码模组": "A180",
    "A200": "A200",
    "CCD模组": "A200",
    "视觉模组": "A200",
    "A300": "A300",
    "排胶模组": "A300",
    "废胶收集模组": "A300",
    "A500": "A500",
    "标定模组": "A500",
    "校准模组": "A500",
    "A600": "A600",
    "箱体": "A600",
    "箱体模组": "A600",
    "A700": "A700",
    "清洁模组": "A700",
    "称重模组": "A700",
    "清洁称重模组": "A700",
    "A800": "A800",
    "传输模组": "A800",
    "输送模组": "A800",
    "T401": "T401",
    "供胶模组": "T401",
    "供胶系统": "T401",
}


MODULE_POLICIES: dict[str, dict[str, Any]] = {
    "A800": {
        "requires": ["A600"],
        "placementKind": "source_installation_interface_case_anchor",
        "ruleSummary": "用A600/A800原型安装接口重建重合与宽度配合，并以项目02案例锚点封闭纵向剩余自由度。",
        "acceptanceChecks": ["重合35", "宽度9", "案例锚点位姿", "保存重开", "AABB/条件B-rep"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": ["仍以项目02案例锚点封闭原型安装接口留下的纵向自由度。"],
    },
    "A180": {
        "requires": ["A800"],
        "placementKind": "mechanical_installation_with_provisional_optical_gate",
        "ruleSummary": "先按A600安装端口插入A180，再验证其与A800条码目标的粗布局光学关系。",
        "acceptanceChecks": ["重合34", "距离24", "案例锚点位姿", "保存重开", "条码工作距离", "A180/A800条件B-rep"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": [
            "槽口3尚未作为驱动配合重建。",
            "扫描原点由对称照明窗口推断，光轴符号、PLC停靠点和生产视线仍待确认。",
        ],
    },
    "A200": {
        "requires": ["A800"],
        "placementKind": "vision_workstation_alignment",
        "ruleSummary": "让CCD视场覆盖传输工作位，并保持结构通道和维护空间。",
        "acceptanceChecks": ["工作位覆盖", "视场范围", "工作距离", "结构通道"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": [
            "当前3条安装配合使用项目02源位姿锚点封闭残余自由度；CCD光学端口仍是项目02案例参数。",
            "已完成保存重开与逐步装配，但条件B-rep闭包完成前不得进入整机静态发布。",
        ],
    },
    "A300": {
        "requires": ["A600", "A700"],
        "placementKind": "service_side_and_valve_reach",
        "ruleSummary": "按操作面剩余空间布置，并保证排胶点进入胶阀可达区。",
        "acceptanceChecks": ["操作面侧空间", "排胶点可达", "维护间隙", "实体分离"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": ["当前用项目02原型位姿选择距离配合的正确半空间分支；后续应由厂商安装基准或有符号半空间规则替代。"],
    },
    "A700": {
        "requires": ["A600", "A180"],
        "placementKind": "service_side_and_valve_reach",
        "ruleSummary": "优先布置在操作面侧，空间不足时转到对侧，并保证清洁/称重点可达。",
        "acceptanceChecks": ["操作面侧容量", "清洁点可达", "称重点可达", "维护间隙"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": [
            "A700必须在创建配合前恢复为柔性；刚性会使健康的宽度10/距离29表现为过定义。",
            "清洁/称重维护包络仍为项目02原型坐标下的粗估，模组移动后必须重算。",
        ],
    },
    "A500": {
        "requires": ["A600", "A700"],
        "placementKind": "semantic_port_mate_plan",
        "ruleSummary": "用A600安装端口完成定位，并把A500/A700间距作为只验证关系。",
        "acceptanceChecks": ["3条驱动配合", "完全约束", "50 mm实测", "条件B-rep"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
    },
    "T401": {
        "requires": ["A600", "A200"],
        "placementKind": "supply_access_and_hose_route",
        "ruleSummary": "布置在龙门外侧可维护区域，并保留供胶管路连接空间。",
        "acceptanceChecks": ["供胶维护空间", "管路连接方向", "与运动区隔离"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": [
            "T401在自然语言层表示两套同源实例，执行时按T401-1、T401-2两个CAD检查点插入。",
            "当前安装配合与源位姿锚点来自项目02；软管扫掠和最终维护包络尚未验证。",
        ],
    },
    "A100": {
        "requires": ["A800", "A180", "A700", "A300", "A500"],
        "placementKind": "dual_valve_reach_coverage",
        "ruleSummary": "最后反求龙门位置，使双胶阀覆盖传输工作区和已布置功能模组。",
        "acceptanceChecks": ["工作位1/2覆盖", "功能点覆盖", "门洞通道", "静态实体安全"],
        "implementationStatus": "single_module_cad_validated",
        "missingImplementation": None,
        "engineeringLimitations": [
            "A100顶层3条安装配合、完全约束、保存重开已通过。",
            "静态Demo将A100顶层和内部A150均设为刚性，并固定A150的Slot2=0%工作状态。",
            "A100/A600新增干涉已消除；剩余接触均与原型基准一致。",
            "该闭环只证明静态工作状态，不替代双胶阀全行程运动仿真。",
        ],
    },
}

# The constants above remain as readable historical context for this module, but
# runtime planning is now driven by the versioned project profile.  This keeps
# the natural-language parser deterministic while moving project-specific
# engineering knowledge out of Python code.
PROJECT02_ASSEMBLY_PROFILE = load_project_assembly_profile("project02")
ORDERED_CLOSURE_RELATIVE_PATH = Path(
    PROJECT02_ASSEMBLY_PROFILE["artifacts"]["orderedClosure"]
)
FULL_MACHINE_CLOSURE_RELATIVE_PATH = Path(
    PROJECT02_ASSEMBLY_PROFILE["artifacts"]["fullMachineClosure"]
)
MODULE_ALIASES = module_alias_map(PROJECT02_ASSEMBLY_PROFILE)
MODULE_POLICIES = module_policy_map(PROJECT02_ASSEMBLY_PROFILE)


_ALIASES_BY_LENGTH = sorted(MODULE_ALIASES, key=len, reverse=True)
_ALIAS_PATTERN = "|".join(re.escape(value) for value in _ALIASES_BY_LENGTH)
_ADD_PATTERN = re.compile(
    rf"(?P<marker>先|再|然后|接着|随后|最后)?\s*"
    rf"(?P<verb>添加|加入|装入|安装)\s*(?P<module>{_ALIAS_PATTERN})",
    flags=re.IGNORECASE,
)


def _canonical_module(value: str) -> str:
    direct = MODULE_ALIASES.get(value)
    if direct:
        return direct
    upper = value.upper()
    direct = MODULE_ALIASES.get(upper)
    if direct:
        return direct
    raise SemanticAssemblySequenceError(f"无法识别模组：{value}")


def _module_label(token: str) -> str:
    row = PROJECT02_ASSEMBLY_PROFILE["modules"].get(token)
    if row is not None:
        return str(row["label"])
    return str(PROJECT02_MODULES[token]["label"])


def parse_project02_ordered_assembly_command(requirement: str) -> dict[str, Any]:
    text = " ".join(str(requirement or "").strip().split())
    if not text:
        raise SemanticAssemblySequenceError("装配命令不能为空。")
    if "项目02" not in text and "PROJECT02" not in text.upper():
        raise SemanticAssemblySequenceError("当前有序装配Demo只支持明确指定项目02。")

    matches = list(_ADD_PATTERN.finditer(text))
    if not matches:
        raise SemanticAssemblySequenceError(
            "没有识别到添加步骤；请使用“先添加A800，再添加A180，然后添加A500”。"
        )

    parsed_steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    base_context = ["A600"]
    warnings: list[str] = []
    for match in matches:
        token = _canonical_module(match.group("module"))
        if token in seen:
            raise SemanticAssemblySequenceError(f"模组{token}在装配顺序中重复出现。")
        seen.add(token)
        if token == "A600":
            if parsed_steps:
                raise SemanticAssemblySequenceError("A600必须作为初始基座，不能在其他模组之后添加。")
            warnings.append("A600被解释为初始固定基座，不作为普通增量插入步骤。")
            continue
        if token not in MODULE_POLICIES:
            raise SemanticAssemblySequenceError(f"当前项目02 Demo尚未登记模组{token}。")
        parsed_steps.append(
            {
                "order": len(parsed_steps) + 1,
                "moduleToken": token,
                "moduleLabel": _module_label(token),
                "orderMarker": match.group("marker") or None,
                "sourceVerb": match.group("verb"),
                "sourceText": match.group(0).strip(),
                "sourceSpan": [match.start(), match.end()],
            }
        )

    if not parsed_steps:
        raise SemanticAssemblySequenceError("至少需要一个待添加模组。")
    if not any(match.group("marker") for match in matches):
        warnings.append("未检测到“先/再/然后/最后”等顺序词，当前按文本出现顺序执行。")
    if "A600" not in text.upper() and "箱体" not in text:
        warnings.append("未显式指定基座；项目02安全默认使用固定A600上下文。")

    return {
        "schemaVersion": ORDERED_ASSEMBLY_SCHEMA,
        "projectId": "project02",
        "projectProfile": {
            "schemaVersion": PROJECT02_ASSEMBLY_PROFILE["schemaVersion"],
            "profileVersion": PROJECT02_ASSEMBLY_PROFILE["profileVersion"],
            "profileDigest": PROJECT02_ASSEMBLY_PROFILE["profileDigest"],
            "profilePath": PROJECT02_ASSEMBLY_PROFILE["profilePath"],
        },
        "operation": "ordered_add_modules",
        "sourceRequirement": requirement,
        "normalizedRequirement": text,
        "initialContextModules": base_context,
        "steps": parsed_steps,
        "outputPolicy": {
            "modifyPrototype": False,
            "createIndependentAssemblyPerAcceptedStep": True,
            "stopOnFailure": True,
        },
        "parser": {
            "mode": "controlled-project02-ordered-rules",
            "geometricEntitiesGenerated": False,
            "warnings": warnings,
        },
    }


def build_project02_ordered_assembly_plan(intent: dict[str, Any]) -> dict[str, Any]:
    if intent.get("schemaVersion") != ORDERED_ASSEMBLY_SCHEMA:
        raise SemanticAssemblySequenceError("不支持的有序装配命令版本。")

    available = list(dict.fromkeys(str(value).upper() for value in intent.get("initialContextModules") or []))
    planned_steps: list[dict[str, Any]] = []
    order_blockers: list[str] = []
    missing_implementations: list[dict[str, str]] = []

    for raw_step in intent.get("steps") or []:
        token = str(raw_step.get("moduleToken") or "").upper()
        policy = MODULE_POLICIES.get(token)
        if policy is None:
            raise SemanticAssemblySequenceError(f"缺少模组{token}的装配策略。")
        required = list(policy["requires"])
        missing = [item for item in required if item not in available]
        dependencies_satisfied = not missing
        implementation_status = str(policy["implementationStatus"])
        cad_ready = dependencies_satisfied and implementation_status == "single_module_cad_validated"
        if missing:
            blocker = f"步骤{raw_step['order']}添加{token}前缺少：{'、'.join(missing)}"
            order_blockers.append(blocker)
            step_status = "blocked_by_order"
        elif cad_ready:
            step_status = "cad_validated_single_step"
        else:
            step_status = "preview_ready_implementation_missing"
            missing_implementations.append(
                {
                    "moduleToken": token,
                    "reason": str(policy.get("missingImplementation") or "尚未实现CAD增量执行。"),
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
                "status": step_status,
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

    order_valid = not order_blockers
    cad_ready_count = sum(1 for item in planned_steps if item["cadExecutableNow"])
    return {
        "schemaVersion": ORDERED_PLAN_SCHEMA,
        "projectId": "project02",
        "projectProfile": dict(intent.get("projectProfile") or {}),
        "sourceRequirement": intent.get("sourceRequirement"),
        "initialContextModules": intent.get("initialContextModules") or [],
        "steps": planned_steps,
        "summary": {
            "stepCount": len(planned_steps),
            "orderValid": order_valid,
            "previewReady": order_valid,
            "cadExecutableStepCount": cad_ready_count,
            "allStepsCadExecutableNow": order_valid and cad_ready_count == len(planned_steps),
            "finalPlannedModuleTokens": available,
            "orderBlockerCount": len(order_blockers),
            "missingImplementationCount": len(missing_implementations),
        },
        "orderBlockers": order_blockers,
        "missingImplementations": missing_implementations,
        "executionBoundary": {
            "mode": "preview_only_multi_step",
            "modifiesPrototype": False,
            "safeToStartCad": order_valid and cad_ready_count == len(planned_steps),
            "reason": (
                "所有步骤均具备已验证的单模组CAD执行能力。"
                if order_valid and cad_ready_count == len(planned_steps)
                else "顺序计划可审核，但仍有模组缺少语义端口或增量CAD执行模板。"
                if order_valid
                else "装配顺序缺少前置模组，必须先调整命令。"
            ),
        },
    }


def preview_project02_ordered_assembly(requirement: str) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()
    intent = parse_project02_ordered_assembly_command(requirement)
    parsed_clock = perf_counter()
    plan = build_project02_ordered_assembly_plan(intent)
    intent_contract = build_assembly_intent_contract(intent)
    plan_contract = build_assembly_plan_contract(plan, intent_contract)
    intent["intentDigest"] = intent_contract["intentDigest"]
    plan["intentDigest"] = intent_contract["intentDigest"]
    plan["planDigest"] = plan_contract["planDigest"]
    planned_clock = perf_counter()
    completed_at = datetime.now(timezone.utc)
    return {
        "success": True,
        "message": (
            "有序装配计划已生成，可在启动SolidWorks前审核顺序、依赖和实现状态。"
            if plan["summary"]["orderValid"]
            else "已生成有序装配计划，但顺序依赖检查未通过。"
        ),
        "intent": intent,
        "plan": plan,
        "contracts": {
            "intent": intent_contract,
            "plan": plan_contract,
        },
        "audit": {
            "runId": f"project02-ordered-{uuid4().hex[:12]}",
            "startedAt": started_at.isoformat().replace("+00:00", "Z"),
            "completedAt": completed_at.isoformat().replace("+00:00", "Z"),
            "timingSeconds": {
                "parseCommand": round(parsed_clock - started_clock, 9),
                "buildPlan": round(planned_clock - parsed_clock, 9),
                "total": round(planned_clock - started_clock, 9),
            },
        },
    }


def build_project02_validated_demo_run(
    requirement: str, closure: dict[str, Any]
) -> dict[str, Any]:
    """Bind a natural-language command to the already validated CAD chain.

    This deliberately does not pretend to rebuild the large assembly during an
    HTTP request.  It proves that the requested order exactly matches the
    independently saved/reopened current static chain and returns every durable
    stage artifact plus its final release gate.
    """

    preview = preview_project02_ordered_assembly(requirement)
    plan = preview["plan"]
    if not plan["summary"]["orderValid"]:
        raise SemanticAssemblySequenceError("装配顺序依赖未通过，不能载入实体闭环。")
    if not plan["summary"]["allStepsCadExecutableNow"]:
        raise SemanticAssemblySequenceError("命令包含尚未完成CAD闭环的模组。")

    requested = [str(item["moduleToken"]) for item in plan["steps"]]
    validated = [str(value) for value in (closure.get("sequence") or []) if str(value) != "A600"]
    if requested != validated:
        raise SemanticAssemblySequenceError(
            "当前实体演示只接受最新闭包记录的完整顺序："
            + " → ".join(validated)
        )
    release = closure.get("releaseDecision") or {}
    gate = closure.get("interferenceGate") or {}
    static_release = (
        release.get("staticTenObjectDemoReleaseAllowed") is True
        or release.get("staticSevenModuleDemoReleaseAllowed") is True
    )
    if not static_release:
        raise SemanticAssemblySequenceError("最新静态实体闭环尚未通过发布门禁。")
    final_path = Path(str(closure.get("finalAssemblyPath") or ""))
    if not final_path.is_file():
        raise SemanticAssemblySequenceError(f"闭环记录的最终装配体不存在：{final_path}")

    return {
        "success": True,
        "executionMode": "validated_artifact_replay",
        "cadExecutedThisRequest": False,
        "validatedCadArtifactReused": True,
        "message": (
            "自然语言顺序已绑定到静态实体闭包："
            f"{gate.get('acceptedPairCount', '?')}/"
            f"{gate.get('expectedPairCount', gate.get('checkedPairCount', '?'))}模组对已接受。"
        ),
        "sourceRequirement": requirement,
        "requestedSequence": ["A600", *requested],
        "validatedSequence": closure.get("sequence") or [],
        "steps": closure.get("steps") or [],
        "finalAssemblyPath": str(final_path.resolve()),
        "interferenceGate": gate,
        "releaseDecision": release,
        "knownLimitations": closure.get("knownLimitations") or [],
        "previewAudit": preview["audit"],
        "contracts": preview["contracts"],
    }


def run_project02_validated_demo(workspace: Path, requirement: str) -> dict[str, Any]:
    closure = load_project02_ordered_assembly_closure(workspace)
    closure_path = Path(str(closure.get("evidencePath") or ""))
    if closure.get("available") is not True or not closure_path.is_file():
        raise SemanticAssemblySequenceError("尚未生成可复用的静态实体闭环。")
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()
    result = build_project02_validated_demo_run(requirement, closure)
    run_id = f"project02-validated-demo-{uuid4().hex[:12]}"
    completed_at = datetime.now(timezone.utc)
    result["audit"] = {
        "runId": run_id,
        "startedAt": started_at.isoformat().replace("+00:00", "Z"),
        "completedAt": completed_at.isoformat().replace("+00:00", "Z"),
        "durationSeconds": round(perf_counter() - started_clock, 9),
        "closureEvidencePath": str(closure_path),
    }
    output_dir = workspace / "demo/semantic_ports/project02_ordered_command_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / f"{run_id}.json").resolve()
    result["audit"]["runEvidencePath"] = str(output_path)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
