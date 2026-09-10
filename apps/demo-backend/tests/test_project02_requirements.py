from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project02_requirements import (
    PROJECT02_MODULE_ORDER,
    confirm_project02_modules,
    recommend_project02_modules,
)


class Project02RequirementRecommendationTests(unittest.TestCase):
    def test_full_process_requirement_recommends_all_eight_modules(self):
        result = recommend_project02_modules(
            "每个载具4个产品，需要双阀环氧胶点胶、扫码追溯、CCD视觉定位、喷嘴校准、清洁、称重和排胶。"
        )

        self.assertEqual(result["requiredModuleCodes"], list(PROJECT02_MODULE_ORDER))
        self.assertTrue(result["coverage"]["complete"])
        self.assertTrue(result["layoutCompatibility"]["compatible"])
        self.assertEqual(result["productCountPerCarrier"], 4)
        self.assertEqual(result["missingInformation"], [])
        a700 = next(item for item in result["modules"] if item["code"] == "A700")
        self.assertTrue(a700["required"])
        self.assertIn("nozzle_cleaning", a700["capabilities"])
        self.assertIn("glue_weighting", a700["capabilities"])

    def test_basic_dispensing_adds_dependencies_and_marks_service_modules_optional(self):
        result = recommend_project02_modules("需要对产品进行自动点胶。")

        self.assertEqual(set(result["requiredModuleCodes"]), {"A100", "A800", "T401"})
        self.assertEqual(set(result["optionalModuleCodes"]), {"A180", "A200", "A300", "A500", "A700"})
        self.assertFalse(result["layoutCompatibility"]["compatible"])
        capability_sources = {item["id"]: item["source"] for item in result["capabilities"]}
        self.assertEqual(capability_sources["epoxy_dispensing"], "explicit")
        self.assertEqual(capability_sources["product_transport"], "dependency")
        self.assertEqual(capability_sources["glue_supply"], "dependency")

    def test_barcode_requirement_adds_transport_dependency(self):
        result = recommend_project02_modules("只要求载具扫码追溯，不需要CCD。")

        self.assertEqual(set(result["requiredModuleCodes"]), {"A180", "A800"})
        self.assertIn("vision_alignment", {item["id"] for item in result["excludedCapabilities"]})

    def test_unknown_requirement_requests_more_information(self):
        result = recommend_project02_modules("设备需要比较灵活。")

        self.assertEqual(result["requiredModuleCodes"], [])
        self.assertFalse(result["coverage"]["complete"])
        self.assertTrue(result["missingInformation"])

    def test_confirmation_gates_fixed_eight_module_solver(self):
        recommendation = recommend_project02_modules("需要自动点胶。")
        subset = confirm_project02_modules(recommendation, ["A100", "A800", "T401"])
        full = confirm_project02_modules(recommendation, list(PROJECT02_MODULE_ORDER))

        self.assertTrue(subset["accepted"])
        self.assertFalse(subset["layoutSolverReady"])
        self.assertTrue(full["accepted"])
        self.assertTrue(full["layoutSolverReady"])

    def test_persisted_recommendation_and_confirmation_are_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            recommendation = recommend_project02_modules(
                "4个产品点胶、扫码、CCD、校准、清洁、称重和排胶",
                workspace=workspace,
                persist=True,
            )
            confirmation = confirm_project02_modules(
                recommendation,
                list(PROJECT02_MODULE_ORDER),
                workspace=workspace,
                persist=True,
            )

            self.assertEqual(json.loads(Path(recommendation["savedPath"]).read_text(encoding="utf-8"))["projectId"], "project02")
            self.assertTrue(json.loads(Path(confirmation["savedPath"]).read_text(encoding="utf-8"))["layoutSolverReady"])


if __name__ == "__main__":
    unittest.main()
