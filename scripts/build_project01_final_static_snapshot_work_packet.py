#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project01_final_static_snapshot_work_packet import build_project01_final_static_snapshot_work_packet
def load(p:Path)->dict:return json.loads(p.resolve().read_text(encoding="utf-8-sig"))
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--prior-effective",required=True,type=Path);p.add_argument("--snapshot",required=True,type=Path);p.add_argument("--snapshot-run",required=True,type=Path);p.add_argument("--lm-comparison",required=True,type=Path);p.add_argument("--zz-comparison",required=True,type=Path);p.add_argument("--output-dir",required=True,type=Path);a=p.parse_args()
 r=build_project01_final_static_snapshot_work_packet(load(a.prior_effective),a.snapshot,load(a.snapshot_run),load(a.lm_comparison),load(a.zz_comparison));o=a.output_dir.resolve();o.mkdir(parents=True,exist_ok=True)
 for name,key in (("assembly_plan_effective.json","effectiveGraph"),("work_packet_summary.json","summary")):(o/name).write_text(json.dumps(r[key],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"outputDir":str(o),"moduleCount":r["effectiveGraph"]["ModuleCount"],"functionalObjectCount":r["summary"]["finalFunctionalObjectCount"],"target":r["summary"]["targetModule"]},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
