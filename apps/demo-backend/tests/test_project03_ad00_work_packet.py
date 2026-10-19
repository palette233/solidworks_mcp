from __future__ import annotations
import json
from pathlib import Path
from demo_backend.project03_incremental_work_packet import build_project03_ad00_work_packet

ROOT = Path(__file__).resolve().parents[3]

def test_project03_ad00_static_packet_is_ready_but_dynamic_gate_remains() -> None:
    graph = json.loads((ROOT / "demo/layout_previews/project03_module_mate_graph.json").read_text(encoding="utf-8-sig"))
    geometry = json.loads((ROOT / "demo/layout_previews/project03_first_stage_geometry.json").read_text(encoding="utf-8-sig"))
    result = build_project03_ad00_work_packet(graph, Path(geometry["sourceAssemblyPath"]))
    summary = result["summary"]
    assert summary["sourceMateTypes"].count("swMateCOINCIDENT") == 1
    assert summary["sourceMateTypes"].count("swMateCONCENTRIC") == 2
    assert summary["endpointCount"] == 6
    assert summary["staticCadReady"] is True
    assert summary["dynamicSweepReady"] is False
    assert result["request"]["initialPlacementMode"] == "deterministic"
    assert result["effectiveGraph"]["InterModuleMateCount"] == 3
    assert result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["dynamicStateBoundary"]["sweptVolumeValidated"] is False
