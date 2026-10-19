from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


ASSEMBLY_INTENT_SCHEMA = "assembly-intent/v1"
ASSEMBLY_PLAN_SCHEMA = "assembly-plan/v1"


class AssemblyContractError(ValueError):
    pass


def canonical_digest(payload: dict[str, Any], *, omit: tuple[str, ...] = ()) -> str:
    normalized = {key: value for key, value in payload.items() if key not in set(omit)}
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_assembly_intent_contract(intent: dict[str, Any]) -> dict[str, Any]:
    steps = [
        {
            "order": int(step["order"]),
            "moduleToken": str(step["moduleToken"]),
            "sourceText": step.get("sourceText"),
            "sourceSpan": list(step.get("sourceSpan") or []),
        }
        for step in intent.get("steps") or []
    ]
    contract = {
        "schemaVersion": ASSEMBLY_INTENT_SCHEMA,
        "projectId": str(intent.get("projectId") or ""),
        "projectProfile": deepcopy(intent.get("projectProfile") or {}),
        "operation": str(intent.get("operation") or ""),
        "sourceRequirement": str(intent.get("sourceRequirement") or ""),
        "normalizedRequirement": str(intent.get("normalizedRequirement") or ""),
        "initialContextModules": [str(value) for value in intent.get("initialContextModules") or []],
        "orderedSteps": steps,
        "outputPolicy": deepcopy(intent.get("outputPolicy") or {}),
        "parser": deepcopy(intent.get("parser") or {}),
    }
    validate_assembly_intent_contract(contract)
    contract["intentDigest"] = canonical_digest(contract)
    return contract


def validate_assembly_intent_contract(contract: dict[str, Any]) -> None:
    if contract.get("schemaVersion") != ASSEMBLY_INTENT_SCHEMA:
        raise AssemblyContractError("不支持的装配意图契约版本。")
    if not str(contract.get("projectId") or ""):
        raise AssemblyContractError("装配意图缺少projectId。")
    if not str(contract.get("sourceRequirement") or "").strip():
        raise AssemblyContractError("装配意图缺少原始自然语言需求。")
    steps = contract.get("orderedSteps")
    if not isinstance(steps, list) or not steps:
        raise AssemblyContractError("装配意图必须包含至少一个有序步骤。")
    expected_orders = list(range(1, len(steps) + 1))
    actual_orders = [int(step.get("order", 0)) for step in steps]
    if actual_orders != expected_orders:
        raise AssemblyContractError("装配意图步骤序号必须从1连续递增。")
    tokens = [str(step.get("moduleToken") or "") for step in steps]
    if any(not token for token in tokens):
        raise AssemblyContractError("装配意图步骤缺少moduleToken。")
    if len(tokens) != len(set(tokens)):
        raise AssemblyContractError("装配意图中存在重复模组。")


def build_assembly_plan_contract(
    plan: dict[str, Any],
    intent_contract: dict[str, Any],
) -> dict[str, Any]:
    validate_assembly_intent_contract(intent_contract)
    steps = []
    for step in plan.get("steps") or []:
        steps.append(
            {
                "stepId": str(step["stepId"]),
                "order": int(step["order"]),
                "moduleToken": str(step["moduleToken"]),
                "requiredModules": [str(value) for value in step.get("requiredModules") or []],
                "availableBefore": [str(value) for value in step.get("availableBefore") or []],
                "missingRequiredModules": [
                    str(value) for value in step.get("missingRequiredModules") or []
                ],
                "dependenciesSatisfied": bool(step.get("dependenciesSatisfied")),
                "placementKind": str(step.get("placementKind") or ""),
                "ruleSummary": str(step.get("ruleSummary") or ""),
                "acceptanceChecks": [str(value) for value in step.get("acceptanceChecks") or []],
                "engineeringLimitations": [
                    str(value) for value in step.get("engineeringLimitations") or []
                ],
                "implementationStatus": str(step.get("implementationStatus") or ""),
                "cadExecutableNow": bool(step.get("cadExecutableNow")),
                "checkpointPolicy": deepcopy(step.get("checkpointPolicy") or {}),
            }
        )
    contract = {
        "schemaVersion": ASSEMBLY_PLAN_SCHEMA,
        "projectId": str(plan.get("projectId") or ""),
        "projectProfile": deepcopy(plan.get("projectProfile") or {}),
        "intentDigest": str(intent_contract["intentDigest"]),
        "initialContextModules": [str(value) for value in plan.get("initialContextModules") or []],
        "steps": steps,
        "summary": deepcopy(plan.get("summary") or {}),
        "orderBlockers": [str(value) for value in plan.get("orderBlockers") or []],
        "missingImplementations": deepcopy(plan.get("missingImplementations") or []),
        "executionBoundary": deepcopy(plan.get("executionBoundary") or {}),
    }
    validate_assembly_plan_contract(contract)
    contract["planDigest"] = canonical_digest(contract)
    return contract


def validate_assembly_plan_contract(contract: dict[str, Any]) -> None:
    if contract.get("schemaVersion") != ASSEMBLY_PLAN_SCHEMA:
        raise AssemblyContractError("不支持的装配计划契约版本。")
    if not str(contract.get("intentDigest") or ""):
        raise AssemblyContractError("装配计划缺少intentDigest。")
    steps = contract.get("steps")
    if not isinstance(steps, list) or not steps:
        raise AssemblyContractError("装配计划必须包含至少一个步骤。")
    step_ids = [str(step.get("stepId") or "") for step in steps]
    if any(not value for value in step_ids) or len(step_ids) != len(set(step_ids)):
        raise AssemblyContractError("装配计划stepId必须非空且唯一。")
    for step in steps:
        if not step.get("placementKind"):
            raise AssemblyContractError(f"步骤{step['stepId']}缺少placementKind。")
        if not step.get("acceptanceChecks"):
            raise AssemblyContractError(f"步骤{step['stepId']}缺少验收检查。")
