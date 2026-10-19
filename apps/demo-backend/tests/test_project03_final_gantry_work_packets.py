from __future__ import annotations
import copy
import json
from pathlib import Path
from demo_backend.project03_incremental_work_packet import build_project03_ab00_work_packet,build_project03_ac00_work_packet
ROOT=Path(__file__).resolve().parents[3]
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def test_final_gantry_packets_are_explicit_about_anchor_and_redundancy()->None:
 g=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json");proto=Path(load(ROOT/"demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]);reach=load(ROOT/"demo/layout_previews/project03_dual_valve_reach.json")
 ab=build_project03_ab00_work_packet(g,proto,reach);ac=build_project03_ac00_work_packet(g,proto,reach)
 assert ab["summary"]["drivingMateCount"]==1 and ab["summary"]["validationRelationCount"]==1 and ab["summary"]["unsupportedMateNames"]==["宽度1"]
 assert ab["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"]==["FL9A24D063AB00"]
 assert ac["summary"]["sourceMateCount"]==4 and ac["summary"]["drivingMateCount"]==3
 assert ac["summary"]["failedThreeMatePoseResidualMeters"]>.05 and ac["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"]==["FL9A24D063AC00"]
 assert ab["summary"]["requiredReachTargetCount"]==9 and ac["summary"]["requiredReachTargetCount"]==9


def test_ab00_versioned_anchor_is_independent_of_captured_top_level_pose()->None:
 g=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json");proto=Path(load(ROOT/"demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]);reach=load(ROOT/"demo/layout_previews/project03_dual_valve_reach.json");parameters=load(ROOT/"demo/semantic_ports/project03_calibrated_parameters_v1.json")
 perturbed=copy.deepcopy(g)
 target=next(item for item in perturbed["Modules"] if item["ModuleToken"]=="FL9A24D063AB00")
 target["SourceTransform"]=[1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,4.0,5.0,6.0,1.0,0.0,0.0,0.0]
 baseline=build_project03_ab00_work_packet(g,proto,reach,calibrated_parameters=parameters)
 changed=build_project03_ab00_work_packet(perturbed,proto,reach,calibrated_parameters=parameters)
 baseline_target=next(item for item in baseline["effectiveGraph"]["Modules"] if item["ModuleToken"]=="FL9A24D063AB00")
 changed_target=next(item for item in changed["effectiveGraph"]["Modules"] if item["ModuleToken"]=="FL9A24D063AB00")
 assert changed_target["SourceTransform"]==baseline_target["SourceTransform"]
 assert changed["summary"]["calibratedAnchorApplied"] is True
 assert changed["summary"]["runtimePrototypeTopLevelPoseReadRequired"] is False
 audit=changed["effectiveGraph"]["SemanticAssemblyPlanAudit"]["unsupportedSourceRelation"]
 assert audit["calibratedAnchor"]["authority"]=="prototype-calibrated-temporary"
 assert audit["runtimePrototypeTopLevelPoseReadRequired"] is False
