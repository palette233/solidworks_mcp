from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_deprototype_audit import (
    build_project03_pose_anchor_ablation,
)


ROOT = Path(__file__).resolve().parents[3]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_ag00_and_ab00_compile_independently_of_captured_top_level_pose() -> None:
    geometry = load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")
    result = build_project03_pose_anchor_ablation(
        load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        Path(geometry["sourceAssemblyPath"]),
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
        load(ROOT / "demo/layout_previews/project03_dual_valve_reach.json"),
        load(ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json"),
    )
    assert result["status"] == "PASSED_RUNTIME_TOP_LEVEL_POSE_DETACHMENT"
    assert result["productionReady"] is False
    assert result["moduleCount"] == 2
    assert all(
        row["compiledTransformStableUnderSourcePosePerturbation"]
        and row["runtimePrototypeTopLevelPoseReadRequired"] is False
        for row in result["modules"]
    )
