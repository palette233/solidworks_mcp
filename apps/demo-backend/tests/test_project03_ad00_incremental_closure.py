from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_ad00_incremental_closure import build_project03_ad00_incremental_closure
ROOT=Path(__file__).resolve().parents[3]
DIR=ROOT / "demo/semantic_ports/project03_AD00_second_increment_v1"
def load(path: Path)->dict:return json.loads(path.read_text(encoding="utf-8-sig"))
def test_real_ad00_static_checkpoint_closes_without_claiming_dynamic_sweep()->None:
    result=build_project03_ad00_incremental_closure(
        source_graph=load(ROOT/"demo/layout_previews/project03_module_mate_graph.json"),
        insert_result=load(DIR/"step02_AD00_increment.result.json"),poses=load(DIR/"step02_top_level_poses.json"),screening=load(DIR/"step02_interference_screening.json"),prototype_ae_ad_brep=load(ROOT/"demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json"),assembly_path=DIR/"step02_AA00_AF00_AE00_AD00_increment.SLDASM")
    assert result["success"] is True
    assert result["componentCount"]==4 and result["drivingMateCount"]==3
    assert result["poseAudit"]["maximumTransformElementError"]<=1e-12
    assert result["collisionGate"]["pairCount"]==6
    assert result["dynamicSweepPassed"] is False
    assert result["productionReady"] is False

