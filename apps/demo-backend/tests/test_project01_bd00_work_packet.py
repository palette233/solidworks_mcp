from __future__ import annotations
import json
from pathlib import Path
import unittest
from demo_backend.project01_bd00_work_packet import build_project01_bd00_work_packet
ROOT=Path(__file__).resolve().parents[3];P=Path(r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM")
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
class Project01Bd00WorkPacketTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls)->None:cls.r=build_project01_bd00_work_packet(load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),load(ROOT/"demo/semantic_ports/project01_GN00_fourth_increment_v1/assembly_plan_effective.json"),P)
 def test_contract(self):
  s=self.r["summary"];self.assertEqual(s["sourceMateNames"],["重合7","同心13","同心12"]);self.assertAlmostEqual(s["locatingHoleSpacingMeters"],.05,places=6);self.assertEqual(s["endpointCount"],6);self.assertTrue(s["safeToStartStaticCad"]);self.assertEqual(self.r["effectiveGraph"]["InterModuleMateCount"],3)
 def test_calibration_target_required(self):self.assertEqual(self.r["summary"]["calibrationEvidenceRequired"]["targetId"],"calibration-prism-target")
if __name__=="__main__":unittest.main()
