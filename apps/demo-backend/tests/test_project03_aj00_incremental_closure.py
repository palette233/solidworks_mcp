from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_aj00_incremental_closure import build_project03_aj00_incremental_closure
ROOT=Path(__file__).resolve().parents[3];DIR=ROOT/"demo/semantic_ports/project03_AJ00_sixth_increment_v1"
def load(p:Path)->dict:return json.loads(p.read_text(encoding="utf-8-sig"))
def test_real_aj00_checkpoint_closes_static_but_not_hose_sweep()->None:
 r=build_project03_aj00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),insert_result=load(DIR/"step06_AJ00_increment.result.json"),poses=load(DIR/"step06_top_level_poses.json"),screening=load(DIR/"step06_interference_screening.json"),occupancy=load(ROOT/"demo/layout_previews/project03_module_occupancy.json"),assembly_path=DIR/"step06_AA00_AF00_AE00_AD00_AI00_AG00_AH00_AJ00_increment.SLDASM")
 assert r["success"] is True and r["componentCount"]==8
 assert r["installationGate"]["drivingMateCount"]==3 and r["installationGate"]["residualAnchorApplied"] is False
 assert r["poseAudit"]["maximumTransformElementError"]<=1e-12
 assert r["maintenanceGate"]["passedForStaticDemo"] is True and r["maintenanceGate"]["productionReady"] is False
 assert r["collisionGate"]["pairCount"]==28 and r["collisionGate"]["aabbSeparatedPairCount"]==15
