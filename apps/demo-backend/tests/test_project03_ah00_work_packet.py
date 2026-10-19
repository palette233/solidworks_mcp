from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_incremental_work_packet import build_project03_ah00_work_packet


ROOT = Path(__file__).resolve().parents[3]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_ah00_packet_has_three_datums_and_one_validation_target() -> None:
    result = build_project03_ah00_work_packet(
        load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        Path(load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]),
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
    )
    summary = result["summary"]
    assert summary["sourceMateTypes"].count("swMateCOINCIDENT") == 1
    assert summary["sourceMateTypes"].count("swMateCONCENTRIC") == 2
    assert summary["endpointCount"] == 6
    assert summary["calibrationTargetCount"] == 1
    assert summary["staticCadReady"] is True
    assert result["effectiveGraph"]["InterModuleMateCount"] == 3
    assert result["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"] == []

