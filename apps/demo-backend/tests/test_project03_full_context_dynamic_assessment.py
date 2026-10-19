from __future__ import annotations

from demo_backend.project03_full_context_dynamic_assessment import (
    assess_against_prototype_baseline,
    leaf_source_pair_multiset,
)


def result(*pairs: tuple[str, str], exact: bool = True, failed: int = 0) -> dict:
    return {
        "ExactCheckComplete": exact,
        "FailedBodyPairCount": failed,
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Path": f"C:/cad/{first}"},
                "SecondComponent": {"Path": f"C:/cad/{second}"},
            }
            for first, second in pairs
        ],
    }


def test_leaf_identity_is_orientation_independent_and_preserves_multiplicity() -> None:
    identities = leaf_source_pair_multiset(result(("A.SLDPRT", "B.SLDPRT"), ("b.sldprt", "a.sldprt")))
    assert identities[("a.sldprt", "b.sldprt")] == 2


def test_baseline_reproduction_requires_equal_multiset() -> None:
    baseline = result(("a.sldprt", "b.sldprt"), ("a.sldprt", "b.sldprt"))
    exact = assess_against_prototype_baseline(baseline, baseline, require_exact_baseline=True)
    missing = assess_against_prototype_baseline(
        result(("a.sldprt", "b.sldprt")), baseline, require_exact_baseline=True
    )
    assert exact["status"] == "PASSED_EXACT_SELECTED_BASELINE_REPRODUCTION"
    assert missing["status"] == "FAILED_FULL_CONTEXT_BASELINE_GATE"


def test_later_state_allows_only_baseline_subset_and_rejects_new_pair() -> None:
    baseline = result(("a.sldprt", "b.sldprt"), ("c.sldprt", "d.sldprt"))
    subset = assess_against_prototype_baseline(
        result(("a.sldprt", "b.sldprt")), baseline, require_exact_baseline=False
    )
    added = assess_against_prototype_baseline(
        result(("a.sldprt", "b.sldprt"), ("x.sldprt", "y.sldprt")),
        baseline,
        require_exact_baseline=False,
    )
    assert subset["passed"] is True
    assert added["passed"] is False
    assert added["newLeafSourcePairs"]
