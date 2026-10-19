import importlib.util
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_nonanchor_checkpoint_graph.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_nonanchor_graph", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_f000_nonanchor_graph_removes_only_case_pose_dependency():
    module = _module()
    source = module._read(module.SUPPORTED["F000"])
    result = module.build_nonanchor_graph(source, "F000")

    assert result["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert result["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert result["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert result["NonAnchorCheckpointExperiment"]["caseAnchorsRemoved"] is True
    assert result["NonAnchorCheckpointExperiment"]["activeMateCount"] == 3
    assert {
        row["ModuleToken"] for row in result["Modules"]
    } == {"A000", "F000"}


def test_nonanchor_graph_rejects_already_unanchored_source():
    module = _module()
    source = module._read(module.SUPPORTED["F000"])
    source["EditPolicy"]["caseAnchoredModuleTokens"] = []

    with pytest.raises(ValueError, match="源有效图未声明"):
        module.build_nonanchor_graph(source, "F000")


def test_k000_nonanchor_graph_keeps_three_source_mates_and_removes_case_anchor():
    module = _module()
    source = module._read(module.SUPPORTED["K000"])
    result = module.build_nonanchor_graph(source, "K000")

    assert result["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert result["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert result["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert result["NonAnchorCheckpointExperiment"]["activeMateCount"] == 3
    assert {row["MateName"] for row in result["Mates"]} == {
        "重合4",
        "平行2",
        "同心5",
    }
    assert {row["ModuleToken"] for row in result["Modules"]} == {
        "A000",
        "K000",
    }


def test_b000_nonanchor_graph_preserves_flexible_component_semantics():
    module = _module()
    source = module._read(module.SUPPORTED["B000"])
    result = module.build_nonanchor_graph(source, "B000")

    assert result["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert result["EditPolicy"]["initialPlacementMode"] == "deterministic"
    target = next(row for row in result["Modules"] if row["ModuleToken"] == "B000")
    assert target["SolvingStateName"] == "swComponentFlexibleSolving"
    assert {row["MateName"] for row in result["Mates"]} == {
        "重合37",
        "同心1",
        "平行1",
    }
