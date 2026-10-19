from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from demo_backend.static_collision_closure import (
    aabb_separated,
    build_execution_plan,
    component_files_older_than_evidence,
    evidence_is_complete_and_clear,
    priority_for_pair,
    relative_pose_matches,
)


def layout(offset_x: float = 0.0, *, a200_delta: float = 0.0) -> dict:
    return {
        "components": [
            {
                "componentName": "FL9A24D062A100.001-1",
                "layout2d": {"x": offset_x, "y": 0.0, "thetaDegrees": 90.0},
            },
            {
                "componentName": "FL9A24D062A200.001-1",
                "layout2d": {
                    "x": offset_x + 0.3 + a200_delta,
                    "y": -0.8,
                    "thetaDegrees": -90.0,
                },
            },
            {
                "componentName": "FL9A24D062A300.001-1",
                "layout2d": {"x": offset_x + 0.34, "y": 0.07, "thetaDegrees": 180.0},
            },
            {
                "componentName": "FL9A24D062A700.001-1",
                "layout2d": {"x": offset_x + 0.36, "y": -0.07, "thetaDegrees": -90.0},
            },
            {
                "componentName": "FL9A24D062A800.001-1",
                "layout2d": {"x": offset_x + 1.26, "y": -0.41, "thetaDegrees": 90.0},
            },
        ]
    }


class StaticCollisionClosureTests(unittest.TestCase):
    def test_relative_pose_reuse_reads_replay_apply_step(self) -> None:
        replay = {
            "steps": [
                {
                    "tool": "apply_captured_common_base_layout",
                    "payload": {"components": layout()["components"]},
                }
            ]
        }
        self.assertTrue(relative_pose_matches(layout(), replay, "A300", "A700"))

    def test_relative_pose_reuse_ignores_global_translation(self) -> None:
        self.assertTrue(relative_pose_matches(layout(), layout(4.2), "A300", "A700"))

    def test_relative_pose_reuse_rejects_pair_motion(self) -> None:
        self.assertFalse(
            relative_pose_matches(layout(), layout(a200_delta=0.01), "A100", "A200")
        )

    def test_exact_evidence_requires_complete_clear_and_no_failures(self) -> None:
        self.assertTrue(
            evidence_is_complete_and_clear(
                {
                    "ExactCheckComplete": True,
                    "HasInterference": False,
                    "FailedBodyPairCount": 0,
                }
            )
        )
        self.assertFalse(
            evidence_is_complete_and_clear(
                {
                    "ExactCheckComplete": True,
                    "HasInterference": True,
                    "FailedBodyPairCount": 0,
                }
            )
        )

    def test_geometry_must_predate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component = root / "component.SLDASM"
            evidence = root / "evidence.json"
            component.write_text("component", encoding="utf-8")
            time.sleep(0.01)
            evidence.write_text("{}", encoding="utf-8")
            self.assertTrue(component_files_older_than_evidence(evidence, [component]))
            time.sleep(0.01)
            component.write_text("changed", encoding="utf-8")
            self.assertFalse(component_files_older_than_evidence(evidence, [component]))

    def test_inflated_world_aabb_requires_real_gap(self) -> None:
        self.assertTrue(
            aabb_separated(
                [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
                [1.3, 0.0, 0.0, 2.0, 1.0, 1.0],
                0.1,
            )
        )
        self.assertFalse(
            aabb_separated(
                [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
                [1.1, 0.0, 0.0, 2.0, 1.0, 1.0],
                0.1,
            )
        )

    def test_plan_prioritizes_primary_gate_and_reuses_matching_pair(self) -> None:
        names = {
            "A100": "FL9A24D062A100.001-1",
            "A200": "FL9A24D062A200.001-1",
            "A300": "FL9A24D062A300.001-1",
            "A700": "FL9A24D062A700.001-1",
            "A800": "FL9A24D062A800.001-1",
        }
        preview = {
            "staticCollisionPolicy": {
                "strictAabbPairs": [[names["A100"], names["A700"]]],
                "brepOnAabbOverlapPairs": [
                    [names["A100"], names["A200"]],
                    [names["A200"], names["A800"]],
                    [names["A300"], names["A700"]],
                ],
                "installationContactPairs": [],
            },
            "modules": [
                {"componentName": name, "bounds": [0.0, 0.0, 1.0, 1.0]}
                for name in names.values()
            ],
            "diagnostics": [
                {
                    "type": "strictInflatedAabbSeparation",
                    "id": "strict-a100-a700",
                    "firstComponent": names["A100"],
                    "secondComponent": names["A700"],
                    "success": True,
                }
            ],
        }
        plan = build_execution_plan(
            preview=preview,
            current_layout=layout(),
            reusable_evidence=[
                {
                    "codes": ["A300", "A700"],
                    "reusable": True,
                    "evidencePath": "v33-clear.json",
                }
            ],
            world_aabbs_by_component={},
        )
        self.assertEqual(plan["status"], "READY_FOR_PRIORITY_BREP_GATE")
        self.assertEqual(plan["conditionalBrep"]["reusedClearPairCount"], 1)
        self.assertEqual(plan["conditionalBrep"]["pendingPairCount"], 2)
        self.assertEqual(
            plan["conditionalBrep"]["batches"][0]["pairs"][0]["codes"],
            ["A100", "A200"],
        )

    def test_transport_gantry_pair_is_an_early_exact_gate(self) -> None:
        priority, reason = priority_for_pair("A100", "A800")
        self.assertEqual(priority, 1)
        self.assertIn("Transport", reason)


if __name__ == "__main__":
    unittest.main()
