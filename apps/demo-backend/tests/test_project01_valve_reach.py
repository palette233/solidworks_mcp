from __future__ import annotations

import unittest

from demo_backend.project01_valve_reach import infer_project01_valve_reach


def _body(name: str, path: str, bounds: list[float]) -> dict:
    return {
        "Component": {"Name": name, "Path": path},
        "BodyIndex": 0,
        "BoundingBoxWorld": bounds,
    }


class Project01ValveReachTests(unittest.TestCase):
    def test_axis_scales_and_valve_spacing_form_common_reach(self) -> None:
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "LM00"},
                    "CoverageComplete": True,
                    "Bodies": [
                        _body("LM00/scale-1", r"C:\FL201AR-00057.SLDPRT", [-0.5, 0, 0.1, 0.5, 0.01, 0.11]),
                        _body("LM00/scale-2", r"C:\FL201AR-00057.SLDPRT", [-0.5, 0, 0.8, 0.5, 0.01, 0.81]),
                        _body("LM00/-磁栅尺（TC-U-02）-1", r"C:\-磁栅尺（TC-U-02）.SLDPRT", [0, 0, 0.0, 0.01, 0.01, 0.9]),
                    ],
                },
                {
                    "TopLevelComponent": {"Name": "ZZ00"},
                    "CoverageComplete": True,
                    "Bodies": [
                        _body("ZZ00/ZZ10/valve", r"C:\FL237AA-00012.SLDPRT", [-0.1, 0.1, 0.1, 0.1, 0.4, 0.2]),
                        _body("ZZ00/ZZ20/valve", r"C:\FL237AA-00012.SLDPRT", [-0.1, 0.1, 0.23, 0.1, 0.4, 0.33]),
                    ],
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
        work = {
            "workPositions": [
                {"stableId": "wp1", "installationFramePointMeters": {"u": 0.2, "v": 0}},
                {"stableId": "wp2", "installationFramePointMeters": {"u": 0.7, "v": 0.2}},
            ]
        }
        services = {
            "servicePorts": [
                {"id": "service", "capability": "cleaning", "installationFrameMeters": {"u": 0.5, "v": 0.4}}
            ]
        }
        result = infer_project01_valve_reach(capture, geometry, work, services)
        common = result["commonReachInstallationFrameMeters"]
        self.assertAlmostEqual(result["valvePair"]["spacingAlongFlowMeters"], 0.13)
        self.assertAlmostEqual(common["minU"], 0.065)
        self.assertAlmostEqual(common["maxU"], 0.835)
        self.assertAlmostEqual(common["widthV"], 1.0)
        self.assertTrue(result["allRequiredTargetsInsideCommonReach"])
        self.assertEqual(result["requiredTargetCount"], 3)
        self.assertFalse(result["vendorConfirmed"])


if __name__ == "__main__":
    unittest.main()
