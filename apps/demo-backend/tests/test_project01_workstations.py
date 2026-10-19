from __future__ import annotations

import unittest

from demo_backend.project01_workstations import infer_project01_work_positions


class Project01WorkstationTests(unittest.TestCase):
    def test_two_carrier_subtrees_become_ordered_work_positions(self) -> None:
        capture = {
            "captures": [{
                "TopLevelComponent": {"Name": "FL9C24N074FF00.001-1"},
                "LeafComponentCount": 2,
                "BodyCount": 2,
                "FailedBodyCount": 0,
                "CoverageComplete": True,
                "Bodies": [
                    {"Component": {"Name": "root/FL9C24N074FF10.001-1/SNAP CARRIER-1/product"}, "BoundingBoxWorld": [-0.1, 0.2, 0.4, 0.1, 0.3, 0.6]},
                    {"Component": {"Name": "root/FL9C24N074FF10.001-2/SNAP CARRIER-1/product"}, "BoundingBoxWorld": [-0.1, 0.2, 0.8, 0.1, 0.3, 1.0]},
                ],
            }]
        }
        geometry = {"transportInstallationInterface": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [0, 0, 1],
            "transverseAxisWorld": [1, 0, 0],
            "upAxisWorld": [0, 1, 0],
        }}
        result = infer_project01_work_positions(capture, geometry)
        self.assertEqual(result["workPositionCount"], 2)
        self.assertEqual(result["workPositions"][0]["stableId"], "workPositionLowU")
        self.assertAlmostEqual(result["workPositions"][0]["installationFramePointMeters"]["u"], 0.5)
        self.assertAlmostEqual(result["workPositions"][1]["installationFramePointMeters"]["u"], 0.9)


if __name__ == "__main__":
    unittest.main()
