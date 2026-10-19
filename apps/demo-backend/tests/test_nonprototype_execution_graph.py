import pytest

from demo_backend.nonprototype_execution_graph import (
    NonprototypeExecutionGraphError,
    prepare_nonprototype_execution_graph,
)


def _graph():
    return {
        "Modules": [
            {"ModuleToken": "BASE", "SourceTransform": [1] * 16},
            {"ModuleToken": "TARGET", "SourceTransform": [2] * 16},
        ],
        "Mates": [{"MateName": "coincident"}],
        "EditPolicy": {
            "initialPlacementMode": "source",
            "fixedModuleTokens": ["BASE", "TARGET"],
            "caseAnchoredModuleTokens": ["TARGET"],
            "targetLeafPoseAnchors": [{"relativeLeafHierarchyPath": "child"}],
        },
    }


def test_preparation_removes_only_target_pose_shortcuts():
    source = _graph()
    prepared = prepare_nonprototype_execution_graph(
        source, target_module_token="target"
    )

    assert prepared["EditPolicy"] == {
        "initialPlacementMode": "deterministic",
        "fixedModuleTokens": ["BASE"],
        "caseAnchoredModuleTokens": [],
        "targetLeafPoseAnchors": [],
        "sourceGraphImmutable": True,
    }
    assert prepared["Mates"] == source["Mates"]
    assert prepared["Modules"] == source["Modules"]
    assert source["EditPolicy"]["targetLeafPoseAnchors"]
    audit = prepared["NonprototypePreparation"]
    assert audit["removedTargetLeafPoseAnchorCount"] == 1
    assert audit["removedCaseAnchorTokens"] == ["TARGET"]
    assert audit["removedTargetFixedTokens"] == ["TARGET"]
    assert audit["mechanicalMateSetModified"] is False


def test_preparation_fails_when_target_is_absent():
    with pytest.raises(NonprototypeExecutionGraphError, match="执行图缺少目标模组"):
        prepare_nonprototype_execution_graph(_graph(), target_module_token="missing")
