"""Audit historical CAD evidence for modules waiting for a controlled release.

This module is intentionally read-only.  It classifies existing insert runs so
that an old successful run is not confused with current checkpoint-safe,
non-prototype placement evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .global_cad_driving_evidence import assess_driving_insert_evidence


RELEASE_PENDING_EVIDENCE_AUDIT_SCHEMA = (
    "release-pending-rigid-module-evidence-audit/v1"
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _anchor_used(payload: dict[str, Any]) -> bool:
    tool = payload.get("toolResult") or {}
    return bool(tool.get("TargetCaseAnchored")) or int(
        tool.get("AppliedTargetLeafPoseAnchorCount") or 0
    ) > 0


def _external_pose_closed(assessment: dict[str, Any]) -> bool:
    observation = assessment.get("constraintStateObservation") or {}
    return bool(observation.get("externalPlacementEquivalenceProven"))


def _classify_evidence(
    payload: dict[str, Any],
    *,
    expected_mate_count: int,
) -> tuple[str, dict[str, Any]]:
    assessment = assess_driving_insert_evidence(
        payload,
        expected_mate_count=expected_mate_count,
    )
    if assessment.get("status") == "release_candidate" and assessment.get(
        "portablePlacementProven"
    ):
        state = "reusable_for_release"
    elif (
        assessment.get("status") == "checkpoint_refresh_required"
        and assessment.get("semanticPassed")
        and _external_pose_closed(assessment)
    ):
        state = "checkpoint_refresh_required"
    elif _anchor_used(payload):
        state = "anchored_only"
    elif not _external_pose_closed(assessment):
        state = "external_pose_open"
    else:
        state = "blocked"
    return state, assessment


def _module_state(evidence_states: set[str]) -> tuple[str, str]:
    if "reusable_for_release" in evidence_states:
        return "reusable_for_release", "publish_controlled_release"
    if "checkpoint_refresh_required" in evidence_states:
        return (
            "checkpoint_refresh_required",
            "rerun_checkpoint_from_nonprototype_pose_without_anchors",
        )
    if "external_pose_open" in evidence_states:
        return (
            "complete_installation_bundle_required",
            "add_independent_position_datum_then_rerun_nonprototype_cad",
        )
    if "anchored_only" in evidence_states:
        return (
            "anchor_dependent_only",
            "replace_pose_anchor_with_semantic_installation_datum",
        )
    if evidence_states:
        return "historical_evidence_blocked", "repair_template_or_rerun_cad"
    return "cad_evidence_missing", "run_nonprototype_cad_checkpoint"


def build_release_pending_evidence_audit(
    cases: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Classify historical result payloads for a small release-pending queue.

    Each case must contain ``projectId``, ``moduleToken``, ``templateId``,
    ``expectedMateCount`` and an ``evidence`` list.  Evidence entries contain a
    human-readable ``path`` and the already parsed ``payload``.
    """

    modules: list[dict[str, Any]] = []
    for case in cases:
        expected = int(case.get("expectedMateCount") or 0)
        evidence_rows: list[dict[str, Any]] = []
        for evidence in case.get("evidence") or []:
            payload = evidence.get("payload") or {}
            state, assessment = _classify_evidence(
                payload,
                expected_mate_count=expected,
            )
            evidence_rows.append(
                {
                    "path": str(evidence.get("path") or ""),
                    "state": state,
                    "schemaVersion": payload.get("schemaVersion"),
                    "casePoseAnchorUsed": bool(
                        (payload.get("toolResult") or {}).get("TargetCaseAnchored")
                    ),
                    "leafPoseAnchorCount": int(
                        (payload.get("toolResult") or {}).get(
                            "AppliedTargetLeafPoseAnchorCount"
                        )
                        or 0
                    ),
                    "assessment": assessment,
                }
            )
        states = {str(row["state"]) for row in evidence_rows}
        state, next_action = _module_state(states)
        modules.append(
            {
                "projectId": str(case.get("projectId") or "").lower(),
                "moduleToken": str(case.get("moduleToken") or ""),
                "moduleRole": case.get("moduleRole"),
                "templateId": str(case.get("templateId") or ""),
                "expectedMateCount": expected,
                "state": state,
                "nextAction": next_action,
                "evidence": evidence_rows,
            }
        )

    modules.sort(key=lambda row: (row["projectId"], row["moduleToken"]))
    summary: dict[str, Any] = {
        "moduleCount": len(modules),
        "reusableForReleaseCount": sum(
            row["state"] == "reusable_for_release" for row in modules
        ),
        "checkpointRefreshRequiredCount": sum(
            row["state"] == "checkpoint_refresh_required" for row in modules
        ),
        "installationBundleRepairRequiredCount": sum(
            row["state"] == "complete_installation_bundle_required"
            for row in modules
        ),
        "otherBlockedCount": sum(
            row["state"]
            not in {
                "reusable_for_release",
                "checkpoint_refresh_required",
                "complete_installation_bundle_required",
            }
            for row in modules
        ),
    }
    digest_source = {
        "schemaVersion": RELEASE_PENDING_EVIDENCE_AUDIT_SCHEMA,
        "summary": summary,
        "modules": modules,
    }
    return {
        **digest_source,
        "auditDigest": _digest(digest_source),
        "policy": {
            "legacySuccessMayDirectlyAuthorizeRelease": False,
            "caseOrLeafPoseAnchorMayAuthorizeRelease": False,
            "nonprototypeInitialPoseRequired": True,
            "externalPlacementClosureRequired": True,
            "checkpointSafeSaveCloseReopenRequired": True,
            "collisionOrBrepEvaluated": False,
        },
    }
