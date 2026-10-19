from __future__ import annotations

import unittest

from demo_backend.project01_geometry import build_project01_first_stage_geometry


class Project01GeometryTests(unittest.TestCase):
    def test_recovers_transport_frame_and_operation_side_candidate(self) -> None:
        def endpoint(token: str, center: list[float], normal: list[float] | None = None) -> dict:
            return {"ModuleToken": token, "FaceCenterWorld": center, "FaceNormalWorld": normal, "FaceArea": 1.0}

        graph = {
            "SourceAssemblyPath": "project01.SLDASM",
            "ModuleCount": 10,
            "InterModuleMateCount": 27,
            "MateBundleCount": 10,
            "Mates": [
                {"MateName": "重合4", "MateTypeName": "swMateCOINCIDENT", "ModuleTokens": ["JJ00", "SS00"], "Endpoints": [endpoint("JJ00", [0, 0, 0], [0, -1, 0]), endpoint("SS00", [0, 0, 0], [0, 1, 0])]},
                {"MateName": "同心6", "MateTypeName": "swMateCONCENTRIC", "ModuleTokens": ["JJ00", "SS00"], "Endpoints": [endpoint("JJ00", [0, -0.01, -0.029]), endpoint("SS00", [0, 0.01, -0.029])]},
                {"MateName": "同心7", "MateTypeName": "swMateCONCENTRIC", "ModuleTokens": ["JJ00", "SS00"], "Endpoints": [endpoint("JJ00", [0, -0.01, 0.029]), endpoint("SS00", [0, 0.01, 0.029])]},
            ],
        }
        poses = {"components": [
            {"Name": "FL9C24N074JJ00.001-1", "BoundingBoxWorld": [-1, -1, -1, 1, 1, 1]},
            {"Name": "FL9C24N074SS00.001-1", "BoundingBoxWorld": [-0.5, 0, -0.8, 0.1, 0.2, 0.8]},
            {"Name": "FL9C24N074GN00.001-1", "BoundingBoxWorld": [0.2, 0, -0.2, 0.4, 0.3, 0.2]},
            {"Name": "FL9C24N074BD00.001-1", "BoundingBoxWorld": [0.3, 0, -0.1, 0.5, 0.2, 0.1]},
            {"Name": "FL9C24N074GJ00.001-1", "BoundingBoxWorld": [0.5, 0, -0.2, 0.7, 0.8, 0.2]},
        ]}
        result = build_project01_first_stage_geometry(graph, poses)
        interface = result["transportInstallationInterface"]
        self.assertAlmostEqual(interface["locatingHoleSpacingMeters"], 0.058)
        self.assertEqual(interface["flowAxisWorld"], [0.0, 0.0, 1.0])
        self.assertEqual(interface["upAxisWorld"], [0.0, 1.0, 0.0])
        self.assertEqual(result["operationSideInference"]["candidate"], "+worldX")
        self.assertFalse(result["topologyCorrection"]["ff00DirectlyMatedToSs00"])


if __name__ == "__main__":
    unittest.main()
