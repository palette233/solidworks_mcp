from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_incremental_work_packet import build_project03_aj00_work_packet
ROOT=Path(__file__).resolve().parents[3]
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def test_aj00_packet_has_three_datums_and_explicit_maintenance_debt()->None:
 r=build_project03_aj00_work_packet(load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),Path(load(ROOT/"demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]),load(ROOT/"demo/layout_previews/project03_module_occupancy.json"))
 assert r["summary"]["sourceMateTypes"].count("swMateCONCENTRIC")==2
 assert r["summary"]["endpointCount"]==6 and r["summary"]["staticCadReady"] is True
 assert r["effectiveGraph"]["InterModuleMateCount"]==3
 audit=r["effectiveGraph"]["SemanticAssemblyPlanAudit"]["maintenanceValidation"]
 assert audit["staticOccupancy"] is not None and audit["hoseContinuousSweepAvailable"] is False
