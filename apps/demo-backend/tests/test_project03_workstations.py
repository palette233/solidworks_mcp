from __future__ import annotations

import unittest

from demo_backend.project03_workstations import infer_project03_work_positions


class Project03WorkstationTests(unittest.TestCase):
    def test_recovers_two_station_centers_between_three_transport_guards(self) -> None:
        def body(name: str, center_u: float, width_u: float = 0.04) -> dict:
            return {
                "Component": {"Name": name},
                "BoundingBoxWorld": [
                    -0.55,
                    -0.05,
                    center_u - width_u / 2,
                    -0.47,
                    0.05,
                    center_u + width_u / 2,
                ],
            }

        ad_bodies = []
        for instance, center in (
            ("FL9A24D063AD10.001-1", -0.05),
            ("FL9A24D063AD10.001-2", 0.35),
        ):
            ad_bodies.append(
                body(
                    f"FL9A24D063AD00.001-1/{instance}/FL9A24D063AD20.001-1/part-1",
                    center,
                )
            )
        ae_bodies = [
            body(f"FL9A24D063AE00.001-1/FL9A24D063AE90.001-{index}/part-1", center)
            for index, center in enumerate((-0.25, 0.15, 0.55), start=1)
        ]
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "FL9A24D063AE00.001-1"},
                    "LeafComponentCount": 3,
                    "BodyCount": 3,
                    "FailedBodyCount": 0,
                    "CoverageComplete": True,
                    "Bodies": ae_bodies,
                },
                {
                    "TopLevelComponent": {"Name": "FL9A24D063AD00.001-1"},
                    "LeafComponentCount": 2,
                    "BodyCount": 2,
                    "FailedBodyCount": 0,
                    "CoverageComplete": True,
                    "Bodies": ad_bodies,
                },
            ]
        }
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0.0, 0.0, 0.0],
                "flowAxisWorld": [0.0, 0.0, 1.0],
                "transverseAxisWorld": [1.0, 0.0, 0.0],
                "upAxisWorld": [0.0, 1.0, 0.0],
            }
        }
        result = infer_project03_work_positions(capture, geometry)
        self.assertTrue(result["coarseLayoutUsable"])
        self.assertEqual(result["workPositionCount"], 2)
        self.assertAlmostEqual(result["centerSeparationMeters"], 0.4)
        self.assertAlmostEqual(
            result["geometricConsistency"]["maximumGuardMidpointDeltaMeters"], 0.0
        )
        self.assertEqual(result["workPositions"][0]["stableId"], "workPositionLowU")
        self.assertEqual(result["workPositions"][1]["stableId"], "workPositionHighU")

    def test_rejects_incomplete_ad_capture(self) -> None:
        with self.assertRaisesRegex(ValueError, "AD00"):
            infer_project03_work_positions(
                {
                    "captures": [
                        {
                            "TopLevelComponent": {"Name": "FL9A24D063AD00.001-1"},
                            "CoverageComplete": False,
                        }
                    ]
                },
                {"transportInstallationInterface": {}},
            )


if __name__ == "__main__":
    unittest.main()
