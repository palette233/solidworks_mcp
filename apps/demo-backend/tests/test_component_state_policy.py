from demo_backend.component_state_policy import evaluate_component_state_policy


def graph(target_state, anchors=None):
    return {
        "Modules": [
            {"ModuleToken": "A700", "SolvingState": target_state},
            {"ModuleToken": "A600", "SolvingState": 1},
        ],
        "EditPolicy": {"targetLeafPoseAnchors": anchors or []},
    }


def test_direct_edit_preserves_flexible_target_without_reinsert_anchor():
    result = evaluate_component_state_policy(
        graph(2), "A700", execution_mode="direct_existing_component_mate_edit"
    )
    assert result["status"] == "ready"
    assert result["requiresParentContextPreservation"] is True
    assert result["requiresSubtreeFingerprintVerification"] is True


def test_flexible_reinsert_without_internal_state_is_blocked():
    result = evaluate_component_state_policy(
        graph(2), "A700", execution_mode="context_incremental_insert"
    )
    assert result["status"] == "blocked"
    assert result["requiresTargetLeafPoseAnchors"] is True


def test_flexible_reinsert_with_anchor_is_ready():
    result = evaluate_component_state_policy(
        graph(2, [{"relativeLeafHierarchyPath": "A730-1", "transform": [0] * 16}]),
        "A700",
        execution_mode="context_incremental_insert",
    )
    assert result["status"] == "ready"


def test_rigid_target_needs_no_internal_anchor():
    result = evaluate_component_state_policy(
        graph(1), "A700", execution_mode="context_incremental_insert"
    )
    assert result["status"] == "ready"
    assert result["requiresTargetLeafPoseAnchors"] is False
