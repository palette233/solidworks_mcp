"""Runtime safety policy for released driving-relation templates.

Immutable releases preserve what was published, but later CAD evidence may show
that a released template is not portable.  This registry is the revocation
layer: compilation can reject such a template before a long SolidWorks run
without rewriting historical release artifacts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


RELATION_DRIVING_SAFETY_SCHEMA = "relation-driving-safety-registry/v1"
VERIFIED_STATUS = "verified_external_pose_equivalent"
BLOCKED_STATUS = "blocked_external_pose_branch"
EXPLICIT_FALLBACK_STATUS = "explicit_calibrated_fallback_selected"


class RelationDrivingSafetyError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def relation_driving_safety_registry_digest(registry: dict[str, Any]) -> str:
    return _digest(
        {key: value for key, value in registry.items() if key != "registryDigest"}
    )


def validate_relation_driving_safety_registry(
    registry: dict[str, Any],
) -> dict[str, Any]:
    if registry.get("schemaVersion") != RELATION_DRIVING_SAFETY_SCHEMA:
        raise RelationDrivingSafetyError("不支持的驱动关系安全目录版本。")
    rows = registry.get("templates")
    if not isinstance(rows, list):
        raise RelationDrivingSafetyError("templates必须是数组。")
    seen: set[str] = set()
    for row in rows:
        template_id = str(row.get("globalTemplateId") or "").strip()
        status = str(row.get("status") or "").strip()
        if not template_id:
            raise RelationDrivingSafetyError("驱动关系安全条目缺少globalTemplateId。")
        if template_id in seen:
            raise RelationDrivingSafetyError(f"驱动模板重复：{template_id}")
        seen.add(template_id)
        if status not in {VERIFIED_STATUS, BLOCKED_STATUS}:
            raise RelationDrivingSafetyError(f"不支持的驱动模板安全状态：{status}")
        if not str(row.get("reason") or "").strip():
            raise RelationDrivingSafetyError("驱动关系安全条目必须包含reason。")
    expected = registry.get("registryDigest")
    actual = relation_driving_safety_registry_digest(registry)
    if expected is not None and expected != actual:
        raise RelationDrivingSafetyError("驱动关系安全目录摘要不一致。")
    return registry


def relation_driving_safety_registry_binding(
    registry: dict[str, Any],
    *,
    registry_path: str | None = None,
) -> dict[str, Any]:
    validate_relation_driving_safety_registry(registry)
    return {
        "schemaVersion": registry["schemaVersion"],
        "registryId": registry.get("registryId"),
        "registryDigest": relation_driving_safety_registry_digest(registry),
        "registryPath": registry_path,
    }


def assess_relation_driving_safety(
    global_template_id: str,
    *,
    registry: dict[str, Any] | None,
    explicit_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if registry is None:
        return {
            "declared": False,
            "status": "not_declared",
            "globalTemplateId": global_template_id,
            "blockers": [],
        }
    validate_relation_driving_safety_registry(registry)
    row = next(
        (
            candidate
            for candidate in registry.get("templates") or []
            if str(candidate.get("globalTemplateId") or "") == global_template_id
        ),
        None,
    )
    if row is None:
        return {
            "declared": False,
            "status": "not_declared",
            "globalTemplateId": global_template_id,
            "blockers": [],
        }
    status = str(row["status"])
    blockers = []
    if status == BLOCKED_STATUS:
        fallback = row.get("recommendedFallback") or {}
        selected_strategy = str(
            (explicit_selection or {}).get("strategyId") or ""
        ).strip()
        expected_strategy = str(fallback.get("strategyId") or "").strip()
        selection_confirmed = (explicit_selection or {}).get("confirmed") is True
        if selected_strategy and selected_strategy != expected_strategy:
            blockers.append(
                {
                    "code": "DRIVING_FALLBACK_SELECTION_MISMATCH",
                    "globalTemplateId": global_template_id,
                    "moduleToken": row.get("moduleToken"),
                    "selectedStrategyId": selected_strategy,
                    "expectedStrategyId": expected_strategy,
                    "detail": "显式回退策略与安全目录建议的策略不一致。",
                }
            )
        elif selected_strategy and not selection_confirmed:
            blockers.append(
                {
                    "code": "DRIVING_FALLBACK_EXPLICIT_CONFIRMATION_REQUIRED",
                    "globalTemplateId": global_template_id,
                    "moduleToken": row.get("moduleToken"),
                    "selectedStrategyId": selected_strategy,
                    "detail": "项目标定回退必须显式confirmed=true，禁止静默启用。",
                }
            )
        elif selected_strategy and selection_confirmed:
            required = (
                "strategyId",
                "scope",
                "effectiveMateGraphPath",
                "effectiveMateGraphSha256",
                "validationEvidencePath",
                "validationEvidenceSha256",
            )
            missing = [key for key in required if not fallback.get(key)]
            if missing:
                blockers.append(
                    {
                        "code": "DRIVING_FALLBACK_EVIDENCE_INCOMPLETE",
                        "globalTemplateId": global_template_id,
                        "moduleToken": row.get("moduleToken"),
                        "selectedStrategyId": selected_strategy,
                        "detail": missing,
                    }
                )
            else:
                status = EXPLICIT_FALLBACK_STATUS
        else:
            blockers.append(
                {
                    "code": "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED",
                    "globalTemplateId": global_template_id,
                    "moduleToken": row.get("moduleToken"),
                    "detail": row.get("reason"),
                    "recommendedFallback": fallback,
                }
            )
    return {
        "declared": True,
        "status": status,
        "globalTemplateId": global_template_id,
        "moduleToken": row.get("moduleToken"),
        "reason": row.get("reason"),
        "evidence": list(row.get("evidence") or []),
        "recommendedFallback": row.get("recommendedFallback"),
        "explicitSelection": explicit_selection,
        "executionOverride": (
            {
                "strategyId": (row.get("recommendedFallback") or {}).get(
                    "strategyId"
                ),
                "scope": (row.get("recommendedFallback") or {}).get("scope"),
                "portable": False,
                "authority": "prototype-calibrated-explicit-fallback",
                "executionStrategy": "calibrated_static_snapshot_insert",
                "effectiveMateGraphPath": (
                    row.get("recommendedFallback") or {}
                ).get("effectiveMateGraphPath"),
                "effectiveMateGraphSha256": (
                    row.get("recommendedFallback") or {}
                ).get("effectiveMateGraphSha256"),
                "validationEvidencePath": (
                    row.get("recommendedFallback") or {}
                ).get("validationEvidencePath"),
                "validationEvidenceSha256": (
                    row.get("recommendedFallback") or {}
                ).get("validationEvidenceSha256"),
                "expectedInternalLeafPoseAnchorCount": (
                    row.get("recommendedFallback") or {}
                ).get("expectedInternalLeafPoseAnchorCount"),
            }
            if status == EXPLICIT_FALLBACK_STATUS
            else None
        ),
        "blockers": blockers,
    }
