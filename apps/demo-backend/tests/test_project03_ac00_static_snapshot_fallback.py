from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_static_snapshot_fallback.py"
SPEC = importlib.util.spec_from_file_location("ac00_fallback", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_diagnostic_fallback_removes_drivers_and_keeps_explicit_anchor() -> None:
    source = {
        "Mates": [{"MateName": "重合26"}],
        "InterModuleMateCount": 1,
        "Modules": [
            {
                "ModuleToken": "FL9A24D063AC00",
                "SolvingState": 1,
                "SolvingStateName": "swComponentFlexibleSolving",
            }
        ],
        "EditPolicy": {"caseAnchoredModuleTokens": []},
    }
    result = MODULE.build(source)
    assert result["Mates"] == []
    assert result["InterModuleMateCount"] == 0
    assert result["EditPolicy"]["caseAnchoredModuleTokens"] == [
        "FL9A24D063AC00"
    ]
    assert result["EditPolicy"]["targetLeafPoseAnchors"] == []
    policy = result["SemanticAssemblyPlanAudit"]["staticSnapshotPolicy"]
    assert policy["motionSemanticsPreserved"] is False
    assert policy["requiresEngineerApprovalForProduction"] is True


def test_anchor_selector_keeps_shallow_unstable_assembly() -> None:
    reference = {
        "components": [
            {"relativeHierarchyPath": "@root", "path": "AC00.SLDASM", "transform": [0] * 16},
            {"relativeHierarchyPath": "A-1", "path": "A.SLDASM", "transform": [1] * 16},
            {"relativeHierarchyPath": "A-1/P-1", "path": "P.SLDPRT", "transform": [2] * 16},
        ]
    }
    comparison = {
        "comparisons": [
            {"relativeHierarchyPath": "@root", "stable": True, "presentInReference": True, "presentInCandidate": True, "translationDistanceMeters": 0.0},
            {"relativeHierarchyPath": "A-1", "stable": False, "presentInReference": True, "presentInCandidate": True, "translationDistanceMeters": 0.01},
            {"relativeHierarchyPath": "A-1/P-1", "stable": False, "presentInReference": True, "presentInCandidate": True, "translationDistanceMeters": 0.01},
        ]
    }
    anchors = MODULE.select_pose_anchors(reference, comparison)
    assert [item["relativeLeafHierarchyPath"] for item in anchors] == ["A-1"]


def test_final_fallback_freezes_the_flexible_target_for_static_reopen() -> None:
    source = {
        "Mates": [{"MateName": "重合26"}],
        "InterModuleMateCount": 1,
        "Modules": [
            {
                "ModuleToken": "FL9A24D063AC00",
                "SolvingState": 1,
                "SolvingStateName": "swComponentFlexibleSolving",
            }
        ],
        "EditPolicy": {"caseAnchoredModuleTokens": []},
    }
    reference = {
        "components": [
            {"relativeHierarchyPath": "@root", "path": "AC00.SLDASM", "transform": [0] * 16},
            {"relativeHierarchyPath": "A-1", "path": "A.SLDASM", "transform": [1] * 16},
        ]
    }
    comparison = {
        "comparisons": [
            {"relativeHierarchyPath": "@root", "stable": True, "presentInReference": True, "presentInCandidate": True, "translationDistanceMeters": 0.0},
            {"relativeHierarchyPath": "A-1", "stable": False, "presentInReference": True, "presentInCandidate": True, "translationDistanceMeters": 0.01},
        ]
    }
    result = MODULE.build(source, reference, comparison)
    target = result["Modules"][0]
    assert target["SolvingState"] == 0
    assert target["SolvingStateName"] == "swComponentRigidSolving"
    policy = result["SemanticAssemblyPlanAudit"]["staticSnapshotPolicy"]
    assert policy["sourceSolvingState"] == "swComponentFlexibleSolving"
    assert policy["staticDemoSolvingState"] == "swComponentRigidSolving"
