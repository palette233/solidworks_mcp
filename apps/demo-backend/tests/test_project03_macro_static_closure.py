from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_macro_static_closure import (
    build_project03_macro_static_closure,
)


ROOT = Path(__file__).resolve().parents[3]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_macro_layout_closes_without_misreporting_full_geometry() -> None:
    prior = [
        ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1/step01_AE00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AD00_second_increment_v1/step02_AD00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AI00_third_increment_v1/step03_AI00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AG00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1/step05_AH00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AJ00_sixth_increment_v1/step06_AJ00_incremental_closure.json",
    ]
    ab = ROOT / "demo/semantic_ports/project03_AB00_final_stage_action1_v1"
    ac = ROOT / "demo/semantic_ports/project03_AC00_final_stage_action2_v1"
    result = build_project03_macro_static_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        prior_closures=[load(path) for path in prior],
        ab00_result=load(ab / "step07a_AB00_increment_v2.result.json"),
        ac00_macro_result=load(ac / "step07b_AC00_static_diagnostic_v4b.result.json"),
        ac00_subtree_comparison=load(ac / "ac00_prototype_vs_static_diagnostic_v4b_comparison.json"),
        ac00_anchor_flexible_result=load(ac / "step07b_AC00_static_snapshot_v5.result.json"),
        ac00_anchor_rigid_result=load(ac / "step07b_AC00_static_snapshot_rigid_v6.result.json"),
        ac00_prefixed_result=load(ac / "step07b_AC00_prefixed_flexible_v7.result.json"),
        poses=load(ac / "step07b_static_diagnostic_v4b_top_level_poses.json"),
        screening=load(ac / "step07b_static_diagnostic_v4b_interference_broadphase.json"),
        valve_reach=load(ROOT / "demo/layout_previews/project03_dual_valve_reach.json"),
        assembly_path=ac / "step07b_project03_full_10_object_static_diagnostic_v4b.SLDASM",
    )
    assert result["macroStaticPassed"] is True
    assert result["fullGeometryClosed"] is False
    assert result["success"] is False
    assert result["componentCount"] == 10
    assert result["macroLayoutGate"]["maximumTransformElementError"] <= 1e-12
    assert result["ac00InternalStateGate"]["unstableNodeCount"] == 72
    assert result["collisionGate"]["allTopLevelPairCount"] == 45
    assert result["collisionGate"]["conditionalBrepPairCount"] == 23
    assert result["collisionGate"]["conditionalBrepExecuted"] is False
