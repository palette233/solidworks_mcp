from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finalize_project03_full_static_collision_closure import build_closure  # noqa: E402


def exact_result(*pairs: tuple[str, str], complete: bool = True) -> dict:
    return {
        "ExactCheckComplete": complete,
        "FailedBodyPairCount": 0,
        "InterferingBodyPairCount": len(pairs),
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Name": first},
                "SecondComponent": {"Name": second},
            }
            for first, second in pairs
        ],
    }


def test_full_static_closure_accepts_zero_and_prototype_existing_contacts() -> None:
    exact = {
        "componentCount": 3,
        "allTopLevelPairCount": 3,
        "aabbProvenPairCount": 1,
        "exactChecks": [
            {
                "pair": ["A", "B"],
                "candidateIndex": 1,
                "result": exact_result(),
            },
            {
                "pair": ["A", "C"],
                "candidateIndex": 2,
                "result": exact_result(("leaf-1", "leaf-2")),
            },
        ],
        "timing": {"durationSeconds": 12.0},
    }
    baseline = exact_result(("leaf-1", "leaf-2"))

    payload = build_closure(
        broadphase={},
        exact=exact,
        insertion={"success": True, "durationSeconds": 5.0},
        context_comparison={"stable": True, "maximumTransformElementError": 0.0},
        baselines={("A", "C"): (baseline, "baseline.json")},
        candidate_fallbacks={},
        baseline_fallbacks={},
    )

    assert payload["success"] is True
    assert payload["absoluteZeroInterference"] is False
    assert payload["coverage"]["coverageComplete"] is True
    assert payload["collisionResult"]["newInterferenceModulePairCount"] == 0
    assert payload["scopeBoundary"]["dynamicMotionValidated"] is False


def test_full_static_closure_rejects_contact_without_baseline() -> None:
    exact = {
        "componentCount": 2,
        "allTopLevelPairCount": 1,
        "aabbProvenPairCount": 0,
        "exactChecks": [
            {
                "pair": ["A", "B"],
                "candidateIndex": 1,
                "result": exact_result(("leaf-1", "leaf-2")),
            }
        ],
    }

    payload = build_closure(
        broadphase={},
        exact=exact,
        insertion={"success": True},
        context_comparison={"stable": True, "maximumTransformElementError": 0.0},
        baselines={},
        candidate_fallbacks={},
        baseline_fallbacks={},
    )

    assert payload["success"] is False
    assert payload["collisionResult"]["newInterferenceModulePairCount"] == 1


def test_official_confirmation_can_clear_provisional_low_level_new_hit() -> None:
    exact = {
        "componentCount": 2,
        "allTopLevelPairCount": 1,
        "aabbProvenPairCount": 0,
        "exactChecks": [
            {
                "pair": ["A", "B"],
                "candidateIndex": 1,
                "result": exact_result(("leaf-1", "leaf-2")),
            }
        ],
    }
    request = {"requestedLeafComponentPairCount": 1}
    confirmation = {
        "success": True,
        "results": [{"success": True, "hasInterference": False}],
    }

    payload = build_closure(
        broadphase={},
        exact=exact,
        insertion={"success": True},
        context_comparison={"stable": True, "maximumTransformElementError": 0.0},
        baselines={
            ("A", "B"): (exact_result(), "baseline.json"),
        },
        candidate_fallbacks={},
        baseline_fallbacks={},
        candidate_confirmations={
            ("A", "B"): (request, confirmation, "confirmation.json")
        },
    )

    assert payload["success"] is True
    comparison = payload["collisionResult"]["pairComparisons"][0]
    assert comparison["acceptance"]["officialCandidateConfirmation"]["complete"]
    assert comparison["acceptance"]["addedInterferingPairs"] == []
