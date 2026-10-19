from __future__ import annotations

import copy
import math
import unittest
from unittest.mock import patch

from demo_backend.constraint_layout import (
    ConstraintLayoutError,
    ConstraintLayoutOptions,
    ConstraintLayoutSearchTimeout,
    Placement,
    _candidate_process_validation,
    _collision_responsibility_key,
    _conditional_brep_leaf_hit_count,
    _constraint_component_names,
    _eligible_envelope_pair_count,
    _evaluate_interaction_hard_constraints,
    _evaluate_spatial_hard_constraints,
    _overlapping_envelope_pairs,
    _point_in_region_anchor_candidates,
    _portal_long_axis_anchor_interval,
    _read_footprints,
    _relative_anchor_window_anchors,
    _relative_anchor_window_target_distance,
    generate_constraint_layout,
)
from demo_backend.process_constraints import (
    compile_process_constraints,
    evaluate_process_constraints,
    normalize_module_semantics,
)


def test_relative_exclusion_window_registers_both_candidate_dependencies():
    assert _constraint_component_names(
        {
            "type": "relativeAnchorExclusionWindow",
            "component": "A300",
            "referenceComponent": "A700",
        }
    ) == {"A300", "A700"}


def test_absolute_exclusion_window_registers_only_moving_component_dependency():
    assert _constraint_component_names(
        {
            "type": "anchorExclusionWindow",
            "component": "A500",
        }
    ) == {"A500"}


def component(name: str, box: list[float], x: float, y: float) -> dict:
    return {
        "componentName": name,
        "filePath": f"{name}.SLDASM",
        "bottomFaceName": "底面",
        "bottomCenterWorld": [x, 0.0, y],
        "bottomNormalWorld": [0.0, 1.0, 0.0],
        "componentXAxis": [1.0, 0.0, 0.0],
        "componentYAxis": [0.0, 1.0, 0.0],
        "componentZAxis": [0.0, 0.0, 1.0],
        "boundingBoxWorld": box,
        "layout2d": {"x": x, "y": y, "thetaDegrees": 0.0, "thetaAxis": "x"},
        "faceMappingFound": True,
    }


def capture() -> dict:
    return {
        "success": True,
        "message": "capture",
        "baseComponentName": "gantry",
        "baseFrame": {
            "origin": [0.0, 0.0, 0.0],
            "uAxis": [1.0, 0.0, 0.0],
            "vAxis": [0.0, 0.0, 1.0],
            "normal": [0.0, 1.0, 0.0],
        },
        "components": [
            component("gantry", [-5.0, 0.0, -3.0, 5.0, 1.0, 3.0], 0.0, 0.0),
            component("transport", [-5.2, 0.0, -0.45, 5.2, 0.5, 0.45], 0.0, 0.0),
            component("function-a", [-1.7, 0.0, 0.8, -0.2, 0.4, 1.8], -0.95, 1.3),
            component("function-b", [0.2, 0.0, -1.8, 1.7, 0.4, -0.8], 0.95, -1.3),
            component("glue", [5.5, 0.0, -0.6, 7.0, 0.6, 0.6], 6.25, 0.0),
        ],
    }


def semantic_capture() -> dict:
    data = capture()
    data["baseComponentName"] = "gantry"
    data["components"] = [
        component("gantry", [-5.0, 0.0, -3.0, 5.0, 1.0, 3.0], 0.0, 0.0),
        component("transport", [-5.2, 0.0, -0.45, 5.2, 0.5, 0.45], 0.0, 0.0),
        component("scanner", [-4.8, 0.0, -2.4, -4.4, 0.4, -2.0], -4.6, -2.2),
        component("ccd", [-4.8, 0.0, 2.0, -4.4, 0.4, 2.4], -4.6, 2.2),
        component("calibration", [-3.8, 0.0, -2.4, -3.4, 0.4, -2.0], -3.6, -2.2),
        component("cleaning", [-2.8, 0.0, -2.4, -2.4, 0.4, -2.0], -2.6, -2.2),
        component("weighing", [-1.8, 0.0, -2.4, -1.4, 0.4, -2.0], -1.6, -2.2),
        component("glue", [5.5, 0.0, -0.6, 7.0, 0.6, 0.6], 6.25, 0.0),
    ]
    return data


def semantic_modules() -> dict:
    return {
        "gantry": {
            "moduleType": "gantry",
            "regions": {
                "dualValveReach": {"minU": -4.9, "minV": -2.9, "maxU": 4.9, "maxV": 2.9},
            },
            "allowedRotationDegrees": [0],
        },
        "transport": {
            "moduleType": "transport",
            "points": {
                "barcode": {"u": -4.7, "v": -0.4},
                "workPosition1": {"u": -4.0, "v": 0.0},
                "workPosition2": {"u": -3.2, "v": 0.0},
            },
            "allowedRotationDegrees": [0],
        },
        "scanner": {
            "moduleType": "scanner",
            "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
            "preferredSide": "low",
            "allowedRotationDegrees": [0],
            "parameters": {"maxWorkingDistanceMeters": 2.0, "barcodeSide": "low"},
        },
        "ccd": {
            "moduleType": "ccd",
            "points": {"cameraOrigin": {"u": 0.0, "v": 0.0}},
            "preferredSide": "high",
            "allowedRotationDegrees": [0],
            "parameters": {"minWorkingDistanceMeters": 0.1, "maxWorkingDistanceMeters": 3.0},
        },
        "calibration": {
            "moduleType": "calibration",
            "points": {"servicePoint": {"u": 0.0, "v": 0.0}},
            "preferredSide": "low",
            "allowedRotationDegrees": [0],
        },
        "cleaning": {
            "moduleType": "cleaning",
            "points": {"servicePoint": {"u": 0.0, "v": 0.0}},
            "preferredSide": "low",
            "allowedRotationDegrees": [0],
            "parameters": {"isolationClearanceMeters": 0.005},
        },
        "weighing": {
            "moduleType": "weighing",
            "points": {"servicePoint": {"u": 0.0, "v": 0.0}},
            "preferredSide": "low",
            "allowedRotationDegrees": [0],
        },
        "glue": {
            "moduleType": "glue_supply",
            "allowedRotationDegrees": [0],
        },
    }


def perturb_component_positions(data: dict, scale: float) -> dict:
    result = copy.deepcopy(data)
    for index, item in enumerate(result["components"], start=1):
        delta_u = scale * (index * 0.73 - 2.1)
        delta_v = scale * (1.7 - index * 0.41)
        item["layout2d"]["x"] += delta_u
        item["layout2d"]["y"] += delta_v
        item["bottomCenterWorld"][0] += delta_u
        item["bottomCenterWorld"][2] += delta_v
        item["boundingBoxWorld"][0] += delta_u
        item["boundingBoxWorld"][3] += delta_u
        item["boundingBoxWorld"][2] += delta_v
        item["boundingBoxWorld"][5] += delta_v
    return result


class ConstraintLayoutTests(unittest.TestCase):
    def test_spatial_validation_uses_component_specific_gantry_boundary_clearance(self):
        placements = [
            Placement("gantry", "gantry", 0, 0, 0, 0, (-5.0, -3.0, 5.0, 3.0)),
            Placement("function", "functional", 0, -4.0, 0, 0, (-4.5, -0.5, -3.5, 0.5)),
        ]
        semantics = normalize_module_semantics(
            ["gantry", "function"],
            {
                "function": {
                    "moduleType": "calibration",
                    "parameters": {"minimumGantryBoundaryClearanceMeters": 1.0},
                }
            },
        )

        result = _evaluate_spatial_hard_constraints(
            placements,
            {},
            {"gantry": "gantry", "function": "functional"},
            semantics,
            "gantry",
            {},
            minimum_transport_gantry_overlap_ratio=0.5,
            minimum_portal_gantry_overlap_ratio=0.85,
            minimum_functional_gantry_overlap_ratio=0.0,
            minimum_functional_gantry_boundary_clearance_meters=0.0,
            maximum_transport_gantry_center_offset_meters=None,
            maximum_portal_gantry_center_offset_meters=None,
            maximum_portal_gantry_overhang_meters=None,
        )

        diagnostic = next(
            item
            for item in result["diagnostics"]
            if item["type"] == "functionalGantryBoundaryClearance"
        )
        self.assertFalse(diagnostic["success"])
        self.assertAlmostEqual(diagnostic["minimumClearanceMeters"], 1.0)
        self.assertFalse(result["hardFeasible"])

    def test_portal_centerline_and_overhang_are_independent_spatial_gates(self):
        placements = [
            Placement("gantry", "gantry", 0, 0, 0, 0, (-5.0, -3.0, 5.0, 3.0)),
            Placement("transport", "transport", 0, 0, 0, 0, (-5.2, -0.4, 5.2, 0.4)),
            Placement("portal", "functional", 0, 0, 0, 0, (-4.0, -2.5, 5.5, 2.5)),
        ]
        result = _evaluate_spatial_hard_constraints(
            placements,
            {},
            {"gantry": "gantry", "transport": "transport", "portal": "functional"},
            {},
            "gantry",
            {"portal": ("transport",)},
            minimum_transport_gantry_overlap_ratio=0.5,
            minimum_portal_gantry_overlap_ratio=0.85,
            minimum_functional_gantry_overlap_ratio=0.0,
            minimum_functional_gantry_boundary_clearance_meters=0.0,
            maximum_transport_gantry_center_offset_meters=0.05,
            maximum_portal_gantry_center_offset_meters=0.03,
            maximum_portal_gantry_overhang_meters=0.4,
        )

        by_type = {item["type"]: item for item in result["diagnostics"]}
        self.assertTrue(by_type["portalGantryCenterOffset"]["success"])
        self.assertFalse(by_type["portalGantryOverhang"]["success"])
        self.assertAlmostEqual(
            by_type["portalGantryOverhang"]["maximumObservedOverhangMeters"],
            0.5,
        )
        self.assertFalse(result["hardFeasible"])

    def test_conditional_brep_pair_defers_leaf_aabb_but_keeps_portal_hard(self):
        data = capture()
        data["components"] = [
            component("portal", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("transport", [-2.0, 0.0, -0.1, 2.0, 0.2, 0.1], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        raw_semantics = {
            "portal": {
                "moduleType": "ccd",
                "regions": {
                    "portalOpening": {
                        "minU": -1.0,
                        "minV": -0.5,
                        "maxU": 1.0,
                        "maxV": 0.5,
                    }
                },
                "parameters": {
                    "occupancyBoxesLocal": [
                        {"id": "portal-frame", "bounds": [-1.0, -0.2, 1.0, 0.2], "heightRangeMeters": [0.0, 0.3]}
                    ],
                    "useOccupancyBoxesForClearance": True,
                    "occupancyBoxesHardClearance": True,
                    "portalOpeningHeightRangeMeters": [0.0, 0.4],
                    "portalPassModeByComponent": {"transport": "throughLongAxis"},
                    "brepOnAabbOverlapWith": ["transport"],
                },
            },
            "transport": {
                "moduleType": "transport",
                "parameters": {
                    "occupancyBoxesLocal": [
                        {"id": "rail", "bounds": [-2.0, -0.1, 2.0, 0.1], "heightRangeMeters": [0.0, 0.2]}
                    ],
                    "useOccupancyBoxesForClearance": True,
                    "occupancyBoxesHardClearance": True,
                    "portalPassBodyBoxesLocal": [
                        {"id": "rail", "bounds": [-2.0, -0.1, 2.0, 0.1], "heightRangeMeters": [0.0, 0.2]}
                    ],
                    "brepOnAabbOverlapWith": ["portal"],
                },
            },
        }
        semantics = normalize_module_semantics(list(footprints), raw_semantics)
        placements = [
            Placement("portal", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
            Placement("transport", "transport", 0, 0, 0, 0, (-2.0, -0.1, 2.0, 0.1)),
        ]

        valid = _evaluate_interaction_hard_constraints(
            placements,
            footprints,
            semantics,
            {"portal": ("transport",)},
            "u",
            0.01,
        )

        self.assertTrue(valid["hardFeasible"])
        occupancy = next(item for item in valid["diagnostics"] if item["type"] == "structuralOccupancyClearance")
        portal = next(item for item in valid["diagnostics"] if item.get("portalCheck"))
        self.assertTrue(occupancy["success"])
        self.assertFalse(occupancy["hard"])
        self.assertEqual(occupancy["resolution"], "conditionalBrepLeafBodyOverlapDeferredToCad")
        self.assertTrue(occupancy["requiresCadInterferenceValidation"])
        self.assertEqual(portal["resolution"], "portalOpening")

        raw_semantics["transport"]["parameters"]["portalPassBodyBoxesLocal"][0]["bounds"] = [
            -2.0,
            -0.6,
            2.0,
            0.6,
        ]
        too_wide = _evaluate_interaction_hard_constraints(
            placements,
            footprints,
            normalize_module_semantics(list(footprints), raw_semantics),
            {"portal": ("transport",)},
            "u",
            0.01,
        )
        self.assertFalse(too_wide["hardFeasible"])
        self.assertEqual(
            next(item for item in too_wide["diagnostics"] if item.get("portalCheck"))["resolution"],
            "unresolvedPortalOverlap",
        )

    def test_forced_hard_occupancy_pair_blocks_conditional_brep_overlap(self):
        data = capture()
        data["components"] = [
            component("portal", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("calibration", [-0.5, 0.0, -0.5, 0.5, 0.5, 0.5], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        semantics = normalize_module_semantics(
            list(footprints),
            {
                "portal": {
                    "moduleType": "ccd",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": "frame", "bounds": [-0.2, -0.2, 0.2, 0.2], "heightRangeMeters": [0.0, 0.3]}
                        ],
                        "useOccupancyBoxesForClearance": True,
                        "brepOnAabbOverlapWith": ["calibration"],
                    },
                },
                "calibration": {
                    "moduleType": "calibration",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": "fixture", "bounds": [-0.1, -0.1, 0.1, 0.1], "heightRangeMeters": [0.0, 0.2]}
                        ],
                        "useOccupancyBoxesForClearance": True,
                        "brepOnAabbOverlapWith": ["portal"],
                        "hardOccupancyClearanceWith": ["portal"],
                        "occupancyClearanceMetersByComponent": {"portal": 0.02},
                    },
                },
            },
        )
        validation = _evaluate_interaction_hard_constraints(
            [
                Placement("portal", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
                Placement("calibration", "functional", 0, 0, 0, 0, (-0.5, -0.5, 0.5, 0.5)),
            ],
            footprints,
            semantics,
            {},
            "u",
            0.01,
        )
        diagnostic = next(
            item for item in validation["diagnostics"] if item["type"] == "multiBoxClearance"
        )
        self.assertFalse(validation["hardFeasible"])
        self.assertTrue(diagnostic["hard"])
        self.assertTrue(diagnostic["conditionalBrepPair"])
        self.assertTrue(diagnostic["forcedHardOccupancyPair"])
        self.assertEqual(diagnostic["minimumClearanceMeters"], 0.02)

    def test_conditional_leaf_hit_count_prefers_clear_broad_phase_candidate(self):
        data = capture()
        data["components"] = [
            component("first", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("second", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        semantics = normalize_module_semantics(
            list(footprints),
            {
                name: {
                    "moduleType": "calibration",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": name, "bounds": [-0.1, -0.1, 0.1, 0.1], "heightRangeMeters": [0.0, 0.2]}
                        ],
                        "brepOnAabbOverlapWith": ["second" if name == "first" else "first"],
                    },
                }
                for name in ("first", "second")
            },
        )
        fixed = Placement("first", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0))
        colliding = Placement("second", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0))
        clear = Placement("second", "functional", 0.5, 0.5, 0, 0, (-0.5, -0.5, 1.5, 1.5))

        self.assertEqual(
            _conditional_brep_leaf_hit_count(
                colliding, [fixed], footprints, semantics, 0.01
            ),
            1,
        )
        self.assertEqual(
            _conditional_brep_leaf_hit_count(clear, [fixed], footprints, semantics, 0.01),
            0,
        )

    def test_protected_service_space_rejects_fixed_structure_obstruction(self):
        data = capture()
        data["components"] = [
            component("structure", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("calibration", [-0.5, 0.0, -0.5, 0.5, 0.5, 0.5], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        semantics = normalize_module_semantics(
            list(footprints),
            {
                "structure": {
                    "moduleType": "ccd",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": "post", "bounds": [0.2, -0.1, 0.4, 0.1], "heightRangeMeters": [0.0, 0.4]}
                        ]
                    },
                },
                "calibration": {
                    "moduleType": "calibration",
                    "parameters": {
                        "protectedSpaceBoxesLocal": [
                            {
                                "id": "maintenance",
                                "bounds": [0.1, -0.2, 0.5, 0.2],
                                "heightRangeMeters": [0.0, 0.3],
                                "hardClearanceWith": ["structure"],
                            }
                        ]
                    },
                },
            },
        )
        validation = _evaluate_interaction_hard_constraints(
            [
                Placement("structure", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
                Placement("calibration", "functional", 0, 0, 0, 0, (-0.5, -0.5, 0.5, 0.5)),
            ],
            footprints,
            semantics,
            {},
            "u",
            0.01,
        )
        diagnostic = next(
            item
            for item in validation["diagnostics"]
            if item["type"] == "protectedServiceSpaceClearance"
        )
        self.assertFalse(validation["hardFeasible"])
        self.assertEqual(diagnostic["resolution"], "protectedServiceSpaceObstructed")

    def test_unconfirmed_advisory_service_space_warns_without_rejecting_candidate(self):
        data = capture()
        data["components"] = [
            component("structure", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("calibration", [-0.5, 0.0, -0.5, 0.5, 0.5, 0.5], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        semantics = normalize_module_semantics(
            list(footprints),
            {
                "structure": {
                    "moduleType": "ccd",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": "post", "bounds": [0.2, -0.1, 0.4, 0.1], "heightRangeMeters": [0.0, 0.4]}
                        ],
                        "useOccupancyBoxesForClearance": True,
                        "brepOnAabbOverlapWith": ["calibration"],
                    },
                },
                "calibration": {
                    "moduleType": "calibration",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": "fixture", "bounds": [-0.4, -0.1, -0.2, 0.1], "heightRangeMeters": [0.0, 0.2]}
                        ],
                        "useOccupancyBoxesForClearance": True,
                        "brepOnAabbOverlapWith": ["structure"],
                        "protectedSpaceBoxesLocal": [
                            {
                                "id": "maintenance",
                                "bounds": [0.1, -0.2, 0.5, 0.2],
                                "heightRangeMeters": [0.0, 0.3],
                                "hardClearanceWith": ["structure"],
                                "enforcement": "advisory",
                                "confirmed": False,
                                "evidenceStatus": "prototype estimate",
                            }
                        ]
                    },
                },
            },
        )
        validation = _evaluate_interaction_hard_constraints(
            [
                Placement("structure", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
                Placement("calibration", "functional", 0, 0, 0, 0, (-0.5, -0.5, 0.5, 0.5)),
            ],
            footprints,
            semantics,
            {},
            "u",
            0.01,
        )
        diagnostic = next(
            item
            for item in validation["diagnostics"]
            if item["type"] == "protectedServiceSpaceClearance"
        )
        self.assertTrue(validation["hardFeasible"])
        self.assertEqual(validation["hardFailureCount"], 0)
        self.assertEqual(validation["softViolationCount"], 1)
        self.assertFalse(diagnostic["hard"])
        self.assertTrue(diagnostic["requiresEngineeringReview"])
        self.assertEqual(
            diagnostic["resolution"], "advisoryProtectedServiceSpaceObstructed"
        )
        self.assertEqual(
            diagnostic["protectedSpace"]["evidenceStatus"], "prototype estimate"
        )

    def test_nonconditional_leaf_aabb_overlap_remains_hard(self):
        data = capture()
        data["components"] = [
            component("first", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
            component("second", [-1.0, 0.0, -1.0, 1.0, 1.0, 1.0], 0.0, 0.0),
        ]
        footprints = {item.component_name: item for item in _read_footprints(data)}
        semantics = normalize_module_semantics(
            list(footprints),
            {
                name: {
                    "moduleType": "calibration",
                    "parameters": {
                        "occupancyBoxesLocal": [
                            {"id": name, "bounds": [-0.5, -0.5, 0.5, 0.5], "heightRangeMeters": [0.0, 0.5]}
                        ],
                        "useOccupancyBoxesForClearance": True,
                        "occupancyBoxesHardClearance": True,
                    },
                }
                for name in ("first", "second")
            },
        )
        validation = _evaluate_interaction_hard_constraints(
            [
                Placement("first", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
                Placement("second", "functional", 0, 0, 0, 0, (-1.0, -1.0, 1.0, 1.0)),
            ],
            footprints,
            semantics,
            {},
            "u",
            0.01,
        )
        self.assertFalse(validation["hardFeasible"])
        self.assertEqual(validation["diagnostics"][0]["resolution"], "leafBodyOccupancyBoxCollision")

    def test_localized_portal_body_constrains_long_axis_while_rail_can_pass_through(self):
        semantics = normalize_module_semantics(
            ["portal"],
            {
                "portal": {
                    "moduleType": "ccd",
                    "regions": {
                        "portalOpening": {
                            "minU": -1.0,
                            "minV": -0.5,
                            "maxU": 1.0,
                            "maxV": 0.5,
                        }
                    },
                }
            },
        )
        interval = _portal_long_axis_anchor_interval(
            Placement("portal", "functional", 0, 0, 0, 0, (-2, -1, 2, 1)),
            semantics["portal"].regions["portalOpening"],
            Placement("transport", "transport", 0, 0, 0, 0, (-5, -0.2, 5, 0.2)),
            [
                {
                    "id": "rail",
                    "bounds": [-5.0, -0.1, 5.0, 0.1],
                    "heightRangeMeters": [0.0, 0.2],
                },
                {
                    "id": "motor",
                    "bounds": [1.4, -0.1, 1.6, 0.1],
                    "heightRangeMeters": [0.0, 0.2],
                    "requireLongAxisContainment": True,
                },
            ],
            "u",
            0.1,
        )

        self.assertIsNotNone(interval)
        self.assertAlmostEqual(interval[0], 0.7)
        self.assertAlmostEqual(interval[1], 2.3)

    def test_layout_emits_complete_target_orientation_frame_for_replay(self):
        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(
                role_overrides={},
                module_semantics=semantic_modules(),
                source_position_independent=True,
            ),
        )

        for item in result["components"]:
            self.assertEqual(item["targetXAxisWorld"], [1.0, 0.0, 0.0])
            self.assertEqual(item["targetYAxisWorld"], [0.0, 1.0, 0.0])
            self.assertEqual(item["targetZAxisWorld"], [0.0, 0.0, 1.0])

    def test_line_of_sight_can_ignore_explicit_portal_frame_aabb(self):
        semantics = normalize_module_semantics(
            ["scanner", "transport", "portal"],
            {
                "scanner": {"moduleType": "scanner", "points": {"scanOrigin": {"u": 0, "v": 0}}},
                "transport": {"moduleType": "transport", "points": {"barcode": {"u": 0, "v": 0}}},
                "portal": {
                    "moduleType": "ccd",
                    "parameters": {"lineOfSightTransparent": True},
                },
            },
        )
        placements = [
            Placement("scanner", "functional", 0, 0, 0, 0, (-0.1, -0.1, 0.1, 0.1)),
            Placement("transport", "transport", 10, 0, 0, 0, (9.9, -0.1, 10.1, 0.1)),
            Placement("portal", "functional", 5, 0, 0, 0, (4, -1, 6, 1)),
        ]
        validation = evaluate_process_constraints(
            [
                {
                    "id": "scanner-los",
                    "type": "lineOfSight",
                    "sourceComponent": "scanner",
                    "sourcePoint": "scanOrigin",
                    "targetComponent": "transport",
                    "targetPoint": "barcode",
                    "hard": True,
                }
            ],
            semantics,
            {},
            placements,
            {"scanner": "functional", "transport": "transport", "portal": "functional"},
            "u",
        )
        self.assertTrue(validation["hardFeasible"])
        self.assertEqual(validation["diagnostics"][0]["measured"]["blockedBy"], [])

    def test_relative_anchor_window_rejects_cross_axis_drift(self):
        placements = [
            Placement("reference", "functional", 1.0, 2.0, 0, 0, (0.9, 1.9, 1.1, 2.1)),
            Placement("service", "functional", 1.01, 2.11, 0, 0, (0.91, 2.01, 1.11, 2.21)),
        ]
        constraint = {
            "id": "service-window",
            "type": "relativeAnchorWindow",
            "component": "service",
            "referenceComponent": "reference",
            "minDeltaU": -0.02,
            "maxDeltaU": 0.02,
            "minDeltaV": 0.08,
            "maxDeltaV": 0.14,
            "hard": True,
        }

        passing = evaluate_process_constraints(
            [constraint], {}, {}, placements, {}, "u"
        )
        drifting = evaluate_process_constraints(
            [constraint], {}, {}, [placements[0], Placement("service", "functional", 1.08, 2.11, 0, 0, (0.98, 2.01, 1.18, 2.21))], {}, "u"
        )

        self.assertTrue(passing["hardFeasible"])
        self.assertAlmostEqual(passing["diagnostics"][0]["measured"]["deltaV"], 0.11)
        self.assertFalse(drifting["hardFeasible"])

    def test_relative_anchor_window_center_is_the_nominal_candidate_target(self):
        reference = Placement(
            "reference", "functional", 1.0, 2.0, 0, 0, (0.9, 1.9, 1.1, 2.1)
        )
        exact = Placement(
            "service", "functional", 1.215, 2.052, 0, 0, (1.1, 1.9, 1.3, 2.2)
        )
        nearby = Placement(
            "service", "functional", 1.215, 2.0546666667, 0, 0, (1.1, 1.9, 1.3, 2.2)
        )
        constraint = {
            "id": "service-window",
            "type": "relativeAnchorWindow",
            "component": "service",
            "referenceComponent": "reference",
            "minDeltaU": 0.208,
            "maxDeltaU": 0.222,
            "minDeltaV": 0.044,
            "maxDeltaV": 0.060,
            "hard": True,
        }

        exact_distance = _relative_anchor_window_target_distance(
            exact, [reference], [constraint]
        )
        nearby_distance = _relative_anchor_window_target_distance(
            nearby, [reference], [constraint]
        )

        self.assertAlmostEqual(exact_distance, 0.0)
        self.assertGreater(nearby_distance, exact_distance)

    def test_relative_anchor_window_injects_its_exact_center_candidate(self):
        footprints = {
            item.component_name: item for item in _read_footprints(semantic_capture())
        }
        semantics = normalize_module_semantics(
            list(footprints), semantic_modules()
        )
        reference = Placement(
            "cleaning", "functional", 0.3, -0.2, 0, 0, (0.1, -0.4, 0.5, 0.0)
        )
        constraint = {
            "id": "calibration-cleaning-window",
            "type": "relativeAnchorWindow",
            "component": "calibration",
            "referenceComponent": "cleaning",
            "minDeltaU": 0.208,
            "maxDeltaU": 0.222,
            "minDeltaV": 0.044,
            "maxDeltaV": 0.060,
            "hard": True,
        }

        candidates = _point_in_region_anchor_candidates(
            footprints["calibration"],
            0,
            [constraint],
            semantics,
            [reference],
            {},
            0.01,
            source_position_independent=True,
            grid_count=13,
        )

        self.assertTrue(
            any(
                abs(anchor_u - 0.515) < 1e-12
                and abs(anchor_v - (-0.148)) < 1e-12
                for anchor_u, anchor_v in candidates
            )
        )

    def test_soft_relative_window_does_not_crop_hard_reach_domain(self):
        footprints = {
            item.component_name: item for item in _read_footprints(semantic_capture())
        }
        semantics = normalize_module_semantics(
            list(footprints), semantic_modules()
        )
        gantry = Placement(
            "gantry", "gantry", 0.0, 0.0, 0.0, 0, (-5.0, -3.0, 5.0, 3.0)
        )
        reference = Placement(
            "cleaning", "functional", 0.3, -0.2, 0, 0, (0.1, -0.4, 0.5, 0.0)
        )
        constraints = [
            {
                "id": "hard-calibration-reach",
                "type": "pointInRegion",
                "pointComponent": "calibration",
                "point": "servicePoint",
                "regionComponent": "gantry",
                "region": "dualValveReach",
                "hard": True,
            },
            {
                "id": "soft-prototype-preference",
                "type": "relativeAnchorWindow",
                "component": "calibration",
                "referenceComponent": "cleaning",
                "minDeltaU": 10.0,
                "maxDeltaU": 10.1,
                "minDeltaV": 10.0,
                "maxDeltaV": 10.1,
                "hard": False,
            },
        ]

        candidates = _point_in_region_anchor_candidates(
            footprints["calibration"],
            0,
            constraints,
            semantics,
            [gantry, reference],
            {},
            0.01,
            source_position_independent=True,
            grid_count=3,
        )

        self.assertTrue(candidates)
        self.assertTrue(all(-4.9 <= u <= 4.9 and -4.9 <= v <= 4.9 for u, v in candidates))
        self.assertEqual(
            _relative_anchor_window_anchors(
                "calibration", [constraints[1]], [reference]
            ),
            (),
        )

    def test_relative_anchor_window_exposes_bounded_portal_event_anchors(self):
        reference = Placement(
            "transport", "transport", 1.25, -0.40, 0, 0, (0.0, -0.5, 1.5, 0.1)
        )
        constraint = {
            "id": "ccd-transport-window",
            "type": "relativeAnchorWindow",
            "component": "ccd",
            "referenceComponent": "transport",
            "minDeltaU": -1.20,
            "maxDeltaU": -1.10,
            "minDeltaV": -0.62,
            "maxDeltaV": -0.54,
            "hard": True,
        }

        anchors = _relative_anchor_window_anchors(
            "ccd", [constraint], [reference]
        )

        self.assertEqual(len(anchors), 9)
        self.assertTrue(
            any(abs(u - 0.10) < 1e-12 and abs(v + 0.98) < 1e-12 for u, v in anchors)
        )
        self.assertTrue(
            any(abs(u - 0.15) < 1e-12 and abs(v + 0.94) < 1e-12 for u, v in anchors)
        )

    def test_candidate_local_refinement_adds_millimeter_scale_event_anchors(self):
        footprints = {
            item.component_name: item for item in _read_footprints(semantic_capture())
        }
        modules = semantic_modules()
        modules["calibration"].setdefault("parameters", {})[
            "candidateLocalRefinementMeters"
        ] = [0.002]
        semantics = normalize_module_semantics(list(footprints), modules)
        constraint = {
            "id": "calibration-window",
            "type": "relativeAnchorWindow",
            "component": "calibration",
            "referenceComponent": "cleaning",
            "minDeltaU": 0.20,
            "maxDeltaU": 0.24,
            "minDeltaV": 0.04,
            "maxDeltaV": 0.08,
            "hard": True,
        }
        reference = Placement(
            "cleaning", "functional", 0.3, -0.2, 0, 0, (0.1, -0.4, 0.5, 0.0)
        )

        candidates = _point_in_region_anchor_candidates(
            footprints["calibration"],
            0,
            [constraint],
            semantics,
            [reference],
            {},
            0.01,
            source_position_independent=True,
            grid_count=3,
        )

        self.assertIn((0.522, -0.14), candidates)

    def test_relative_anchor_exclusion_window_rejects_only_failed_pose_neighborhood(self):
        reference = Placement("reference", "functional", 1.0, 2.0, 0, 0, (0.9, 1.9, 1.1, 2.1))
        failed = Placement("service", "functional", 1.18, 2.15, 0, 0, (1.08, 2.05, 1.28, 2.25))
        repaired = Placement("service", "functional", 1.22, 2.05, 0, 0, (1.12, 1.95, 1.32, 2.15))
        constraint = {
            "id": "failed-brep-pose",
            "type": "relativeAnchorExclusionWindow",
            "component": "service",
            "referenceComponent": "reference",
            "minDeltaU": 0.16,
            "maxDeltaU": 0.20,
            "minDeltaV": 0.12,
            "maxDeltaV": 0.18,
            "hard": True,
        }

        rejected = evaluate_process_constraints(
            [constraint], {}, {}, [reference, failed], {}, "u"
        )
        accepted = evaluate_process_constraints(
            [constraint], {}, {}, [reference, repaired], {}, "u"
        )

        self.assertFalse(rejected["hardFeasible"])
        self.assertTrue(rejected["diagnostics"][0]["measured"]["insideExcludedWindow"])
        self.assertTrue(accepted["hardFeasible"])

    def test_anchor_exclusion_window_rejects_only_failed_absolute_pose_neighborhood(self):
        failed = Placement("service", "functional", 1.18, 2.15, 0, 0, (1.08, 2.05, 1.28, 2.25))
        repaired = Placement("service", "functional", 1.22, 2.05, 0, 0, (1.12, 1.95, 1.32, 2.15))
        constraint = {
            "id": "failed-fixed-environment-pose",
            "type": "anchorExclusionWindow",
            "component": "service",
            "minU": 1.16,
            "maxU": 1.20,
            "minV": 2.12,
            "maxV": 2.18,
            "hard": True,
        }

        rejected = evaluate_process_constraints(
            [constraint], {}, {}, [failed], {}, "u"
        )
        accepted = evaluate_process_constraints(
            [constraint], {}, {}, [repaired], {}, "u"
        )

        self.assertFalse(rejected["hardFeasible"])
        self.assertTrue(rejected["diagnostics"][0]["measured"]["insideExcludedWindow"])
        self.assertTrue(accepted["hardFeasible"])

    def test_line_of_sight_uses_blocker_height_when_endpoint_heights_are_known(self):
        semantics = normalize_module_semantics(
            ["scanner", "transport", "low-blocker"],
            {
                "scanner": {
                    "moduleType": "scanner",
                    "points": {"scanOrigin": {"u": 0, "v": 0}},
                },
                "transport": {
                    "moduleType": "transport",
                    "points": {"barcode": {"u": 0, "v": 0}},
                },
                "low-blocker": {
                    "moduleType": "cleaning",
                    "parameters": {
                        "useOccupancyBoxesForLineOfSight": True,
                        "occupancyBoxesLocal": [
                            {
                                "bounds": [-1, -1, 1, 1],
                                "heightRangeMeters": [0.0, 0.1],
                            }
                        ],
                    },
                },
            },
        )
        placements = [
            Placement("scanner", "functional", 0, 0, 0, 0, (-0.1, -0.1, 0.1, 0.1)),
            Placement("transport", "transport", 10, 0, 0, 0, (9.9, -0.1, 10.1, 0.1)),
            Placement("low-blocker", "functional", 5, 0, 0, 0, (4, -1, 6, 1)),
        ]
        roles = {
            "scanner": "functional",
            "transport": "transport",
            "low-blocker": "functional",
        }
        constraint = {
            "id": "height-aware-los",
            "type": "lineOfSight",
            "sourceComponent": "scanner",
            "sourcePoint": "scanOrigin",
            "targetComponent": "transport",
            "targetPoint": "barcode",
            "sourceHeightMeters": 0.2,
            "targetHeightMeters": 0.2,
            "hard": True,
        }

        height_aware = evaluate_process_constraints(
            [constraint], semantics, {}, placements, roles, "u"
        )
        projected_only = evaluate_process_constraints(
            [
                {
                    key: value
                    for key, value in constraint.items()
                    if key not in {"sourceHeightMeters", "targetHeightMeters"}
                }
            ],
            semantics,
            {},
            placements,
            roles,
            "u",
        )

        self.assertTrue(height_aware["hardFeasible"])
        self.assertTrue(height_aware["diagnostics"][0]["measured"]["heightAware"])
        self.assertFalse(projected_only["hardFeasible"])

    def test_point_distance_uses_point_height_and_module_installation_offset(self):
        semantics = normalize_module_semantics(
            ["scanner", "transport"],
            {
                "scanner": {
                    "moduleType": "scanner",
                    "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
                    "parameters": {
                        "installationNormalOffsetMeters": 0.018,
                        "scanOriginHeightMeters": 0.2368,
                    },
                },
                "transport": {
                    "moduleType": "transport",
                    "points": {"barcode": {"u": 0.04, "v": 0.0}},
                    "parameters": {
                        "installationNormalOffsetMeters": 0.133225,
                        "barcodeHeightMeters": 0.001,
                    },
                },
            },
        )
        placements = [
            Placement("scanner", "functional", 0.0, 0.0, 0.0, 0, (-0.1, -0.1, 0.1, 0.1)),
            Placement("transport", "transport", 0.0, 0.0, 0.0, 0, (-0.1, -0.1, 0.1, 0.1)),
        ]
        constraint = {
            "id": "height-aware-working-distance",
            "type": "pointDistance",
            "sourceComponent": "scanner",
            "sourcePoint": "scanOrigin",
            "targetComponent": "transport",
            "targetPoint": "barcode",
            "minDistanceMeters": 0.05,
            "maxDistanceMeters": 0.35,
            "hard": True,
        }

        result = evaluate_process_constraints(
            [constraint], semantics, {}, placements, {}, "u"
        )
        measured = result["diagnostics"][0]["measured"]

        self.assertTrue(result["hardFeasible"])
        self.assertTrue(measured["heightAware"])
        self.assertAlmostEqual(measured["planarDistanceMeters"], 0.04)
        self.assertAlmostEqual(measured["verticalDistanceMeters"], 0.120575)
        self.assertAlmostEqual(
            measured["distanceMeters"],
            math.hypot(0.04, 0.120575),
        )

    def test_explicit_roles_generate_replay_compatible_layout(self):
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        result = generate_constraint_layout(
            capture(),
            ConstraintLayoutOptions(role_overrides=roles),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["layoutKind"], "constraintGenerated")
        self.assertEqual(result["constraintPlan"]["gantryComponentName"], "gantry")
        self.assertTrue(result["constraintPlan"]["validation"]["success"])
        self.assertEqual(len(result["components"]), 5)
        self.assertTrue(all("layout2d" in item for item in result["components"]))
        self.assertTrue(all("projectedFootprint" in item for item in result["components"]))

    def test_generated_layout_preserves_normal_installation_offset(self):
        data = capture()
        target = next(item for item in data["components"] if item["componentName"] == "function-a")
        target["layout2d"]["normalOffsetMeters"] = 0.042
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }

        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(role_overrides=roles),
        )

        solved = next(
            item for item in result["components"] if item["componentName"] == "function-a"
        )
        self.assertAlmostEqual(solved["layout2d"]["normalOffsetMeters"], 0.042)

    def test_case_anchor_translates_complete_solution_to_source_component_pose(self):
        data = capture()
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        source_transport = next(
            item for item in data["components"] if item["componentName"] == "transport"
        )
        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides=roles,
                source_position_independent=True,
                case_anchor_component_name="transport",
            ),
        )
        solved_transport = next(
            item for item in result["components"] if item["componentName"] == "transport"
        )
        report = result["constraintPlan"]["caseAnchor"]

        self.assertAlmostEqual(
            solved_transport["layout2d"]["x"], source_transport["layout2d"]["x"]
        )
        self.assertAlmostEqual(
            solved_transport["layout2d"]["y"], source_transport["layout2d"]["y"]
        )
        self.assertTrue(report["exactSourcePoseReuse"])
        self.assertFalse(result["constraintPlan"]["requiresAnchorTranslationBeforeReplay"])

    def test_explicit_world_anchor_does_not_read_source_component_position(self):
        data = capture()
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        source_transport = next(
            item for item in data["components"] if item["componentName"] == "transport"
        )
        source_transport["layout2d"]["x"] = 18.0
        source_transport["layout2d"]["y"] = -11.0
        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides=roles,
                source_position_independent=True,
                case_anchor_component_name="transport",
                case_anchor_target_world=(1.25, 0.0, -0.75),
                case_anchor_target_kind="installationFramePoint",
                case_anchor_target_source="unit-test-installation-datum",
            ),
        )
        solved_transport = next(
            item for item in result["components"] if item["componentName"] == "transport"
        )
        report = result["constraintPlan"]["caseAnchor"]

        self.assertAlmostEqual(solved_transport["layout2d"]["x"], 1.25)
        self.assertAlmostEqual(solved_transport["layout2d"]["y"], -0.75)
        self.assertEqual(report["targetKind"], "installationFramePoint")
        self.assertFalse(report["exactSourcePoseReuse"])
        self.assertFalse(report["sourceCapturePoseReadForAnchor"])

    def test_final_process_gate_rejects_constraint_broken_by_case_anchor_translation(self):
        data = capture()
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        common = dict(
            role_overrides=roles,
            source_position_independent=True,
            case_anchor_component_name="transport",
            case_anchor_target_world=(1.25, 0.0, -0.75),
            case_anchor_target_kind="installationFramePoint",
            case_anchor_target_source="unit-test-installation-datum",
        )
        baseline = generate_constraint_layout(data, ConstraintLayoutOptions(**common))
        solved = next(
            item
            for item in baseline["components"]
            if item["componentName"] == "function-a"
        )
        x = float(solved["layout2d"]["x"])
        y = float(solved["layout2d"]["y"])
        translation = baseline["constraintPlan"]["caseAnchor"]["appliedTranslation"]
        self.assertGreater(math.hypot(*translation), 0.01)

        with self.assertRaisesRegex(
            ConstraintLayoutError,
            "Final layout violates hard process constraints",
        ):
            generate_constraint_layout(
                data,
                ConstraintLayoutOptions(
                    **common,
                    process_constraints=(
                        {
                            "id": "post-case-failed-anchor",
                            "type": "anchorExclusionWindow",
                            "component": "function-a",
                            "minU": x - 0.001,
                            "maxU": x + 0.001,
                            "minV": y - 0.001,
                            "maxV": y + 0.001,
                            "hard": True,
                        },
                    ),
                ),
            )

    def test_post_solve_bias_is_applied_to_primary_and_top_k_layouts(self):
        data = capture()
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides=roles,
                source_position_independent=True,
                joint_candidate_search=True,
                maximum_layout_solutions=1,
                module_semantics={
                    "gantry": {
                        "moduleType": "gantry",
                        "parameters": {"postSolveAnchorBiasV": 0.03},
                    }
                },
            ),
        )
        primary = next(
            item for item in result["components"] if item["componentName"] == "gantry"
        )
        top_k = next(
            item
            for item in result["constraintPlan"]["jointSearch"]["solutions"][0][
                "placements"
            ]
            if item["componentName"] == "gantry"
        )

        self.assertAlmostEqual(primary["layout2d"]["x"], top_k["x"])
        self.assertAlmostEqual(primary["layout2d"]["y"], top_k["y"])
        self.assertEqual(
            result["constraintPlan"]["jointSearch"]["solutions"][0][
                "postSolveAnchorBiases"
            ][0]["componentName"],
            "gantry",
        )

    def test_post_case_anchor_bias_moves_only_target_module(self):
        data = capture()
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }
        common = dict(
            role_overrides=roles,
            source_position_independent=True,
            joint_candidate_search=True,
            maximum_layout_solutions=1,
            case_anchor_component_name="transport",
        )
        baseline = generate_constraint_layout(data, ConstraintLayoutOptions(**common))
        biased = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                **common,
                module_semantics={
                    "gantry": {
                        "moduleType": "gantry",
                        "parameters": {"postCaseAnchorBiasV": 0.001},
                    }
                },
            ),
        )
        baseline_by_name = {
            item["componentName"]: item for item in baseline["components"]
        }
        biased_by_name = {
            item["componentName"]: item for item in biased["components"]
        }
        for name in ("transport", "function-a", "function-b", "glue"):
            self.assertAlmostEqual(
                baseline_by_name[name]["layout2d"]["x"],
                biased_by_name[name]["layout2d"]["x"],
            )
            self.assertAlmostEqual(
                baseline_by_name[name]["layout2d"]["y"],
                biased_by_name[name]["layout2d"]["y"],
            )
        self.assertAlmostEqual(
            baseline_by_name["gantry"]["layout2d"]["y"] + 0.001,
            biased_by_name["gantry"]["layout2d"]["y"],
        )
        top_k = next(
            item
            for item in biased["constraintPlan"]["jointSearch"]["solutions"][0][
                "placements"
            ]
            if item["componentName"] == "gantry"
        )
        self.assertAlmostEqual(biased_by_name["gantry"]["layout2d"]["y"], top_k["y"])
        self.assertEqual(
            "gantry",
            biased["constraintPlan"]["postCaseAnchorBiases"][0]["componentName"],
        )

    def test_geometry_heuristic_assigns_all_roles(self):
        result = generate_constraint_layout(
            capture(),
            ConstraintLayoutOptions(role_overrides={}),
        )
        roles = result["constraintPlan"]["roles"]

        self.assertEqual(roles["gantry"], "gantry")
        self.assertEqual(roles["transport"], "transport")
        self.assertEqual(roles["glue"], "glue")
        self.assertEqual(set(roles), {item["componentName"] for item in capture()["components"]})

    def test_seven_component_layout_supports_four_functional_modules(self):
        data = capture()
        data["components"].extend(
            [
                component("function-c", [-1.7, 0.0, -1.8, -0.2, 0.4, -0.8], -0.95, -1.3),
                component("function-d", [0.2, 0.0, 0.8, 1.7, 0.4, 1.8], 0.95, 1.3),
            ]
        )
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "function-c": "functional",
            "function-d": "functional",
            "glue": "glue",
        }

        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(role_overrides=roles, allow_rotation=True),
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["components"]), 7)
        self.assertEqual(
            sum(role == "functional" for role in result["constraintPlan"]["roles"].values()),
            4,
        )
        self.assertTrue(result["constraintPlan"]["validation"]["success"])

    def test_missing_bounding_box_stops_before_replay(self):
        invalid = capture()
        invalid["components"][2].pop("boundingBoxWorld")

        with self.assertRaisesRegex(ConstraintLayoutError, "has no boundingBoxWorld"):
            generate_constraint_layout(invalid, ConstraintLayoutOptions(role_overrides={}))

    def test_oversized_functional_module_uses_documented_containment_relaxation(self):
        data = capture()
        data["components"][2]["boundingBoxWorld"] = [-4.8, 0.0, -2.8, 4.8, 0.4, 2.8]
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }

        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(role_overrides=roles),
        )

        relaxed = result["constraintPlan"]["containmentRelaxedComponents"]
        self.assertIn("function-a", relaxed)
        self.assertTrue(result["constraintPlan"]["validation"]["success"])

    def test_non_gantry_base_component_is_pinned_to_avoid_moving_fixed_first_component(self):
        data = capture()
        data["baseComponentName"] = "function-a"
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }

        result = generate_constraint_layout(data, ConstraintLayoutOptions(role_overrides=roles))
        pinned = next(item for item in result["components"] if item["componentName"] == "function-a")

        self.assertAlmostEqual(pinned["layout2d"]["x"], -0.95)
        self.assertAlmostEqual(pinned["layout2d"]["y"], 1.3)
        self.assertEqual(result["constraintPlan"]["pinnedComponentName"], "function-a")

    def test_portal_component_can_contain_transport_aabb_overlap(self):
        data = capture()
        data["components"][2]["boundingBoxWorld"] = [-4.5, 0.0, -1.5, 4.5, 2.0, 1.5]
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }

        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides=roles,
                portal_pass_through={"function-a": ("transport",)},
            ),
        )

        plan = result["constraintPlan"]
        portal = next(item for item in result["components"] if item["componentName"] == "function-a")
        self.assertFalse(portal["constraintPlacement"]["containmentRelaxed"])
        self.assertEqual(plan["portalConstraints"][0]["portalComponentName"], "function-a")
        self.assertIn(
            ["transport", "function-a"],
            plan["validation"]["allowedAabbOverlapPairs"],
        )
        self.assertTrue(plan["validation"]["requiresCadInterferenceValidation"])
        self.assertTrue(plan["validation"]["success"])

    def test_portal_rejects_pass_through_larger_than_estimated_opening(self):
        data = capture()
        data["components"][2]["boundingBoxWorld"] = [-4.5, 0.0, -1.5, 4.5, 2.0, 1.5]
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "function-b": "functional",
            "glue": "glue",
        }

        with self.assertRaisesRegex(ConstraintLayoutError, "wider than the estimated opening"):
            generate_constraint_layout(
                data,
                ConstraintLayoutOptions(
                    role_overrides=roles,
                    portal_pass_through={"function-a": ("transport",)},
                    portal_opening_width_ratio=0.1,
                ),
            )

    def test_transport_sweep_rejects_source_overlap_and_moves_hard_body(self):
        data = capture()
        data["components"] = [
            item for item in data["components"] if item["componentName"] != "function-b"
        ]
        moving = next(
            item for item in data["components"] if item["componentName"] == "function-a"
        )
        moving["layout2d"]["y"] = 0.0
        moving["bottomCenterWorld"][2] = 0.0
        moving["boundingBoxWorld"] = [-1.7, 0.0, -0.5, -0.2, 0.4, 0.5]
        roles = {
            "gantry": "gantry",
            "transport": "transport",
            "function-a": "functional",
            "glue": "glue",
        }
        semantics = {
            "transport": {
                "moduleType": "transport",
                "parameters": {
                    "transportSweepBoundsLocal": [-5.2, -0.45, 5.2, 0.45],
                    "transportSweepHeightRangeMeters": [0.0, 0.5],
                },
            },
            "function-a": {
                "moduleType": "calibration",
                "parameters": {
                    "avoidTransportSweep": True,
                    "resolveTransportProjectionWithInteractionEnvelope": True,
                },
            },
        }

        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides=roles,
                module_semantics=semantics,
                auto_generate_process_constraints=False,
                prefer_source_layout=True,
            ),
        )

        moved = next(
            item for item in result["components"] if item["componentName"] == "function-a"
        )
        transport = next(
            item for item in result["components"] if item["componentName"] == "transport"
        )
        self.assertNotAlmostEqual(moved["layout2d"]["y"], 0.0)
        self.assertEqual(moved["hardBodyEnvelope"]["source"], "fullAabbBody")
        self.assertEqual(
            transport["transportSweepEnvelope"]["source"],
            "semanticTransportSweepBounds",
        )
        sweep_diagnostics = [
            item
            for item in result["constraintPlan"]["interactionValidation"]["diagnostics"]
            if item["type"] == "transportSweepClearance"
        ]
        self.assertEqual(len(sweep_diagnostics), 1)
        self.assertTrue(sweep_diagnostics[0]["success"])
        self.assertEqual(
            sweep_diagnostics[0]["resolution"],
            "separatedTransportSweepAndHardBody",
        )

    def test_semantic_modules_generate_and_validate_process_hard_constraints(self):
        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(
                role_overrides={},
                module_semantics=semantic_modules(),
                auto_generate_process_constraints=True,
            ),
        )

        plan = result["constraintPlan"]
        validation = plan["processValidation"]
        self.assertTrue(validation["hardFeasible"])
        self.assertGreaterEqual(validation["constraintCount"], 12)
        self.assertEqual(validation["hardFailureCount"], 0)
        self.assertTrue(plan["validation"]["processHardFeasible"])
        self.assertEqual(plan["roles"]["scanner"], "functional")
        self.assertEqual(plan["moduleSemantics"]["ccd"]["moduleType"], "ccd")

    def test_provisional_weighing_placeholder_is_explicit_and_process_constrained(self):
        data = semantic_capture()
        data["components"] = [
            item for item in data["components"] if item["componentName"] != "weighing"
        ]
        semantics = semantic_modules()
        semantics["gantry"]["regions"]["dualValveReach"] = {
            "minU": -5.0,
            "minV": -3.0,
            "maxU": 5.0,
            "maxV": 3.0,
        }
        semantics["weighing"]["points"]["servicePoint"] = {"u": 0.0, "v": -0.15}
        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides={},
                module_semantics=semantics,
                auto_generate_process_constraints=True,
                provisional_components=(
                    {
                        "componentName": "weighing",
                        "widthMeters": 0.22,
                        "depthMeters": 0.22,
                        "heightMeters": 0.20,
                        "anchorU": -1.6,
                        "anchorV": -2.2,
                        "reason": "No verified WKC204C CAD.",
                        "replayable": False,
                    },
                ),
            ),
        )

        placeholder = next(item for item in result["components"] if item["componentName"] == "weighing")
        plan = result["constraintPlan"]
        self.assertTrue(result["provisional"])
        self.assertTrue(placeholder["isProvisionalPlaceholder"])
        self.assertFalse(placeholder["provisionalPlaceholder"]["replayable"])
        self.assertEqual(plan["provisionalPlaceholderCount"], 1)
        self.assertTrue(plan["assumptionWarnings"])
        self.assertFalse(plan["validation"]["productionReady"])
        self.assertTrue(plan["processValidation"]["hardFeasible"])
        self.assertTrue(
            any(
                item["type"] == "pointInRegion" and item.get("pointComponent") == "weighing"
                for item in plan["processConstraints"]
            )
        )

    def test_service_region_adds_dedicated_service_zone_constraint(self):
        semantics_raw = semantic_modules()
        semantics_raw["gantry"]["regions"]["calibrationServiceZone"] = {
            "minU": -1.0,
            "minV": -1.0,
            "maxU": 1.0,
            "maxV": 1.0,
        }
        semantics_raw["calibration"]["parameters"] = {
            "serviceRegion": "calibrationServiceZone"
        }
        semantics = normalize_module_semantics(
            list(semantics_raw),
            semantics_raw,
        )
        constraints = compile_process_constraints(
            list(semantics_raw),
            semantics,
            {
                name: ("gantry" if name == "gantry" else "transport" if name == "transport" else "functional")
                for name in semantics_raw
            },
            "gantry",
            "u",
            (),
            True,
            0.01,
        )
        service_zone = next(
            item
            for item in constraints
            if item["id"] == "auto-calibration-service-zone-calibration-calibrationServiceZone"
        )
        self.assertEqual(service_zone["type"], "pointInRegion")
        self.assertEqual(service_zone["region"], "calibrationServiceZone")

    def test_provisional_placeholder_cannot_shadow_real_component(self):
        with self.assertRaisesRegex(ConstraintLayoutError, "conflicts with an existing geometry component"):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(
                    role_overrides={},
                    provisional_components=(
                        {
                            "componentName": "weighing",
                            "widthMeters": 0.22,
                            "depthMeters": 0.22,
                            "heightMeters": 0.20,
                        },
                    ),
                ),
            )

    def test_provisional_semantic_parameters_disable_production_ready(self):
        semantics = semantic_modules()
        semantics["scanner"]["parameters"]["provisional"] = True
        semantics["scanner"]["parameters"]["assumptionReason"] = "scan origin is estimated"

        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(role_overrides={}, module_semantics=semantics),
        )

        plan = result["constraintPlan"]
        self.assertTrue(result["provisional"])
        self.assertEqual(plan["provisionalPlaceholderCount"], 0)
        self.assertEqual(plan["provisionalSemanticCount"], 1)
        self.assertFalse(plan["validation"]["productionReady"])
        self.assertIn("scan origin is estimated", plan["assumptionWarnings"][0])

    def test_scanner_missing_working_distance_is_configuration_error(self):
        semantics = semantic_modules()
        del semantics["scanner"]["parameters"]["maxWorkingDistanceMeters"]

        with self.assertRaisesRegex(ConstraintLayoutError, "maxWorkingDistanceMeters"):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(role_overrides={}, module_semantics=semantics),
            )

    def test_scanner_minimum_working_distance_prevents_zero_length_scan(self):
        semantics = semantic_modules()
        semantics["scanner"]["parameters"]["minWorkingDistanceMeters"] = 0.1

        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(
                role_overrides={},
                module_semantics=semantics,
                source_position_independent=True,
            ),
        )

        diagnostic = next(
            item
            for item in result["constraintPlan"]["processValidation"]["diagnostics"]
            if item["id"].startswith("auto-scanner-distance-")
        )
        self.assertTrue(diagnostic["success"])
        self.assertGreaterEqual(diagnostic["measured"]["distanceMeters"], 0.1 - 1e-9)

    def test_scanner_directed_axis_uses_source_to_barcode_vector(self):
        raw = {
            "scanner": {
                "moduleType": "scanner",
                "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
                "parameters": {
                    "scanOriginHeightMeters": 0.2,
                    "maxWorkingDistanceMeters": 10.0,
                    "barcodeSide": "high",
                    "opticalAxisDirectionLocal": [1.0, 0.0, -1.0],
                    "maxOpticalAxisDeviationDegrees": 20.0,
                },
            },
            "transport": {
                "moduleType": "transport",
                "points": {"barcode": {"u": 0.0, "v": 0.0}},
                "parameters": {"barcodeHeightMeters": 0.0},
            },
        }
        semantics = normalize_module_semantics(list(raw), raw)
        constraints = compile_process_constraints(
            list(raw),
            semantics,
            {"scanner": "functional", "transport": "transport"},
            "gantry",
            "u",
            (),
            True,
            0.01,
        )
        placements = [
            Placement("scanner", "functional", 0.0, 0.0, 0.0, 0, (-0.1, -0.1, 0.1, 0.1)),
            Placement("transport", "transport", 0.2, 0.0, 0.0, 0, (0.1, -0.1, 0.3, 0.1)),
        ]
        result = evaluate_process_constraints(
            constraints,
            semantics,
            {},
            placements,
            {"scanner": "functional", "transport": "transport"},
            "u",
        )

        diagnostic = next(
            item for item in result["diagnostics"] if item["type"] == "directedPointing"
        )
        self.assertTrue(diagnostic["success"])
        self.assertLessEqual(
            diagnostic["measured"]["deviationDegrees"],
            diagnostic["measured"]["maxDeviationDegrees"],
        )

    def test_scanner_directed_axis_rejects_opposite_direction(self):
        semantics = normalize_module_semantics(
            ["scanner", "transport"],
            {
                "scanner": {
                    "moduleType": "scanner",
                    "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
                    "parameters": {"scanOriginHeightMeters": 0.2},
                },
                "transport": {
                    "moduleType": "transport",
                    "points": {"barcode": {"u": 0.0, "v": 0.0}},
                    "parameters": {"barcodeHeightMeters": 0.0},
                },
            },
        )
        placements = [
            Placement("scanner", "functional", 0.0, 0.0, 0.0, 0, (-0.1, -0.1, 0.1, 0.1)),
            Placement("transport", "transport", 1.0, 0.0, 0.0, 0, (0.9, -0.1, 1.1, 0.1)),
        ]
        validation = evaluate_process_constraints(
            [
                {
                    "id": "opposite-axis",
                    "type": "directedPointing",
                    "sourceComponent": "scanner",
                    "sourcePoint": "scanOrigin",
                    "targetComponent": "transport",
                    "targetPoint": "barcode",
                    "expectedDirectionLocal": [-1.0, 0.0, 0.0],
                    "maxDeviationDegrees": 10.0,
                    "sourceHeightMeters": 0.2,
                    "targetHeightMeters": 0.0,
                    "hard": True,
                }
            ],
            semantics,
            {},
            placements,
            {"scanner": "functional", "transport": "transport"},
            "u",
        )
        self.assertFalse(validation["hardFeasible"])
        self.assertGreater(
            validation["diagnostics"][0]["measured"]["deviationDegrees"],
            90.0,
        )

    def test_scanner_dynamic_stop_window_generates_robust_endpoint_constraints(self):
        raw = {
            "scanner": {
                "moduleType": "scanner",
                "points": {"scanOrigin": {"u": 0.0, "v": 0.0}},
                "parameters": {
                    "scanOriginHeightMeters": 0.2,
                    "minWorkingDistanceMeters": 0.1,
                    "maxWorkingDistanceMeters": 0.5,
                    "barcodeSide": "high",
                    "opticalAxisDirectionLocal": [1.0, 0.0, -1.0],
                    "maxOpticalAxisDeviationDegrees": 20.0,
                },
            },
            "transport": {
                "moduleType": "transport",
                "points": {
                    "barcode": {"u": 0.0, "v": 0.0},
                    "barcodeStopLowU": {"u": -0.005, "v": 0.0},
                    "barcodeStopHighU": {"u": 0.005, "v": 0.0},
                },
                "parameters": {
                    "barcodeHeightMeters": 0.0,
                    "dynamicScanWindowPointNames": [
                        "barcodeStopLowU",
                        "barcodeStopHighU",
                    ],
                    "dynamicScanWindowAcceptedForCoarseLayout": True,
                },
            },
        }
        semantics = normalize_module_semantics(list(raw), raw)

        constraints = compile_process_constraints(
            list(raw),
            semantics,
            {"scanner": "functional", "transport": "transport"},
            "gantry",
            "u",
            (),
            True,
            0.01,
        )

        dynamic = [
            item for item in constraints if item["id"].startswith("auto-scanner-dynamic-")
        ]
        self.assertEqual(len(dynamic), 6)
        self.assertEqual(
            {item["type"] for item in dynamic},
            {"pointDistance", "lineOfSight", "directedPointing"},
        )
        self.assertEqual(
            {item["targetPoint"] for item in dynamic},
            {"barcodeStopLowU", "barcodeStopHighU"},
        )

    def test_moving_axis_ccd_uses_coverage_without_fixed_origin_line_of_sight(self):
        semantics = semantic_modules()
        semantics["ccd"]["regions"] = {
            "fieldOfView": {"minU": -5.0, "minV": -3.0, "maxU": 5.0, "maxV": 3.0}
        }
        semantics["ccd"]["parameters"] = {"movingAxisCoverage": True}

        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(role_overrides={}, module_semantics=semantics),
        )

        ccd_constraints = [
            item
            for item in result["constraintPlan"]["processConstraints"]
            if item["id"].startswith("auto-ccd-")
        ]
        self.assertTrue(any(item["type"] == "pointInRegion" for item in ccd_constraints))
        self.assertFalse(any(item["type"] == "lineOfSight" for item in ccd_constraints))

    def test_cleaning_can_isolate_service_points_for_portal_style_ccd(self):
        semantics = semantic_modules()
        semantics["cleaning"]["parameters"] = {
            "isolationClearanceMeters": 0.005,
            "isolationMode": "servicePoints",
        }

        result = generate_constraint_layout(
            semantic_capture(),
            ConstraintLayoutOptions(role_overrides={}, module_semantics=semantics),
        )

        isolation = [
            item
            for item in result["constraintPlan"]["processConstraints"]
            if item["id"].startswith("auto-cleaning-isolation-")
        ]
        self.assertEqual(len(isolation), 2)
        self.assertTrue(all(item["type"] == "pointDistance" for item in isolation))

    def test_explicit_process_constraint_failure_blocks_layout(self):
        semantics = semantic_modules()
        with self.assertRaisesRegex(
            ConstraintLayoutError,
            "(?:Process hard constraints failed|hard process constraints)",
        ):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(
                    role_overrides={},
                    module_semantics=semantics,
                    auto_generate_process_constraints=False,
                    process_constraints=(
                        {
                            "id": "impossible-scanner-distance",
                            "type": "pointDistance",
                            "sourceComponent": "scanner",
                            "sourcePoint": "scanOrigin",
                            "targetComponent": "transport",
                            "targetPoint": "barcode",
                            "maxDistanceMeters": 0.001,
                            "hard": True,
                        },
                    ),
                ),
            )

    def test_joint_search_failure_reports_process_constraint_ids(self):
        semantics = semantic_modules()
        with self.assertRaisesRegex(
            ConstraintLayoutError,
            "processConstraintFailureCounts=.*impossible-ccd-gantry-clearance",
        ):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(
                    role_overrides={},
                    module_semantics=semantics,
                    source_position_independent=True,
                    joint_candidate_search=True,
                    joint_candidate_limit=4,
                    auto_generate_process_constraints=False,
                    process_constraints=(
                        {
                            "id": "impossible-ccd-gantry-clearance",
                            "type": "moduleClearance",
                            "firstComponent": "ccd",
                            "secondComponent": "gantry",
                            "minDistanceMeters": 100.0,
                            "hard": True,
                        },
                    ),
                ),
            )

    def test_semantic_role_conflict_is_rejected(self):
        with self.assertRaisesRegex(ConstraintLayoutError, "conflicting role"):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(
                    role_overrides={"scanner": "glue"},
                    module_semantics=semantic_modules(),
                ),
            )

    def test_reach_region_outside_gantry_is_rejected_before_layout(self):
        semantics = semantic_modules()
        semantics["gantry"]["regions"]["dualValveReach"] = {
            "minU": -8.0,
            "minV": -2.0,
            "maxU": 1.0,
            "maxV": 2.0,
        }

        with self.assertRaisesRegex(ConstraintLayoutError, "valve reach extends outside"):
            generate_constraint_layout(
                semantic_capture(),
                ConstraintLayoutOptions(role_overrides={}, module_semantics=semantics),
            )

    def test_source_aware_layout_preserves_valid_prototype_positions(self):
        data = semantic_capture()
        result = generate_constraint_layout(
            data,
            ConstraintLayoutOptions(
                role_overrides={},
                module_semantics=semantic_modules(),
                prefer_source_layout=True,
                minimum_transport_gantry_overlap_ratio=0.9,
                minimum_functional_gantry_overlap_ratio=0.5,
            ),
        )

        source = {
            item["componentName"]: item["layout2d"]
            for item in data["components"]
        }
        for item in result["components"]:
            expected = source[item["componentName"]]
            self.assertAlmostEqual(item["layout2d"]["x"], expected["x"])
            self.assertAlmostEqual(item["layout2d"]["y"], expected["y"])
        plan = result["constraintPlan"]
        self.assertTrue(plan["preferSourceLayout"])
        self.assertTrue(plan["reachValidation"]["hardFeasible"])
        self.assertTrue(plan["spatialValidation"]["hardFeasible"])

    def test_source_position_independent_layout_ignores_perturbed_source_anchors(self):
        options = ConstraintLayoutOptions(
            role_overrides={},
            module_semantics=semantic_modules(),
            source_position_independent=True,
            minimum_transport_gantry_overlap_ratio=0.5,
            minimum_functional_gantry_overlap_ratio=0.0,
        )
        first = generate_constraint_layout(
            perturb_component_positions(semantic_capture(), 1.0),
            options,
        )
        second = generate_constraint_layout(
            perturb_component_positions(semantic_capture(), -1.7),
            options,
        )

        first_layout = {
            item["componentName"]: item["layout2d"] for item in first["components"]
        }
        second_layout = {
            item["componentName"]: item["layout2d"] for item in second["components"]
        }
        for name, layout in first_layout.items():
            self.assertAlmostEqual(layout["x"], second_layout[name]["x"])
            self.assertAlmostEqual(layout["y"], second_layout[name]["y"])
            self.assertAlmostEqual(
                layout["thetaDegrees"], second_layout[name]["thetaDegrees"]
            )

        plan = first["constraintPlan"]
        self.assertTrue(plan["sourcePositionIndependent"])
        self.assertFalse(plan["preferSourceLayout"])
        self.assertIsNone(plan["pinnedComponentName"])
        self.assertTrue(plan["processValidation"]["hardFeasible"])
        self.assertTrue(plan["spatialValidation"]["hardFeasible"])

    def test_joint_search_time_budget_is_reported_as_timeout_not_infeasible(self):
        options = ConstraintLayoutOptions(
            role_overrides={},
            module_semantics=semantic_modules(),
            source_position_independent=True,
            joint_candidate_search=True,
            joint_candidate_limit=2,
            maximum_layout_solutions=1,
            joint_search_time_limit_seconds=0.5,
        )

        with patch(
            "demo_backend.constraint_layout.time.perf_counter",
            side_effect=[0.0, 1.0, 1.0, 1.0],
        ):
            with self.assertRaisesRegex(
                ConstraintLayoutSearchTimeout,
                "not proof that the layout is infeasible",
            ):
                generate_constraint_layout(semantic_capture(), options)

    def test_joint_search_failure_does_not_repeat_legacy_outside_fallback(self):
        options = ConstraintLayoutOptions(
            role_overrides={},
            module_semantics=semantic_modules(),
            source_position_independent=True,
            joint_candidate_search=True,
            margin_ratios=(0.0,),
        )

        with patch(
            "demo_backend.constraint_layout._solve_with_margin",
            side_effect=ConstraintLayoutError("joint-search-failed"),
        ) as solve:
            with self.assertRaisesRegex(
                ConstraintLayoutError,
                "joint-search-failed",
            ):
                generate_constraint_layout(semantic_capture(), options)

        self.assertEqual(solve.call_count, 1)

    def test_collision_partner_codes_only_activate_recorded_component_pair(self):
        first = [
            {
                "id": "a-active-leaf",
                "bounds": (0.0, 0.0, 1.0, 1.0),
                "heightRangeMeters": (0.0, 1.0),
                "componentCode": "A100",
                "collisionPartnerCodes": ["A200"],
            }
        ]
        unrelated = [
            {
                "id": "unrelated-leaf",
                "bounds": (0.0, 0.0, 1.0, 1.0),
                "heightRangeMeters": (0.0, 1.0),
                "componentCode": "A700",
                "collisionPartnerCodes": ["A100"],
            }
        ]
        recorded_partner = [
            {
                "id": "recorded-leaf",
                "bounds": (0.0, 0.0, 1.0, 1.0),
                "heightRangeMeters": (0.0, 1.0),
                "componentCode": "A200",
                "collisionPartnerCodes": ["A100"],
            }
        ]

        self.assertEqual(_overlapping_envelope_pairs(first, unrelated, 0.0), [])
        self.assertEqual(_eligible_envelope_pair_count(first, unrelated), 0)
        self.assertEqual(
            len(_overlapping_envelope_pairs(first, recorded_partner, 0.0)),
            1,
        )
        self.assertEqual(_eligible_envelope_pair_count(first, recorded_partner), 1)

    def test_collision_responsibility_key_prunes_only_same_box_axis_and_lane(self):
        parent = Placement(
            "A200",
            "functional",
            0.0,
            0.0,
            0.0,
            0,
            (0.0, 0.0, 1.0, 1.0),
        )
        validation = {
            "diagnostics": [
                {
                    "hard": True,
                    "success": False,
                    "firstComponent": "A100",
                    "secondComponent": "A200",
                    "resolution": "leafBodyOccupancyBoxCollision",
                    "collidingBoxPairs": [
                        {"firstBox": "frame-1", "secondBox": "camera-2"}
                    ],
                }
            ]
        }
        same_lane_first = Placement(
            "A200", "functional", 0.10, 0.0040, 0.0, 0, (0.10, 0.0040, 1.10, 1.0040)
        )
        same_lane_second = Placement(
            "A200", "functional", 0.20, 0.0041, 0.0, 0, (0.20, 0.0041, 1.20, 1.0041)
        )
        different_lane = Placement(
            "A200", "functional", 0.20, 0.025, 0.0, 0, (0.20, 0.025, 1.20, 1.025)
        )
        opposite_direction = Placement(
            "A200", "functional", -0.10, 0.0040, 0.0, 0, (-0.10, 0.0040, 0.90, 1.0040)
        )

        first_key = _collision_responsibility_key(
            validation, parent, same_lane_first
        )
        second_key = _collision_responsibility_key(
            validation, parent, same_lane_second
        )
        different_key = _collision_responsibility_key(
            validation, parent, different_lane
        )
        opposite_key = _collision_responsibility_key(
            validation, parent, opposite_direction
        )

        self.assertEqual(first_key, second_key)
        self.assertNotEqual(first_key, different_key)
        self.assertNotEqual(first_key, opposite_key)

    def test_candidate_process_validation_only_rechecks_affected_constraints(self):
        placed = [
            Placement("A", "functional", 0.0, 0.0, 0.0, 0, (0.0, 0.0, 1.0, 1.0)),
            Placement("B", "functional", 2.0, 0.0, 0.0, 0, (2.0, 0.0, 3.0, 1.0)),
        ]
        candidate = Placement(
            "C", "functional", 4.0, 0.0, 0.0, 0, (4.0, 0.0, 5.0, 1.0)
        )
        constraints = [
            {
                "id": "historical-clearance",
                "type": "moduleClearance",
                "firstComponent": "A",
                "secondComponent": "B",
                "minDistanceMeters": 0.1,
            },
            {
                "id": "candidate-clearance",
                "type": "moduleClearance",
                "firstComponent": "A",
                "secondComponent": "C",
                "minDistanceMeters": 0.1,
            },
            {
                "id": "candidate-implicit-blocker",
                "type": "lineOfSight",
                "sourceComponent": "A",
                "sourcePoint": "p",
                "targetComponent": "B",
                "targetPoint": "p",
            },
            {
                "id": "unrelated-configured-blocker",
                "type": "lineOfSight",
                "sourceComponent": "A",
                "sourcePoint": "p",
                "targetComponent": "B",
                "targetPoint": "p",
                "blockerComponents": ["D"],
            },
        ]
        captured: list[str] = []

        def evaluate(applicable, *_args, **_kwargs):
            captured.extend(item["id"] for item in applicable)
            return {"hardFeasible": True}

        with patch(
            "demo_backend.constraint_layout.evaluate_process_constraints",
            side_effect=evaluate,
        ):
            result = _candidate_process_validation(
                candidate,
                placed,
                constraints,
                {},
                {},
                {"A": "functional", "B": "functional", "C": "functional"},
                "u",
            )

        self.assertTrue(result["hardFeasible"])
        self.assertEqual(
            captured,
            ["candidate-clearance", "candidate-implicit-blocker"],
        )

    def test_source_independent_glue_search_uses_interaction_gate(self):
        data = capture()
        data["components"] = [
            item
            for item in data["components"]
            if item["componentName"] in {"gantry", "transport", "glue"}
        ]
        glue_trials: list[float] = []

        def interaction_gate(candidate, *_args, **_kwargs):
            if candidate.role != "glue":
                return True
            glue_trials.append(candidate.anchor_u)
            return len(glue_trials) >= 2

        with patch(
            "demo_backend.constraint_layout._candidate_interaction_feasible",
            side_effect=interaction_gate,
        ):
            result = generate_constraint_layout(
                data,
                ConstraintLayoutOptions(
                    role_overrides={
                        "gantry": "gantry",
                        "transport": "transport",
                        "glue": "glue",
                    },
                    module_semantics={
                        "glue": {
                            "moduleType": "glue_supply",
                            "preferredSide": "low",
                            "allowedRotationDegrees": [0],
                            "parameters": {"preferredLongAxisFraction": 0.5},
                        }
                    },
                    source_position_independent=True,
                    auto_generate_process_constraints=False,
                ),
            )

        self.assertGreaterEqual(len(glue_trials), 2)
        self.assertNotAlmostEqual(glue_trials[0], glue_trials[1])
        self.assertTrue(result["constraintPlan"]["interactionValidation"]["hardFeasible"])


if __name__ == "__main__":
    unittest.main()
