from demo_backend.global_cad_driving_evidence import (
    assess_external_placement_repeatability,
)
from demo_backend.global_module_gap_report import _external_pose_closed


def _payload(transform, *, witness=False):
    mate = {
        "Success": True,
        "Found": True,
        "TypeMatches": True,
        "AlignmentMatches": True,
        "DistanceMatches": True,
        "AngleMatches": True,
        "AdvancedOptionsMatch": True,
    }
    return {
        "schemaVersion": "checkpoint-selected-face-context-insert-run/v1",
        "success": True,
        "sourceAssemblyUnchanged": True,
        "outputAssemblySha256": "artifact-sha",
        "outputClosedAfterVerification": True,
        "targetSourceSessionClean": True,
        "toolResult": {
            "Success": True,
            "ExecutionMode": "context_incremental_insert",
            "IndependentComponentInserted": True,
            "OriginalComponentRemoved": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "AppliedTargetLeafPoseAnchorCount": 0,
            "RequestedMateCount": 1,
            "CreatedMateCount": 1,
            "MateResults": [mate],
            "MateVerifications": [mate],
            "ValidationResults": [],
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "TargetFullyConstrained": False,
            "TargetConstraintStateAccepted": True,
            "ExternalPlacementEquivalencePassed": witness,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
            "ReopenedTargetRootTransform": transform,
        },
    }


def test_two_seed_witness_accepts_same_root_without_pose_anchors():
    transform = [float(value) for value in range(16)]
    baseline = _payload(transform)
    confirmation = _payload(transform, witness=True)
    graph = {
        "ExternalPlacementRepeatabilityAudit": {
            "initialPlacementVariant": 1,
            "witnessIsValidationOnly": True,
            "poseAnchorUsed": False,
            "witnessTransform": transform,
            "firstRunOutputAssemblySha256": "artifact-sha",
        }
    }

    assessment = assess_external_placement_repeatability(
        baseline, confirmation, graph, expected_mate_count=1
    )

    assert assessment["passed"] is True


def test_gap_report_accepts_current_external_witness_field():
    assessment = {
        "semanticPassed": True,
        "checkpointPassed": True,
        "constraintStateObservation": {
            "targetFullyConstrained": False,
            "externalPlacementEquivalenceProven": True,
        },
    }

    assert _external_pose_closed(assessment) is True
