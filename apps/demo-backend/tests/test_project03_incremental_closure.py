from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_incremental_closure import (
    build_project03_ae00_incremental_closure,
)


ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_project03_ae00_incremental_checkpoint_is_closed() -> None:
    result = build_project03_ae00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        base_result=load(DIRECTORY / "step00_AA00_AF00_context.result.json"),
        insert_result=load(DIRECTORY / "step01_AA00_AF00_AE00_increment.result.json"),
        poses=load(DIRECTORY / "step01_top_level_poses.json"),
        screening=load(DIRECTORY / "step01_interference_screening.json"),
        assembly_path=DIRECTORY / "step01_AA00_AF00_AE00_increment.SLDASM",
    )
    assert result["status"] == "PROJECT03_AE00_INCREMENT_DEMO_CLOSED"
    assert result["success"] is True
    assert result["componentCount"] == 3
    assert result["drivingMateCount"] == 3
    assert result["poseAudit"]["maximumTransformElementError"] <= 1e-12
    assert result["collisionGate"]["aabbSeparatedPairCount"] == 1
    assert result["collisionGate"]["sourcePoseEquivalentInstallationPairCount"] == 2
    assert result["zeroInterferenceClaimed"] is False
    assert result["productionReady"] is False

