from __future__ import annotations

import unittest

from demo_backend.project05_geometry import infer_project05_first_stage_geometry


class Project05GeometryTests(unittest.TestCase):
    def test_installation_frame_is_recovered_from_three_mate_types(self) -> None:
        def endpoint(token: str, center: list[float], normal: list[float]) -> dict:
            return {"ModuleToken": token, "FaceCenterWorld": center, "FaceNormalWorld": normal}

        graph = {
            "SourceAssemblyPath": "project05.SLDASM",
            "ModuleCount": 13,
            "InterModuleMateCount": 31,
            "MateBundleCount": 10,
            "Mates": [
                {"MateTypeName": "swMateCOINCIDENT", "ModuleTokens": ["A000", "D000"], "Endpoints": [endpoint("A000", [0.52, 0.656, 0.0], [0, -1, 0]), endpoint("D000", [0.3165, 0.656, -0.57], [0, 1, 0])]},
                {"MateTypeName": "swMateDISTANCE", "ModuleTokens": ["A000", "D000"], "Distance": 0.312, "Endpoints": [endpoint("D000", [0.312, 0.778, 0.0], [-1, 0, 0]), endpoint("A000", [0.0, 0.595, 0.0], [1, 0, 0])]},
                {"MateTypeName": "swMateWIDTH", "ModuleTokens": ["A000", "D000"], "Endpoints": [endpoint("A000", [0.7, 0.595, -0.7], [0, 0, 1]), endpoint("A000", [0.7, 0.595, 0.7], [0, 0, -1]), endpoint("D000", [0.3155, 0.76, 0.69], [0, 0, -1]), endpoint("D000", [0.3155, 0.76, -0.69], [0, 0, 1])]},
            ],
        }
        poses = {"components": [{"Name": f"module-{index}"} for index in range(13)]}
        result = infer_project05_first_stage_geometry(graph, poses)
        self.assertEqual(result["installationFrame"]["flowAxisWorld"], [0.0, 0.0, 1.0])
        self.assertEqual(result["installationFrame"]["transverseAxisWorld"], [1.0, 0.0, 0.0])
        self.assertEqual(result["installationFrame"]["upAxisWorld"], [0.0, 1.0, 0.0])
        self.assertAlmostEqual(result["installationFrame"]["originWorldMeters"][1], 0.656)
        self.assertAlmostEqual(result["transportInstallationInterface"]["frameToTransportTransverseDistanceMeters"], 0.312)
        self.assertTrue(result["transportInstallationInterface"]["transportCenteredInFrameWidth"])


if __name__ == "__main__":
    unittest.main()
