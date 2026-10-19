from __future__ import annotations
import json
from pathlib import Path
import unittest
from demo_backend.project01_gj00_incremental_closure import build_project01_gj00_incremental_closure
ROOT=Path(__file__).resolve().parents[3];D=ROOT/"demo/semantic_ports/project01_GJ00_sixth_increment_v1"
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
@unittest.skipUnless((D/"step06_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_GJ00_increment.SLDASM").is_file(),"GJ00 CAD missing")
class Project01Gj00IncrementalClosureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=build_project01_gj00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),insert_result=load(D/"step06_GJ00_increment.result.json"),poses=load(D/"step06_top_level_poses.json"),screening=load(D/"step06_interference_screening.json"),assembly_path=D/"step06_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_GJ00_increment.SLDASM")
 def test_static_closure(self):self.assertTrue(self.r["success"]);self.assertEqual(self.r["componentCount"],8);self.assertEqual(self.r["drivingMateCount"],3);self.assertEqual(self.r["collisionGate"]["pairCount"],28);self.assertLessEqual(self.r["poseAudit"]["maximumTransformElementError"],1e-12)
 def test_hose_gate_blocked(self):self.assertFalse(self.r["hoseMaintenanceGate"]["passed"]);self.assertFalse(self.r["productionReady"])
if __name__=="__main__":unittest.main()
