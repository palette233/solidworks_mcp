from demo_backend.project02_prototype_dynamic_closure import (
    build_closure_report,
    compare_candidate_to_reference,
    recover_reference_layout,
)


IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def test_reference_layout_recovers_bottom_anchor_from_transform():
    source = {
        "baseFrame": {
            "origin": [0, 0, 0],
            "uAxis": [1, 0, 0],
            "vAxis": [0, 1, 0],
        },
        "components": [
            {
                "componentName": "A",
                "sourceTransform": IDENTITY,
                "bottomCenterWorld": [2, 3, 4],
            }
        ],
    }
    moved = IDENTITY.copy()
    moved[9:12] = [10, 20, 30]
    reference = {"components": [{"componentName": "A", "sourceTransform": moved}]}
    assert recover_reference_layout(source, reference)["A"] == [12.0, 23.0]


def test_comparison_requires_replay_when_pose_changed():
    solution = {
        "components": [
            {"componentName": "A", "layout2d": {"x": 1.01, "y": 2.0}}
        ]
    }
    result = compare_candidate_to_reference(solution, {"A": [1.0, 2.0]})
    assert result["changedComponentCount"] == 1
    assert result["cadReplayRequired"] is True


def test_closure_report_keeps_production_release_closed():
    preview = {
        "metrics": {
            "hardFeasible": True,
            "processPassed": 1,
            "processTotal": 1,
            "spatialPassed": 1,
            "spatialTotal": 1,
            "interactionPassed": 1,
            "interactionTotal": 1,
        },
        "solutions": [
            {
                "rank": 1,
                "score": 2,
                "predictedConditionalBrepPairCount": 3,
                "predictedConditionalLeafAabbHitCount": 1,
            }
        ],
    }
    report = build_closure_report(
        {"gate": {"prototypeEstimatedDynamicDemoPassed": True}},
        {"estimatedProfilePassed": True},
        preview,
        {"cadReplayRequired": True},
    )
    assert report["solverHardConstraintsPassed"] is True
    assert report["cadReplayRequired"] is True
    assert report["productionDynamicReleaseAllowed"] is False
