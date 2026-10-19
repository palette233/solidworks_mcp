#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project01_bd00_incremental_closure import build_project01_bd00_incremental_closure  # noqa:E402
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def main()->int:
 d=ROOT/"demo/semantic_ports/project01_BD00_fifth_increment_v1";r=build_project01_bd00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),insert_result=load(d/"step05_BD00_increment.result.json"),poses=load(d/"step05_top_level_poses.json"),screening=load(d/"step05_interference_screening.json"),service_points=load(ROOT/"demo/layout_previews/project01_service_points.json"),assembly_path=d/"step05_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_increment.SLDASM");o=d/"step05_BD00_incremental_closure.json";o.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({"status":r["status"],"success":r["success"],"componentCount":r["componentCount"],"poseMaximumError":r["poseAudit"]["maximumTransformElementError"],"collisionPairCount":r["collisionGate"]["pairCount"],"calibrationTargetPassed":r["calibrationTargetGate"]["staticDemoPassed"],"totalMeasuredSeconds":r["timingSeconds"]["totalMeasuredSeconds"],"output":str(o)},ensure_ascii=False,indent=2));return 0 if r["success"] else 2
if __name__=="__main__":raise SystemExit(main())
