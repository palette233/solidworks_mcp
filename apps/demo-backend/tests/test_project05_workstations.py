from __future__ import annotations

import unittest

from demo_backend.project05_workstations import infer_project05_work_positions


class Project05WorkstationTests(unittest.TestCase):
    def test_repeated_header_subtrees_become_two_coarse_work_points(self) -> None:
        bodies = []
        for instance, z in ((1, 0.0), (2, 0.415)):
            bodies.append({
                "Component": {"HierarchyPath": f"FL9C254098KA00.001-{instance}/header 点胶位置-1/part-1"},
                "BoundingBoxWorld": [0.39, 0.89, z, 0.49, 0.934, z + 0.07],
            })
        capture = {
            "coverageComplete": True,
            "leafComponentCount": 2,
            "bodyCount": 2,
            "bodies": bodies,
        }
        geometry = {"installationFrame": {
            "originWorldMeters": [0, 0.656, 0],
            "flowAxisWorld": [0, 0, 1],
            "transverseAxisWorld": [1, 0, 0],
            "upAxisWorld": [0, 1, 0],
        }}
        result = infer_project05_work_positions(capture, geometry)
        self.assertTrue(result["coarseLayoutUsable"])
        self.assertAlmostEqual(result["centerSeparationMeters"], 0.415)
        self.assertAlmostEqual(result["workPositions"][0]["installationFramePointMeters"]["v"], 0.44)
        self.assertAlmostEqual(result["workPositions"][0]["installationFramePointMeters"]["normal"], 0.278)

    def test_incomplete_capture_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete"):
            infer_project05_work_positions(
                {"coverageComplete": False, "bodies": []},
                {"installationFrame": {}},
            )


if __name__ == "__main__":
    unittest.main()
