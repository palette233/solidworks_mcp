from __future__ import annotations

import unittest

from demo_backend.layout_preview import apply_project02_solve_profile
from demo_backend.project02_direct_geometry import (
    apply_direct_geometry_calibration,
    build_direct_geometry_calibration,
    build_direct_major_subassembly_occupancy,
    derive_common_axis_clearance_offsets,
)


class Project02DirectGeometryTests(unittest.TestCase):
    def test_reduced_profile_accepts_unlocked_solver_generated_warm_start(self) -> None:
        request = {
            "sourceIndependentPolicy": {
                "warmStartKind": "previousSolverReplayResult",
                "warmStartReplayResultPath": "prototype.json",
                "warmStartLockedComponents": ["A700"],
                "solverGeneratedWarmStartReplayResultPath": "previous-solver.json",
            },
            "processConstraints": [],
        }
        profiled, metadata = apply_project02_solve_profile(request, "reduced-prototype")
        policy = profiled["sourceIndependentPolicy"]
        self.assertEqual("previous-solver.json", policy["warmStartReplayResultPath"])
        self.assertEqual([], policy["warmStartLockedComponents"])
        self.assertTrue(metadata["removedWarmStart"])
        self.assertTrue(metadata["solverGeneratedWarmStartUsed"])

    def test_builds_anchor_relative_footprint_and_promotes_pair(self) -> None:
        layout = {
            "baseFrame": {
                "origin": [0, 0, 0],
                "uAxis": [1, 0, 0],
                "vAxis": [0, 1, 0],
                "normal": [0, 0, 1],
            },
            "components": [
                {
                    "componentName": "X-A700.001-1",
                    "layout2d": {"x": 3, "y": 4},
                    "constraintPlacement": {"rotationQuarters": 0},
                }
            ],
        }
        poses = [{"Name": "X-A700.001-1", "BoundingBoxWorld": [2, 2, 0, 5, 8, 1]}]
        calibration = build_direct_geometry_calibration(
            layout, poses, component_codes=["X-A700.001-1"], evidence_path="evidence.json"
        )
        self.assertEqual([-1.0, -2.0, 2.0, 4.0], calibration["entries"][0]["layoutFootprintBoundsLocal"])

        request = {
            "moduleSemantics": {
                "A300": {"parameters": {}},
                "X-A700.001-1": {"parameters": {}},
            },
            "staticCollisionPolicy": {
                "strictAabbPairs": [],
                "brepOnAabbOverlapPairs": [["A300", "X-A700.001-1"]],
            },
        }
        updated, metadata = apply_direct_geometry_calibration(
            request, calibration, promote_strict_pairs=[("A300", "X-A700.001-1")]
        )
        self.assertEqual(
            [-1.0, -2.0, 2.0, 4.0],
            updated["moduleSemantics"]["X-A700.001-1"]["parameters"]["layoutFootprintBoundsLocal"],
        )
        self.assertEqual(1, len(updated["staticCollisionPolicy"]["strictAabbPairs"]))
        self.assertEqual([], updated["staticCollisionPolicy"]["brepOnAabbOverlapPairs"])
        self.assertEqual([["A300", "X-A700.001-1"]], metadata["promotedStrictPairs"])

    def test_direct_footprint_is_unrotated_back_to_canonical_frame(self) -> None:
        layout = {
            "baseFrame": {
                "origin": [0, 0, 0],
                "uAxis": [1, 0, 0],
                "vAxis": [0, 1, 0],
                "normal": [0, 0, 1],
            },
            "components": [
                {
                    "componentName": "FL9A24D062A300.001-1",
                    "layout2d": {"x": 10, "y": 20},
                    "constraintPlacement": {"rotationQuarters": 1},
                }
            ],
        }
        # At q1, canonical [u: -2..3, v: -4..1] appears as
        # oriented [u: -1..4, v: -2..3] around the anchor.
        poses = [
            {
                "Name": "FL9A24D062A300.001-1",
                "BoundingBoxWorld": [9, 18, 0, 14, 23, 1],
            }
        ]
        calibration = build_direct_geometry_calibration(
            layout,
            poses,
            component_codes=["A300"],
            evidence_path="direct.json",
        )
        bounds = calibration["entries"][0]["layoutFootprintBoundsLocal"]
        self.assertAlmostEqual(-2.0, bounds[0])
        self.assertAlmostEqual(-4.0, bounds[1])
        self.assertAlmostEqual(3.0, bounds[2])
        self.assertAlmostEqual(1.0, bounds[3])

    def test_unions_direct_leaf_bodies_by_first_child(self) -> None:
        layout = {
            "baseFrame": {
                "origin": [0, 0, 0],
                "uAxis": [1, 0, 0],
                "vAxis": [0, 1, 0],
                "normal": [0, 0, 1],
            },
            "components": [
                {"componentName": "FL9A24D062A700.001-1", "layout2d": {"x": 1, "y": 2}}
            ],
        }
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "FL9A24D062A700.001-1"},
                    "CoverageComplete": True,
                    "Bodies": [
                        {"Component": {"Name": "FL9A24D062A700.001-1/A710-1/p1"}, "BoundingBoxWorld": [1, 2, 0, 2, 3, 1]},
                        {"Component": {"Name": "FL9A24D062A700.001-1/A710-1/p2"}, "BoundingBoxWorld": [2, 3, 0, 4, 5, 2]},
                        {"Component": {"Name": "FL9A24D062A700.001-1/A730-1/p3"}, "BoundingBoxWorld": [0, 1, 0, 1, 2, 1]},
                    ],
                }
            ]
        }
        boxes = build_direct_major_subassembly_occupancy(
            layout, capture, component_code="A700", collision_partner_codes=["A300"]
        )
        self.assertEqual(2, len(boxes))
        a710 = next(item for item in boxes if item["leafComponent"] == "A710-1")
        self.assertEqual([0.0, 0.0, 3.0, 3.0], a710["bounds"])
        self.assertEqual(["A300"], a710["collisionPartnerCodes"])

    def test_derives_four_common_axis_collision_clearance_offsets(self) -> None:
        detail = {
            "InterferingBodyPairs": [
                {
                    "FirstComponent": {"Name": "FL9A24D062A800.001-1/no-box"},
                    "SecondComponent": {"Name": "FL9A24D062A700.001-1/part"},
                    "FirstBoundingBoxWorld": [],
                    "SecondBoundingBoxWorld": [1, 1, 0, 3, 3, 1],
                },
                {
                    "FirstComponent": {"Name": "FL9A24D062A800.001-1/part"},
                    "SecondComponent": {"Name": "FL9A24D062A700.001-1/part"},
                    "FirstBoundingBoxWorld": [0, 0, 0, 2, 2, 1],
                    "SecondBoundingBoxWorld": [1, 1, 0, 3, 3, 1],
                }
            ]
        }
        frame = {"origin": [0, 0, 0], "uAxis": [1, 0, 0], "vAxis": [0, 1, 0]}
        offsets = derive_common_axis_clearance_offsets(
            detail, frame, moving_component_code="A700", clearance_meters=0.1
        )
        self.assertEqual(4, len(offsets))
        self.assertTrue(any(item[0] < -3.0 for item in offsets))
        self.assertTrue(any(item[1] > 1.0 for item in offsets))


if __name__ == "__main__":
    unittest.main()
