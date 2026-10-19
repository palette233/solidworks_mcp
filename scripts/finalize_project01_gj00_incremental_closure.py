#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project01_gj00_incremental_closure import build_project01_gj00_incremental_closure  # noqa:E402
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def main()->int:
 d=ROOT/"demo/semantic_ports/project01_GJ00_sixth_increment_v1";r=build_project01_gj00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"),insert_result=load(d/"step06_GJ00_increment.result.json"),poses=load(d/"step06_top_level_poses.json"),screening=load(d/"step06_interference_screening.json"),assembly_path=d/"step06_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_GJ00_increment.SLDASM");o=d/"step06_GJ00_incremental_closure.json";o.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({"status":r["status"],"success":r["success"],"componentCount":r["componentCount"],"poseMaximumError":r["poseAudit"]["maximumTransformElementError"],"collisionPairCount":r["collisionGate"]["pairCount"],"hoseMaintenancePassed":r["hoseMaintenanceGate"]["passed"],"totalMeasuredSeconds":r["timingSeconds"]["totalMeasuredSeconds"],"output":str(o)},ensure_ascii=False,indent=2));return 0 if r["success"] else 2
if __name__=="__main__":raise SystemExit(main())
