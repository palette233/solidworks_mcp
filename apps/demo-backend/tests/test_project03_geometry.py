from __future__ import annotations

import unittest

from demo_backend.project03_geometry import build_project03_first_stage_geometry


class Project03GeometryTests(unittest.TestCase):
    def test_recovers_aa00_ae00_interface_and_excludes_loose_parts(self) -> None:
        def endpoint(token: str, center: list[float], normal: list[float] | None = None) -> dict:
            return {"ModuleToken": token, "FaceCenterWorld": center, "FaceNormalWorld": normal, "FaceArea": 1.0}

        graph = {
            "SourceAssemblyPath": "project03.SLDASM",
            "ModuleCount": 10,
            "InterModuleMateCount": 29,
            "MateBundleCount": 9,
            "Mates": [
                {"MateName": "重合28", "MateTypeName": "swMateCOINCIDENT", "ModuleTokens": ["FL9A24D063AA00", "FL9A24D063AE00"], "Endpoints": [endpoint("FL9A24D063AA00", [0, 0, 0], [0, -1, 0]), endpoint("FL9A24D063AE00", [0, 0, 0], [0, 1, 0])]},
                {"MateName": "同心39", "MateTypeName": "swMateCONCENTRIC", "ModuleTokens": ["FL9A24D063AA00", "FL9A24D063AE00"], "Endpoints": [endpoint("FL9A24D063AA00", [0, -0.01, -0.029]), endpoint("FL9A24D063AE00", [0, 0.01, -0.029])]},
                {"MateName": "同心40", "MateTypeName": "swMateCONCENTRIC", "ModuleTokens": ["FL9A24D063AA00", "FL9A24D063AE00"], "Endpoints": [endpoint("FL9A24D063AA00", [0, -0.01, 0.029]), endpoint("FL9A24D063AE00", [0, 0.01, 0.029])]},
            ],
            "MateBundles": [
                {"FirstModuleToken": "FL9A24D063AA00", "SecondModuleToken": f"FL9A24D063{suffix}"}
                for suffix in ("AB00", "AD00", "AE00", "AF00", "AG00", "AH00", "AI00", "AJ00")
            ] + [{"FirstModuleToken": "FL9A24D063AB00", "SecondModuleToken": "FL9A24D063AC00"}],
        }
        components = [
            {"Name": "FL9A24D063AA00.001-1", "BoundingBoxWorld": [-1, -1, -1, 1, 1, 1]},
            {"Name": "FL9A24D063AE00.001-1", "BoundingBoxWorld": [-0.7, 0, -0.8, -0.4, 0.2, 0.8]},
            {"Name": "FL9A24D063AG00.001-1", "BoundingBoxWorld": [-0.2, 0, -0.2, 0.0, 0.3, 0.2]},
            {"Name": "FL9A24D063AH00.001-1", "BoundingBoxWorld": [0.0, 0, -0.1, 0.2, 0.2, 0.1]},
            {"Name": "FL9A24D063AJ00.001-1", "BoundingBoxWorld": [0.4, 0, -0.2, 0.7, 0.8, 0.2]},
        ]
        for suffix in ("AB00", "AC00", "AD00", "AF00", "AI00"):
            components.append({"Name": f"FL9A24D063{suffix}.001-1", "BoundingBoxWorld": [-0.2, 0, -0.2, 0.2, 0.4, 0.2]})
        components.append({"Name": "FL5B24D063AF00003.01-1", "BoundingBoxWorld": [0, 0, 0, 0.1, 0.1, 0.1]})
        result = build_project03_first_stage_geometry(graph, {"components": components})
        self.assertAlmostEqual(result["transportInstallationInterface"]["locatingHoleSpacingMeters"], 0.058)
        self.assertEqual(result["transportInstallationInterface"]["flowAxisWorld"], [0.0, 0.0, 1.0])
        self.assertEqual(result["operationSideInference"]["candidate"], "+worldX")
        self.assertEqual(result["topLevelOccupancy"]["majorModuleCount"], 10)
        self.assertEqual(result["topLevelOccupancy"]["looseAuxiliaryInstanceCount"], 1)
        self.assertTrue(result["topology"]["allIndependentModulesDirectlyMatedToAa00"])
        self.assertFalse(result["topology"]["ad00DirectlyMatedToAe00"])


if __name__ == "__main__":
    unittest.main()
