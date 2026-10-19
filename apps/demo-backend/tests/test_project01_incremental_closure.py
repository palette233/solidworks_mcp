from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_incremental_closure import (
    build_project01_ss00_incremental_closure,
)


ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "demo/semantic_ports/project01_SS00_first_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


@unittest.skipUnless(
    (DIRECTORY / "step01_JJ00_HL00_SS00_increment.SLDASM").is_file(),
    "Project01 live CAD checkpoint has not been generated",
)
class Project01IncrementalClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_ss00_incremental_closure(
            source_graph=load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            base_result=load(DIRECTORY / "step00_JJ00_HL00_context.result.json"),
            insert_result=load(DIRECTORY / "step01_JJ00_HL00_SS00_increment.result.json"),
            poses=load(DIRECTORY / "step01_top_level_poses.json"),
            screening=load(DIRECTORY / "step01_interference_screening.json"),
            assembly_path=DIRECTORY / "step01_JJ00_HL00_SS00_increment.SLDASM",
        )

    def test_live_checkpoint_closes(self) -> None:
        self.assertTrue(self.result["success"])
        self.assertEqual(self.result["componentCount"], 3)
        self.assertEqual(self.result["drivingMateCount"], 3)

    def test_pose_is_source_equivalent_with_tight_tolerance(self) -> None:
        self.assertTrue(self.result["poseAudit"]["passed"])
        self.assertLessEqual(
            self.result["poseAudit"]["maximumTransformElementError"], 1e-12
        )

    def test_collision_claim_is_scoped_and_explainable(self) -> None:
        gate = self.result["collisionGate"]
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["pairCount"], 3)
        self.assertEqual(gate["aabbSeparatedPairCount"], 1)
        self.assertEqual(gate["unchangedFixedContextPairCount"], 1)
        self.assertEqual(gate["sourceEquivalentInstallationPairCount"], 1)
        self.assertFalse(self.result["absoluteZeroInterferenceClaimed"])
        self.assertTrue(self.result["noNewInterferenceOverPrototype"])

    def test_performance_debt_is_not_hidden(self) -> None:
        attempt = self.result["collisionGate"]["fullLeafBrepAttempt"]
        self.assertEqual(attempt["status"], "ABORTED_PERFORMANCE_BUDGET")
        self.assertFalse(attempt["durableExactEvidenceProduced"])
        self.assertFalse(self.result["productionReady"])


if __name__ == "__main__":
    unittest.main()
