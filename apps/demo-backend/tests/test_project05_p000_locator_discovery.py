import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/discover_project05_p000_locators.py"
SPEC = importlib.util.spec_from_file_location("discover_project05_p000_locators", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_project05_p000_source_slot_and_derived_distance_close_expected_dof():
    report, free_graph, distance_graph = MODULE.build_discovery(
        MODULE._read(MODULE.DEFAULT_SOURCE_GRAPH),
        MODULE._read(MODULE.DEFAULT_EFFECTIVE_GRAPH),
        MODULE._read(MODULE.DEFAULT_P000_CATALOG),
        MODULE._read(MODULE.DEFAULT_A000_CATALOG),
    )

    assert report["sourceSlot"]["constraintName"] == "swSlotMateConstraintOption_Free"
    assert abs(report["sourceSlot"]["slotLengthMeters"] - 0.05) < 1e-9
    assert abs(
        report["sourceSlot"]["signedPinOffsetFromCenterMeters"]
        - 0.00487746473968087
    ) < 1e-9
    assert report["sourceFreeSlotDofAnalysis"]["constraintRank"] == 5
    assert report["sourceFreeSlotDofAnalysis"]["residualDof"] == 1
    assert report["derivedDistanceDofAnalysis"]["constraintRank"] == 6
    assert report["derivedDistanceDofAnalysis"]["residualDof"] == 0
    assert free_graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert distance_graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert distance_graph["Mates"][-1]["MateName"] == "P000_LOCATING_DISTANCE_X"
    assert abs(distance_graph["Mates"][-1]["Distance"] - 0.3451225352602813) < 1e-9
