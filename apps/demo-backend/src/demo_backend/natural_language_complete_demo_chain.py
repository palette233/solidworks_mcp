"""Evidence closure for the first base/transport/scanner/function demo chain."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


SCHEMA = "natural-language-complete-demo-chain-closure/v1"


class NaturalLanguageCompleteDemoChainError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def build_complete_demo_chain_closure(
    job: dict[str, Any],
    cad_results: list[dict[str, Any]],
    *,
    expected_release_id: str,
    expected_order: list[str],
    base_module_token: str,
    scanner_process_status: str,
    scanner_module_token: str = "AI00",
    transport_module_token: str = "SS00",
    packet_template_ids: list[str] | None = None,
    release_manifest: dict[str, Any] | None = None,
    release_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if job.get("schemaVersion") != "ordered-assembly-job/v2":
        raise NaturalLanguageCompleteDemoChainError("不支持的持久任务版本。")
    steps = job.get("steps") or []
    if len(cad_results) != len(steps):
        raise NaturalLanguageCompleteDemoChainError("CAD结果数与任务步骤数不一致。")
    actual_order = [str(row.get("moduleToken") or "").upper() for row in steps]
    expected = [str(value).upper() for value in expected_order]
    plan = job.get("plan") or {}
    release = plan.get("relationReleaseBinding") or {}
    packet_template_ids = packet_template_ids or []
    release_assessments_by_template: dict[str, dict[str, Any]] = {}
    release_proof_binding_valid = False
    if release_manifest is not None and release_evidence is not None:
        release_proof_binding_valid = bool(
            release_manifest.get("releaseId") == release.get("releaseId")
            and release_manifest.get("releaseDigest") == release.get("releaseDigest")
            and release_manifest.get("catalogDigest") == release.get("catalogDigest")
            and release_evidence.get("outputCatalogDigest")
            == release.get("catalogDigest")
        )
        assessments = release_evidence.get("cadAssessments") or {}
        for derivation in release_evidence.get("derivations") or []:
            entry = derivation.get("entry") or {}
            result = derivation.get("result") or {}
            legacy_id = str(entry.get("legacyTemplateId") or "")
            global_id = str(result.get("derivedGlobalTemplateId") or "")
            assessment = assessments.get(legacy_id)
            if global_id and isinstance(assessment, dict):
                release_assessments_by_template[global_id] = assessment
    checks: dict[str, bool] = {
        "jobSucceeded": job.get("status") == "succeeded",
        "assemblyCommitted": job.get("assemblyStatus") == "assembled",
        "releaseMatches": release.get("releaseId") == expected_release_id,
        "moduleOrderMatches": actual_order == expected,
        "allStepsSucceededOnce": len(steps) == len(expected)
        and all(
            row.get("status") == "succeeded"
            and int(row.get("attemptCount") or 0) == 1
            for row in steps
        ),
        "finalCheckpointExists": bool(
            (job.get("lastCommittedCheckpoint") or {}).get("assemblyPath")
        ),
        "collisionExplicitlyNotEvaluated": job.get("collisionStatus")
        == "not_evaluated",
    }
    cad_summaries = []
    previous_output = None
    chain_is_cumulative = True
    for index, (step, result) in enumerate(zip(steps, cad_results), start=1):
        tool = result.get("toolResult") or {}
        requested_mate_count = int(tool.get("RequestedMateCount") or 0)
        created_mate_count = int(tool.get("CreatedMateCount") or 0)
        mate_results = list(tool.get("MateResults") or [])
        mate_verifications = list(tool.get("MateVerifications") or [])
        packet_template_id = (
            packet_template_ids[index - 1]
            if index <= len(packet_template_ids)
            else ""
        )
        release_assessment = release_assessments_by_template.get(packet_template_id) or {}
        release_repeatability = release_assessment.get(
            "externalPlacementRepeatability"
        ) or {}
        release_external_placement_proven = bool(
            release_proof_binding_valid
            and packet_template_id
            in set(release.get("authorizedDrivingTemplateIds") or [])
            and release_assessment.get("portablePlacementProven") is True
            and release_repeatability.get("passed") is True
        )
        current_run_anchor_free = bool(
            tool.get("TargetCaseAnchored") is False
            and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
        )
        current_run_mechanically_accepted = bool(
            tool.get("TargetConstraintStateAccepted") is True
            and tool.get("MateSolveClean") is True
        )
        external_placement_proven = bool(
            tool.get("TargetFullyConstrained") is True
            or tool.get("ExternalPlacementEquivalencePassed") is True
            or (
                release_external_placement_proven
                and current_run_anchor_free
                and current_run_mechanically_accepted
            )
        )
        source = str(result.get("sourceAssemblyPath") or "")
        output = str(result.get("outputAssemblyPath") or tool.get("OutputAssemblyPath") or "")
        if index > 1 and source != previous_output:
            chain_is_cumulative = False
        previous_output = output
        passed = (
            result.get("success") is True
            and tool.get("Success") is True
            and requested_mate_count > 0
            and created_mate_count == requested_mate_count
            and len(mate_results) == requested_mate_count
            and all(row.get("Success") is True for row in mate_results)
            and len(mate_verifications) == requested_mate_count
            and all(
                row.get("Found") is True
                and row.get("TypeMatches") is True
                and row.get("AlignmentMatches") is True
                and row.get("DistanceMatches") is True
                and row.get("AngleMatches") is True
                and row.get("AdvancedOptionsMatch") is True
                for row in mate_verifications
            )
            and external_placement_proven
            and tool.get("TargetConstraintStateAccepted") is True
            and tool.get("MateSolveClean") is True
            and tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and tool.get("TargetCaseAnchored") is False
            and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
            and result.get("sourceAssemblyUnchanged") is True
            and bool(result.get("outputAssemblySha256"))
            and result.get("outputClosedAfterVerification") is True
            and result.get("targetSourceSessionClean") is True
        )
        cad_summaries.append(
            {
                "packetId": step.get("stepId"),
                "moduleToken": step.get("moduleToken"),
                "passed": passed,
                "sourceAssemblyPath": source,
                "outputAssemblyPath": output,
                "requestedMateCount": requested_mate_count,
                "createdMateCount": created_mate_count,
                "fullyConstrained": tool.get("TargetFullyConstrained"),
                "externalPlacementEquivalencePassed": tool.get(
                    "ExternalPlacementEquivalencePassed"
                ),
                "externalPlacementProven": external_placement_proven,
                "externalPlacementEvidenceSource": (
                    "current_run_fully_constrained"
                    if tool.get("TargetFullyConstrained") is True
                    else "current_run_equivalence_witness"
                    if tool.get("ExternalPlacementEquivalencePassed") is True
                    else "immutable_release_two_pose_repeatability"
                    if release_external_placement_proven
                    and current_run_anchor_free
                    and current_run_mechanically_accepted
                    else "missing"
                ),
                "globalTemplateId": packet_template_id or None,
                "releasePlacementProofBound": release_external_placement_proven,
                "targetCaseAnchored": tool.get("TargetCaseAnchored"),
                "appliedLeafPoseAnchorCount": tool.get(
                    "AppliedTargetLeafPoseAnchorCount"
                ),
                "sourceAssemblyUnchanged": result.get(
                    "sourceAssemblyUnchanged"
                ),
                "outputClosedAfterVerification": result.get(
                    "outputClosedAfterVerification"
                ),
                "reopened": tool.get("Reopened"),
                "durationSeconds": (
                    (step.get("attempts") or [{}])[-1].get("durationSeconds")
                ),
            }
        )
        checks[f"packet{index}CadPassed"] = passed
    checks["cumulativeCheckpointChain"] = chain_is_cumulative
    mechanical_passed = all(checks.values())
    optical_passed = scanner_process_status in {
        "passed",
        "static_demo_passed_barcode_surface_proxy",
    }
    optical_partial = scanner_process_status == (
        "coarse_geometry_compatible_working_distance_unconfirmed"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": (
            "mechanical_demo_chain_passed_scanner_process_partial"
            if mechanical_passed and optical_partial
            else "mechanical_demo_chain_passed_scanner_process_pending"
            if mechanical_passed and not optical_passed
            else "complete_demo_chain_passed"
            if mechanical_passed and optical_passed
            else "mechanical_demo_chain_failed"
        ),
        "jobId": job.get("jobId"),
        "releaseId": release.get("releaseId"),
        "naturalLanguageRequirements": deepcopy(
            ((plan.get("commandAudit") or {}).get("payload") or {}).get(
                "commands"
            )
            or []
        ),
        "moduleSequence": [base_module_token.upper(), *actual_order],
        "checks": checks,
        "cadPackets": cad_summaries,
        "mechanicalDemoChainPassed": mechanical_passed,
        "scannerProcessValidation": {
            "status": scanner_process_status,
            "passed": optical_passed,
            "evidenceLevel": (
                "static_demo_proxy"
                if scanner_process_status == "static_demo_passed_barcode_surface_proxy"
                else "engineering"
                if scanner_process_status == "passed"
                else "incomplete"
            ),
            "productionReady": scanner_process_status == "passed",
            "statement": (
                f"{scanner_module_token}—{transport_module_token}粗几何与扫描器官方读取距离通过静态Demo验证；条码面、码尺寸、视野和现场触发仍待工程确认。"
                if scanner_process_status == "static_demo_passed_barcode_surface_proxy"
                else f"{scanner_module_token}光轴与{transport_module_token}动态条码通道的粗几何对齐已通过；权威工作距离区间和真实条码面尚未确认。"
                if optical_partial
                else f"{scanner_module_token}已按已发布安装端口完成机械定位；其对{transport_module_token}条码目标的光轴和工作距离尚未验证。"
                if not optical_passed
                else "扫描光轴、目标点和工作距离已经通过。"
            ),
        },
        "completeFunctionalDemoPassed": mechanical_passed and optical_passed,
        "collisionStatus": job.get("collisionStatus"),
        "finalAssemblyPath": (
            job.get("lastCommittedCheckpoint") or {}
        ).get("assemblyPath"),
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "project06Included": False,
        "nextAction": (
            f"register-real-{transport_module_token.lower()}-barcode-surface-and-verify-code-size-field-of-view"
            if mechanical_passed
            and scanner_process_status == "static_demo_passed_barcode_surface_proxy"
            else f"confirm-{scanner_module_token.lower()}-working-distance-range-and-register-{transport_module_token.lower()}-barcode-surface"
            if mechanical_passed and optical_partial
            else f"capture-{scanner_module_token.lower()}-optical-axis-and-{transport_module_token.lower()}-barcode-target-then-run-read-only-process-validation"
            if mechanical_passed and not optical_passed
            else None
        ),
    }
    return {**core, "closureDigest": _digest(core)}
