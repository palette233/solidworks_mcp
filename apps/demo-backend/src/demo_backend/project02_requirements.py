from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT02_MODULE_ORDER = ("A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401")

PROJECT02_MODULES: dict[str, dict[str, Any]] = {
    "A100": {
        "label": "XYZ龙门与双阀点胶执行模组",
        "componentName": "FL9A24D062A100.001-1",
        "capabilities": ["epoxy_dispensing", "valve_service_reach"],
    },
    "A180": {
        "label": "条码扫描模组",
        "componentName": "FL9A24D062A180.001-1",
        "capabilities": ["barcode_traceability"],
    },
    "A200": {
        "label": "CCD视觉定位模组",
        "componentName": "FL9A24D062A200.001-1",
        "capabilities": ["vision_alignment"],
    },
    "A300": {
        "label": "排胶与废胶收集模组",
        "componentName": "FL9A24D062A300.001-1",
        "capabilities": ["waste_dispense"],
    },
    "A500": {
        "label": "胶阀/喷嘴校准模组",
        "componentName": "FL9A24D062A500.001-1",
        "capabilities": ["nozzle_calibration"],
    },
    "A700": {
        "label": "清洁与称重组合模组",
        "componentName": "FL9A24D062A700.001-1",
        "capabilities": ["nozzle_cleaning", "glue_weighting"],
    },
    "A800": {
        "label": "产品传输与载具定位模组",
        "componentName": "FL9A24D062A800.001-1",
        "capabilities": ["product_transport", "carrier_positioning"],
    },
    "T401": {
        "label": "胶水供应模组",
        "componentName": "T401AA-07388-0-1",
        "capabilities": ["glue_supply"],
    },
}

CAPABILITIES: dict[str, dict[str, Any]] = {
    "epoxy_dispensing": {
        "label": "环氧胶点胶",
        "keywords": ["点胶", "涂胶", "打胶", "环氧胶", "epoxy", "dispens"],
    },
    "product_transport": {
        "label": "产品传输",
        "keywords": ["传输", "输送", "上下料", "流水线", "载具流转"],
    },
    "carrier_positioning": {
        "label": "载具定位",
        "keywords": ["载具定位", "顶升定位", "工作位", "工位1", "工位2", "双工位"],
    },
    "barcode_traceability": {
        "label": "条码扫描与追溯",
        "keywords": ["扫码", "扫描", "条码", "二维码", "追溯", "barcode"],
    },
    "vision_alignment": {
        "label": "CCD视觉定位",
        "keywords": ["ccd", "视觉定位", "视觉对位", "拍照定位", "相机定位", "产品定位"],
    },
    "nozzle_calibration": {
        "label": "喷嘴校准",
        "keywords": ["校准", "标定", "针头定位", "喷嘴定位", "对针"],
    },
    "nozzle_cleaning": {
        "label": "喷嘴清洁",
        "keywords": ["清洁", "清洗", "擦胶", "洗针", "喷嘴维护"],
    },
    "glue_weighting": {
        "label": "胶量称重",
        "keywords": ["称重", "胶量", "重量检测", "出胶量", "点胶量"],
    },
    "waste_dispense": {
        "label": "排胶与废胶收集",
        "keywords": ["排胶", "吐胶", "废胶", "排胶杯", "胶杯"],
    },
    "glue_supply": {
        "label": "胶水供应",
        "keywords": ["供胶", "胶桶", "胶水供应", "供料"],
    },
}

# Deterministic dependency rules.  Natural-language parsing only proposes capabilities;
# these rules own the final module dependency closure.
CAPABILITY_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "epoxy_dispensing": ("product_transport", "carrier_positioning", "glue_supply"),
    "barcode_traceability": ("product_transport",),
    "vision_alignment": ("product_transport", "carrier_positioning"),
    "nozzle_calibration": ("epoxy_dispensing",),
    "nozzle_cleaning": ("epoxy_dispensing",),
    "glue_weighting": ("epoxy_dispensing",),
    "waste_dispense": ("epoxy_dispensing",),
    "glue_supply": ("epoxy_dispensing",),
}

CAPABILITY_TO_MODULES: dict[str, tuple[str, ...]] = {
    "epoxy_dispensing": ("A100",),
    "product_transport": ("A800",),
    "carrier_positioning": ("A800",),
    "barcode_traceability": ("A180",),
    "vision_alignment": ("A200",),
    "nozzle_calibration": ("A500",),
    "nozzle_cleaning": ("A700",),
    "glue_weighting": ("A700",),
    "waste_dispense": ("A300",),
    "glue_supply": ("T401",),
}

OPTIONAL_FOR_DISPENSING: dict[str, tuple[str, str]] = {
    "A180": ("barcode_traceability", "可增加产品和载具条码追溯"),
    "A200": ("vision_alignment", "可增加产品位置视觉补偿"),
    "A300": ("waste_dispense", "可增加自动排胶和废胶收集"),
    "A500": ("nozzle_calibration", "可增加喷嘴自动校准"),
    "A700": ("nozzle_cleaning", "可增加清洁，并复用同一组合模组完成称重"),
}

NEGATION_PATTERN = re.compile(r"(?:不需要|无需|不要|不要求|不考虑|取消).{0,5}$", re.IGNORECASE)


def _keyword_is_negated(text: str, keyword_start: int) -> bool:
    return bool(NEGATION_PATTERN.search(text[max(0, keyword_start - 12):keyword_start]))


def _detect_capabilities(requirement: str) -> tuple[dict[str, list[str]], list[str]]:
    lowered = requirement.lower()
    detected: dict[str, list[str]] = {}
    excluded: list[str] = []
    for capability_id, definition in CAPABILITIES.items():
        evidence: list[str] = []
        negated = False
        for keyword in definition["keywords"]:
            start = lowered.find(keyword.lower())
            if start < 0:
                continue
            if _keyword_is_negated(lowered, start):
                negated = True
                continue
            evidence.append(requirement[start:start + len(keyword)])
        if evidence:
            detected[capability_id] = list(dict.fromkeys(evidence))
        elif negated:
            excluded.append(capability_id)
    return detected, excluded


def _dependency_closure(initial: set[str], excluded: set[str]) -> tuple[set[str], list[dict[str, str]]]:
    resolved = set(initial)
    additions: list[dict[str, str]] = []
    changed = True
    while changed:
        changed = False
        for capability in tuple(resolved):
            for dependency in CAPABILITY_DEPENDENCIES.get(capability, ()):
                if dependency in resolved:
                    continue
                # A dependency of an explicitly requested process remains mandatory even if the
                # input contains a contradictory negation; surface the contradiction separately.
                resolved.add(dependency)
                additions.append({"capability": dependency, "requiredBy": capability})
                changed = True
    return resolved, additions


def _extract_product_count(requirement: str) -> int | None:
    patterns = [
        r"(?:每(?:个|套)?载具|载具(?:上)?|一次|同时)?\s*(\d+)\s*(?:个|件|pcs?)\s*(?:产品|工件|header)?",
        r"(?:产品|工件)\s*(?:数量)?\s*[：:]?\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, requirement, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def recommend_project02_modules(
    requirement: str,
    *,
    workspace: Path | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    normalized = " ".join(requirement.strip().split())
    if not normalized:
        raise ValueError("需求描述不能为空。")

    detected, excluded_list = _detect_capabilities(normalized)
    excluded = set(excluded_list)
    resolved, dependency_additions = _dependency_closure(set(detected), excluded)

    required_codes: set[str] = set()
    reasons_by_module: dict[str, list[str]] = {}
    for capability in sorted(resolved):
        for code in CAPABILITY_TO_MODULES.get(capability, ()):
            required_codes.add(code)
            reason = f"满足“{CAPABILITIES[capability]['label']}”能力"
            reasons_by_module.setdefault(code, []).append(reason)

    modules: list[dict[str, Any]] = []
    for code in PROJECT02_MODULE_ORDER:
        definition = PROJECT02_MODULES[code]
        status = "required" if code in required_codes else "not_selected"
        reasons = list(dict.fromkeys(reasons_by_module.get(code, [])))
        optional_capability: str | None = None
        if (
            status == "not_selected"
            and "epoxy_dispensing" in resolved
            and code in OPTIONAL_FOR_DISPENSING
        ):
            optional_capability, optional_reason = OPTIONAL_FOR_DISPENSING[code]
            status = "optional"
            reasons.append(optional_reason)

        modules.append({
            "code": code,
            "label": definition["label"],
            "componentName": definition["componentName"],
            "status": status,
            "required": status == "required",
            "selectedByDefault": status == "required",
            "capabilities": definition["capabilities"],
            "optionalCapability": optional_capability,
            "reasons": reasons,
        })

    contradictions = [
        capability
        for capability in excluded
        if capability in resolved
    ]
    missing_information: list[str] = []
    if not detected:
        missing_information.append("未识别到项目02支持的工艺能力，请说明是否需要点胶、传输、扫码、CCD、校准、清洁、称重或排胶。")
    if "epoxy_dispensing" in resolved and _extract_product_count(normalized) is None:
        missing_information.append("未给出每个载具的产品数量；模组推荐可继续，但节拍和工位数量尚不能校核。")
    if contradictions:
        labels = "、".join(CAPABILITIES[item]["label"] for item in contradictions)
        missing_information.append(f"需求否定了依赖能力（{labels}），但其他已选能力仍要求它们，请确认工艺边界。")

    capability_rows = []
    for capability in sorted(resolved):
        direct = capability in detected
        addition = next((item for item in dependency_additions if item["capability"] == capability), None)
        capability_rows.append({
            "id": capability,
            "label": CAPABILITIES[capability]["label"],
            "source": "explicit" if direct else "dependency",
            "evidence": detected.get(capability, []),
            "requiredBy": addition["requiredBy"] if addition else None,
        })

    default_selected = [code for code in PROJECT02_MODULE_ORDER if code in required_codes]
    all_capabilities_covered = all(
        any(code in required_codes for code in CAPABILITY_TO_MODULES.get(capability, ()))
        for capability in resolved
    )
    result: dict[str, Any] = {
        "projectId": "project02",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "requirement": requirement,
        "normalizedRequirement": normalized,
        "productCountPerCarrier": _extract_product_count(normalized),
        "capabilities": capability_rows,
        "excludedCapabilities": [
            {"id": item, "label": CAPABILITIES[item]["label"]}
            for item in sorted(excluded)
        ],
        "dependencyAdditions": dependency_additions,
        "modules": modules,
        "requiredModuleCodes": default_selected,
        "defaultSelectedModuleCodes": default_selected,
        "optionalModuleCodes": [item["code"] for item in modules if item["status"] == "optional"],
        "coverage": {
            "requiredCapabilityCount": len(resolved),
            "coveredCapabilityCount": len(resolved) if all_capabilities_covered else 0,
            "complete": all_capabilities_covered and bool(resolved),
        },
        "missingInformation": missing_information,
        "assumptions": [
            "当前仅使用项目02八模组目录和确定性关键词/依赖规则，不调用外部大模型。",
            "模块推荐与空间布局分离；推荐子集不等于现有八模组布局案例已经支持子集求解。",
        ],
        "layoutCompatibility": {
            "caseId": "project02",
            "compatible": set(default_selected) == set(PROJECT02_MODULE_ORDER),
            "requiredBaselineModuleCodes": list(PROJECT02_MODULE_ORDER),
            "missingForCurrentSolver": [code for code in PROJECT02_MODULE_ORDER if code not in required_codes],
            "message": (
                "推荐结果包含项目02八模组基线，可确认后进入现有布局求解。"
                if set(default_selected) == set(PROJECT02_MODULE_ORDER)
                else "推荐结果是有效模块子集，但当前项目02展示求解器仍固定使用八模组基线。"
            ),
        },
    }

    if persist:
        if workspace is None:
            raise ValueError("persist=True requires workspace.")
        output = workspace / "demo" / "requirements" / "project02_latest_recommendation.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        result["savedPath"] = str(output)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        result["savedPath"] = None
    return result


def confirm_project02_modules(
    recommendation: dict[str, Any],
    selected_module_codes: list[str],
    *,
    workspace: Path | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    selected = [code for code in PROJECT02_MODULE_ORDER if code in set(selected_module_codes)]
    unknown = sorted(set(selected_module_codes) - set(PROJECT02_MODULE_ORDER))
    required = set(recommendation.get("requiredModuleCodes", []))
    missing_required = [code for code in PROJECT02_MODULE_ORDER if code in required and code not in selected]
    missing_solver = [code for code in PROJECT02_MODULE_ORDER if code not in selected]
    accepted = not unknown and not missing_required
    result: dict[str, Any] = {
        "projectId": "project02",
        "confirmedAt": datetime.now(timezone.utc).isoformat(),
        "accepted": accepted,
        "selectedModuleCodes": selected,
        "missingRequiredModuleCodes": missing_required,
        "unknownModuleCodes": unknown,
        "layoutSolverReady": accepted and not missing_solver,
        "missingForCurrentSolver": missing_solver,
        "message": (
            "模组选择已确认，可进入项目02布局求解。"
            if accepted and not missing_solver
            else "模组选择满足需求，但当前固定八模组求解案例尚不支持该子集。"
            if accepted
            else "确认失败：缺少需求必选模组或包含未知模组。"
        ),
    }
    if persist:
        if workspace is None:
            raise ValueError("persist=True requires workspace.")
        output = workspace / "demo" / "requirements" / "project02_confirmed_modules.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        result["savedPath"] = str(output)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        result["savedPath"] = None
    return result
