from __future__ import annotations

import unittest

from demo_backend.project01_service_points import infer_project01_service_points


def _body(name: str, path: str, bounds: list[float]) -> dict:
    return {
        "Component": {"Name": name, "Path": path},
        "BodyIndex": 0,
        "BoundingBoxWorld": bounds,
    }


class Project01ServicePointTests(unittest.TestCase):
    def test_six_reach_targets_are_restored_from_four_gn_functions_and_bd(self) -> None:
        gn_root = "FL9C24N074GN00.001-1"
        gn_bodies = [
            _body(f"{gn_root}/FL9C24N074GN10.001-1/cleaner", r"C:\cleaner.SLDPRT", [0, 0, 0, 0.2, 0.1, 0.4]),
            _body(f"{gn_root}/FL9C24N074GN20.001-1/cup", r"C:\FL00002-00468.SLDPRT", [0.3, 0.02, 0.1, 0.35, 0.08, 0.15]),
            _body(f"{gn_root}/FL9C24N074FJ00.001-1/cup-1", r"C:\FL00002-00549.SLDPRT", [0.4, 0.01, 0.0, 0.46, 0.09, 0.06]),
            _body(f"{gn_root}/FL9C24N074FJ00.001-1/cup-2", r"C:\FL00002-00549.SLDPRT", [0.4, 0.01, 0.2, 0.46, 0.09, 0.26]),
            _body(f"{gn_root}/FL9C24N074GN30.001-1/bench", r"C:\FL5A24N074GN30002.01.SLDPRT", [0.5, 0.01, 0.1, 0.6, 0.11, 0.2]),
        ]
        bd_bodies = [
            _body("FL9C24N074BD00.001-1/target-low", r"C:\FL5C24N074BD00007.01.SLDPRT", [0.7, 0.02, 0.1, 0.74, 0.05, 0.14]),
            _body("FL9C24N074BD00.001-1/target-high", r"C:\FL5C24N074BD00009.01.SLDPRT", [0.7, 0.08, 0.1, 0.74, 0.1, 0.14]),
        ]
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": gn_root},
                    "CoverageComplete": True,
                    "LeafComponentCount": 5,
                    "BodyCount": 5,
                    "FailedBodyCount": 0,
                    "Bodies": gn_bodies,
                },
                {
                    "TopLevelComponent": {"Name": "FL9C24N074BD00.001-1"},
                    "CoverageComplete": True,
                    "LeafComponentCount": 2,
                    "BodyCount": 2,
                    "FailedBodyCount": 0,
                    "Bodies": bd_bodies,
                },
            ]
        }
        geometry = {
            "transportInstallationInterface": {
                "originWorldMeters": [0, 0, 0],
                "flowAxisWorld": [0, 0, 1],
                "transverseAxisWorld": [1, 0, 0],
                "upAxisWorld": [0, 1, 0],
            }
        }
        result = infer_project01_service_points(capture, geometry)
        ports = {item["id"]: item for item in result["servicePorts"]}
        self.assertEqual(result["combinedServiceModule"]["functionCount"], 4)
        self.assertEqual(result["combinedServiceModule"]["reachTargetCount"], 5)
        self.assertEqual(len(ports), 6)
        for actual, expected in zip(
            ports["weighing-cup"]["worldMeters"], [0.325, 0.08, 0.125]
        ):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(
            ports["glue-drain-cup-1"]["worldMeters"], [0.43, 0.09, 0.03]
        ):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(
            ports["glue-drain-cup-2"]["worldMeters"], [0.43, 0.09, 0.23]
        ):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(
            ports["calibration-prism-target"]["worldMeters"], [0.72, 0.1, 0.12]
        ):
            self.assertAlmostEqual(actual, expected)
        self.assertTrue(result["coarseLayoutUsable"])
        self.assertFalse(result["engineeringConfirmed"])


if __name__ == "__main__":
    unittest.main()
