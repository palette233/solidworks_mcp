import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/discover_project05_n000_locators.py"
SPEC = importlib.util.spec_from_file_location("discover_project05_n000_locators", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_real_n000_graph_closes_one_free_slot_translation():
    report, free_graph, closed_graph = MODULE.build_discovery(
        MODULE._read(MODULE.DEFAULT_SOURCE_GRAPH),
        MODULE._read(MODULE.DEFAULT_EFFECTIVE_GRAPH),
        MODULE._read(MODULE.DEFAULT_N000_CATALOG),
    )

    assert report["sourceSlot"]["constraint"] == 0
    assert report["sourceSlot"]["slotDirectionWorld"] == [1.0, 0.0, 0.0]
    assert report["sourceFreeSlotDofAnalysis"]["constraintRank"] == 5
    assert report["sourceFreeSlotDofAnalysis"]["residualDof"] == 1
    assert report["derivedDistanceDofAnalysis"]["constraintRank"] == 6
    assert report["derivedDistanceDofAnalysis"]["residualDof"] == 0
    assert abs(report["derivedDistanceDatum"]["distanceMeters"] - 0.465) < 1e-9
    assert free_graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert closed_graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert closed_graph["EditPolicy"]["sourceMateNamesToSuppress"] == [
        "重合42",
        "平行13",
        "槽口4",
    ]
    assert [mate["MateName"] for mate in closed_graph["Mates"]][-2:] == [
        "槽口4",
        "N000_LOCATING_DISTANCE_X",
    ]
