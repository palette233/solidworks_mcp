from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from demo_backend.project02_ablation import (
    build_ablation_request,
    build_geometry_only_occupancy,
    compare_rank1_poses,
    load_dependency_ablation_bundle,
)


class Project02AblationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {
            "structuralOccupancyPath": "v42.json",
            "moduleSemantics": {
                "A300": {
                    "parameters": {
                        "sourceIndependentAnchorBiasU": 0.1,
                        "candidateLocalRefinementMeters": [0.001],
                    }
                }
            },
            "processConstraints": [
                {
                    "id": "a300-a700-coarse-service-cluster-envelope",
                    "type": "relativeAnchorWindow",
                    "retainInReducedPrototype": True,
                },
                {
                    "id": "a180-a200-scanner-ccd-channel-window",
                    "type": "relativeAnchorWindow",
                    "retainInReducedPrototype": True,
                },
            ],
        }

    def test_variants_do_not_mutate_source_and_have_explicit_dependency_layers(self) -> None:
        original = copy.deepcopy(self.request)
        variant_a, _ = build_ablation_request(self.request, "A")
        variant_b, _ = build_ablation_request(
            self.request, "B", geometry_occupancy_path="geometry.json"
        )
        variant_c, metadata = build_ablation_request(
            self.request, "C", geometry_occupancy_path="geometry.json"
        )
        self.assertEqual(self.request, original)
        self.assertIn("structuralOccupancyPath", variant_a)
        self.assertEqual(variant_b["structuralOccupancyPath"], "geometry.json")
        self.assertNotIn("sourceIndependentAnchorBiasU", variant_c["moduleSemantics"]["A300"]["parameters"])
        self.assertIn("candidateLocalRefinementMeters", variant_c["moduleSemantics"]["A300"]["parameters"])
        ids = [item["id"] for item in variant_c["processConstraints"]]
        self.assertNotIn("a300-a700-coarse-service-cluster-envelope", ids)
        self.assertIn("a180-a200-scanner-ccd-channel-window", ids)
        self.assertIn("a300-a700-coarse-service-cluster-envelope", metadata["removedConstraintIds"])

    def test_pose_comparison_detects_material_change(self) -> None:
        def preview(x: float) -> dict:
            return {
                "solutions": [
                    {
                        "rank": 1,
                        "modules": [
                            {
                                "componentName": "FL9A24D062A300.001-1",
                                "center": [x, 0.0],
                                "thetaDegrees": 0.0,
                            }
                        ],
                    }
                ]
            }

        comparison = compare_rank1_poses(preview(0.03), preview(0.0))
        self.assertTrue(comparison["materiallyDifferent"])
        self.assertAlmostEqual(comparison["maximumCenterDistanceMeters"], 0.03)

    def test_display_bundle_includes_optional_collision_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            base = workspace / "demo/layout_previews"
            ablation = base / "project02_dependency_ablation"
            feedback = base / "project02_collision_feedback"
            ablation.mkdir(parents=True)
            feedback.mkdir(parents=True)
            (base / "project02_dependency_ablation_report.json").write_text(
                json.dumps({"experiments": []}), encoding="utf-8"
            )
            (ablation / "variant_c_preview.json").write_text(
                json.dumps({"solutions": []}), encoding="utf-8"
            )
            (feedback / "feedback_hardened_report.json").write_text(
                json.dumps({"success": True}), encoding="utf-8"
            )
            (feedback / "feedback_hardened_preview.json").write_text(
                json.dumps({"solutions": [{"rank": 1}]}), encoding="utf-8"
            )
            bundle = load_dependency_ablation_bundle(workspace)
            self.assertEqual(bundle["schemaVersion"], "project02-dependency-ablation-display/v2")
            self.assertTrue(bundle["collisionFeedback"]["report"]["success"])
            self.assertEqual(bundle["collisionFeedback"]["preview"]["solutions"][0]["rank"], 1)

    def test_geometry_variants_remove_forced_hard_conflict_with_conditional_brep(self) -> None:
        request = {
            "structuralOccupancyPath": "v42.json",
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [["A300", "A800"]]
            },
            "moduleSemantics": {
                "FL9A24D062A300.001-1": {
                    "parameters": {
                        "hardOccupancyClearanceWith": [
                            "FL9A24D062A800.001-1",
                            "T401AA-07388-0-1",
                        ]
                    }
                }
            },
        }
        variant, metadata = build_ablation_request(
            request, "B", geometry_occupancy_path="geometry.json"
        )
        self.assertEqual(
            variant["moduleSemantics"]["FL9A24D062A300.001-1"]["parameters"][
                "hardOccupancyClearanceWith"
            ],
            ["T401AA-07388-0-1"],
        )
        self.assertTrue(
            any("conditional-brep-conflicts-removed" in item for item in metadata["removedFields"])
        )

    def test_geometry_variants_downgrade_only_unconfirmed_operator_access(self) -> None:
        request = {
            "structuralOccupancyPath": "v42.json",
            "staticCollisionPolicy": {
                "brepOnAabbOverlapPairs": [["A700", "A200"]]
            },
            "moduleSemantics": {
                "A700": {
                    "parameters": {
                        "serviceAccessLaneConfirmed": False,
                        "protectedSpaceBoxesLocal": [
                            {
                                "id": "cleaning-vertical-service-approach",
                                "hardClearanceWith": ["A200"],
                            },
                            {"id": "cleaning-operator-access"},
                        ],
                    }
                }
            },
        }
        variant, metadata = build_ablation_request(
            request, "B", geometry_occupancy_path="geometry.json"
        )
        spaces = variant["moduleSemantics"]["A700"]["parameters"][
            "protectedSpaceBoxesLocal"
        ]
        self.assertNotIn("enforcement", spaces[0])
        self.assertEqual(spaces[0]["conditionalBrepWith"], ["A200"])
        self.assertEqual(spaces[1]["enforcement"], "advisory")
        self.assertFalse(spaces[1]["confirmed"])
        self.assertTrue(any("hard-to-advisory" in item for item in metadata["removedFields"]))

    def test_geometry_only_occupancy_groups_bodies_without_partner_history(self) -> None:
        geometry = {
            "baseFrame": {
                "origin": [0, 0, 0],
                "uAxis": [1, 0, 0],
                "vAxis": [0, 1, 0],
                "normal": [0, 0, 1],
            },
            "components": [
                {"componentName": "FL9A24D062A300.001-1", "layout2d": {"x": 0, "y": 0, "thetaDegrees": 0}}
            ],
        }
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": "FL9A24D062A300.001-1"},
                    "BodyCount": 2,
                    "Bodies": [
                        {"Component": {"Name": "FL9A24D062A300.001-1/child-1/part-1"}, "BoundingBoxWorld": [0, 0, 0, 1, 1, 1]},
                        {"Component": {"Name": "FL9A24D062A300.001-1/child-1/part-2"}, "BoundingBoxWorld": [1, 1, 0, 2, 2, 1]},
                    ],
                }
            ]
        }
        layout = {"components": geometry["components"]}
        result = build_geometry_only_occupancy(geometry, [(capture, layout, "capture.json")])
        boxes = result["components"]["FL9A24D062A300.001-1"]["boxes"]
        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0]["bounds"], [0.0, 0.0, 1.0, 1.0])
        self.assertNotIn("collisionPartnerCodes", boxes[0])

    def test_geometry_only_occupancy_preserves_open_structures_but_compresses_transport(self) -> None:
        names = ["FL9A24D062A100.001-1", "FL9A24D062A800.001-1"]
        geometry = {
            "baseFrame": {
                "origin": [0, 0, 0],
                "uAxis": [1, 0, 0],
                "vAxis": [0, 1, 0],
                "normal": [0, 0, 1],
            },
            "components": [
                {
                    "componentName": name,
                    "layout2d": {"x": 0, "y": 0, "thetaDegrees": 0},
                }
                for name in names
            ],
        }
        capture = {
            "captures": [
                {
                    "TopLevelComponent": {"Name": name},
                    "BodyCount": 2,
                    "Bodies": [
                        {
                            "Component": {"Name": f"{name}/child-1/part-1"},
                            "BoundingBoxWorld": [0, 0, 0, 1, 1, 1],
                        },
                        {
                            "Component": {"Name": f"{name}/child-1/part-2"},
                            "BoundingBoxWorld": [2, 2, 0, 3, 3, 1],
                        },
                    ],
                }
                for name in names
            ]
        }
        layout = {"components": geometry["components"]}
        result = build_geometry_only_occupancy(geometry, [(capture, layout, "capture.json")])
        self.assertEqual(len(result["components"][names[0]]["boxes"]), 2)
        self.assertEqual(len(result["components"][names[1]]["boxes"]), 1)
        self.assertEqual(
            result["components"][names[0]]["boxMergeMode"],
            "leaf-instance-union-without-collision-history",
        )
        self.assertEqual(
            result["components"][names[1]]["boxMergeMode"],
            "direct-child-union-without-collision-history",
        )

    def test_display_bundle_is_read_only_and_keeps_b_c_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            output = workspace / "demo/layout_previews/project02_dependency_ablation"
            output.mkdir(parents=True)
            (workspace / "demo/layout_previews/project02_dependency_ablation_report.json").write_text(
                json.dumps({"recommendedVariantForVisualReview": "C"}), encoding="utf-8"
            )
            for variant in ("b", "c"):
                (output / f"variant_{variant}_preview.json").write_text(
                    json.dumps({"caseId": "project02", "variant": variant.upper()}),
                    encoding="utf-8",
                )
            bundle = load_dependency_ablation_bundle(workspace)
        self.assertTrue(bundle["readOnly"])
        self.assertEqual(bundle["report"]["recommendedVariantForVisualReview"], "C")
        self.assertEqual(set(bundle["variants"]), {"B", "C"})


if __name__ == "__main__":
    unittest.main()
