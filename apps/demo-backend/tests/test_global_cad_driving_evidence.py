from demo_backend.global_cad_driving_evidence import assess_driving_insert_evidence


def _payload(schema: str) -> dict:
    return {
        "schemaVersion": schema,
        "success": True,
        "sourceAssemblyUnchanged": True,
        "outputAssemblySha256": "sha",
        "outputClosedAfterVerification": True,
        "targetSourceSessionClean": True,
        "targetModuleToken": "FL9A24D063AE00",
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
            "MateResults": [{"Success": True}],
            "MateVerifications": [
                {
                    "Found": True,
                    "TypeMatches": True,
                    "AlignmentMatches": True,
                    "DistanceMatches": True,
                    "AngleMatches": True,
                    "AdvancedOptionsMatch": True,
                }
            ],
            "ValidationResults": [],
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "TargetFullyConstrained": True,
            "TargetConstraintStateAccepted": True,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
        },
    }


def test_checkpoint_evidence_is_release_candidate():
    result = assess_driving_insert_evidence(
        _payload("checkpoint-selected-face-context-insert-run/v1"),
        expected_mate_count=1,
    )

    assert result["status"] == "release_candidate"
    assert result["checkpointPassed"] is True
    assert result["blockers"] == []


def test_legacy_evidence_requires_checkpoint_refresh():
    payload = _payload("context-incremental-insert-run/v1")
    for key in (
        "sourceAssemblyUnchanged",
        "outputAssemblySha256",
        "outputClosedAfterVerification",
        "targetSourceSessionClean",
    ):
        payload.pop(key)

    result = assess_driving_insert_evidence(payload, expected_mate_count=1)

    assert result["semanticPassed"] is True
    assert result["status"] == "checkpoint_refresh_required"
    assert "checkpointEnvelope" in result["blockers"]


def test_anchor_dependency_blocks_candidate():
    payload = _payload("checkpoint-selected-face-context-insert-run/v1")
    payload["toolResult"]["TargetCaseAnchored"] = True

    result = assess_driving_insert_evidence(payload, expected_mate_count=1)

    assert result["status"] == "blocked"
    assert "casePoseAnchorNotUsed" in result["blockers"]


def test_flexible_internal_state_can_preserve_motion_while_external_placement_closes():
    payload = _payload("checkpoint-selected-face-context-insert-run/v1")
    payload["toolResult"]["TargetFullyConstrained"] = False
    payload["toolResult"]["ExternalPlacementEquivalencePassed"] = True

    result = assess_driving_insert_evidence(payload, expected_mate_count=1)

    assert result["status"] == "release_candidate"
    assert result["checkpointPassed"] is True
    assert result["constraintStateObservation"] == {
        "targetFullyConstrained": False,
        "targetConstraintStateAccepted": True,
        "acceptedFlexibleInternalState": True,
        "externalPlacementEquivalenceProven": True,
        "residualDofScope": "internal_mechanism",
    }
    assert result["portablePlacementProven"] is True


def test_flexible_acceptance_without_external_witness_is_not_portable():
    payload = _payload("checkpoint-selected-face-context-insert-run/v1")
    payload["toolResult"]["TargetFullyConstrained"] = False

    result = assess_driving_insert_evidence(payload, expected_mate_count=1)

    assert result["checkpointPassed"] is True
    assert result["portablePlacementProven"] is False
    assert result["constraintStateObservation"]["residualDofScope"] == (
        "unclassified_without_external_placement_witness"
    )


def test_unaccepted_constraint_state_still_blocks_candidate():
    payload = _payload("checkpoint-selected-face-context-insert-run/v1")
    payload["toolResult"]["TargetFullyConstrained"] = False
    payload["toolResult"]["TargetConstraintStateAccepted"] = False

    result = assess_driving_insert_evidence(payload, expected_mate_count=1)

    assert result["status"] == "blocked"
    assert "targetConstraintStateAccepted" in result["blockers"]
