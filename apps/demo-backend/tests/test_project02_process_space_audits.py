from __future__ import annotations

import unittest

from demo_backend.project02_service_access import build_project02_service_access_audit
from demo_backend.project02_valve_reach import (
    REQUIRED_REACH_DIAGNOSTICS,
    build_project02_valve_reach_audit,
)


class Project02ProcessSpaceAuditTests(unittest.TestCase):
    def test_service_access_requires_every_generated_clearance(self) -> None:
        component = "FL9A24D062A500.001-1"
        request = {
            "moduleSemantics": {
                component: {
                    "parameters": {
                        "serviceAccessLaneRequired": True,
                        "protectedSpaceBoxesLocal": [
                            {"id": "lane", "hardClearanceWith": ["other"]}
                        ],
                    }
                },
                "FL9A24D062A700.001-1": {"parameters": {}},
                "FL9A24D062A300.001-1": {"parameters": {}},
            }
        }
        preview = {
            "metrics": {"hardFeasible": True},
            "modules": [{"componentName": component, "protectedSpaces": [{"id": "lane"}]}],
            "diagnostics": [
                {"id": f"protected-space-{component}-lane-other", "success": True}
            ],
        }
        report = build_project02_service_access_audit(request, preview)
        self.assertFalse(report["success"])
        self.assertTrue(report["modules"][0]["passed"])

    def test_valve_reach_accepts_exact_common_intersection_and_all_checks(self) -> None:
        request = {
            "moduleSemantics": {
                "FL9A24D062A100.001-1": {
                    "regions": {
                        "leftValveReach": {"minU": 0, "minV": 0, "maxU": 2, "maxV": 2},
                        "rightValveReach": {"minU": 1, "minV": -1, "maxU": 3, "maxV": 1},
                        "dualValveReach": {"minU": 1, "minV": 0, "maxU": 2, "maxV": 1},
                    },
                    "parameters": {"estimatedValveHeadSpacingMeters": 0.09},
                }
            }
        }
        preview = {
            "metrics": {"hardFeasible": True},
            "diagnostics": [
                {"id": diagnostic_id, "success": True}
                for diagnostic_id in REQUIRED_REACH_DIAGNOSTICS
            ],
        }
        report = build_project02_valve_reach_audit(request, preview)
        self.assertTrue(report["success"])
        self.assertTrue(report["commonIntersectionMatches"])


if __name__ == "__main__":
    unittest.main()
