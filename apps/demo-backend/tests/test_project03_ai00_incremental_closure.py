from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_ai00_incremental_closure import (
    build_project03_ai00_incremental_closure,
)


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "demo/semantic_ports/project03_AI00_third_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_ai00_checkpoint_separates_driving_and_validation_relations() -> None:
    result = build_project03_ai00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        failed_all_driving_result=load(DIR / "step03_AI00_increment.result.json"),
        insert_result=load(DIR / "step03_AI00_increment_v2.result.json"),
        poses=load(DIR / "step03_top_level_poses_v2.json"),
        screening=load(DIR / "step03_interference_screening_v2.json"),
        scanner_geometry=load(ROOT / "demo/layout_previews/project03_scanner_geometry.json"),
        prototype_ae_ai_brep=load(
            ROOT
            / "demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AI00.json"
        ),
        assembly_path=DIR / "step03_AA00_AF00_AE00_AD00_AI00_increment_v2.SLDASM",
    )
    assert result["success"] is True
    assert result["componentCount"] == 5
    assert result["relationSemantics"]["drivingMateCount"] == 3
    assert result["relationSemantics"]["validationRelationCount"] == 2
    assert result["overconstraintRepairAudit"]["passed"] is True
    assert set(result["overconstraintRepairAudit"]["overdefinedMateNames"]) == {"同心31", "同心32"}
    assert result["poseAudit"]["maximumTransformElementError"] <= 1e-12
    assert result["collisionGate"]["pairCount"] == 10
    assert result["noNewInterferenceOverPrototype"] is True
    assert result["zeroInterferenceClaimed"] is False
    assert result["opticalGate"]["passedForStaticDemo"] is True
    assert result["opticalGate"]["productionReady"] is False
