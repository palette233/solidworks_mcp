from __future__ import annotations
import json
from pathlib import Path
import unittest
from demo_backend.project01_gn00_incremental_closure import build_project01_gn00_incremental_closure
ROOT=Path(__file__).resolve().parents[3]; D=ROOT/"demo/semantic_ports/project01_GN00_fourth_increment_v1"
def load(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8-sig"))
@unittest.skipUnless((D/"step04_JJ00_HL00_SS00_FF00_SM00_GN00_increment.SLDASM").is_file(),"GN00 CAD missing")
class Project01Gn00IncrementalClosureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls)->None:
  cls.r=build_project01_gn00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),insert_result=load(D/"step04_GN00_increment.result.json"),poses=load(D/"step04_top_level_poses.json"),screening=load(D/"step04_interference_screening.json"),service_points=load(ROOT/"demo/layout_previews/project01_service_points.json"),assembly_path=D/"step04_JJ00_HL00_SS00_FF00_SM00_GN00_increment.SLDASM")
 def test_static_closure(self):
  self.assertTrue(self.r["success"]);self.assertEqual(self.r["componentCount"],6);self.assertEqual(self.r["drivingMateCount"],3);self.assertEqual(self.r["collisionGate"]["pairCount"],15);self.assertLessEqual(self.r["poseAudit"]["maximumTransformElementError"],1e-12)
 def test_service_targets_pass_demo_but_maintenance_remains_blocked(self):
  self.assertTrue(self.r["serviceTargetGate"]["staticDemoPassed"]);self.assertEqual(self.r["serviceTargetGate"]["targetCount"],5);self.assertFalse(self.r["serviceTargetGate"]["engineeringConfirmed"]);self.assertFalse(self.r["maintenanceEnvelopeGate"]["passed"]);self.assertFalse(self.r["productionReady"])
if __name__=="__main__":unittest.main()
