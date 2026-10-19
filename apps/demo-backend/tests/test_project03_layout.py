from __future__ import annotations

import json
import unittest
from pathlib import Path

from demo_backend.layout_preview import solve_case_preview
from demo_backend.project03_layout import solve_project03_top3


ROOT = Path(__file__).resolve().parents[3]


class Project03LayoutTests(unittest.TestCase):
    def test_real_project03_artifacts_produce_three_feasible_solutions(self) -> None:
        def load(name: str) -> dict:
            return json.loads(
                (ROOT / f"demo/layout_previews/project03_{name}.json").read_text(
                    encoding="utf-8-sig"
                )
            )

        result = solve_project03_top3(
            load("module_occupancy"),
            load("work_positions"),
            load("service_points"),
            load("dual_valve_reach"),
            load("scanner_geometry"),
        )
        plan = result["constraintPlan"]
        self.assertEqual(result["caseId"], "project03")
        self.assertEqual(plan["jointSearch"]["solutionCount"], 3)
        self.assertEqual(plan["jointSearch"]["acceptedCandidateCounts"]["joint"], 92)
        self.assertEqual(plan["staticCollisionPolicy"]["strictAabbPairCount"], 12)
        self.assertEqual(plan["staticCollisionPolicy"]["brepOnAabbOverlapPairCount"], 9)
        self.assertFalse(plan["staticCollisionPolicy"]["solverInvokesBrep"])
        self.assertEqual(plan["caseAnchor"]["componentName"], "FL9A24D063AE00.001-1")

    def test_project03_preview_uses_project_specific_metrics_and_review(self) -> None:
        preview = solve_case_preview(ROOT, "project03", persist=False)
        self.assertEqual(preview["caseId"], "project03")
        self.assertEqual(len(preview["solutions"]), 3)
        self.assertTrue(preview["metrics"]["hardFeasible"])
        self.assertEqual(preview["metrics"]["strictAabbPairCount"], 12)
        self.assertEqual(preview["metrics"]["conditionalBrepPairCount"], 9)
        self.assertEqual(preview["metrics"]["solverBrepCallCount"], 0)
        self.assertIn("项目03顺序求解", {item["title"] for item in preview["reviewItems"]})


if __name__ == "__main__":
    unittest.main()
