from __future__ import annotations

import unittest

from demo_backend.project05_local_capture import (
    map_standalone_capture_to_project05_world,
    map_standalone_capture_to_project05_world_instances,
    transform_aabb,
)


class Project05LocalCaptureTests(unittest.TestCase):
    def test_rotated_aabb_is_mapped_by_all_eight_corners(self) -> None:
        pose = {
            "XAxis": [0.0, 1.0, 0.0],
            "YAxis": [-1.0, 0.0, 0.0],
            "ZAxis": [0.0, 0.0, 1.0],
            "Translation": [10.0, 20.0, 30.0],
        }
        self.assertEqual(
            transform_aabb([0.0, 0.0, 0.0, 2.0, 3.0, 4.0], pose),
            [7.0, 20.0, 30.0, 10.0, 22.0, 34.0],
        )

    def test_complete_root_capture_maps_to_unique_top_level_pose(self) -> None:
        capture = {
            "assemblyPath": "K000.SLDASM",
            "captures": [{
                "CoverageComplete": True,
                "LeafComponentCount": 1,
                "Bodies": [{"BoundingBoxWorld": [0, 0, 0, 1, 2, 3]}],
            }],
        }
        poses = {
            "sourceAssemblyPath": "project05.SLDASM",
            "components": [{
                "Name": "FL9C254098K000.001-1",
                "XAxis": [1, 0, 0],
                "YAxis": [0, 1, 0],
                "ZAxis": [0, 0, 1],
                "Translation": [4, 5, 6],
                "BoundingBoxWorld": [4, 5, 6, 5, 7, 9],
            }],
        }
        result = map_standalone_capture_to_project05_world(capture, poses, "K000")
        self.assertEqual(result["bodies"][0]["BoundingBoxWorld"], [4, 5, 6, 5, 7, 9])
        self.assertEqual(result["bodies"][0]["BoundingBoxStandaloneModule"], [0, 0, 0, 1, 2, 3])

    def test_incomplete_capture_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete"):
            map_standalone_capture_to_project05_world(
                {"captures": [{"CoverageComplete": False, "Bodies": []}]},
                {"components": [{
                    "Name": "K000-1",
                    "XAxis": [1, 0, 0], "YAxis": [0, 1, 0], "ZAxis": [0, 0, 1],
                    "Translation": [0, 0, 0],
                    "BoundingBoxWorld": [0, 0, 0, 1, 1, 1],
                }]},
                "K000",
            )

    def test_one_capture_maps_to_two_repeated_instances(self) -> None:
        capture = {
            "assemblyPath": "N000.SLDASM",
            "captures": [{
                "CoverageComplete": True,
                "LeafComponentCount": 1,
                "Bodies": [{"BoundingBoxWorld": [0, 0, 0, 1, 1, 1]}],
            }],
        }
        poses = {
            "sourceAssemblyPath": "project05.SLDASM",
            "components": [
                {
                    "Name": "FL9C251093N000.001-4",
                    "XAxis": [1, 0, 0], "YAxis": [0, 1, 0], "ZAxis": [0, 0, 1],
                    "Translation": [10, 0, 0],
                    "BoundingBoxWorld": [10, 0, 0, 11, 1, 1],
                },
                {
                    "Name": "FL9C251093N000.001-3",
                    "XAxis": [1, 0, 0], "YAxis": [0, 1, 0], "ZAxis": [0, 0, 1],
                    "Translation": [0, 20, 0],
                    "BoundingBoxWorld": [0, 20, 0, 1, 21, 1],
                },
            ],
        }

        result = map_standalone_capture_to_project05_world_instances(capture, poses, "N000")

        self.assertEqual(result["instanceCount"], 2)
        self.assertEqual(result["bodyCount"], 2)
        self.assertEqual(result["instanceNames"], [
            "FL9C251093N000.001-3", "FL9C251093N000.001-4"
        ])
        self.assertEqual(result["bodies"][0]["TopLevelInstanceName"], "FL9C251093N000.001-3")
        self.assertEqual(result["bodies"][0]["BoundingBoxWorld"], [0, 20, 0, 1, 21, 1])
        self.assertEqual(result["bodies"][1]["BoundingBoxWorld"], [10, 0, 0, 11, 1, 1])


if __name__ == "__main__":
    unittest.main()
