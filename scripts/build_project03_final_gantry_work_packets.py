#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project03_incremental_work_packet import build_project03_ab00_work_packet,build_project03_ac00_work_packet
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def write(out:Path,r:dict)->None:
 out.mkdir(parents=True,exist_ok=True);arts={"path_recovery_audit.json":r["pathAudit"],"face_endpoint_catalog.json":r["endpointCatalog"],"semantic_port_catalog.json":r["semanticCatalog"],"base_context_graph.json":r["baseGraph"],"assembly_plan_request.json":r["request"],"assembly_plan_patch.json":r["patch"],"assembly_plan_effective.json":r["effectiveGraph"],"work_packet_summary.json":{**r["summary"],"generatedAt":datetime.now(timezone.utc).isoformat()}}
 for n,p in arts.items():(out/n).write_text(json.dumps(p,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main()->int:
 g=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json");proto=Path(load(ROOT/"demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]);reach=load(ROOT/"demo/layout_previews/project03_dual_valve_reach.json")
 ab=build_project03_ab00_work_packet(g,proto,reach);ac=build_project03_ac00_work_packet(g,proto,reach);write(ROOT/"demo/semantic_ports/project03_AB00_final_stage_action1_v1",ab);write(ROOT/"demo/semantic_ports/project03_AC00_final_stage_action2_v1",ac);print(json.dumps({"ab00":ab["summary"],"ac00":ac["summary"]},ensure_ascii=False,indent=2));return 0 if ab["summary"]["staticCadReady"] and ac["summary"]["staticCadReady"] else 2
if __name__=="__main__":raise SystemExit(main())
