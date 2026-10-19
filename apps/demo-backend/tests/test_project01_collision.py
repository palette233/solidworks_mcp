from __future__ import annotations

import json
import unittest
from pathlib import Path

from demo_backend.project01_collision import (
    build_project01_replay_screening,
    evaluate_project01_allowed_contacts,
)


ROOT = Path(__file__).resolve().parents[3]


class Project01CollisionTests(unittest.TestCase):
    def load(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))

    def test_saved_rank_one_replay_passes_strict_gate_and_routes_risk_pairs(self) -> None:
        result = build_project01_replay_screening(
            self.load("demo/layout_previews/project01_module_occupancy.json"),
            self.load("demo/layout_previews/project01_selected_solution_replay.json"),
            self.load("demo/layout_previews/project01_solution1_v1_replay_result.json"),
            self.load("demo/layout_previews/project01_top_level_poses.json"),
        )
        self.assertEqual(result["status"], "PROJECT01_PRIORITY_BREP_READY")
        self.assertTrue(result["replayPoseAudit"]["success"])
        self.assertEqual(result["strictAabb"]["pairCount"], 12)
        self.assertEqual(result["strictAabb"]["failedPairCount"], 0)
        self.assertEqual(result["conditionalBrep"]["pendingPairCount"], 9)
        self.assertEqual(result["installationContact"]["pendingPairCount"], 7)

    def test_rank_two_pose_audit_uses_selected_target_not_prototype_pose(self) -> None:
        result = build_project01_replay_screening(
            self.load("demo/layout_previews/project01_module_occupancy.json"),
            self.load("demo/layout_previews/project01_rank2_selected_solution_replay.json"),
            self.load("demo/layout_previews/project01_solution2_v1_replay_result.json"),
            self.load("demo/layout_previews/project01_top_level_poses.json"),
        )
        self.assertEqual(result["status"], "PROJECT01_PRIORITY_BREP_READY")
        self.assertTrue(result["replayPoseAudit"]["success"])
        self.assertLessEqual(result["replayPoseAudit"]["maximumTransformElementError"], 1e-6)
        self.assertEqual(result["strictAabb"]["failedPairCount"], 0)

    def test_exact_hits_match_only_the_three_instance_aware_provisional_rules(self) -> None:
        exact = self.load(
            "demo/interference_project01_solution1_v1/conditional/"
            "FL9C24N074AA00_project01_solution1_v1_leaf_details_FL9C24N074ZZ00_FL9C24N074GN00.json"
        )
        policy = self.load("demo/layout_previews/project01_allowed_contact_policy.json")
        result = evaluate_project01_allowed_contacts([exact], policy)
        self.assertTrue(result["allInterferencesClassified"])
        self.assertEqual(result["temporarilyAllowedCount"], 3)
        self.assertEqual(result["illegalInterferenceCount"], 0)
        self.assertFalse(result["engineeringConfirmed"])

    def test_unlisted_instance_is_never_hidden_by_module_level_exception(self) -> None:
        exact = self.load(
            "demo/interference_project01_solution1_v1/conditional/"
            "FL9C24N074AA00_project01_solution1_v1_leaf_details_FL9C24N074ZZ00_FL9C24N074GN00.json"
        )
        exact["InterferingBodyPairs"][0]["FirstComponent"]["HierarchyPath"] += "/UNLISTED-9"
        exact["InterferingBodyPairs"][0]["FirstComponent"]["Path"] = "UNLISTED.SLDPRT"
        policy = self.load("demo/layout_previews/project01_allowed_contact_policy.json")
        result = evaluate_project01_allowed_contacts([exact], policy)
        self.assertFalse(result["allInterferencesClassified"])
        self.assertEqual(result["illegalInterferenceCount"], 1)


if __name__ == "__main__":
    unittest.main()
