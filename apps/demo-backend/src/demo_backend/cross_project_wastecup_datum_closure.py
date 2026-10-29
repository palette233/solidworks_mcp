"""Close a cross-project WasteCup datum-placement CAD demonstration.

This closure intentionally separates a successful semantic datum placement
from a direct mechanical-interface compatibility claim.  BodyFaceIndex is an
accepted recovery fallback for the unchanged source topology, but it is made
visible as a portability limitation instead of being promoted to a production
release guarantee.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "cross-project-wastecup-datum-closure/v1"


class CrossProjectWasteCupDatumClosureError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(checks: dict[str, bool]) -> None:
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise CrossProjectWasteCupDatumClosureError(
            "跨项目排胶杯基准定位闭环未通过：" + ", ".join(failed)
        )


def close_project05_p000_to_project02_a600_datum_demo(
    *,
    candidate_audit: dict[str, Any],
    cad_result: dict[str, Any],
    effective_graph_path: Path,
    output_assembly_path: Path,
    read_only_state: dict[str, Any] | None = None,
    expected_context_module_tokens: tuple[str, ...] = ("A600",),
    target_base_token: str = "A600",
    target_project_id: str = "project02",
) -> dict[str, Any]:
    if candidate_audit.get("schemaVersion") != (
        "cross-project-wastecup-datum-candidate/v1"
    ):
        raise CrossProjectWasteCupDatumClosureError("候选审计版本不受支持。")
    if cad_result.get("schemaVersion") != (
        "checkpoint-selected-face-context-insert-run/v1"
    ):
        raise CrossProjectWasteCupDatumClosureError("CAD结果版本不受支持。")
    if not effective_graph_path.is_file():
        raise CrossProjectWasteCupDatumClosureError("有效配合图文件不存在。")
    if not output_assembly_path.is_file():
        raise CrossProjectWasteCupDatumClosureError("输出装配体不存在。")

    tool = cad_result.get("toolResult") or {}
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    strategies = [
        str(strategy)
        for row in mate_results
        for strategy in row.get("EndpointResolutionStrategies") or []
    ]
    graph_sha256 = _sha256(effective_graph_path)
    output_sha256 = _sha256(output_assembly_path)
    checks = {
        "targetBaseIdentityMatches": candidate_audit.get("targetBaseToken", "A600") == target_base_token
        and candidate_audit.get("targetProjectId", "project02") == target_project_id,
        "candidateAuthorizedCadValidation": candidate_audit.get("cadLaunchAllowed")
        is True,
        "candidateUsesNoPrototypeTopLevelPose": candidate_audit.get(
            "prototypeTopLevelTargetPoseUsed"
        )
        is False,
        "candidateUsesNoCaseOrLeafAnchors": candidate_audit.get("caseAnchorUsed")
        is False
        and candidate_audit.get("targetLeafPoseAnchorsUsed") is False,
        "graphDigestMatchesCadRun": graph_sha256
        == str(cad_result.get("effectiveGraphSha256") or "").lower(),
        "cadSucceeded": cad_result.get("success") is True
        and tool.get("Success") is True,
        "sourceAssemblyUnchanged": cad_result.get("sourceAssemblyUnchanged") is True,
        "independentTargetInserted": tool.get("IndependentComponentInserted") is True,
        "deterministicNonSourceInsertionRecorded": any(
            "deterministic non-source pose" in str(row).lower()
            for row in tool.get("Diagnostics") or []
        ),
        "noCaseOrLeafPoseAnchors": tool.get("TargetCaseAnchored") is False
        and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
        and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
        "threeOfThreeMatesCreated": int(tool.get("RequestedMateCount") or 0) == 3
        and int(tool.get("CreatedMateCount") or 0) == 3,
        "allMateCreatesPassed": len(mate_results) == 3
        and all(
            row.get("Success") is True
            and row.get("ErrorName") == "swAddMateError_NoError"
            for row in mate_results
        ),
        "targetFullyConstrained": tool.get("TargetFullyConstrained") is True
        and tool.get("TargetConstraintStateAccepted") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True,
        "saveCloseReopenPassed": tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True,
        "allReopenedMateChecksPassed": len(verifications) == 3
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in verifications
        ),
        "outputWasClosedCleanly": cad_result.get("outputClosedAfterVerification")
        is True,
        "outputDigestMatchesCadRun": output_sha256
        == str(cad_result.get("outputAssemblySha256") or "").lower(),
    }
    support_demo = candidate_audit.get("mode") == "support_position_demo"
    if support_demo:
        # This opt-in mode proves geometric placement, not a screw/hole joint.
        # Do not let the weaker physical scope weaken real-CAD state evidence.
        state = read_only_state or {}
        observed = state.get("observed") or {}
        components = observed.get("components") or []
        base = [row for row in components if f"{target_base_token}.001-" in row.get("name", "")]
        target = [row for row in components if "P000.001-" in row.get("name", "")]
        mates = observed.get("mates") or []
        expected_names = {row.get("ExpectedMateName") for row in verifications}
        checks.update({
            "supportDemoExplicitlyExcludesFixationClaim": candidate_audit.get("holePatternMatchRequired") is False
            and candidate_audit.get("actualFixationMethod") == "not_verified"
            and candidate_audit.get("directMechanicalCompatibilityClaim") is False,
            "readOnlyStateBoundToOutput": state.get("success") is True
            and state.get("assemblySha256") == output_sha256
            and observed.get("readOnly") is True,
            "onlyBaseFixedTargetLocatedByMates": len(components) == len(expected_context_module_tokens) + 1
            and len(base) == 1 and base[0].get("isFixed") is True
            and len(target) == 1 and target[0].get("isFixed") is False
            and all(sum(f"{token}.001-" in row.get("name", "") for row in components) == 1 for token in expected_context_module_tokens),
            "threeNamedMatesActiveAfterReopen": len(mates) == 3
            and {row.get("name") for row in mates} == expected_names
            and all(row.get("isSuppressed") is False and row.get("errorCode") == 0 for row in mates),
        })
    _require(checks)

    uses_body_face_index = any("BodyFaceIndex" in row for row in strategies)
    all_context_endpoints_persistent = all(
        any("endpoint#1: SourceAssemblyPersistentReference" in value for value in row.get("EndpointResolutionStrategies") or [])
        for row in mate_results
    )
    timing = tool.get("PhaseDurationsSeconds") or {}
    result = {
        "schemaVersion": SCHEMA,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED_CROSS_PROJECT_DATUM_PLACEMENT_DEMO",
        "success": True,
        "sourceProjectId": "project05",
        "sourceModuleToken": "P000",
        "targetProjectId": target_project_id,
        "targetBaseToken": target_base_token,
        "moduleRole": "WasteCup",
        "placementMode": "three_orthogonal_planar_datums",
        "semanticDatumPlacementPassed": True,
        "directMechanicalInterfaceCompatible": "not_evaluated",
        "adapterOrFastenerCompatibility": "not_evaluated",
        "releaseEligibleForDatumPlacementDemo": True,
        "releaseEligibleForDirectMechanicalSubstitution": False,
        "productionReady": False,
        "checks": checks,
        "endpointRecovery": {
            "strategies": strategies,
            "usesBodyFaceIndexFallback": uses_body_face_index,
            "allContextEndpointsUsedSourceAssemblyPersistentReference": all_context_endpoints_persistent,
            "portableAcrossUnchangedTopology": True,
            "portableAcrossTopologyEdits": False if uses_body_face_index else "not_proven",
        },
        "collisionOrBrep": "not_evaluated",
        "effectiveGraphPath": str(effective_graph_path.resolve()),
        "effectiveGraphSha256": graph_sha256,
        "outputAssemblyPath": str(output_assembly_path.resolve()),
        "outputAssemblySha256": output_sha256,
        "timingSeconds": {
            "wallClock": float(cad_result.get("durationSeconds") or 0.0),
            "cadToolInternal": float(timing.get("total") or 0.0),
            "phases": timing,
        },
        "limitations": [
            f"该闭环证明P000可由三个语义基准面定位到{target_base_token}，并不证明孔系、紧固件或实体转接件兼容。",
            "P000端点通过BodyFaceIndex恢复；源零件拓扑改变后必须重新登记或重新验证。",
            "碰撞、B-rep、维护空间和工艺可达性未纳入本轮验收。",
            "该结果仅授权基准定位Demo，不得写入直接机械替换角色统计。",
        ],
        "meaning": (
            "在不读取P000原型顶层位姿、不使用案例锚点或叶级位姿锚点的条件下，"
            "系统从确定性的非原型初始位姿插入Project05 P000，并仅凭语义端口与"
            "三条真实SolidWorks配合完成完全约束、保存关闭和重开复核。"
        ),
    }
    if support_demo:
        result.update({
            "status": "PASSED_SUPPORT_POSITION_DEMO",
            "mode": "support_position_demo",
            "holePatternMatchRequired": False,
            "actualFixationMethod": "not_verified",
            "actualFixationNotice": "实际固定方式暂未验证",
            "positionParametersMeters": candidate_audit["positionParametersMeters"],
            "parameterAuthority": candidate_audit["parameterAuthority"],
            "readOnlyStateVerification": read_only_state,
            "legacyExternalPlacementWitness": {
                "passed": tool.get("ExternalPlacementEquivalencePassed"),
                "acceptanceCriterion": False,
                "reason": "本轮SourceTransform是identity占位，不是最终位姿目标；验收支承/距离配合与重开状态，不验收与该占位变换相等。",
            },
        })
    return result

