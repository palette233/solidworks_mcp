from __future__ import annotations
import json
from pathlib import Path
import unittest
from demo_backend.project01_bd00_incremental_closure import build_project01_bd00_incremental_closure
ROOT=Path(__file__).resolve().parents[3];D=ROOT/"demo/semantic_ports/project01_BD00_fifth_increment_v1"
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
@unittest.skipUnless((D/"step05_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_increment.SLDASM").is_file(),"BD00 CAD missing")
class Project01Bd00IncrementalClosureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls)->None:cls.r=build_project01_bd00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),insert_result=load(D/"step05_BD00_increment.result.json"),poses=load(D/"step05_top_level_poses.json"),screening=load(D/"step05_interference_screening.json"),service_points=load(ROOT/"demo/layout_previews/project01_service_points.json"),assembly_path=D/"step05_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_increment.SLDASM")
 def test_static_closure(self):self.assertTrue(self.r["success"]);self.assertEqual(self.r["componentCount"],7);self.assertEqual(self.r["drivingMateCount"],3);self.assertEqual(self.r["collisionGate"]["pairCount"],21);self.assertLessEqual(self.r["poseAudit"]["maximumTransformElementError"],1e-12)
 def test_calibration_proxy_scope(self):self.assertTrue(self.r["calibrationTargetGate"]["staticDemoPassed"]);self.assertFalse(self.r["calibrationTargetGate"]["engineeringConfirmed"]);self.assertEqual(self.r["calibrationTargetGate"]["target"]["id"],"calibration-prism-target");self.assertFalse(self.r["productionReady"])
if __name__=="__main__":unittest.main()
