"""Certify the complete Project01 ten-functional-object static CAD chain."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


SOURCE_TOKENS = ("JJ00", "HL00", "SS00", "FF00", "SM00", "GN00", "BD00", "GJ00")
SNAPSHOT_TOKEN = "LM00_ZZ00_STATIC"


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def token(text: str) -> str:
    upper = str(text).upper()
    matches = [item for item in SOURCE_TOKENS if item in upper]
    if len(matches) == 1:
        return matches[0]
    if "PROJECT01_LM00_ZZ00_STATIC_CONTEXT" in upper:
        return SNAPSHOT_TOKEN
    raise ValueError(f"Cannot identify one final Project01 node in {text!r}")


def build_project01_full_static_closure(
    *,
    source_graph: dict[str, Any],
    prior_closures: list[dict[str, Any]],
    dynamic_attempts: list[dict[str, Any]],
    subset_run: dict[str, Any],
    lm_comparison: dict[str, Any],
    zz_comparison: dict[str, Any],
    insert_run: dict[str, Any],
    poses: dict[str, Any],
    broadphase: dict[str, Any],
    exact_batch: dict[str, Any],
    valve_reach: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly = assembly_path.resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)
    prior_ok = len(prior_closures) == 6 and all(item.get("success") is True for item in prior_closures)
    dynamic_failures = [item for item in dynamic_attempts if item.get("success") is False]
    dynamic_gap_proven = len(dynamic_attempts) >= 2 and len(dynamic_failures) == len(dynamic_attempts)
    subset_tool = subset_run.get("toolResult") or {}
    subset_ok = bool(
        subset_run.get("success")
        and pick(subset_tool, "Reopened") is True
        and pick(subset_tool, "PathsMatch") is True
        and pick(subset_tool, "RootPosesMatch") is True
        and int(pick(subset_tool, "ReopenedTopLevelComponentCount", -1)) == 2
        and lm_comparison.get("stable") is True
        and zz_comparison.get("stable") is True
    )
    insert_tool = insert_run.get("toolResult") or {}
    insert_ok = bool(
        insert_run.get("success")
        and pick(insert_tool, "IndependentComponentInserted") is True
        and int(pick(insert_tool, "CreatedMateCount", -1)) == 0
        and pick(insert_tool, "ReopenedMateParametersMatch") is True
        and pick(insert_tool, "TargetFullyConstrained") is True
    )

    source = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in SOURCE_TOKENS
    }
    observed = {
        token(str(row.get("HierarchyPath") or row.get("Name") or "")): row
        for row in poses.get("components") or []
    }
    if set(source) != set(SOURCE_TOKENS) or set(observed) != set(SOURCE_TOKENS) | {SNAPSHOT_TOKEN}:
        raise ValueError("Expected eight source modules plus the LM00+ZZ00 static snapshot.")
    pose_rows: list[dict[str, Any]] = []
    for module_token in SOURCE_TOKENS:
        expected = source[module_token]["SourceTransform"]
        actual = observed[module_token]["Transform"]
        error = max(abs(float(a) - float(b)) for a, b in zip(expected, actual, strict=True))
        pose_rows.append({"moduleToken": module_token, "maximumTransformElementError": error, "sourcePoseEquivalent": error <= 1e-12})
    snapshot_transform = observed[SNAPSHOT_TOKEN]["Transform"]
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    snapshot_error = max(abs(float(a) - float(b)) for a, b in zip(identity, snapshot_transform, strict=True))
    pose_rows.append({"moduleToken": SNAPSHOT_TOKEN, "maximumTransformElementError": snapshot_error, "sourcePoseEquivalent": snapshot_error <= 1e-12})
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)

    broad_rows = list(broadphase.get("broadPhase") or [])
    broad_ok = bool(
        broadphase.get("status") == "BROAD_PHASE_COMPLETE"
        and int(broadphase.get("allTopLevelPairCount") or 0) == 36
        and int(broadphase.get("aabbProvenPairCount") or 0) == 17
        and int(broadphase.get("exactCandidatePairCount") or 0) == 19
        and len(broad_rows) == 36
    )
    exact_pairs = list(exact_batch.get("pairs") or [])
    exact_ok = bool(
        int(exact_batch.get("requestedPairCount") or 0) == 4
        and int(exact_batch.get("completedPairCount") or 0) == 4
        and int(exact_batch.get("hardFailureCount") or 0) == 0
        and int(exact_batch.get("acceptedPairCount") or 0) == 4
        and all((row.get("acceptance") or {}).get("accepted") is True for row in exact_pairs)
    )
    baseline_pairs = [row for row in exact_pairs if (row.get("acceptance") or {}).get("policy") == "noNewInterferenceOverAcceptedBaseline"]
    collision_ok = broad_ok and exact_ok and pose_ok

    reach_checks = list(valve_reach.get("requiredTargetChecks") or [])
    reach_ok = bool(
        valve_reach.get("coarseLayoutUsable") is True
        and valve_reach.get("allRequiredTargetsInsideCommonReach") is True
        and int(valve_reach.get("requiredTargetCount") or 0) == 8
        and len(reach_checks) == 8
        and all(row.get("insideCommonReach") is True for row in reach_checks)
    )
    success = prior_ok and dynamic_gap_proven and subset_ok and insert_ok and pose_ok and collision_ok and reach_ok
    prior_seconds = sum(float((item.get("timingSeconds") or {}).get("totalMeasuredSeconds") or 0) for item in prior_closures)
    dynamic_seconds = sum(float(item.get("durationSeconds") or 0) for item in dynamic_attempts)
    return {
        "schemaVersion": "project01-full-static-closure/v1",
        "projectId": "project01",
        "status": "PROJECT01_FULL_10_FUNCTIONAL_OBJECT_STATIC_DEMO_CLOSED" if success else "PROJECT01_FULL_STATIC_DEMO_BLOCKED",
        "success": success,
        "staticDemoPassed": success,
        "productionReady": False,
        "absoluteZeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok,
        "functionalModuleCount": 10,
        "cadTopLevelNodeCount": 9,
        "assemblyPath": str(assembly),
        "assemblySha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
        "priorCheckpointGate": {"passed": prior_ok, "checkpointCount": len(prior_closures)},
        "dynamicSemanticsGate": {
            "passed": False,
            "failureCaptured": dynamic_gap_proven,
            "attemptCount": len(dynamic_attempts),
            "reason": "Real LM00/ZZ00 mates do not uniquely persist the flexible internal travel state after save/reopen.",
        },
        "staticSnapshotGate": {
            "passed": subset_ok,
            "lmSubtreeComponentCount": int(lm_comparison.get("comparedCount") or 0),
            "zzSubtreeComponentCount": int(zz_comparison.get("comparedCount") or 0),
            "maximumInternalTransformElementError": max(float(lm_comparison.get("maximumTransformElementError") or 0), float(zz_comparison.get("maximumTransformElementError") or 0)),
            "motionSemanticsPreserved": False,
        },
        "finalInsertGate": {"passed": insert_ok, "drivingMateCount": int(pick(insert_tool, "CreatedMateCount", 0))},
        "poseAudit": {"passed": pose_ok, "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows), "nodes": pose_rows},
        "collisionGate": {
            "passed": collision_ok,
            "topLevelPairCount": 36,
            "aabbSeparatedPairCount": 17,
            "broadPhaseCandidatePairCount": 19,
            "newSnapshotExactPairCount": 4,
            "zeroInterferenceExactPairCount": 2,
            "prototypeBaselineAcceptedPairCount": len(baseline_pairs),
            "oldContextCandidatePairCountReused": 15,
            "absoluteZeroInterference": False,
            "noNewInterference": collision_ok,
            "exactPairs": exact_pairs,
        },
        "reachGate": {
            "passedForStaticDemo": reach_ok,
            "productionReady": False,
            "requiredTargetCount": len(reach_checks),
            "minimumBoundaryMarginMeters": valve_reach.get("minimumTargetBoundaryMarginMeters"),
            "engineeringConfirmed": valve_reach.get("engineeringConfirmed") is True,
            "vendorConfirmed": valve_reach.get("vendorConfirmed") is True,
        },
        "timingSeconds": {
            "priorSuccessfulCheckpoints": prior_seconds,
            "failedDynamicExperiments": dynamic_seconds,
            "staticSubsetCreation": float(subset_run.get("durationSeconds") or 0),
            "finalStaticInsert": float(insert_run.get("durationSeconds") or 0),
            "finalPoseCapture": float(poses.get("durationSeconds") or 0),
            "finalBroadPhase": float((broadphase.get("timing") or {}).get("totalDurationSeconds") or 0),
            "newSnapshotExactBatch": float((exact_batch.get("timing") or {}).get("durationSeconds") or 0),
        },
        "productionBlockers": [
            "LM00/ZZ00 is a parent-context static snapshot; independent kinematics are not reconstructed.",
            "Dual-valve travel and eight-target reach are prototype estimates, not vendor or limit-switch values.",
            "FF00 dynamic rotation/sweep is not closed.",
            "GJ00 hose centerlines, bend radii, sweep and maintenance route are not validated.",
            "Two exact collision pairs are accepted only as unchanged prototype baselines, so absolute zero interference is not claimed.",
        ],
        "nextStep": "Use this as the Project01 static Demo checkpoint; acquire authoritative motion limits and internal mechanism relations before dynamic/production release.",
    }
