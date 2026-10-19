from __future__ import annotations
import json
from pathlib import Path
import unittest
from demo_backend.project01_gn00_work_packet import build_project01_gn00_work_packet

ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = Path(r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM")

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

class Project01Gn00WorkPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = build_project01_gn00_work_packet(
            load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
            load(ROOT / "demo/semantic_ports/project01_SM00_third_increment_v1/assembly_plan_effective.json"),
            PROTOTYPE,
        )

    def test_multibase_contract_has_three_driving_mates(self) -> None:
        summary = self.result["summary"]
        self.assertEqual(summary["sourceMateNames"], ["重合6", "同心11", "平行1"])
        self.assertEqual(summary["connectionCount"], 2)
        self.assertEqual(summary["endpointCount"], 6)
        self.assertEqual(self.result["effectiveGraph"]["InterModuleMateCount"], 3)
        self.assertTrue(summary["safeToStartStaticCad"])

    def test_service_targets_remain_a_separate_gate(self) -> None:
        self.assertFalse(self.result["summary"]["serviceTargetGateReady"])
        self.assertTrue(any("service targets" in row for row in self.result["summary"]["knownLimits"]))

if __name__ == "__main__":
    unittest.main()
