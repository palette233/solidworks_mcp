from __future__ import annotations

import unittest

from demo_backend.project03_valve_reach import infer_project03_valve_reach


def _body(name: str, path: str, bounds: list[float]) -> dict:
    return {"Component": {"Name": name, "Path": path}, "BodyIndex": 0, "BoundingBoxWorld": bounds}


class Project03ValveReachTests(unittest.TestCase):
    def test_project03_scale_geometry_forms_common_reach(self) -> None:
        capture = {"captures": [
            {"TopLevelComponent": {"Name": "AB00"}, "CoverageComplete": True, "Bodies": [
                _body("AB00/x1", r"C:\24D063电气-FL201AR-00057.SLDPRT", [-0.5, 0, 0.1, 0.5, 0.01, 0.11]),
                _body("AB00/x2", r"C:\24D063电气-FL201AR-00057.SLDPRT", [-0.5, 0, 0.8, 0.5, 0.01, 0.81]),
                _body("AB00/u", r"C:\24D063-TC-SLM160-D01-T7509A-800L-TH10-T-GP3(2).SLDPRT", [0, 0, 0, 0.01, 0.01, 0.9]),
            ]},
            {"TopLevelComponent": {"Name": "AC00"}, "CoverageComplete": True, "Bodies": [
                _body("AC00/AC20/valve", r"C:\24D063电气-FL237AA-00012.SLDPRT", [-0.1, 0.1, 0.1, 0.1, 0.4, 0.2]),
                _body("AC00/AC30/valve", r"C:\24D063电气-FL237AA-00012.SLDPRT", [-0.1, 0.1, 0.23, 0.1, 0.4, 0.33]),
            ]},
        ]}
        geometry = {"transportInstallationInterface": {"originWorldMeters": [0, 0, 0], "flowAxisWorld": [0, 0, 1], "transverseAxisWorld": [1, 0, 0], "upAxisWorld": [0, 1, 0]}}
        work = {"workPositions": [{"stableId": "wp", "installationFramePointMeters": {"u": 0.5, "v": 0.0}}]}
        services = {"servicePorts": [{"id": "service", "capability": "cleaning", "installationFrameMeters": {"u": 0.3, "v": 0.4}}]}
        result = infer_project03_valve_reach(capture, geometry, work, services)
        self.assertAlmostEqual(result["valvePair"]["spacingAlongFlowMeters"], 0.13)
        self.assertAlmostEqual(result["commonReachInstallationFrameMeters"]["widthU"], 0.77)
        self.assertAlmostEqual(result["commonReachInstallationFrameMeters"]["widthV"], 1.0)
        self.assertEqual(result["requiredTargetCount"], 2)
        self.assertTrue(result["allRequiredTargetsInsideCommonReach"])
        self.assertFalse(result["pptNominalTravelMeters"]["usedAsCadReachLimit"])


if __name__ == "__main__":
    unittest.main()
