from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from capture_leaf_interference_details import (  # noqa: E402
    baseline_acceptance,
    batch_exit_code,
    pair_output_path,
)


def result(*pairs: tuple[str, str], complete: bool = True) -> dict:
    return {
        "ExactCheckComplete": complete,
        "FailedBodyPairCount": 0,
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Name": first},
                "SecondComponent": {"Name": second},
            }
            for first, second in pairs
        ],
    }


def result_with_paths(
    first_name: str,
    second_name: str,
    first_path: str,
    second_path: str,
) -> dict:
    return {
        "ExactCheckComplete": True,
        "FailedBodyPairCount": 0,
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Name": first_name, "Path": first_path},
                "SecondComponent": {"Name": second_name, "Path": second_path},
            }
        ],
    }


def failed_result(first: str, second: str, *contacts: tuple[str, str]) -> dict:
    payload = result(*contacts, complete=False)
    payload["FailedBodyPairCount"] = 1
    payload["Failures"] = [
        f"root/{first} <-> copied-root/{second}: Boolean intersection returned error 547"
    ]
    return payload


def clear_fallback(first: str, second: str) -> dict:
    return {
        "success": True,
        "results": [
            {
                "success": True,
                "hasInterference": False,
                "hierarchyPaths": [f"other-parent/{first}", f"root/{second}"],
            }
        ],
    }


def interfering_fallback(first: str, second: str) -> dict:
    return {
        "success": True,
        "results": [
            {
                "success": True,
                "hasInterference": True,
                "hierarchyPaths": [f"other-parent/{first}", f"root/{second}"],
            }
        ],
    }


class BaselineAcceptanceTests(unittest.TestCase):
    def test_long_pair_evidence_path_uses_stable_compact_name(self):
        output_dir = Path("C:/") / ("nested-directory-" * 8)
        first = "A100_WITH_A150_SLOT0_RIGID_V3-1"
        second = "FL9A24D062A180.001-1"

        first_path = pair_output_path(
            output_dir,
            "FL9A24D062A000_prototype_estimated_rank1_feedback10_20260930",
            first,
            second,
        )
        second_path = pair_output_path(
            output_dir,
            "FL9A24D062A000_prototype_estimated_rank1_feedback10_20260930",
            first,
            second,
        )

        self.assertEqual(first_path, second_path)
        self.assertLessEqual(len(str(first_path)), 240)
        self.assertTrue(first_path.name.startswith("pair_"))

    def test_zero_interference_policy_rejects_any_contact(self):
        self.assertFalse(baseline_acceptance(result(("a", "b")), None)["accepted"])

    def test_baseline_policy_accepts_subset_and_pair_order_change(self):
        baseline = result(("a", "b"), ("c", "d"))
        candidate = result(("b", "a"))

        acceptance = baseline_acceptance(candidate, baseline)

        self.assertTrue(acceptance["accepted"])
        self.assertEqual(acceptance["addedInterferingPairs"], [])
        self.assertEqual(len(acceptance["missingBaselinePairs"]), 1)

    def test_baseline_policy_rejects_new_contact(self):
        baseline = result(("a", "b"))
        candidate = result(("a", "b"), ("x", "y"))

        acceptance = baseline_acceptance(candidate, baseline)

        self.assertFalse(acceptance["accepted"])
        self.assertEqual(acceptance["addedInterferingPairs"], [("x", "y")])

    def test_baseline_policy_ignores_replaced_parent_hierarchy_names(self):
        baseline = result_with_paths(
            "FL9A100-1/FL9A150-1/FL408-1",
            "FL9A600-1/Cover-10",
            r"C:\Models\FL408.SLDPRT",
            r"C:\Models\Cover.SLDPRT",
        )
        candidate = result_with_paths(
            "A100_COPY-1/A150_COPY-1/FL408-1",
            "FL9A600-1/Cover-10",
            r"C:\Models\FL408.SLDPRT",
            r"C:\Models\Cover.SLDPRT",
        )

        acceptance = baseline_acceptance(candidate, baseline)

        self.assertTrue(acceptance["accepted"])
        self.assertEqual(acceptance["addedInterferingPairs"], [])

    def test_official_fallback_closes_same_failed_pair_on_candidate_and_baseline(self):
        baseline = failed_result("FL209-1", "LJ56-1", ("a", "b"))
        candidate = failed_result("FL209-1", "LJ56-1", ("b", "a"))

        acceptance = baseline_acceptance(
            candidate,
            baseline,
            candidate_fallback=clear_fallback("FL209-1", "LJ56-1"),
            baseline_fallback=clear_fallback("LJ56-1", "FL209-1"),
        )

        self.assertTrue(acceptance["accepted"])
        self.assertEqual(
            acceptance["policy"],
            "noNewInterferenceOverAcceptedBaselineWithOfficialFallback",
        )
        self.assertTrue(acceptance["effectiveExactCheckComplete"])
        self.assertTrue(acceptance["baselineEffectiveExactCheckComplete"])

    def test_fallback_rejects_uncovered_failed_pair(self):
        exact = failed_result("FL209-1", "LJ56-1")

        acceptance = baseline_acceptance(
            exact,
            None,
            candidate_fallback=clear_fallback("different-1", "pair-1"),
        )

        self.assertFalse(acceptance["accepted"])
        self.assertFalse(acceptance["effectiveExactCheckComplete"])

    def test_baseline_positive_fallback_covers_candidate_exact_contact(self):
        baseline = failed_result("FL209-1", "Bracket-4")
        candidate = result(("copy/FL209-1", "copy/Bracket-4"))

        acceptance = baseline_acceptance(
            candidate,
            baseline,
            baseline_fallback=interfering_fallback("Bracket-4", "FL209-1"),
        )

        self.assertTrue(acceptance["accepted"])
        self.assertTrue(acceptance["baselineEffectiveExactCheckComplete"])
        self.assertEqual(acceptance["addedInterferingPairs"], [])
        self.assertEqual(
            acceptance["baselineFailureFallback"]["fallbackInterferingPairCount"],
            1,
        )

    def test_candidate_positive_fallback_is_rejected_without_baseline_contact(self):
        candidate = failed_result("FL209-1", "Bracket-4")

        acceptance = baseline_acceptance(
            candidate,
            None,
            candidate_fallback=interfering_fallback("FL209-1", "Bracket-4"),
        )

        self.assertFalse(acceptance["accepted"])
        self.assertTrue(acceptance["effectiveExactCheckComplete"])
        self.assertEqual(len(acceptance["candidateFallbackInterferingPairs"]), 1)

    def test_batch_exit_code_matches_zero_interference_gate(self):
        self.assertEqual(batch_exit_code({"hardFailureCount": 0}), 0)
        self.assertEqual(batch_exit_code({"hardFailureCount": 1}), 2)


if __name__ == "__main__":
    unittest.main()
