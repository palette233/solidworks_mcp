#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"apps/demo-backend/src"))
from demo_backend.project03_incremental_work_packet import build_project03_ai00_work_packet
SRC=ROOT/"demo/layout_previews/project03_module_mate_graph.json"; GEO=ROOT/"demo/layout_previews/project03_first_stage_geometry.json"; SCAN=ROOT/"demo/layout_previews/project03_scanner_geometry.json"; OUT=ROOT/"demo/semantic_ports/project03_AI00_third_increment_v1"
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def main()->int:
 r=build_project03_ai00_work_packet(load(SRC),Path(load(GEO)["sourceAssemblyPath"]),load(SCAN));OUT.mkdir(parents=True,exist_ok=True)
 files={"path_recovery_audit.json":r["pathAudit"],"face_endpoint_catalog.json":r["endpointCatalog"],"semantic_port_catalog.json":r["semanticCatalog"],"base_context_graph.json":r["baseGraph"],"assembly_plan_request.json":r["request"],"assembly_plan_patch.json":r["patch"],"assembly_plan_effective.json":r["effectiveGraph"],"work_packet_summary.json":{**r["summary"],"generatedAt":datetime.now(timezone.utc).isoformat()}}
 for n,v in files.items():(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(files["work_packet_summary.json"],ensure_ascii=False,indent=2));return 0 if r["summary"]["staticCadReady"] else 2
if __name__=="__main__":raise SystemExit(main())
