from __future__ import annotations

import unittest

from demo_backend.project02_engineering_inputs import (
    EngineeringInputError,
    apply_confirmed_project02_engineering_inputs,
)
from demo_backend.project02_robustness import (
    compare_signatures,
    with_scan_tolerance,
    with_service_component_scale,
    with_service_space_scale,
    with_valve_reach_directional_insets,
    with_valve_reach_inset,
)


class Project02EngineeringInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {
            "sourceIndependentPolicy": {},
            "assemblySequencePolicy": {"vendorTransportInterface": {}},
            "processConstraints": [
                {
                    "id": "a700-weighing-reach",
                    "type": "pointInRegion",
                    "pointComponent": "FL9A24D062A700.001-1",
                    "point": "servicePoint",
                }
            ],
            "moduleSemantics": {
                "FL9A24D062A800.001-1": {
                    "points": {"barcode": {"u": 1.0, "v": 2.0}, "low": {}, "high": {}},
                    "parameters": {"dynamicScanWindowPointNames": ["low", "high"]},
                },
                "FL9A24D062A100.001-1": {
                    "regions": {
                        "leftValveReach": {"minU": 0, "minV": 0, "maxU": 4, "maxV": 4},
                        "rightValveReach": {"minU": 1, "minV": 1, "maxU": 5, "maxV": 5},
                        "dualValveReach": {"minU": 1, "minV": 1, "maxU": 4, "maxV": 4},
                    },
                    "parameters": {},
                },
                "FL9A24D062A500.001-1": {
                    "parameters": {"protectedSpaceBoxesLocal": [{"bounds": [0, 0, 2, 2]}]}
                },
                "FL9A24D062A700.001-1": {"parameters": {"protectedSpaceBoxesLocal": []}},
                "FL9A24D062A300.001-1": {"parameters": {"protectedSpaceBoxesLocal": []}},
            }
        }

    def test_unconfirmed_inputs_are_inert(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(self.request, {})
        self.assertEqual(updated, self.request)
        self.assertFalse(report["layoutResolveRequired"])

    def test_confirmed_scan_updates_both_endpoints(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {"dynamicScan": {"confirmed": True, "stopToleranceMeters": 0.02}},
        )
        points = updated["moduleSemantics"]["FL9A24D062A800.001-1"]["points"]
        self.assertAlmostEqual(points["low"]["u"], 0.98)
        self.assertAlmostEqual(points["high"]["u"], 1.02)
        self.assertEqual(report["appliedSections"], ["dynamicScan"])
        self.assertEqual(report["dynamicScanAuthority"], "vendorConfirmed")

    def test_accepted_prototype_scan_baseline_remains_unconfirmed(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "dynamicScan": {
                    "sourceType": "prototypeBaseline",
                    "acceptedForCoarseLayout": True,
                    "vendorConfirmed": False,
                    "scope": "project02-only",
                    "stopToleranceMeters": 0.005,
                    "source": "half of measured Project02 QR width",
                }
            },
        )
        transport = updated["moduleSemantics"]["FL9A24D062A800.001-1"]
        sequence = updated["assemblySequencePolicy"]["dynamicScan"]
        self.assertFalse(transport["parameters"]["dynamicScanStopToleranceConfirmed"])
        self.assertTrue(transport["parameters"]["dynamicScanWindowAcceptedForCoarseLayout"])
        self.assertEqual(
            transport["parameters"]["dynamicScanStopToleranceAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )
        self.assertFalse(sequence["confirmed"])
        self.assertTrue(sequence["estimateAcceptedForCoarseLayout"])
        self.assertEqual(sequence["inputScope"], "project02-only")
        self.assertEqual(
            report["dynamicScanAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )

    def test_prototype_scan_baseline_cannot_be_marked_vendor_confirmed(self) -> None:
        with self.assertRaises(EngineeringInputError):
            apply_confirmed_project02_engineering_inputs(
                self.request,
                {
                    "dynamicScan": {
                        "sourceType": "prototypeBaseline",
                        "acceptedForCoarseLayout": True,
                        "vendorConfirmed": True,
                        "scope": "project02-only",
                    }
                },
            )

    def test_confirmed_transport_installation_replaces_prototype_anchor(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "transportInstallation": {
                    "sourceType": "vendorDatum",
                    "vendorConfirmed": True,
                    "frameName": "A600_INSTALLATION_FRAME",
                    "a800AnchorPointFrameMeters": [0.58, 0.535, 0.115],
                    "source": "vendor drawing datum D1",
                }
            },
        )
        policy = updated["sourceIndependentPolicy"]
        vendor = updated["assemblySequencePolicy"]["vendorTransportInterface"]
        self.assertEqual(policy["caseAnchorTargetKind"], "installationFramePoint")
        self.assertEqual(policy["caseAnchorTargetFrameMeters"], [0.58, 0.535, 0.115])
        self.assertFalse(policy["caseAnchorTargetPrototypeDerived"])
        self.assertTrue(vendor["confirmed"])
        self.assertEqual(report["appliedSections"], ["transportInstallation"])
        self.assertEqual(report["transportInstallationAuthority"], "vendorConfirmed")

    def test_accepted_prototype_baseline_is_applied_without_vendor_claim(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "transportInstallation": {
                    "sourceType": "prototypeBaseline",
                    "acceptedForCoarseLayout": True,
                    "vendorConfirmed": False,
                    "scope": "project02-only",
                    "frameName": "A600_INSTALLATION_FRAME",
                    "a800AnchorPointFrameMeters": [0.5788, 0.535, 0.115225],
                    "source": "Project02 prototype mate-derived baseline",
                }
            },
        )
        policy = updated["sourceIndependentPolicy"]
        vendor = updated["assemblySequencePolicy"]["vendorTransportInterface"]
        self.assertTrue(policy["caseAnchorTargetPrototypeDerived"])
        self.assertEqual(policy["caseAnchorScope"], "project02-only")
        self.assertFalse(vendor["confirmed"])
        self.assertIsNone(vendor["xyzMeters"])
        self.assertEqual(
            report["transportInstallationAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )

    def test_prototype_baseline_cannot_be_marked_vendor_confirmed(self) -> None:
        with self.assertRaises(EngineeringInputError):
            apply_confirmed_project02_engineering_inputs(
                self.request,
                {
                    "transportInstallation": {
                        "sourceType": "prototypeBaseline",
                        "acceptedForCoarseLayout": True,
                        "vendorConfirmed": True,
                        "scope": "project02-only",
                    }
                },
            )

    def test_confirmed_valve_regions_require_a_nonempty_intersection(self) -> None:
        with self.assertRaises(EngineeringInputError):
            apply_confirmed_project02_engineering_inputs(
                self.request,
                {
                    "dualValveReach": {
                        "sourceType": "vendorDatum",
                        "vendorConfirmed": True,
                        "valveHeadSpacingMeters": 0.09,
                        "leftValveReachLocalMeters": {"minU": 0, "minV": 0, "maxU": 1, "maxV": 1},
                        "rightValveReachLocalMeters": {"minU": 2, "minV": 2, "maxU": 3, "maxV": 3},
                    }
                },
            )

    def test_accepted_prototype_valve_baseline_remains_provisional(self) -> None:
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "dualValveReach": {
                    "sourceType": "prototypeBaseline",
                    "acceptedForCoarseLayout": True,
                    "vendorConfirmed": False,
                    "scope": "project02-only",
                    "valveHeadSpacingMeters": 0.09,
                    "leftValveReachLocalMeters": {
                        "minU": 0.0,
                        "minV": 0.0,
                        "maxU": 4.0,
                        "maxV": 4.0,
                    },
                    "rightValveReachLocalMeters": {
                        "minU": 1.0,
                        "minV": 1.0,
                        "maxU": 5.0,
                        "maxV": 5.0,
                    },
                    "source": "Project02 geometry baseline",
                }
            },
        )
        parameters = updated["moduleSemantics"][
            "FL9A24D062A100.001-1"
        ]["parameters"]
        sequence = updated["assemblySequencePolicy"]["dualValveReach"]
        self.assertTrue(parameters["provisionalReach"])
        self.assertFalse(parameters["valveHeadSpacingConfirmed"])
        self.assertEqual(
            parameters["reachEvidenceAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )
        self.assertFalse(sequence["confirmed"])
        self.assertTrue(sequence["estimateAcceptedForCoarseLayout"])
        self.assertEqual(
            report["dualValveReachAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )

    def test_prototype_valve_baseline_cannot_be_marked_vendor_confirmed(self) -> None:
        with self.assertRaises(EngineeringInputError):
            apply_confirmed_project02_engineering_inputs(
                self.request,
                {
                    "dualValveReach": {
                        "sourceType": "prototypeBaseline",
                        "acceptedForCoarseLayout": True,
                        "vendorConfirmed": True,
                        "scope": "project02-only",
                    }
                },
            )

    def test_accepted_prototype_service_baseline_remains_unconfirmed(self) -> None:
        space = {
            "id": "calibration-access",
            "bounds": [-0.1, -0.2, 0.1, 0.0],
            "heightRangeMeters": [0.0, 0.3],
            "hardClearanceWith": ["FL9A24D062A200.001-1"],
        }
        updated, report = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "serviceAccess": {
                    "sourceType": "prototypeBaseline",
                    "acceptedForCoarseLayout": True,
                    "vendorConfirmed": False,
                    "scope": "project02-only",
                    "source": "Project02 protected-space baseline",
                    "modules": {"FL9A24D062A500.001-1": [space]},
                }
            },
        )
        parameters = updated["moduleSemantics"][
            "FL9A24D062A500.001-1"
        ]["parameters"]
        sequence = updated["assemblySequencePolicy"]["serviceAccess"]
        self.assertFalse(parameters["serviceAccessLaneConfirmed"])
        self.assertEqual(
            parameters["serviceAccessLaneAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )
        self.assertFalse(sequence["confirmed"])
        self.assertTrue(sequence["estimateAcceptedForCoarseLayout"])
        self.assertEqual(
            report["serviceAccessAuthority"],
            "prototypeBaselineAcceptedForCoarseLayout",
        )

    def test_prototype_service_baseline_cannot_be_marked_vendor_confirmed(self) -> None:
        with self.assertRaises(EngineeringInputError):
            apply_confirmed_project02_engineering_inputs(
                self.request,
                {
                    "serviceAccess": {
                        "sourceType": "prototypeBaseline",
                        "acceptedForCoarseLayout": True,
                        "vendorConfirmed": True,
                        "scope": "project02-only",
                    }
                },
            )

    def test_service_functional_points_update_alias_and_named_constraint(self) -> None:
        updated, _ = apply_confirmed_project02_engineering_inputs(
            self.request,
            {
                "serviceAccess": {
                    "sourceType": "prototypeBaseline",
                    "acceptedForCoarseLayout": True,
                    "vendorConfirmed": False,
                    "scope": "project02-only",
                    "modules": {
                        "FL9A24D062A700.001-1": [
                            {
                                "id": "access",
                                "bounds": [-0.1, -0.1, 0.1, 0.1],
                                "heightRangeMeters": [0.0, 0.3],
                            }
                        ]
                    },
                    "functionalPoints": {
                        "FL9A24D062A700.001-1": {
                            "cleaning": {
                                "pointName": "cleaningServicePoint",
                                "pointLocalMeters": {"u": 0.4, "v": -0.08},
                                "defaultServiceFunction": True,
                            },
                            "weighing": {
                                "pointName": "weighingServicePoint",
                                "pointLocalMeters": {"u": 0.0, "v": 0.0},
                                "processConstraintIds": ["a700-weighing-reach"],
                            },
                        }
                    },
                }
            },
        )
        semantic = updated["moduleSemantics"]["FL9A24D062A700.001-1"]
        self.assertEqual(
            semantic["points"]["servicePoint"],
            semantic["points"]["cleaningServicePoint"],
        )
        self.assertEqual(
            semantic["parameters"]["functionalServicePointNames"],
            {"cleaning": "cleaningServicePoint", "weighing": "weighingServicePoint"},
        )
        self.assertEqual(
            updated["processConstraints"][0]["point"], "weighingServicePoint"
        )

    def test_stress_transformations_are_source_immutable(self) -> None:
        scan = with_scan_tolerance(self.request, 0.1)
        scaled = with_service_space_scale(self.request, 1.5)
        inset = with_valve_reach_inset(self.request, 0.25)
        self.assertEqual(self.request["moduleSemantics"]["FL9A24D062A800.001-1"]["points"]["low"], {})
        self.assertAlmostEqual(scan["moduleSemantics"]["FL9A24D062A800.001-1"]["points"]["low"]["u"], 0.9)
        self.assertEqual(scaled["moduleSemantics"]["FL9A24D062A500.001-1"]["parameters"]["protectedSpaceBoxesLocal"][0]["bounds"], [-0.5, -0.5, 2.5, 2.5])
        self.assertAlmostEqual(inset["moduleSemantics"]["FL9A24D062A100.001-1"]["regions"]["dualValveReach"]["minU"], 1.25)

    def test_component_service_scale_only_changes_the_selected_module(self) -> None:
        changed = with_service_component_scale(
            self.request, "FL9A24D062A500.001-1", 1.5
        )
        self.assertEqual(
            changed["moduleSemantics"]["FL9A24D062A500.001-1"]["parameters"]
            ["protectedSpaceBoxesLocal"][0]["bounds"],
            [-0.5, -0.5, 2.5, 2.5],
        )
        self.assertEqual(
            changed["moduleSemantics"]["FL9A24D062A700.001-1"]["parameters"]
            ["protectedSpaceBoxesLocal"],
            [],
        )

    def test_directional_reach_insets_recompute_the_common_region(self) -> None:
        changed = with_valve_reach_directional_insets(self.request, 0.1, 0.2)
        regions = changed["moduleSemantics"]["FL9A24D062A100.001-1"]["regions"]
        self.assertEqual(regions["leftValveReach"], {"minU": 0.1, "minV": 0.2, "maxU": 3.9, "maxV": 3.8})
        self.assertEqual(regions["rightValveReach"], {"minU": 1.1, "minV": 1.2, "maxU": 4.9, "maxV": 4.8})
        self.assertEqual(regions["dualValveReach"], {"minU": 1.1, "minV": 1.2, "maxU": 3.9, "maxV": 3.8})
        self.assertEqual(
            self.request["moduleSemantics"]["FL9A24D062A100.001-1"]["regions"]["dualValveReach"],
            {"minU": 1, "minV": 1, "maxU": 4, "maxV": 4},
        )

    def test_pose_comparison_routes_changed_layout_to_replay(self) -> None:
        reference = {"A": (0.0, 0.0, 0.0, 0.0)}
        self.assertTrue(compare_signatures(reference, reference)["equivalent"])
        self.assertFalse(compare_signatures(reference, {"A": (0.001, 0.0, 0.0, 0.0)})["equivalent"])


if __name__ == "__main__":
    unittest.main()
