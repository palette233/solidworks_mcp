#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project03_full_incremental_closure import build_project03_full_incremental_closure
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def main()->int:
 dirs=[ROOT/"demo/semantic_ports/project03_AE00_first_increment_v1/step01_AE00_incremental_closure.json",ROOT/"demo/semantic_ports/project03_AD00_second_increment_v1/step02_AD00_incremental_closure.json",ROOT/"demo/semantic_ports/project03_AI00_third_increment_v1/step03_AI00_incremental_closure.json",ROOT/"demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AG00_incremental_closure.json",ROOT/"demo/semantic_ports/project03_AH00_fifth_increment_v1/step05_AH00_incremental_closure.json",ROOT/"demo/semantic_ports/project03_AJ00_sixth_increment_v1/step06_AJ00_incremental_closure.json"]
 acdir=ROOT/"demo/semantic_ports/project03_AC00_final_stage_action2_v1";abdir=ROOT/"demo/semantic_ports/project03_AB00_final_stage_action1_v1"
 r=build_project03_full_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),prior_closures=[load(p) for p in dirs],failed_ab00_result=load(abdir/"step07a_AB00_increment.result.json"),ab00_result=load(abdir/"step07a_AB00_increment_v2.result.json"),ac00_result=load(acdir/"step07b_AC00_increment.result.json"),poses=load(acdir/"step07b_top_level_poses.json"),screening=load(acdir/"step07b_interference_screening.json"),valve_reach=load(ROOT/"demo/layout_previews/project03_dual_valve_reach.json"),assembly_path=acdir/"step07b_project03_full_10_object_increment.SLDASM")
 outdir=ROOT/"demo/semantic_ports/project03_full_machine_increment_v1";outdir.mkdir(parents=True,exist_ok=True);out=outdir/"project03_full_machine_closure.json";out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 ordered=ROOT/"demo/semantic_ports/project03_ordered_jobs";ordered.mkdir(parents=True,exist_ok=True);(ordered/"latest_ordered_closure.json").write_text(json.dumps({"schemaVersion":"project03-latest-ordered-closure/v1","projectId":"project03","status":r["status"],"success":r["success"],"semanticStageCount":r["semanticStageCount"],"cadActionCount":r["cadActionCount"],"componentCount":r["componentCount"],"assemblyPath":r["assemblyPath"],"fullClosurePath":str(out.resolve())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":r["status"],"success":r["success"],"components":r["componentCount"],"pairs":r["collisionGate"]["pairCount"],"targets":r["reachGate"]["requiredTargetCount"],"output":str(out)},ensure_ascii=False,indent=2));return 0 if r["success"] else 2
if __name__=="__main__":raise SystemExit(main())
