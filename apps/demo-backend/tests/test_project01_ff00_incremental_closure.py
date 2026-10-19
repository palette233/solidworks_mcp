from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_ff00_incremental_closure import (
    build_project01_ff00_incremental_closure,
)


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "demo/semantic_ports/project01_FF00_second_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


@unittest.skipUnless(
    (DIR / "step02_JJ00_HL00_SS00_FF00_increment.SLDASM").is_file(),
    "Project01 FF00 live CAD checkpoint has not been generated",
)
class Project01Ff00IncrementalClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_ff00_incremental_closure(
            source_graph=load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            insert_result=load(DIR / "step02_FF00_increment.result.json"),
            poses=load(DIR / "step02_top_level_poses.json"),
            screening=load(DIR / "step02_interference_screening.json"),
            assembly_path=DIR / "step02_JJ00_HL00_SS00_FF00_increment.SLDASM",
        )

    def test_static_checkpoint_closes(self) -> None:
        self.assertTrue(self.result["success"])
        self.assertTrue(self.result["staticCheckpointPassed"])
        self.assertEqual(self.result["componentCount"], 4)
        self.assertEqual(self.result["drivingMateCount"], 3)
        self.assertLessEqual(
            self.result["poseAudit"]["maximumTransformElementError"], 1e-12
        )

    def test_dynamic_gate_remains_truthfully_blocked(self) -> None:
        self.assertFalse(self.result["dynamicCheckpointPassed"])
        self.assertFalse(self.result["dynamicGate"]["passed"])
        self.assertEqual(
            self.result["dynamicGate"]["requiredStates"],
            ["home", "work", "flip-25deg"],
        )
        self.assertFalse(self.result["productionReady"])

    def test_all_six_static_pairs_have_an_explained_decision(self) -> None:
        gate = self.result["collisionGate"]
        self.assertTrue(gate["staticPassed"])
        self.assertEqual(gate["pairCount"], 6)
        self.assertEqual(gate["aabbSeparatedPairCount"], 2)
        self.assertTrue(all(row["accepted"] for row in gate["pairs"]))
        self.assertFalse(self.result["absoluteZeroInterferenceClaimed"])


if __name__ == "__main__":
    unittest.main()
