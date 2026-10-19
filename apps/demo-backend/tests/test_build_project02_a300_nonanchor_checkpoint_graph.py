from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a300_nonanchor_checkpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a300_nonanchor_checkpoint_graph", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a300_nonanchor_graph_is_scoped_closed_and_keeps_half_space_override() -> None:
    graph, dof = MODULE.build_graph(MODULE._read(MODULE.SOURCE))
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "A300"]
    assert [row["MateName"] for row in graph["Mates"]] == MODULE.EXPECTED_MATES
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert graph["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert graph["BaseGraphPolicy"]["fixedAtKnownContextPoses"] is False
    assert graph["SemanticAssemblyPlanAudit"]["mateCreationOverrides"] == [
        {
            "mateName": "距离20",
            "sourceDistanceFlipDimension": True,
            "normalizedAddMate5FlipDimension": False,
            "status": "project02-cad-verified-normalization-pending",
        }
    ]
    audit = graph["Project02A300NonAnchorExperiment"]
    assert audit["removedCaseAnchoredModuleTokens"] == ["A300"]
    assert audit["distanceHalfSpacePolicy"] == (
        "preserve_explicit_cad_verified_creation_override"
    )
    assert dof["closed"] is True
    assert dof["residualDof"] == 0
