from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from consolidate_incremental_brep_closure import exact_acceptance, pair_signature


class IncrementalBrepClosureTests(unittest.TestCase):
    def test_raw_zero_and_accepted_baseline_are_distinguished(self):
        self.assertEqual(
            exact_acceptance(
                {
                    "exactCheckComplete": True,
                    "hasInterference": False,
                    "failedBodyPairCount": 0,
                }
            ),
            (True, "raw_zero_interference"),
        )
        self.assertEqual(
            exact_acceptance(
                {
                    "exactCheckComplete": True,
                    "hasInterference": True,
                    "failedBodyPairCount": 0,
                    "acceptance": {"accepted": True},
                }
            ),
            (True, "accepted_prototype_baseline_no_new_interference"),
        )

    def test_pair_signature_ignores_common_global_translation(self):
        axes = {
            "XAxis": [1.0, 0.0, 0.0],
            "YAxis": [0.0, 1.0, 0.0],
            "ZAxis": [0.0, 0.0, 1.0],
        }
        first = {**axes, "Translation": [2.0, 3.0, 4.0]}
        second = {**axes, "Translation": [1.0, 1.0, 1.0]}
        moved_first = {**axes, "Translation": [12.0, -2.0, 6.0]}
        moved_second = {**axes, "Translation": [11.0, -4.0, 3.0]}

        self.assertEqual(
            pair_signature(first, second),
            pair_signature(moved_first, moved_second),
        )


if __name__ == "__main__":
    unittest.main()
