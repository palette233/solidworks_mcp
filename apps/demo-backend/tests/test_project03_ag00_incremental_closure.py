from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_ag00_incremental_closure import (
    build_project03_ag00_incremental_closure,
)


ROOT = Path(__file__).resolve().parents[3]
ANCHORED = ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1"
DIAGNOSTIC = ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_diagnostic_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_ag00_checkpoint_records_residual_anchor_debt() -> None:
    result = build_project03_ag00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        diagnostic_result=load(DIAGNOSTIC / "step04_AG00_diagnostic.result.json"),
        anchored_result=load(ANCHORED / "step04_AG00_increment.result.json"),
        poses=load(ANCHORED / "step04_top_level_poses.json"),
        screening=load(ANCHORED / "step04_interference_screening.json"),
        service_points=load(ROOT / "demo/layout_previews/project03_service_points.json"),
        assembly_path=ANCHORED / "step04_AA00_AF00_AE00_AD00_AI00_AG00_increment.SLDASM",
    )
    assert result["success"] is True
    assert result["componentCount"] == 6
    assert result["installationSemantics"]["sourceMateBundleFullyLocatesTarget"] is False
    assert result["installationSemantics"]["diagnosticConfirmedResidualDof"] is True
    assert result["installationSemantics"]["residualAnchorApplied"] is True
    assert result["poseAudit"]["maximumTransformElementError"] <= 1e-12
    assert result["serviceTargetGate"]["targetCount"] == 6
    assert result["serviceTargetGate"]["passedForStaticDemo"] is True
    assert result["serviceTargetGate"]["productionReady"] is False
    assert result["collisionGate"]["pairCount"] == 15
    assert result["noNewInterferenceOverPrototype"] is True
    assert result["zeroInterferenceClaimed"] is False
