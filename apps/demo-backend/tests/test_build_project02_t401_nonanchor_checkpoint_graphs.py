from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_t401_nonanchor_checkpoint_graphs.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_t401_nonanchor_checkpoint_graphs", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_t401_minimal_derived_locators_close_both_occurrences() -> None:
    first, second, report = MODULE.build_graphs()
    assert [row["MateName"] for row in first["Mates"]] == [
        "重合14",
        "距离10",
        "T401_1_LOCATING_DISTANCE_Z",
    ]
    assert first["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert first["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert first["Project02T401NonAnchorExperiment"]["dofAnalysis"]["closed"] is True
    assert [row["MateName"] for row in second["Mates"]] == [
        "距离28",
        "T401_2_LOCATING_DISTANCE_Y",
        "T401_2_LOCATING_DISTANCE_X",
    ]
    assert second["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert second["Project02T401NonAnchorExperiment"]["dofAnalysis"]["closed"] is True
    assert report["status"] == "ready_for_authoritative_cad_checkpoint"
    for occurrence in report["occurrences"]:
        assert occurrence["closedDofAnalysis"]["constraintRank"] == 6
        assert occurrence["closedDofAnalysis"]["residualDof"] == 0
        assert all(
            row["DerivedEngineeringDatum"]["authority"] == "prototype_estimate"
            for row in occurrence["derivedMates"]
        )
