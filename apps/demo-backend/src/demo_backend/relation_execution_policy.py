"""Fail-closed execution policy for relation-template evidence classes."""

from __future__ import annotations

from typing import Any


DIRECT_INSTALLATION = "direct_installation"
DATUM_PLACEMENT_DEMO = "datum_placement_demo"
SUPPORTED_RELATION_EXECUTION_MODES = {
    DIRECT_INSTALLATION,
    DATUM_PLACEMENT_DEMO,
}


class RelationExecutionPolicyError(ValueError):
    pass


def normalize_relation_execution_mode(value: Any) -> str:
    mode = str(value or DIRECT_INSTALLATION).strip().casefold()
    if mode not in SUPPORTED_RELATION_EXECUTION_MODES:
        raise RelationExecutionPolicyError(
            "relationExecutionMode仅支持direct_installation或datum_placement_demo。"
        )
    return mode


def template_evidence_class(template: dict[str, Any]) -> str:
    purposes = {
        str(value or "").strip().casefold()
        for value in template.get("purposes") or []
    }
    return (
        DATUM_PLACEMENT_DEMO
        if DATUM_PLACEMENT_DEMO in purposes
        else DIRECT_INSTALLATION
    )


def assess_template_execution_policy(
    template: dict[str, Any], *, requested_mode: Any = None
) -> dict[str, Any]:
    mode = normalize_relation_execution_mode(requested_mode)
    evidence_class = template_evidence_class(template)
    allowed = evidence_class == mode
    return {
        "requestedMode": mode,
        "templateEvidenceClass": evidence_class,
        "allowed": allowed,
        "code": None if allowed else "RELATION_EXECUTION_MODE_MISMATCH",
        "detail": (
            "模板证据等级与本次执行模式一致。"
            if allowed
            else (
                "普通工程安装默认禁止使用仅完成基准定位验证的模板；"
                "如确需概念布局，必须显式选择datum_placement_demo。"
                if mode == DIRECT_INSTALLATION
                else "基准定位Demo模式只接受明确标记为datum_placement_demo的模板。"
            )
        ),
    }


def filter_connection_candidates_by_execution_policy(
    catalog: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    requested_mode: Any = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mode = normalize_relation_execution_mode(requested_mode)
    templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    allowed: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for candidate in candidates:
        template_id = str(candidate.get("globalTemplateId") or "")
        template = templates.get(template_id)
        if template is None:
            assessment = {
                "requestedMode": mode,
                "templateEvidenceClass": None,
                "allowed": False,
                "code": "RELATION_TEMPLATE_NOT_FOUND",
                "detail": "候选关系在目录中找不到模板。",
            }
        else:
            assessment = assess_template_execution_policy(
                template, requested_mode=mode
            )
        enriched = {**candidate, "executionPolicyAssessment": assessment}
        audit.append(enriched)
        if assessment["allowed"]:
            allowed.append(enriched)
    return allowed, audit
