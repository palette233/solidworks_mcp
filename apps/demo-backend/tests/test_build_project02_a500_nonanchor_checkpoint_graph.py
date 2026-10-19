from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a500_nonanchor_checkpoint_graph.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a500_nonanchor_checkpoint_graph", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a500_nonanchor_graph_is_scoped_and_statically_closed() -> None:
    graph, dof = MODULE.build_graph(MODULE._read(MODULE.SOURCE))
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "A500"]
    assert [row["MateName"] for row in graph["Mates"]] == [
        "重合13",
        "宽度4",
        "距离27",
    ]
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert graph["BaseGraphPolicy"]["moduleTokens"] == ["A600"]
    assert graph["SemanticAssemblyPlanAudit"]["validationRelations"] == []
    assert len(
        graph["Project02A500NonAnchorExperiment"]["deferredReadOnlyValidations"]
    ) == 1
    assert dof["closed"] is True
    assert dof["residualDof"] == 0
