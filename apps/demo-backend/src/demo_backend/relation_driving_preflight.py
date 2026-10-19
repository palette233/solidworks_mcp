"""Fail-closed classification for natural-language driving relation requests.

The classifier joins two evidence layers without pretending either is the CAD
solver: a released semantic template says what use has been validated, while a
proposed effective mate graph supplies conservative rigid-body DOF evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


RELATION_DRIVING_PREFLIGHT_SCHEMA = "relation-driving-preflight/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def classify_relation_driving_preflight(
    *,
    requirement: str,
    released_verification_preview: dict[str, Any],
    transaction_preflight: dict[str, Any],
    release: dict[str, Any],
) -> dict[str, Any]:
    """Classify a request as driving candidate, verification-only, or blocked."""

    transaction_blockers = list(transaction_preflight.get("blockers") or [])
    transaction_codes = {str(row.get("code") or "") for row in transaction_blockers}
    semantic_matches = list(released_verification_preview.get("matchingTemplates") or [])
    profiles = [row.get("templateProfile") or {} for row in semantic_matches]
    released_driving_templates = [
        profile for profile in profiles if profile.get("drivesPlacement") is True
    ]
    release_scope = release.get("scope") or {}
    authorized_driving_ids = set(
        release_scope.get("authorizedDrivingTemplateIds") or []
    )
    matched_driving_ids = {
        str(row.get("globalTemplateId") or "")
        for row in semantic_matches
        if (row.get("templateProfile") or {}).get("drivesPlacement") is True
    }
    reason_codes: list[str] = []

    if "REDUNDANT_MUTATING_RELATION" in transaction_codes:
        category = "verification_only"
        reason_codes.append("PROPOSED_RELATION_ADDS_NO_INDEPENDENT_DOF_CONSTRAINT")
        next_action = "删除该新增配合，或把它保留为只读验证关系。"
    elif transaction_blockers:
        category = "blocked"
        reason_codes.extend(sorted(transaction_codes))
        next_action = "先补齐端点几何或消除自由度/事务阻塞，再重新预检。"
    elif not semantic_matches:
        category = "blocked"
        reason_codes.append("NO_RELEASED_SEMANTIC_RELATION_EVIDENCE")
        next_action = "先登记并真实验证对应关系模板。"
    elif not released_driving_templates:
        category = "verification_only"
        reason_codes.append("RELEASED_TEMPLATE_IS_VALIDATION_ONLY")
        next_action = "当前可检查关系是否成立；驱动新增需另建模板和CAD证据。"
    elif release_scope.get("drivingRelationRelease") is not True:
        category = "blocked"
        reason_codes.append("RELEASE_SCOPE_FORBIDS_DRIVING_RELATION")
        next_action = "完成驱动关系真实CAD闭环并发布允许驱动的新目录版本。"
    elif not (matched_driving_ids & authorized_driving_ids):
        category = "blocked"
        reason_codes.append("MATCHED_RELATION_TEMPLATE_NOT_AUTHORIZED_FOR_DRIVING")
        next_action = "只授权已完成当前CAD副本闭环的具体关系模板。"
    else:
        category = "ready_for_driving_cad_trial"
        reason_codes.append("SEMANTIC_AND_DOF_PREFLIGHT_PASSED")
        next_action = "可对装配体副本执行CAD试运行；保存重开结果仍是最终裁决。"

    result = {
        "schemaVersion": RELATION_DRIVING_PREFLIGHT_SCHEMA,
        "requirement": requirement,
        "decisionCategory": category,
        "cadExecutionAllowed": category == "ready_for_driving_cad_trial",
        "reasonCodes": reason_codes,
        "releasedSemanticEvidence": {
            "releaseId": release.get("releaseId"),
            "releaseDigest": release.get("releaseDigest"),
            "matchingTemplateIds": [
                row.get("globalTemplateId") for row in semantic_matches
            ],
            "drivingTemplateIds": [
                profile.get("globalTemplateId") for profile in released_driving_templates
            ],
            "scope": release_scope,
        },
        "transactionPreflight": transaction_preflight,
        "nextAction": next_action,
        "authorityBoundary": (
            "预检只负责启动CAD前的失败关闭；即使允许试运行，也必须在副本中完成"
            "SolidWorks求解、保存、重开和配合参数复核。"
        ),
    }
    result["preflightDigest"] = _digest(result)
    return result
