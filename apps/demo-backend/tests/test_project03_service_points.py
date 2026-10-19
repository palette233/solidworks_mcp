from __future__ import annotations

import unittest

from demo_backend.project03_service_points import infer_project03_service_points


def _body(name: str, path: str, bounds: list[float]) -> dict:
    return {
        "Component": {"Name": name, "Path": path},
        "BodyIndex": 0,
        "BoundingBoxWorld": bounds,
    }


class Project03ServicePointTests(unittest.TestCase):
    def test_two_cleaning_positions_and_five_other_targets_are_restored(self) -> None:
        root = "FL9A24D063AG00.001-1"
        ag_bodies = [
            _body(f"{root}/FL9A24D063AG10.001-1/FL9A24D063AG12.001-2/a", r"C:\a.SLDPRT", [0, 0, 0.1, 0.04, 0.1, 0.14]),
            _body(f"{root}/FL9A24D063AG10.001-1/FL9A24D063AG13.001-2/b", r"C:\b.SLDPRT", [0, 0, 0.3, 0.04, 0.1, 0.34]),
            _body(f"{root}/FL9A24D063AG20.001-1/cup", r"C:\24D063辅料-FL00002-00468.SLDPRT", [0.1, 0.01, 0.1, 0.15, 0.08, 0.15]),
            _body(f"{root}/FL9A24D063AG30.001-1/plate", r"C:\FL5A24D063AG30002.01.SLDPRT", [0.2, 0.01, 0.1, 0.3, 0.12, 0.2]),
            _body(f"{root}/FL9A24D063AG40.001-1/cup-1", r"C:\24D063辅料-FL00002-00549.SLDPRT", [0.3, 0.01, 0.1, 0.36, 0.09, 0.16]),
            _body(f"{root}/FL9A24D063AG40.001-1/cup-2", r"C:\24D063辅料-FL00002-00549.SLDPRT", [0.3, 0.01, 0.3, 0.36, 0.09, 0.36]),
        ]
        ah_bodies = [
            _body(
                "FL9A24D063AH00.001-1/FL9A24D063AH10.001-1/prism",
                r"C:\24D063电气-FL812AA-00003.SLDPRT",
                [0.4, 0.02, 0.1, 0.43, 0.05, 0.13],
            )
        ]
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": root},
                    "CoverageComplete": True,
                    "LeafComponentCount": 6,
                    "BodyCount": 6,
                    "FailedBodyCount": 0,
                    "Bodies": ag_bodies,
                },
                {
                    "TopLevelComponent": {"Name": "FL9A24D063AH00.001-1"},
                    "CoverageComplete": True,
                    "LeafComponentCount": 1,
                    "BodyCount": 1,
                    "FailedBodyCount": 0,
                    "Bodies": ah_bodies,
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

        result = infer_project03_service_points(capture, geometry)
        ports = {item["id"]: item for item in result["servicePorts"]}
        self.assertEqual(result["combinedServiceModule"]["functionCount"], 4)
        self.assertEqual(result["combinedServiceModule"]["reachTargetCount"], 6)
        self.assertEqual(len(ports), 7)
        self.assertAlmostEqual(ports["cleaning-position-1"]["installationFrameMeters"]["u"], 0.12)
        self.assertAlmostEqual(ports["cleaning-position-2"]["installationFrameMeters"]["u"], 0.32)
        self.assertEqual(ports["calibration-prism-target"]["confidence"], "high")
        self.assertTrue(result["coarseLayoutUsable"])
        self.assertFalse(result["engineeringConfirmed"])


if __name__ == "__main__":
    unittest.main()
