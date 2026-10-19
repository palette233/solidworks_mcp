from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a700_nonanchor_checkpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a700_nonanchor_checkpoint_graph", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a700_nonanchor_graph_is_scoped_and_statically_closed() -> None:
    graph, dof = MODULE.build_graph(MODULE._read(MODULE.SOURCE))
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "A700"]
    assert [row["MateName"] for row in graph["Mates"]] == MODULE.EXPECTED_MATES
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert graph["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert graph["BaseGraphPolicy"]["moduleTokens"] == ["A600"]
    assert graph["BaseGraphPolicy"]["fixedAtKnownContextPoses"] is False
    audit = graph["Project02A700NonAnchorExperiment"]
    assert audit["removedCaseAnchoredModuleTokens"] == ["A700"]
    assert audit["removedLeafPoseAnchorCount"] == 2
    assert audit["requiredSolvingState"] == "flexible"
    assert dof["closed"] is True
    assert dof["residualDof"] == 0
