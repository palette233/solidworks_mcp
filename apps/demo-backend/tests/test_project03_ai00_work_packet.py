from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_incremental_work_packet import build_project03_ai00_work_packet
ROOT=Path(__file__).resolve().parents[3]
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def test_ai00_packet_separates_mechanical_drivers_from_optical_validation()->None:
 r=build_project03_ai00_work_packet(load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),Path(load(ROOT/"demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]),load(ROOT/"demo/layout_previews/project03_scanner_geometry.json"));s=r["summary"]
 assert s["sourceMateTypes"].count("swMateCOINCIDENT")==1 and s["sourceMateTypes"].count("swMateDISTANCE")==2 and s["sourceMateTypes"].count("swMateCONCENTRIC")==2
 assert s["endpointCount"]==10 and s["staticCadReady"] is True and s["opticalValidationReady"] is True and s["productionOpticalReady"] is False
 assert r["effectiveGraph"]["InterModuleMateCount"]==3
 assert len(r["effectiveGraph"]["SemanticAssemblyPlanAudit"]["validationRelations"])==2
 optical=r["effectiveGraph"]["SemanticAssemblyPlanAudit"]["opticalValidation"]
 assert optical["applicationMode"]=="validate_only" and optical["modeledWorkingDistanceMeters"]==0.1
