from __future__ import annotations

import json
from pathlib import Path
import unittest

from demo_backend.project01_sm00_work_packet import build_project01_sm00_work_packet


ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Project01Sm00WorkPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_sm00_work_packet(
            load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            load(
                ROOT
                / "demo/semantic_ports/project01_FF00_second_increment_v1/assembly_plan_effective.json"
            ),
            PROTOTYPE,
        )

    def test_scanner_three_datum_contract(self) -> None:
        summary = self.result["summary"]
        self.assertEqual(summary["sourceMateNames"], ["重合8", "同心15", "同心14"])
        self.assertAlmostEqual(summary["locatingHoleSpacingMeters"], 0.022, places=6)
        self.assertEqual(summary["endpointCount"], 6)
        self.assertTrue(summary["safeToStartStaticCad"])
        self.assertEqual(self.result["effectiveGraph"]["InterModuleMateCount"], 3)

    def test_optical_evidence_is_required_but_not_used_as_a_mechanical_mate(self) -> None:
        evidence = self.result["summary"]["opticalEvidenceRequired"]
        self.assertEqual(evidence["scannerCount"], 2)
        self.assertEqual(evidence["explicitBeamLengthMeters"], 0.2)
        self.assertEqual(
            evidence["roles"], ["carrierBarcodeScanner", "productBarcodeScanner"]
        )
        self.assertEqual(len(self.result["effectiveGraph"]["Mates"]), 3)


if __name__ == "__main__":
    unittest.main()
