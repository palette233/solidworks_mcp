"""Triage cross-project installation incompatibilities without inventing CAD.

The candidate matrix is directional, while an engineering incompatibility is
normally reviewed once per unordered module pair.  This module collapses the
two directions, separates known locating-pattern conflicts from topology and
context-architecture conflicts, and can emit a fail-closed adapter requirement
for a deliberately selected pilot.  It never authorizes CAD execution.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from typing import Any


TRIAGE_SCHEMA = "cross-project-interface-incompatibility-triage/v1"
ADAPTER_REQUIREMENT_SCHEMA = "cross-project-adapter-requirement/v1"


class CrossProjectInterfaceTriageError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _pair_key(row: dict[str, Any]) -> str:
    return "::".join(
        sorted(
            [
                str(row.get("sourceModuleDefinitionId") or ""),
                str(row.get("targetModuleDefinitionId") or ""),
            ]
        )
    )


def _module_ref(row: dict[str, Any], side: str) -> dict[str, Any]:
    return {
        "moduleDefinitionId": row[f"{side}ModuleDefinitionId"],
        "projectIds": list(row.get(f"{side}ProjectIds") or []),
        "moduleTokens": list(row.get(f"{side}ModuleTokens") or []),
    }


def _classify(codes: set[str]) -> tuple[str, str, str]:
    if "TARGET_SLOT_PROVIDER_ROLE_MISMATCH" in codes:
        return (
            "context_architecture_mismatch",
            "重新设计安装上下文或增加具有双上下文接口的结构件",
            "现有模组依赖不同数量或角色的槽位提供方，不能用单一配合别名解决。",
        )
    if "LOCATING_FEATURE_SPACING_MISMATCH" in codes:
        return (
            "known_pattern_mismatch_adapter_candidate",
            "建立双侧定位图案的实体转接件",
            "两侧定位特征已可比较且尺寸不同，直接安装应失败关闭。",
        )
    if "MATE_TOPOLOGY_MISMATCH" in codes:
        return (
            "topology_mismatch_adapter_or_slot_redesign",
            "补充目标槽位几何证据，再选择转接件或重定义槽位",
            "两侧完整安装束采用不同定位拓扑，不能把关系名称直接互换。",
        )
    return (
        "manual_mechanical_review",
        "人工复核机械接口",
        "现有证据不足以自动归类。",
    )


def build_blocked_substitution_disposition(
    substitution_report: dict[str, Any],
) -> dict[str, Any]:
    """Turn a blocked direct replacement into an actionable, fail-closed answer."""

    if substitution_report.get("status") != "blocked":
        raise CrossProjectInterfaceTriageError("工程处置只适用于已阻断的替换请求。")
    codes = {
        str(row.get("code") or "")
        for row in substitution_report.get("blockers") or []
        if str(row.get("code") or "")
    }
    category, action, explanation = _classify(codes)
    geometry = substitution_report.get("locatingFeatureGeometry") or {}
    core = {
        "schemaVersion": "cross-project-blocked-substitution-disposition/v1",
        "classification": category,
        "directCombinationAllowed": False,
        "cadLaunchDecision": "fail_closed_before_cad",
        "recommendedEngineeringAction": action,
        "explanation": explanation,
        "blockerCodes": sorted(codes),
        "knownLocatingDifferences": deepcopy(geometry.get("differences") or []),
        "requiredNextEvidence": (
            [
                "实体转接件或等效双接口支架CAD",
                "转接件两侧稳定端点目录",
                "两侧完整安装配合束",
            ]
            if category == "known_pattern_mismatch_adapter_candidate"
            else ["目标槽位补充几何证据与机械接口评审"]
        ),
        "collisionOrBrepRequiredAtThisStage": False,
    }
    return {**core, "dispositionDigest": _digest(core)}


def _direction_summary(row: dict[str, Any]) -> dict[str, Any]:
    assessment = row.get("selectedAssessment") or {}
    source = assessment.get("sourceInstallation") or {}
    target = assessment.get("targetInstallation") or {}
    return {
        "source": _module_ref(row, "source"),
        "target": _module_ref(row, "target"),
        "sourceInstallationProfileId": source.get("installationProfileId"),
        "targetInstallationProfileId": target.get("installationProfileId"),
        "sourceTemplateId": source.get("templateId"),
        "targetTemplateId": target.get("templateId"),
        "sourceInterfaceClass": source.get("canonicalInterfaceClass"),
        "targetInterfaceClass": target.get("canonicalInterfaceClass"),
        "sourceSlotProviderRoles": list(source.get("targetSlotProviderRoles") or []),
        "targetSlotProviderRoles": list(target.get("targetSlotProviderRoles") or []),
        "sourceLocatingGeometry": deepcopy(source.get("locatingFeatureGeometry") or {}),
        "targetLocatingGeometry": deepcopy(target.get("locatingFeatureGeometry") or {}),
        "blockers": deepcopy(row.get("blockers") or []),
    }


def build_incompatibility_triage(matrix: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("schemaVersion") != "cross-project-module-candidate-matrix/v1":
        raise CrossProjectInterfaceTriageError("不支持的跨项目候选矩阵版本。")
    rows = [
        row
        for row in matrix.get("rows") or []
        if row.get("status") == "incompatible" and row.get("deferred") is not True
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_pair_key(row), []).append(row)

    pairs: list[dict[str, Any]] = []
    for pair_key, directions in sorted(grouped.items()):
        directions = sorted(
            directions,
            key=lambda row: (
                str((row.get("sourceProjectIds") or [""])[0]),
                str((row.get("sourceModuleTokens") or [""])[0]),
            ),
        )
        blocker_codes = {
            str(blocker.get("code") or "")
            for row in directions
            for blocker in row.get("blockers") or []
            if str(blocker.get("code") or "")
        }
        category, action, explanation = _classify(blocker_codes)
        first = directions[0]
        modules = sorted(
            [_module_ref(first, "source"), _module_ref(first, "target")],
            key=lambda row: row["moduleDefinitionId"],
        )
        pairs.append(
            {
                "pairId": "interface-pair/" + hashlib.sha256(pair_key.encode()).hexdigest()[:12],
                "primaryRole": first.get("primaryRole"),
                "modules": modules,
                "classification": category,
                "directCombinationAllowed": False,
                "recommendedEngineeringAction": action,
                "explanation": explanation,
                "blockerCodes": sorted(blocker_codes),
                "directionCount": len(directions),
                "directions": [_direction_summary(row) for row in directions],
            }
        )

    counts = Counter(row["classification"] for row in pairs)
    core = {
        "schemaVersion": TRIAGE_SCHEMA,
        "sourceMatrixDigest": matrix.get("matrixDigest"),
        "directionalIncompatibleCount": len(rows),
        "undirectedPairCount": len(pairs),
        "classificationCounts": dict(sorted(counts.items())),
        "pairs": pairs,
        "policy": {
            "directCadExecutionAuthorized": False,
            "adapterGeometryInvented": False,
            "slotAliasMayOverrideHardMismatch": False,
            "collisionOrBrepRequired": False,
            "deferredRowsExcluded": True,
        },
    }
    return {**core, "triageDigest": _digest(core)}


def _find_direction(
    triage: dict[str, Any],
    *,
    source_project: str,
    source_token: str,
    target_project: str,
    target_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for pair in triage.get("pairs") or []:
        for direction in pair.get("directions") or []:
            source = direction.get("source") or {}
            target = direction.get("target") or {}
            if (
                source.get("projectIds") == [source_project]
                and source.get("moduleTokens") == [source_token]
                and target.get("projectIds") == [target_project]
                and target.get("moduleTokens") == [target_token]
            ):
                return pair, direction
    raise CrossProjectInterfaceTriageError("找不到指定的跨项目不兼容方向。")


def build_adapter_requirement(
    triage: dict[str, Any],
    *,
    source_project: str,
    source_token: str,
    target_project: str,
    target_token: str,
) -> dict[str, Any]:
    pair, direction = _find_direction(
        triage,
        source_project=source_project,
        source_token=source_token,
        target_project=target_project,
        target_token=target_token,
    )
    if pair.get("classification") != "known_pattern_mismatch_adapter_candidate":
        raise CrossProjectInterfaceTriageError(
            "只有已量化定位图案不一致的模组对可自动生成转接需求。"
        )
    source_geometry = direction.get("sourceLocatingGeometry") or {}
    target_geometry = direction.get("targetLocatingGeometry") or {}
    source_spacings = sorted(
        float(row["distanceMeters"])
        for row in source_geometry.get("pairSpacings") or []
        if isinstance(row.get("distanceMeters"), (int, float))
    )
    target_spacings = sorted(
        float(row["distanceMeters"])
        for row in target_geometry.get("pairSpacings") or []
        if isinstance(row.get("distanceMeters"), (int, float))
    )
    if not source_spacings or not target_spacings:
        raise CrossProjectInterfaceTriageError("转接需求缺少可量化的双侧定位间距。")
    core = {
        "schemaVersion": ADAPTER_REQUIREMENT_SCHEMA,
        "status": "engineering_geometry_required",
        "naturalLanguageIntent": (
            f"使用{source_project}的{source_token}替换"
            f"{target_project}的{target_token}槽位"
        ),
        "sourceModule": direction["source"],
        "targetNativeModule": direction["target"],
        "targetSlotProviderRoles": direction.get("targetSlotProviderRoles") or [],
        "moduleSide": {
            "installationProfileId": direction.get("sourceInstallationProfileId"),
            "interfaceClass": direction.get("sourceInterfaceClass"),
            "locatingPairSpacingsMeters": source_spacings,
        },
        "baseSide": {
            "nativeInstallationProfileId": direction.get("targetInstallationProfileId"),
            "interfaceClass": direction.get("targetInterfaceClass"),
            "locatingPairSpacingsMeters": target_spacings,
        },
        "requiredArtifact": {
            "kind": "physical_adapter_or_equivalent_dual_interface_bracket",
            "mustExposeModuleSidePort": True,
            "mustExposeBaseSidePort": True,
            "cadFilePath": None,
            "endpointCatalogPath": None,
        },
        "executionPolicy": {
            "directCadExecutionAllowed": False,
            "failClosedReason": "ADAPTER_GEOMETRY_NOT_AVAILABLE",
            "collisionOrBrepRequired": False,
        },
        "releaseChecks": [
            "登记转接件两侧稳定端点",
            "分别建立模组侧与基座侧完整零自由度配合束",
            "从非原型初始位姿执行累计CAD装配",
            "保存关闭重开并复核配合参数和外部约束状态",
        ],
    }
    return {**core, "requirementDigest": _digest(core)}
