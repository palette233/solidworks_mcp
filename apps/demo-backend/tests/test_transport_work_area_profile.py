import hashlib
import json

import pytest

from demo_backend.transport_work_area_profile import (
    build_transport_context_work_area_profile,
    compare_transport_work_area_profiles,
)


def sha(value=b"artifact"):
    return hashlib.sha256(value).hexdigest()


def artifact(project="project01", spacing=0.435, transverse=0.0):
    return {
        "schemaVersion": f"{project}-work-positions/v1",
        "projectId": project,
        "authority": "measured prototype context",
        "engineeringConfirmed": False,
        "workPositionCount": 2,
        "centerSeparationMeters": spacing,
        "workPositions": [
            {
                "stableId": "workPositionLowU",
                "sourceInstance": "station-1",
                "installationFramePointMeters": {
                    "u": 0.1, "v": 0.2, "normal": 0.3,
                },
            },
            {
                "stableId": "workPositionHighU",
                "sourceInstance": "station-2",
                "installationFramePointMeters": {
                    "u": 0.1 + spacing, "v": 0.2 + transverse, "normal": 0.3,
                },
            },
        ],
        "interpretationLimits": ["coarse target"],
    }


def profile(project="project01", transport="T", owner="CTX", spacing=0.435):
    return build_transport_context_work_area_profile(
        artifact=artifact(project, spacing),
        artifact_binding={"path": f"{project}.json", "sha256": sha(project.encode())},
        transport_definition_id=f"{project}::{transport}",
        context_definition_ids=[f"{project}::{owner}"],
        context_description="two process stations owned by a context module",
    )


def test_profile_keeps_context_ownership_separate_from_bare_transport():
    result = profile()
    assert result["workPositionsOwnedByBareTransport"] is False
    assert result["workPositionContextDefinitionIds"] == ["project01::CTX"]
    assert result["metrics"]["longitudinalSpanMeters"] == pytest.approx(0.435)
    assert result["metrics"]["planSeparationMeters"] == pytest.approx(0.435)
    assert len(result["profileDigest"]) == 64
    assert result["cadStarted"] is False


def test_profile_rejects_project_mismatch_and_bad_rows():
    with pytest.raises(ValueError, match="project differs"):
        build_transport_context_work_area_profile(
            artifact=artifact("project01"),
            artifact_binding={"path": "a.json", "sha256": sha()},
            transport_definition_id="project03::AE00",
            context_definition_ids=["project03::AD00"],
            context_description="context",
        )
    broken = artifact()
    broken["workPositions"][1]["stableId"] = "workPositionLowU"
    with pytest.raises(ValueError, match="unique"):
        build_transport_context_work_area_profile(
            artifact=broken,
            artifact_binding={"path": "a.json", "sha256": sha()},
            transport_definition_id="project01::SS00",
            context_definition_ids=["project01::FF00"],
            context_description="context",
        )


def test_comparison_reports_metrics_but_does_not_invent_tolerance():
    source = profile(spacing=0.4362)
    target = profile(
        project="project05", transport="D000", owner="K000", spacing=0.415
    )
    result = compare_transport_work_area_profiles(
        source_profile=source,
        target_profile=target,
        target_base_definition_id="project05::A000",
        candidate_rule_id="transport-position-project01-ss00-to-project05-a000-v1",
    )
    assert result["measuredComparison"][
        "absoluteCenterSeparationDifferenceMeters"
    ] == pytest.approx(0.0212)
    assert result["engineeringAcceptanceRecorded"] is False
    assert result["publicationAllowed"] is False
    assert "WORK_POSITION_SPACING_ACCEPTANCE_POLICY_REQUIRED" in result[
        "blockingReasonCodes"
    ]
    assert "WORK_POSITION_CONTEXT_SELECTION_REQUIRED" in result[
        "blockingReasonCodes"
    ]
    assert "CURRENT_CAD_WORK_POSITION_REPROJECTION_REQUIRED" in result[
        "blockingReasonCodes"
    ]
    assert result["contextComparison"][
        "bareTransportOnlyCandidateCanReprojectBothContexts"
    ] is False
    assert result["contextComparison"][
        "requiredSourceContextInstancesForCurrentCadReprojection"
    ] == ["project01::CTX"]


def test_equal_spacing_still_needs_track_context_and_current_cad_evidence():
    source = profile(spacing=0.415)
    target = profile(
        project="project05", transport="D000", owner="K000", spacing=0.415
    )
    result = compare_transport_work_area_profiles(
        source_profile=source,
        target_profile=target,
        target_base_definition_id="project05::A000",
        candidate_rule_id="candidate",
    )
    assert "WORK_POSITION_SPACING_ACCEPTANCE_POLICY_REQUIRED" not in result[
        "blockingReasonCodes"
    ]
    assert result["blockingReasonCodes"] == [
        "TRACK_AND_CARRIER_INTERFACE_EVIDENCE_REQUIRED",
        "WORK_POSITION_CONTEXT_SELECTION_REQUIRED",
        "CURRENT_CAD_WORK_POSITION_REPROJECTION_REQUIRED",
    ]
    assert result["status"] == "requires_engineering_threshold_or_context_selection"


def test_comparison_rejects_tampered_profile_digest():
    source = profile()
    target = profile(project="project05", transport="D000", owner="K000")
    source["metrics"]["artifactCenterSeparationMeters"] = 99
    with pytest.raises(ValueError, match="digest mismatch"):
        compare_transport_work_area_profiles(
            source_profile=source,
            target_profile=target,
            target_base_definition_id="project05::A000",
            candidate_rule_id="candidate",
        )
