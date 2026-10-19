from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_full_incremental_closure import build_project03_full_incremental_closure
ROOT=Path(__file__).resolve().parents[3]
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def test_legacy_three_mate_ac00_candidate_is_rejected_by_pose_gate()->None:
 closures=[load(ROOT/p) for p in ["demo/semantic_ports/project03_AE00_first_increment_v1/step01_AE00_incremental_closure.json","demo/semantic_ports/project03_AD00_second_increment_v1/step02_AD00_incremental_closure.json","demo/semantic_ports/project03_AI00_third_increment_v1/step03_AI00_incremental_closure.json","demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AG00_incremental_closure.json","demo/semantic_ports/project03_AH00_fifth_increment_v1/step05_AH00_incremental_closure.json","demo/semantic_ports/project03_AJ00_sixth_increment_v1/step06_AJ00_incremental_closure.json"]]
 ab=ROOT/"demo/semantic_ports/project03_AB00_final_stage_action1_v1";ac=ROOT/"demo/semantic_ports/project03_AC00_final_stage_action2_v1"
 r=build_project03_full_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),prior_closures=closures,failed_ab00_result=load(ab/"step07a_AB00_increment.result.json"),ab00_result=load(ab/"step07a_AB00_increment_v2.result.json"),ac00_result=load(ac/"step07b_AC00_increment.result.json"),poses=load(ac/"step07b_top_level_poses.json"),screening=load(ac/"step07b_interference_screening.json"),valve_reach=load(ROOT/"demo/layout_previews/project03_dual_valve_reach.json"),assembly_path=ac/"step07b_project03_full_10_object_increment.SLDASM")
 assert r["success"] is False and r["productionReady"] is False
 assert r["semanticStageCount"]==7 and r["cadActionCount"]==8 and r["componentCount"]==10
 assert r["poseAudit"]["maximumTransformElementError"]>.05
 assert r["reachGate"]["requiredTargetCount"]==9 and r["reachGate"]["allInsideCommonReach"] is True
 assert r["collisionGate"]["pairCount"]==45 and r["collisionGate"]["aabbSeparatedPairCount"]==22
 assert r["zeroInterferenceClaimed"] is False and r["noNewInterferenceOverPrototype"] is False
