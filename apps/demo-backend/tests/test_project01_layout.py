from __future__ import annotations

import json
import unittest
from pathlib import Path

from demo_backend.project01_layout import solve_project01_top3


ROOT = Path(__file__).resolve().parents[3]


class Project01LayoutTests(unittest.TestCase):
    def test_real_project01_artifacts_produce_three_feasible_solutions(self) -> None:
        def load(relative: str) -> dict:
            return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))

        result = solve_project01_top3(
            load("demo/layout_previews/project01_module_occupancy.json"),
            load("demo/layout_previews/project01_work_positions.json"),
            load("demo/layout_previews/project01_service_points.json"),
            load("demo/layout_previews/project01_dual_valve_reach.json"),
            load("demo/layout_previews/project01_scanner_geometry.json"),
        )
        plan = result["constraintPlan"]
        self.assertEqual(plan["jointSearch"]["solutionCount"], 3)
        self.assertEqual(len(result["components"]), 8)
        self.assertTrue(plan["processValidation"]["hardFeasible"])
        self.assertFalse(plan["staticCollisionPolicy"]["solverInvokesBrep"])
        self.assertEqual(plan["staticCollisionPolicy"]["pairCount"], 28)
        self.assertEqual(plan["staticCollisionPolicy"]["strictAabbPairCount"], 12)
        self.assertEqual(plan["staticCollisionPolicy"]["brepOnAabbOverlapPairCount"], 9)
        solutions = plan["jointSearch"]["solutions"]
        baseline = {item["componentName"]: item for item in solutions[0]["placements"]}
        maximum_alternative_shift = max(
            max(
                abs(item["x"] - baseline[item["componentName"]]["x"]),
                abs(item["y"] - baseline[item["componentName"]]["y"]),
            )
            for solution in solutions[1:]
            for item in solution["placements"]
        )
        self.assertGreaterEqual(maximum_alternative_shift, 0.03 - 1e-9)


if __name__ == "__main__":
    unittest.main()
