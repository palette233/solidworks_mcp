from __future__ import annotations

import unittest

from scripts.screen_source_independent_layout_3d import (
    boxes_by_layout_name,
    classify_world_aabb_pairs,
    pose_rows,
)


class StaticCollisionScreenTests(unittest.TestCase):
    def test_versioned_pose_catalog_and_static_a100_alias_are_supported(self):
        rows = pose_rows(
            {
                "components": [
                    {
                        "Name": "A100_WITH_A150_SLOT0_RIGID_V3-1",
                        "BoundingBoxWorld": [0, 0, 0, 1, 1, 1],
                    }
                ]
            }
        )
        boxes = boxes_by_layout_name(
            rows,
            {
                "components": [
                    {"componentName": "FL9A24D062A100.001-1"}
                ]
            },
        )

        self.assertEqual(
            boxes,
            {"FL9A24D062A100.001-1": [0, 0, 0, 1, 1, 1]},
        )

    def test_strict_overlap_fails_without_brep_and_structural_overlap_is_deferred(self):
        boxes = {
            "ordinary-a": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "ordinary-b": [0.99, 0.0, 0.0, 1.99, 1.0, 1.0],
            "portal": [0.25, 0.25, 0.0, 0.75, 0.75, 1.0],
        }
        policy = {
            "aabbInflationPerSideMeters": 0.01,
            "strictAabbPairs": [["ordinary-a", "ordinary-b"]],
            "brepOnAabbOverlapPairs": [
                ["ordinary-a", "portal"],
                ["ordinary-b", "portal"],
            ],
        }

        diagnostics = classify_world_aabb_pairs(boxes, policy)
        by_pair = {frozenset(item["components"]): item for item in diagnostics}

        strict = by_pair[frozenset(("ordinary-a", "ordinary-b"))]
        self.assertEqual(strict["status"], "failed_strict_inflated_aabb")
        self.assertFalse(strict["requiresExactBrep"])
        structural = by_pair[frozenset(("ordinary-a", "portal"))]
        self.assertEqual(structural["status"], "needs_exact_brep_check")
        self.assertTrue(structural["requiresExactBrep"])

    def test_structural_pair_with_world_aabb_gap_passes_without_brep(self):
        boxes = {
            "frame": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "module": [1.1, 0.0, 0.0, 2.1, 1.0, 1.0],
        }
        diagnostics = classify_world_aabb_pairs(
            boxes,
            {
                "strictAabbPairs": [],
                "brepOnAabbOverlapPairs": [["frame", "module"]],
            },
        )

        self.assertEqual(diagnostics[0]["status"], "passed_by_world_aabb")
        self.assertFalse(diagnostics[0]["requiresExactBrep"])


if __name__ == "__main__":
    unittest.main()
