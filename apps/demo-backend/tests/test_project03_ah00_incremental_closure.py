from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_ah00_incremental_closure import build_project03_ah00_incremental_closure

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_ah00_checkpoint_closes_without_residual_anchor() -> None:
    result = build_project03_ah00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        insert_result=load(DIR / "step05_AH00_increment.result.json"),
        poses=load(DIR / "step05_top_level_poses.json"),
        screening=load(DIR / "step05_interference_screening.json"),
        service_points=load(ROOT / "demo/layout_previews/project03_service_points.json"),
        assembly_path=DIR / "step05_AA00_AF00_AE00_AD00_AI00_AG00_AH00_increment.SLDASM",
    )
    assert result["success"] is True
    assert result["componentCount"] == 7
    assert result["installationGate"]["drivingMateCount"] == 3
    assert result["installationGate"]["residualAnchorApplied"] is False
    assert result["poseAudit"]["maximumTransformElementError"] <= 1e-12
    assert result["calibrationTargetGate"]["targetCount"] == 1
    assert result["calibrationTargetGate"]["productionReady"] is False
    assert result["collisionGate"]["pairCount"] == 21
    assert result["noNewInterferenceOverPrototype"] is True
