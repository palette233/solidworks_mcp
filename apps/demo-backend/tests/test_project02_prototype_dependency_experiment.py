from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project02_prototype_dependency_experiment import (
    build_project02_prototype_dependency_experiment,
    build_top_level_initial_pose_ablation,
    recommended_dependency_replacement,
    summarize_initial_pose_result,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_project02_dependency_audit_builds_nine_nonmutating_variants(tmp_path):
    report = build_project02_prototype_dependency_experiment(WORKSPACE, tmp_path)

    assert report["summary"]["installationStepCount"] == 9
    assert report["summary"]["topLevelCaseAnchorStepCount"] == 7
    assert report["summary"]["alreadyNonprototypeInitialPoseStepCount"] == 2
    assert report["summary"]["internalPrototypeStateAnchorModuleCount"] == 1
    assert [row["targetModuleToken"] for row in report["steps"]] == [
        "A800",
        "A180",
        "A700",
        "A300",
        "A500",
        "A100",
        "A200",
        "T401",
        "T401",
    ]
    a700 = next(row for row in report["steps"] if row["targetModuleToken"] == "A700")
    assert a700["internalLeafStateAnchorCount"] == 2
    for row in report["steps"]:
        source = Path(row["sourceGraphPath"])
        variant = json.loads(Path(row["ablatedGraphPath"]).read_text("utf-8"))
        assert source.is_file()
        assert variant["EditPolicy"]["caseAnchoredModuleTokens"] == []
        assert variant["EditPolicy"]["initialPlacementMode"] == (
            "deterministic_nonprototype_pose"
        )


def test_top_level_ablation_retains_internal_state_anchors():
    source = {
        "Modules": [{"ModuleToken": "A700"}],
        "EditPolicy": {
            "caseAnchoredModuleTokens": ["A700"],
            "targetLeafPoseAnchors": [{"relativeLeafHierarchyPath": "leaf"}],
        },
    }
    variant = build_top_level_initial_pose_ablation(source, "A700")

    assert source["EditPolicy"]["caseAnchoredModuleTokens"] == ["A700"]
    assert variant["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert len(variant["EditPolicy"]["targetLeafPoseAnchors"]) == 1


def test_initial_pose_summary_requires_full_constraint_when_declared():
    row = {
        "order": 1,
        "targetModuleToken": "A800",
        "contextModuleToken": "A600",
        "constraintRequirement": "fully_constrained",
        "internalLeafStateAnchorCount": 0,
    }
    evidence = {
        "success": True,
        "toolResult": {
            "TargetCaseAnchored": False,
            "IndependentComponentInserted": True,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "ComponentSemanticsMatch": True,
            "TargetConstraintStateAccepted": True,
            "TargetFullyConstrained": False,
            "MateSolveClean": True,
        },
    }
    result = summarize_initial_pose_result(row, evidence)

    assert result["cadTransactionSuccess"] is True
    assert result["nonprototypeInitialPoseGatePassed"] is False


def test_dependency_replacement_distinguishes_redundant_and_missing_datums():
    assert "Remove the redundant" in recommended_dependency_replacement(
        "A200", "A600", True
    )
    assert "One distance relation" in recommended_dependency_replacement(
        "T401", "A200", False
    )
