#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project03_aj00_incremental_closure import build_project03_aj00_incremental_closure
DIR=ROOT/"demo/semantic_ports/project03_AJ00_sixth_increment_v1"
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def main()->int:
 r=build_project03_aj00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),insert_result=load(DIR/"step06_AJ00_increment.result.json"),poses=load(DIR/"step06_top_level_poses.json"),screening=load(DIR/"step06_interference_screening.json"),occupancy=load(ROOT/"demo/layout_previews/project03_module_occupancy.json"),assembly_path=DIR/"step06_AA00_AF00_AE00_AD00_AI00_AG00_AH00_AJ00_increment.SLDASM")
 out=DIR/"step06_AJ00_incremental_closure.json";out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({"status":r["status"],"success":r["success"],"pairCount":r["collisionGate"]["pairCount"],"output":str(out)},ensure_ascii=False,indent=2));return 0 if r["success"] else 2
if __name__=="__main__":raise SystemExit(main())
