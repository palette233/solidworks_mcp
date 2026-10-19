from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a200_nonanchor_checkpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a200_nonanchor_checkpoint_graph", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a200_nonanchor_graph_defers_only_advanced_slot_static_closure() -> None:
    graph, dof = MODULE.build_graph(MODULE._read(MODULE.SOURCE))
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "A200"]
    assert [row["MateName"] for row in graph["Mates"]] == MODULE.EXPECTED_MATES
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert graph["BaseGraphPolicy"]["fixedAtKnownContextPoses"] is False
    assert {row["mateName"] for row in dof["unsupportedRelations"]} == {
        "槽口1",
        "槽口2",
    }
    assert graph["Project02A200NonAnchorExperiment"]["staticDofDecision"] == (
        "defer_advanced_slot_closure_to_authoritative_cad"
    )
