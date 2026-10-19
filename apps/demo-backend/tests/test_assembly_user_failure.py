from demo_backend.assembly_user_failure import (
    build_assembly_user_failure,
    explain_candidate_matrix_row,
)


def test_topology_mismatch_has_concrete_mechanical_recovery() -> None:
    result = build_assembly_user_failure(
        blockers=[{"code": "MATE_TOPOLOGY_MISMATCH"}],
        stage="natural_language_preview",
    )

    assert result["reasonCode"] == "INSTALLATION_TOPOLOGY_INCOMPATIBLE"
    assert result["cadLaunchDecision"] == "fail_closed_before_cad"
    assert "槽位" in "".join(result["suggestedActions"])


def test_spacing_mismatch_is_not_reported_as_generic_collision() -> None:
    result = build_assembly_user_failure(
        blockers=[
            {
                "code": "LOCATING_FEATURE_SPACING_MISMATCH",
                "sourceDistanceMeters": 0.2,
                "targetDistanceMeters": 0.022,
            }
        ]
    )

    assert result["reasonCode"] == "LOCATING_PATTERN_MISMATCH"
    assert result["category"] == "mechanical_incompatibility"
    assert result["collisionOrBrepRequiredForRetry"] is False


def test_missing_target_slot_and_missing_release_are_distinct() -> None:
    missing_slot = build_assembly_user_failure(
        blockers=[{"code": "TARGET_SLOT_PORT_OR_TEMPLATE_MISSING"}]
    )
    missing_release = build_assembly_user_failure(
        blockers=[{"code": "TEMPLATE_NOT_AUTHORIZED_BY_BOUND_RELEASE"}]
    )

    assert missing_slot["reasonCode"] == "TARGET_SLOT_NOT_REGISTERED"
    assert missing_release["reasonCode"] == "DRIVING_RELATION_NOT_AUTHORIZED"
    assert missing_slot["retryableAfter"] != missing_release["retryableAfter"]


def test_compatible_but_unpublished_candidate_has_release_action() -> None:
    explanation = explain_candidate_matrix_row(
        {
            "status": "ready_for_effective_graph_composition",
            "blockers": [],
        }
    )

    assert explanation is not None
    assert explanation["reasonCode"] == "DRIVING_RELATION_NOT_PUBLISHED"
    assert "发布" in explanation["summary"]


def test_released_candidate_has_no_failure_explanation() -> None:
    assert (
        explain_candidate_matrix_row(
            {"status": "released_direct_execution", "blockers": []}
        )
        is None
    )
