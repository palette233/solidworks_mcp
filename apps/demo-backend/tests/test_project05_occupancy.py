from __future__ import annotations

import unittest

from demo_backend.project05_occupancy import (
    LAYOUT_OBJECTS,
    build_project05_occupancy_and_collision_policy,
)


def _pose(code: str, index: int) -> dict:
    x = float(index)
    family = "251093" if code == "N000" else "254098"
    return {
        "Name": f"FL9C{family}{code}.001-1",
        "Path": f"C:/{code}.SLDASM",
        "BoundingBoxWorld": [x, 0.0, 0.0, x + 0.4, 0.4, 0.4],
    }


class Project05OccupancyTests(unittest.TestCase):
    def test_pair_taxonomy_covers_all_36_pairs_with_only_k000_leaf_complete(self) -> None:
        codes = [code for _, members in LAYOUT_OBJECTS for code in members]
        poses = {"components": [_pose(code, index) for index, code in enumerate(codes)]}
        k_capture = {
            "coverageComplete": True,
            "bodies": [{
                "Component": {"HierarchyPath": "FL9C254098KA00.001-1/part-1"},
                "BoundingBoxWorld": [2.0, 0.0, 0.0, 2.2, 0.2, 0.2],
            }],
        }
        geometry = {"installationFrame": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [1, 0, 0],
            "transverseAxisWorld": [0, 1, 0],
            "upAxisWorld": [0, 0, 1],
        }}
        result = build_project05_occupancy_and_collision_policy(poses, geometry, k_capture)
        policy = result["staticCollisionPolicy"]
        self.assertEqual(policy["pairCount"], 36)
        self.assertEqual(policy["coveredPairCount"], 36)
        self.assertTrue(policy["pairPolicyComplete"])
        self.assertEqual(len(policy["strictMultiAabbPairs"]), 15)
        self.assertEqual(len(policy["conditionalBrepPairs"]), 13)
        self.assertEqual(len(policy["installationContactPairs"]), 8)
        self.assertEqual(result["coverage"]["leafCompleteModuleCodes"], ["K000"])
        self.assertFalse(result["solverOccupancyReady"])

    def test_multiple_complete_leaf_captures_replace_top_level_placeholders(self) -> None:
        poses = {"components": []}
        for index, code in enumerate(("A000", "E000", "D000", "K000", "B000", "Z000", "F000", "G000", "M000", "N000", "P000")):
            poses["components"].append({
                "Name": f"FL9C254098{code}.001-1" if code != "N000" else "FL9C251093N000.001-4",
                "Path": f"C:/{code}.SLDASM",
                "BoundingBoxWorld": [index, 0, 0, index + 0.5, 0.5, 0.5],
            })
        geometry = {"installationFrame": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [0, 0, 1],
            "transverseAxisWorld": [1, 0, 0],
            "upAxisWorld": [0, 1, 0],
        }}
        captures = {
            code: {"coverageComplete": True, "bodies": [{
                "Component": {"HierarchyPath": f"{code}-subtree/leaf"},
                "BoundingBoxWorld": [index, 0, 0, index + 0.1, 0.1, 0.1],
            }]}
            for index, code in enumerate(("K000", "F000", "M000", "G000", "N000", "P000"))
        }

        result = build_project05_occupancy_and_collision_policy(
            poses, geometry, world_captures_by_code=captures
        )
        self.assertEqual(
            result["coverage"]["leafCompleteModuleCodes"],
            ["F000", "G000", "K000", "M000", "N000", "P000"],
        )
        self.assertEqual(result["modules"]["G000"]["occupancySource"], "complete-leaf-subtree-union")
        self.assertEqual(len(result["modules"]["G000"]["leafBodyOccupancyBoxes"]), 1)
        self.assertEqual(result["modules"]["A000"]["occupancySource"], "conservative-top-level-aabb")
        self.assertEqual(
            result["staticCollisionPolicy"]["strictPairOccupancyMode"],
            "complete-leaf-body-aabbs",
        )
        self.assertFalse(result["staticCollisionPolicy"]["solverInvokesBrep"])

    def test_incomplete_k000_capture_is_rejected(self) -> None:
        codes = [code for _, members in LAYOUT_OBJECTS for code in members]
        poses = {"components": [_pose(code, index) for index, code in enumerate(codes)]}
        geometry = {"installationFrame": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [1, 0, 0],
            "transverseAxisWorld": [0, 1, 0],
            "upAxisWorld": [0, 0, 1],
        }}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            build_project05_occupancy_and_collision_policy(
                poses, geometry, {"coverageComplete": False, "bodies": []}
            )

    def test_all_required_captures_promote_solver_occupancy_to_ready(self) -> None:
        codes = [code for _, members in LAYOUT_OBJECTS for code in members]
        poses = {"components": [_pose(code, index) for index, code in enumerate(codes)]}
        geometry = {"installationFrame": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [1, 0, 0],
            "transverseAxisWorld": [0, 1, 0],
            "upAxisWorld": [0, 0, 1],
        }}
        captures = {
            code: {"coverageComplete": True, "bodies": [{
                "Component": {"HierarchyPath": f"{code}-subtree/leaf"},
                "BoundingBoxWorld": [float(index), 0, 0, float(index) + 0.1, 0.1, 0.1],
            }]}
            for index, code in enumerate(codes)
        }

        result = build_project05_occupancy_and_collision_policy(
            poses, geometry, world_captures_by_code=captures
        )

        self.assertTrue(result["solverOccupancyReady"])
        self.assertEqual(result["status"], "PROJECT05_COLLISION_POLICY_AND_OCCUPANCY_READY")
        self.assertEqual(result["coverage"]["leafCompleteModuleCodes"], sorted(codes))


if __name__ == "__main__":
    unittest.main()
