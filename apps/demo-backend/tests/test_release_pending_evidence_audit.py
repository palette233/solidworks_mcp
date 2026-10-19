from demo_backend.release_pending_evidence_audit import (
    build_release_pending_evidence_audit,
)


def _payload(*, schema="context-incremental-insert-run/v1", anchored=False):
    checkpoint = schema == "checkpoint-selected-face-context-insert-run/v1"
    return {
        "schemaVersion": schema,
        "success": True,
        "sourceAssemblyUnchanged": True if checkpoint else None,
        "outputAssemblySha256": "sha" if checkpoint else None,
        "outputClosedAfterVerification": True if checkpoint else None,
        "targetSourceSessionClean": True if checkpoint else None,
        "targetModuleToken": "X100",
        "toolResult": {
            "Success": True,
            "ExecutionMode": "context_incremental_insert",
            "IndependentComponentInserted": True,
            "OriginalComponentRemoved": True,
            "TargetCaseAnchored": anchored,
            "RequestedTargetLeafPoseAnchorCount": 0,
            "AppliedTargetLeafPoseAnchorCount": 0,
            "RequestedMateCount": 3,
            "CreatedMateCount": 3,
            "MateResults": [{"Success": True}] * 3,
            "MateVerifications": [
                {
                    "Found": True,
                    "TypeMatches": True,
                    "AlignmentMatches": True,
                    "DistanceMatches": True,
                    "AngleMatches": True,
                    "AdvancedOptionsMatch": True,
                }
            ]
            * 3,
            "ValidationResults": [],
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "TargetFullyConstrained": True,
            "TargetConstraintStateAccepted": True,
            "MateSolveClean": True,
            "ComponentSemanticsMatch": True,
        },
    }


def _case(payloads):
    return {
        "projectId": "project01",
        "moduleToken": "X100",
        "moduleRole": "Calibration",
        "templateId": "X100_to_BASE_three_datum",
        "expectedMateCount": 3,
        "evidence": [
            {"path": f"run-{index}.json", "payload": payload}
            for index, payload in enumerate(payloads)
        ],
    }


def test_legacy_complete_run_requires_only_checkpoint_refresh():
    report = build_release_pending_evidence_audit([_case([_payload()])])

    row = report["modules"][0]
    assert row["state"] == "checkpoint_refresh_required"
    assert row["evidence"][0]["state"] == "checkpoint_refresh_required"
    assert report["summary"]["checkpointRefreshRequiredCount"] == 1


def test_strict_checkpoint_can_be_reused_for_release():
    report = build_release_pending_evidence_audit(
        [_case([_payload(schema="checkpoint-selected-face-context-insert-run/v1")])]
    )

    assert report["modules"][0]["state"] == "reusable_for_release"
    assert report["summary"]["reusableForReleaseCount"] == 1


def test_nonanchor_open_pose_takes_priority_over_anchored_success():
    open_payload = _payload()
    open_payload["success"] = False
    open_payload["toolResult"]["Success"] = False
    open_payload["toolResult"]["TargetFullyConstrained"] = False
    open_payload["toolResult"]["TargetConstraintStateAccepted"] = False
    report = build_release_pending_evidence_audit(
        [_case([_payload(anchored=True), open_payload])]
    )

    row = report["modules"][0]
    assert row["state"] == "complete_installation_bundle_required"
    assert {item["state"] for item in row["evidence"]} == {
        "anchored_only",
        "external_pose_open",
    }


def test_missing_evidence_is_explicit():
    report = build_release_pending_evidence_audit([_case([])])

    assert report["modules"][0]["state"] == "cad_evidence_missing"
    assert report["summary"]["otherBlockedCount"] == 1
