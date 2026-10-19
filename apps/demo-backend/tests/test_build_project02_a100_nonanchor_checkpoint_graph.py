from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a100_nonanchor_checkpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a100_nonanchor_checkpoint_graph", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a100_nonanchor_graph_closes_external_dof_and_preserves_flexibility() -> None:
    graph, dof = MODULE.build_graph(MODULE._read(MODULE.SOURCE))
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "A100"]
    assert [row["MateName"] for row in graph["Mates"]] == MODULE.EXPECTED_MATES
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert graph["BaseGraphPolicy"]["fixedAtKnownContextPoses"] is False
    assert graph["Modules"][1]["SolvingStateName"] == "swComponentFlexibleSolving"
    assert dof["closed"] is True
    assert dof["constraintRank"] == 6
    assert dof["residualDof"] == 0
    experiment = graph["Project02A100NonAnchorExperiment"]
    assert experiment["requiredSolvingState"] == "flexible"
    assert experiment["internalMotionStatePolicy"] == (
        "preserve_source_flexible_state_not_release_authority"
    )
