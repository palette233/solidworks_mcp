"""Close Project03 macro layout while preserving the AC00 geometry blocker."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = (
    "FL9A24D063AA00",
    "FL9A24D063AF00",
    "FL9A24D063AE00",
    "FL9A24D063AD00",
    "FL9A24D063AI00",
    "FL9A24D063AG00",
    "FL9A24D063AH00",
    "FL9A24D063AJ00",
    "FL9A24D063AB00",
    "FL9A24D063AC00",
)


def pick(document: dict[str, Any], name: str, default: Any = None) -> Any:
    return document.get(name, document.get(name[0].lower() + name[1:], default))


def token_for(value: str) -> str:
    matches = [token for token in TOKENS if token in value.upper()]
    if len(matches) != 1:
        raise ValueError(f"Could not identify one Project03 token in {value!r}")
    return matches[0]


def build_project03_macro_static_closure(
    *,
    source_graph: dict[str, Any],
    prior_closures: list[dict[str, Any]],
    ab00_result: dict[str, Any],
    ac00_macro_result: dict[str, Any],
    ac00_subtree_comparison: dict[str, Any],
    ac00_anchor_flexible_result: dict[str, Any],
    ac00_anchor_rigid_result: dict[str, Any],
    ac00_prefixed_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    valve_reach: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly_path = assembly_path.resolve()
    if not assembly_path.is_file():
        raise FileNotFoundError(assembly_path)
    source = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in TOKENS
    }
    observed = {
        token_for(str(row.get("Name") or row.get("HierarchyPath") or "")): row
        for row in poses.get("components") or []
    }
    if set(source) != set(TOKENS) or set(observed) != set(TOKENS):
        raise ValueError("Expected the complete ten-object Project03 token set")
    pose_rows = []
    for token in TOKENS:
        error = max(
            abs(float(left) - float(right))
            for left, right in zip(
                source[token]["SourceTransform"], observed[token]["Transform"], strict=True
            )
        )
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": error,
                "sourcePoseEquivalent": error <= 1e-12,
            }
        )
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)
    prior_ok = len(prior_closures) == 6 and all(
        row.get("success") is True for row in prior_closures
    )
    ab_tool = ab00_result.get("toolResult") or {}
    ab_ok = bool(
        ab00_result.get("success") is True
        and pick(ab_tool, "CreatedMateCount") == 1
        and pick(ab_tool, "TargetCaseAnchored") is True
        and pick(ab_tool, "CaseAnchorPoseMatch") is True
    )
    macro_tool = ac00_macro_result.get("toolResult") or {}
    macro_insert_ok = bool(
        ac00_macro_result.get("success") is True
        and pick(macro_tool, "CreatedMateCount") == 0
        and pick(macro_tool, "TargetCaseAnchored") is True
        and pick(macro_tool, "CaseAnchorPoseMatch") is True
        and pick(macro_tool, "Reopened") is True
    )
    broadphase_ok = bool(
        screening.get("status") == "BROAD_PHASE_COMPLETE"
        and int(screening.get("componentCount") or 0) == 10
        and int(screening.get("allTopLevelPairCount") or 0) == 45
        and int(screening.get("aabbProvenPairCount") or 0) == 22
        and int(screening.get("exactCandidatePairCount") or 0) == 23
    )
    reach_ok = bool(
        valve_reach.get("allRequiredTargetsInsideCommonReach") is True
        and int(valve_reach.get("requiredTargetCount") or 0) == 9
    )
    macro_static_passed = (
        prior_ok and ab_ok and macro_insert_ok and pose_ok and broadphase_ok and reach_ok
    )
    unstable_count = int(ac00_subtree_comparison.get("unstableCount") or 0)
    internal_geometry_closed = bool(
        ac00_subtree_comparison.get("stable") is True and unstable_count == 0
    )
    full_geometry_closed = bool(
        macro_static_passed
        and internal_geometry_closed
        and screening.get("status") == "EXACT_CHECK_COMPLETE"
        and screening.get("success") is True
    )

    def trial(result: dict[str, Any], interpretation: str) -> dict[str, Any]:
        tool = result.get("toolResult") or {}
        return {
            "success": result.get("success") is True,
            "durationSeconds": float(result.get("durationSeconds") or 0),
            "requestedMateCount": int(pick(tool, "RequestedMateCount", 0) or 0),
            "createdMateCount": int(pick(tool, "CreatedMateCount", 0) or 0),
            "requestedLeafPoseAnchorCount": int(
                pick(tool, "RequestedTargetLeafPoseAnchorCount", 0) or 0
            ),
            "appliedLeafPoseAnchorCount": int(
                pick(tool, "AppliedTargetLeafPoseAnchorCount", 0) or 0
            ),
            "interpretation": interpretation,
        }

    return {
        "schemaVersion": "project03-macro-static-closure/v1",
        "projectId": "project03",
        "status": (
            "PROJECT03_MACRO_STATIC_CAD_CLOSED_FULL_GEOMETRY_BLOCKED"
            if macro_static_passed and not full_geometry_closed
            else "PROJECT03_MACRO_STATIC_CAD_BLOCKED"
        ),
        "success": full_geometry_closed,
        "macroStaticPassed": macro_static_passed,
        "fullGeometryClosed": full_geometry_closed,
        "productionReady": False,
        "assemblyPath": str(assembly_path),
        "assemblySha256": hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        "componentCount": len(observed),
        "semanticStageCount": 7,
        "completedIndependentCadActionCount": 8,
        "macroLayoutGate": {
            "passed": macro_static_passed,
            "priorCheckpointCount": len(prior_closures),
            "ab00Passed": ab_ok,
            "ac00IndependentTopLevelInsertPassed": macro_insert_ok,
            "poseAuditPassed": pose_ok,
            "maximumTransformElementError": max(
                row["maximumTransformElementError"] for row in pose_rows
            ),
            "modules": pose_rows,
        },
        "ac00InternalStateGate": {
            "passed": internal_geometry_closed,
            "prototypeNodeCount": int(
                ac00_subtree_comparison.get("comparedCount") or 0
            ),
            "unstableNodeCount": unstable_count,
            "maximumTranslationDistanceMeters": ac00_subtree_comparison.get(
                "maximumTranslationDistanceMeters"
            ),
            "conclusion": (
                "AC00 top-level pose is recovered, but its flexible parent-context "
                "internal state is not reproduced by the independent module file."
            ),
            "failedRecoveryTrials": {
                "leafAnchorsFlexible": trial(
                    ac00_anchor_flexible_result,
                    "All selected anchors applied, then drifted after save/reopen.",
                ),
                "leafAnchorsRigid": trial(
                    ac00_anchor_rigid_result,
                    "Rigid top-level solving did not persist nested transforms.",
                ),
                "preFixedRootWithSourceMates": trial(
                    ac00_prefixed_result,
                    "Concentric source mates became over-defined after pre-fixing the root.",
                ),
            },
        },
        "reachGate": {
            "passedForMacroStatic": reach_ok,
            "requiredTargetCount": int(valve_reach.get("requiredTargetCount") or 0),
            "engineeringConfirmed": valve_reach.get("engineeringConfirmed") is True,
        },
        "collisionGate": {
            "broadPhasePassed": broadphase_ok,
            "fullGeometryPassed": full_geometry_closed,
            "allTopLevelPairCount": int(screening.get("allTopLevelPairCount") or 0),
            "aabbSeparatedPairCount": int(screening.get("aabbProvenPairCount") or 0),
            "conditionalBrepPairCount": int(
                screening.get("exactCandidatePairCount") or 0
            ),
            "conditionalBrepExecuted": False,
            "zeroInterferenceClaimed": False,
            "reason": (
                "Conditional B-rep is intentionally deferred because AC00's internal "
                "geometry state is not yet equivalent to the prototype working state."
            ),
        },
        "timingSeconds": {
            "ac00MacroInsert": float(ac00_macro_result.get("durationSeconds") or 0),
            "prototypeSubtreeCapture": 410.76525880000554,
            "candidateSubtreeCapture": 380.096952999942,
            "broadPhase": float(
                (screening.get("timing") or {}).get("totalDurationSeconds") or 0
            ),
        },
        "blockers": [
            "AC00独立文件Default状态与原型父装配柔性状态有72个子树节点不一致。",
            "顶层刚性设置不能固化嵌套组件Transform2；需要命名内部配置、内部配合状态导出，或派生静态快照子装配体。",
            "在AC00内部状态恢复前，23对宽相候选不执行发布级条件B-rep，也不宣称零干涉。",
            "AB00宽度配合仍由显式原型残差锚点替代；双阀行程仍是原型估计值。",
        ],
        "nextStep": (
            "为AC00实现父装配柔性状态的可移植表达：优先导出内部配合抑制/配置状态；"
            "若源文件没有命名配置，则生成派生静态快照子装配体并再次执行134节点对比。"
        ),
    }
