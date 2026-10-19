from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_project02_priority_brep_gate.py"
SPEC = importlib.util.spec_from_file_location("run_project02_priority_brep_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_pair_acceptance_prefers_explicit_prototype_baseline_decision() -> None:
    assert MODULE.pair_acceptance_passed(
        {
            "hasInterference": True,
            "exactCheckComplete": True,
            "acceptance": {
                "policy": "noNewInterferenceOverAcceptedBaseline",
                "accepted": True,
            },
        }
    )


def test_pair_acceptance_rejects_explicit_failed_decision() -> None:
    assert not MODULE.pair_acceptance_passed(
        {
            "hasInterference": False,
            "exactCheckComplete": True,
            "acceptance": {"policy": "zeroInterference", "accepted": False},
        }
    )


def test_pair_acceptance_keeps_legacy_zero_interference_compatibility() -> None:
    assert MODULE.pair_acceptance_passed(
        {
            "HasInterference": False,
            "ExactCheckComplete": True,
            "FailedBodyPairCount": 0,
        }
    )
    assert not MODULE.pair_acceptance_passed(
        {
            "HasInterference": True,
            "ExactCheckComplete": True,
            "FailedBodyPairCount": 0,
        }
    )
