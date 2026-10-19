from __future__ import annotations

import unittest

from demo_backend.layout_preview import LayoutPreviewError, _materialize_solution
from demo_backend.project02_ablation_cad import materialize_ablation_cad_layout


def baseline() -> dict:
    return {
        "baseFrame": {"normal": [0.0, 0.0, 1.0]},
        "components": [
            {
                "componentName": "A700",
                "layout2d": {"x": 0.0, "y": 0.0, "thetaDegrees": 0.0},
                "projectedFootprint": {},
                "constraintPlacement": {"rotationQuarters": 0},
                "targetXAxisWorld": [1.0, 0.0, 0.0],
                "targetYAxisWorld": [0.0, 1.0, 0.0],
                "targetZAxisWorld": [0.0, 0.0, 1.0],
            }
        ],
        "constraintPlan": {},
    }


def selected() -> dict:
    return {
        "rank": 1,
        "score": 1.0,
        "placements": [
            {
                "componentName": "A700",
                "x": 0.1,
                "y": 0.2,
                "thetaDegrees": 90.0,
                "rotationQuarters": 1,
                "bounds": [0.0, 0.0, 1.0, 1.0],
            }
        ],
    }


class Project02AblationCadTests(unittest.TestCase):
    def test_default_materialization_still_rejects_orientation_change(self):
        with self.assertRaises(LayoutPreviewError):
            _materialize_solution(baseline(), selected())

    def test_orientation_change_rotates_world_axes_about_installation_normal(self):
        result = _materialize_solution(
            baseline(), selected(), allow_orientation_change=True
        )
        component = result["components"][0]
        self.assertAlmostEqual(component["targetXAxisWorld"][0], 0.0, places=8)
        self.assertAlmostEqual(component["targetXAxisWorld"][1], 1.0, places=8)
        self.assertAlmostEqual(component["targetYAxisWorld"][0], -1.0, places=8)
        self.assertAlmostEqual(component["targetYAxisWorld"][1], 0.0, places=8)
        self.assertTrue(
            result["constraintPlan"]["selectedTopKSolution"]["orientationChanged"]
        )

    def test_ablation_materialization_requires_explicit_authorization_note(self):
        preview = {
            "metrics": {"hardFeasible": True},
            "solutions": [
                {
                    "rank": 1,
                    "score": 1.0,
                    "modules": [
                        {
                            "componentName": "A700",
                            "center": [0.1, 0.2],
                            "bounds": [0.0, 0.0, 1.0, 1.0],
                            "thetaDegrees": 90.0,
                            "rotationQuarters": 1,
                        }
                    ],
                }
            ],
        }
        with self.assertRaises(ValueError):
            materialize_ablation_cad_layout(
                baseline(), preview, variant="C", authorization_note=""
            )

    def test_feedback_variant_can_be_materialized_after_visual_authorization(self):
        preview = {
            "generatedAt": "2026-09-08T00:00:00+00:00",
            "metrics": {"hardFeasible": True},
            "solutions": [
                {
                    "rank": 1,
                    "score": 1.0,
                    "modules": [
                        {
                            "componentName": "A700",
                            "center": [0.1, 0.2],
                            "bounds": [0.0, 0.0, 1.0, 1.0],
                            "thetaDegrees": 0.0,
                            "rotationQuarters": 0,
                        }
                    ],
                }
            ],
        }
        result = materialize_ablation_cad_layout(
            baseline(),
            preview,
            variant="F",
            authorization_note="visual review passed",
        )
        self.assertEqual(
            result["constraintPlan"]["dependencyAblationCadExecution"]["variant"],
            "F",
        )
        self.assertTrue(result["visualApproval"]["approved"])

    def test_numbered_collision_iteration_variant_can_be_materialized(self):
        preview = {
            "generatedAt": "2026-09-08T00:00:00+00:00",
            "metrics": {"hardFeasible": True},
            "solutions": [
                {
                    "rank": 1,
                    "score": 1.0,
                    "modules": [
                        {
                            "componentName": "A700",
                            "center": [0.01, 0.02],
                            "bounds": [0.0, 0.0, 1.0, 1.0],
                            "thetaDegrees": 0.0,
                            "rotationQuarters": 0,
                        }
                    ],
                }
            ],
        }
        result = materialize_ablation_cad_layout(
            baseline(), preview, variant="H4", authorization_note="automated gate passed"
        )
        self.assertEqual(
            "H4", result["constraintPlan"]["dependencyAblationCadExecution"]["variant"]
        )


if __name__ == "__main__":
    unittest.main()
