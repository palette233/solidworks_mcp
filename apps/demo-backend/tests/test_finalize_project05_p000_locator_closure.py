import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/finalize_project05_p000_locator_closure.py"
SPEC = importlib.util.spec_from_file_location("finalize_project05_p000_locator_closure", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_p000_locator_closure_accepts_expected_free_and_closed_cad_outcomes(tmp_path):
    assembly = tmp_path / "result.SLDASM"
    assembly.write_bytes(b"assembly")
    discovery = {
        "sourceFreeSlotDofAnalysis": {"constraintRank": 5, "residualDof": 1},
        "derivedDistanceDofAnalysis": {"constraintRank": 6, "residualDof": 0},
        "derivedDistanceDatum": {"distanceMeters": 0.345122535},
    }
    free_result = {
        "durationSeconds": 5,
        "toolResult": {
            "IndependentComponentInserted": True,
            "CreatedMateCount": 3,
            "ReopenedMateParametersMatch": True,
            "TargetFullyConstrained": False,
        },
    }
    closed_result = {
        "success": True,
        "durationSeconds": 7,
        "toolResult": {
            "IndependentComponentInserted": True,
            "CreatedMateCount": 4,
            "ReopenedMateParametersMatch": True,
            "TargetFullyConstrained": True,
            "TargetCaseAnchored": False,
            "RequestedTargetLeafPoseAnchorCount": 0,
        },
    }

    result = MODULE.build_closure(discovery, free_result, closed_result, assembly)

    assert result["success"] is True
    assert result["status"] == "PROJECT05_P000_NONANCHOR_STATIC_CLOSED"
    assert result["timingSeconds"]["totalCad"] == 12
