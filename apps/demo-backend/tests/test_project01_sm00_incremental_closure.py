from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_sm00_incremental_closure import build_project01_sm00_incremental_closure


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "demo/semantic_ports/project01_SM00_third_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


@unittest.skipUnless((DIR / "step03_JJ00_HL00_SS00_FF00_SM00_increment.SLDASM").is_file(), "SM00 CAD checkpoint missing")
class Project01Sm00IncrementalClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_sm00_incremental_closure(
            source_graph=load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            insert_result=load(DIR / "step03_SM00_increment.result.json"),
            poses=load(DIR / "step03_top_level_poses.json"),
            screening=load(DIR / "step03_interference_screening.json"),
            scanner_geometry=load(ROOT / "demo/layout_previews/project01_scanner_geometry.json"),
            assembly_path=DIR / "step03_JJ00_HL00_SS00_FF00_SM00_increment.SLDASM",
        )

    def test_static_mechanical_checkpoint_closes(self) -> None:
        self.assertTrue(self.result["success"])
        self.assertEqual(self.result["componentCount"], 5)
        self.assertEqual(self.result["drivingMateCount"], 3)
        self.assertLessEqual(self.result["poseAudit"]["maximumTransformElementError"], 1e-12)
        self.assertEqual(self.result["collisionGate"]["pairCount"], 10)

    def test_optical_demo_passes_without_claiming_engineering_confirmation(self) -> None:
        optical = self.result["opticalGate"]
        self.assertTrue(optical["staticDemoPassed"])
        self.assertFalse(optical["engineeringConfirmed"])
        self.assertEqual(optical["scannerCount"], 2)
        self.assertEqual(
            optical["roles"], ["carrierBarcodeScanner", "productBarcodeScanner"]
        )
        self.assertFalse(self.result["productionReady"])


if __name__ == "__main__":
    unittest.main()
