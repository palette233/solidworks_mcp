from __future__ import annotations

import unittest

from demo_backend.project01_occupancy import build_project01_occupancy_and_collision_policy


MODULE_CODES = ("JJ00", "HL00", "SS00", "FF00", "LM00", "ZZ00", "GN00", "BD00", "SM00", "GJ00")


def _pose(code: str, index: int) -> dict:
    offset = float(index)
    return {
        "Name": f"FL9C24N074{code}.001-1",
        "Translation": [offset, 0.0, 0.0],
        "BoundingBoxWorld": [offset, 0.0, 0.0, offset + 0.4, 0.4, 0.4],
    }


def _capture(code: str, index: int) -> dict:
    offset = float(index)
    return {
        "TopLevelComponent": {"Name": f"FL9C24N074{code}.001-1"},
        "CoverageComplete": True,
        "LeafComponentCount": 1,
        "BodyCount": 1,
        "Bodies": [
            {
                "Component": {
                    "Name": f"FL9C24N074{code}.001-1/part-1",
                    "HierarchyPath": f"FL9C24N074{code}.001-1/FL9C24N074{code}.001-1/{code}-part-1",
                    "Path": f"C:\\{code}.SLDPRT",
                },
                "BodyIndex": 0,
                "BoundingBoxWorld": [offset, 0.0, 0.0, offset + 0.2, 0.2, 0.2],
            }
        ],
    }


class Project01OccupancyTests(unittest.TestCase):
    def test_builds_complete_pair_partition_without_requiring_gj_leaf_capture(self) -> None:
        poses = {"components": [_pose(code, index) for index, code in enumerate(MODULE_CODES)]}
        captured_codes = ("SS00", "FF00", "LM00", "ZZ00", "GN00", "BD00", "SM00")
        captures = [{"captures": [_capture(code, MODULE_CODES.index(code))]} for code in captured_codes]
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0, 0, 0],
                "flowAxisWorld": [1, 0, 0],
                "transverseAxisWorld": [0, 1, 0],
                "upAxisWorld": [0, 0, 1],
            },
            "operationSideInference": {"estimatedFacePlaneWorldX": 9.4},
        }
        result = build_project01_occupancy_and_collision_policy(poses, geometry, captures)
        policy = result["staticCollisionPolicy"]
        self.assertEqual(result["status"], "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY")
        self.assertEqual(result["coverage"]["layoutObjectCount"], 8)
        self.assertEqual(policy["pairCount"], 28)
        self.assertEqual(
            policy["coveredPairCount"],
            len(policy["strictMultiAabbPairs"])
            + len(policy["conditionalBrepPairs"])
            + len(policy["installationContactPairs"]),
        )
        self.assertFalse(result["modules"]["GJ00"]["leafCoverageComplete"])
        self.assertEqual(result["modules"]["GJ00"]["occupancySource"], "conservative-top-level-aabb")
        self.assertTrue(result["modules"]["SM00"]["leafCoverageComplete"])
        self.assertFalse(policy["solverInvokesBrep"])


if __name__ == "__main__":
    unittest.main()
