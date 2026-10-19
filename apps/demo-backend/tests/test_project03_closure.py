from __future__ import annotations

import json
import unittest
from pathlib import Path

from demo_backend.project03_closure import build_project03_solution_closure


ROOT = Path(__file__).resolve().parents[3]


class Project03ClosureTests(unittest.TestCase):
    def test_real_solution1_closes_without_claiming_zero_interference(self) -> None:
        def load(relative: str) -> dict:
            return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))

        result = build_project03_solution_closure(
            load("demo/layout_previews/project03_solution1_v1_3d_screening.json"),
            load("demo/layout_previews/project03_selected_solution_replay.json"),
            load("demo/interference_project03_solution1_v1/conditional/FL9A24D063A000_project03_solution1_v1_leaf_details_batch.json"),
            [
                load("demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AD00.json"),
                load("demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AI00.json"),
            ],
            load("demo/layout_previews/project03_solution1_v1_reopened_capture.json"),
        )
        self.assertTrue(result["demoClosurePassed"])
        self.assertTrue(result["noNewInterferenceOverPrototype"])
        self.assertFalse(result["zeroInterferenceClaimed"])
        self.assertFalse(result["productionReady"])
        self.assertEqual(result["conditionalExactBrep"]["clearPairCount"], 7)
        self.assertEqual(result["conditionalExactBrep"]["prototypeExistingHitPairCount"], 2)
        self.assertEqual(result["conditionalExactBrep"]["prototypeExistingInterferingBodyPairCount"], 8)
        self.assertEqual(result["conditionalExactBrep"]["newInterferingBodyPairCount"], 0)


if __name__ == "__main__":
    unittest.main()
