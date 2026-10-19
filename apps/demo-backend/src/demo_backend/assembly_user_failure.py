"""Translate existing assembly blockers into concise user-facing guidance.

This module does not decide mechanical compatibility.  It only normalizes
blockers already emitted by the catalog, release, compiler, or CAD executor so
that API clients do not need to understand every low-level code.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


SCHEMA = "assembly-user-failure-explanation/v1"


def _normalized_blockers(blockers: Iterable[Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in blockers or []:
        if isinstance(value, dict):
            row = deepcopy(value)
            row["code"] = str(row.get("code") or "UNKNOWN_BLOCKER")
        else:
            row = {"code": str(value or "UNKNOWN_BLOCKER")}
        rows.append(row)
    return rows


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def build_assembly_user_failure(
    *,
    blockers: Iterable[Any] | None = None,
    status: str | None = None,
    raw_error: str | None = None,
    stage: str = "planning",
) -> dict[str, Any]:
    """Return one stable reason code, explanation, and recovery action."""

    rows = _normalized_blockers(blockers)
    codes = {str(row.get("code") or "") for row in rows}
    error = str(raw_error or "").strip()
    normalized_status = str(status or "").strip().lower()

    if "LOCATING_FEATURE_SPACING_MISMATCH" in codes:
        reason = {
            "reasonCode": "LOCATING_PATTERN_MISMATCH",
            "category": "mechanical_incompatibility",
            "summary": "定位孔或定位特征尺寸不一致，不能直接安装。",
            "explanation": "两侧安装接口的定位图案已经可以比较，但关键间距不同。",
            "suggestedActions": [
                "使用具有两侧接口的实体转接件",
                "或选择定位图案一致的目标槽位",
                "登记转接件两侧端点和完整配合束后重新发布",
            ],
            "retryableAfter": "adapter_or_compatible_slot_registered",
        }
    elif "TARGET_SLOT_PROVIDER_ROLE_MISMATCH" in codes:
        reason = {
            "reasonCode": "INSTALLATION_CONTEXT_INCOMPATIBLE",
            "category": "mechanical_incompatibility",
            "summary": "模组需要的安装上下文与目标槽位结构不一致。",
            "explanation": "两侧依赖的基座、传输或其他槽位提供方角色不同，不能简化为单一配合。",
            "suggestedActions": [
                "选择具有相同安装上下文的槽位",
                "或补充多接口结构件及其真实CAD端点",
            ],
            "retryableAfter": "compatible_installation_context_registered",
        }
    elif "MATE_TOPOLOGY_MISMATCH" in codes:
        reason = {
            "reasonCode": "INSTALLATION_TOPOLOGY_INCOMPATIBLE",
            "category": "mechanical_incompatibility",
            "summary": "两侧完整安装配合的结构不同，不能直接组合。",
            "explanation": "例如一侧采用支承面加双定位孔，另一侧采用宽度居中或不同类型的定位关系。",
            "suggestedActions": [
                "检查目标基座是否存在其他已登记槽位",
                "若无兼容槽位，补充真实槽位几何或设计实体转接件",
            ],
            "retryableAfter": "compatible_slot_or_adapter_registered",
        }
    elif codes & {
        "TARGET_SLOT_PORT_OR_TEMPLATE_MISSING",
        "TARGET_SLOT_GEOMETRY_NOT_REGISTERED",
        "NO_REGISTERED_ALTERNATE_SLOT",
    }:
        reason = {
            "reasonCode": "TARGET_SLOT_NOT_REGISTERED",
            "category": "semantic_port_missing",
            "summary": "目标模组尚未登记可供安装的槽位端口。",
            "explanation": "当前目录无法确定应使用哪些面、孔、轴或边建立完整安装配合。",
            "suggestedActions": [
                "从原型配合图迁移目标provided槽位",
                "或定向选择并登记目标安装面和定位特征",
                "完成端点恢复和配合束验证后重新发布",
            ],
            "retryableAfter": "target_provided_slot_published",
        }
    elif "SOURCE_INSTALLATION_PORT_OR_TEMPLATE_MISSING" in codes:
        reason = {
            "reasonCode": "SOURCE_INSTALLATION_PORT_MISSING",
            "category": "semantic_port_missing",
            "summary": "待安装模组缺少自身安装端口。",
            "explanation": "当前目录不知道该模组应通过哪些几何端点连接到外部槽位。",
            "suggestedActions": [
                "从原型配合关系提取required安装端口",
                "登记稳定端点和完整零自由度配合束",
            ],
            "retryableAfter": "source_required_port_published",
        }
    elif codes & {
        "TEMPLATE_NOT_AUTHORIZED_BY_BOUND_RELEASE",
        "RELATION_TEMPLATE_NOT_AUTHORIZED_BY_RELEASE",
        "MATCHED_RELATION_TEMPLATE_NOT_AUTHORIZED_FOR_DRIVING",
        "RELEASE_SCOPE_FORBIDS_DRIVING_RELATION",
    } or _contains_any(error, ("发布授权", "未获得逐模板驱动授权", "not authorized")):
        reason = {
            "reasonCode": "DRIVING_RELATION_NOT_AUTHORIZED",
            "category": "release_authority_missing",
            "summary": "已找到关系模板，但当前发布没有授权它驱动CAD装配。",
            "explanation": "机械关系或端点可能已经存在，但尚未绑定通过验证的不可变执行发布。",
            "suggestedActions": [
                "完成非原型初始位姿CAD验证",
                "发布该驱动模板并重新绑定自然语言任务",
            ],
            "retryableAfter": "driving_template_authorized_by_release",
        }
    elif normalized_status in {
        "ready_for_effective_graph_composition",
        "needs_release_authorization",
    }:
        reason = {
            "reasonCode": "DRIVING_RELATION_NOT_PUBLISHED",
            "category": "release_authority_missing",
            "summary": "接口可能兼容，但尚未形成可直接执行的发布关系。",
            "explanation": "仍需组合有效配合图、完成真实CAD验证并发布执行授权。",
            "suggestedActions": [
                "组合双方已登记端口的有效配合图",
                "完成真实CAD保存重开验证",
                "发布并绑定驱动模板",
            ],
            "retryableAfter": "effective_graph_validated_and_released",
        }
    elif "ATOMIC_INSTALLATION_TEMPLATE_DISAMBIGUATION_REQUIRED" in codes:
        reason = {
            "reasonCode": "INSTALLATION_CONFIGURATION_AMBIGUOUS",
            "category": "semantic_ambiguity",
            "summary": "存在多个同等级安装方案，当前命令无法唯一选择。",
            "explanation": "需要指定目标基座、槽位方位或installationProfileId。",
            "suggestedActions": ["补充目标槽位、方位或安装配置名称后重试"],
            "retryableAfter": "installation_context_disambiguated",
        }
    elif normalized_status == "needs_mechanical_geometry_review":
        reason = {
            "reasonCode": "MECHANICAL_GEOMETRY_REVIEW_REQUIRED",
            "category": "evidence_incomplete",
            "summary": "接口语义相近，但定位几何证据不足。",
            "explanation": "现有端点无法自动比较孔距、轴向或支承面等关键不变量。",
            "suggestedActions": ["补充定向几何测量或人工确认定位端点"],
            "retryableAfter": "locating_geometry_evidence_added",
        }
    elif normalized_status in {"failed", "cad_execution_failed", "not_passed"}:
        reason = {
            "reasonCode": "CAD_EXECUTION_FAILED",
            "category": "cad_execution",
            "summary": "CAD装配事务未通过。",
            "explanation": error or "配合创建、求解或保存重开验证至少有一项未通过。",
            "suggestedActions": [
                "查看失败步骤及最近检查点",
                "修正端点、配合参数或执行环境后从检查点重试",
            ],
            "retryableAfter": "cad_failure_resolved",
        }
    else:
        reason = {
            "reasonCode": "ASSEMBLY_REQUEST_BLOCKED",
            "category": "unclassified",
            "summary": "当前装配请求被阻止。",
            "explanation": error or "现有证据不足以安全生成CAD事务。",
            "suggestedActions": ["查看底层阻塞码并补充缺失的端口、模板或参数"],
            "retryableAfter": "reported_blockers_resolved",
        }

    return {
        "schemaVersion": SCHEMA,
        **reason,
        "stage": stage,
        "cadLaunchDecision": (
            "stopped_after_failure"
            if stage == "cad_execution"
            else "fail_closed_before_cad"
        ),
        "sourceBlockerCodes": sorted(code for code in codes if code),
        "sourceBlockers": rows,
        "rawError": error or None,
        "collisionOrBrepRequiredForRetry": False,
    }


def explain_candidate_matrix_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Explain a non-executable cross-project candidate row."""

    status = str(row.get("status") or "")
    if status == "released_direct_execution":
        return None
    return build_assembly_user_failure(
        blockers=row.get("blockers") or [],
        status=status,
        stage="candidate_selection",
    )
