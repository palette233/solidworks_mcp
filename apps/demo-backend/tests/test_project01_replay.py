from __future__ import annotations

import json
import copy
import unittest
from pathlib import Path

from demo_backend.project01_replay import build_project01_replay_layout


ROOT = Path(__file__).resolve().parents[3]


class Project01ReplayTests(unittest.TestCase):
    def load(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))

    def test_approved_rank_one_expands_to_all_ten_top_level_modules(self) -> None:
        result = build_project01_replay_layout(
            self.load("demo/layout_previews/project01_selected_solution.json"),
            self.load("demo/layout_previews/project01_module_occupancy.json"),
            self.load("demo/layout_previews/project01_top_level_poses.json"),
        )
        self.assertEqual(len(result["components"]), 10)
        self.assertEqual(len({item["componentName"] for item in result["components"]}), 10)
        self.assertTrue(result["constraintPlan"]["prototypeEquivalent"])
        self.assertLessEqual(result["constraintPlan"]["maximumReplayDeltaMeters"], 1e-9)
        self.assertEqual(
            {item["memberCode"] for item in result["components"]},
            {"JJ00", "LM00", "ZZ00", "FF00", "SS00", "HL00", "GN00", "BD00", "SM00", "GJ00"},
        )

    def test_unapproved_selection_is_rejected(self) -> None:
        selected = self.load("demo/layout_previews/project01_selected_solution.json")
        selected["visualApproval"]["approved"] = False
        with self.assertRaisesRegex(ValueError, "visually approved"):
            build_project01_replay_layout(
                selected,
                self.load("demo/layout_previews/project01_module_occupancy.json"),
                self.load("demo/layout_previews/project01_top_level_poses.json"),
            )

    def test_approved_rank_two_is_preserved_in_replay_document(self) -> None:
        selected = copy.deepcopy(
            self.load("demo/layout_previews/project01_selected_solution.json")
        )
        selected["visualApproval"]["selectedSolutionRank"] = 2
        for component in selected["components"]:
            component["constraintPlacement"]["selectedTopKSolutionRank"] = 2
        result = build_project01_replay_layout(
            selected,
            self.load("demo/layout_previews/project01_module_occupancy.json"),
            self.load("demo/layout_previews/project01_top_level_poses.json"),
        )
        self.assertEqual(2, result["constraintPlan"]["selectedSolutionRank"])
        self.assertTrue(
            all(
                item["constraintPlacement"]["selectedTopKSolutionRank"] == 2
                for item in result["components"]
            )
        )


if __name__ == "__main__":
    unittest.main()
