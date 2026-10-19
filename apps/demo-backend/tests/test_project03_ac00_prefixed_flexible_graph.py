from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_prefixed_flexible_graph.py"
SPEC = importlib.util.spec_from_file_location("ac00_prefixed", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_ac00_prefixed_graph_restores_all_four_source_relations() -> None:
    geometry = load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")
    result = MODULE.build(
        load(
            ROOT
            / "demo/semantic_ports/project03_AC00_final_stage_action2_v1/assembly_plan_effective.json"
        ),
        load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        Path(geometry["sourceAssemblyPath"]),
    )
    assert len(result["Mates"]) == 4
    assert sorted(mate["MateName"] for mate in result["Mates"]) == [
        "同心34",
        "同心35",
        "重合26",
        "重合29",
    ]
    assert result["EditPolicy"]["fixCaseAnchorBeforeMates"] is True
    assert result["EditPolicy"]["targetLeafPoseAnchors"] == []
    target = next(
        module
        for module in result["Modules"]
        if module["ModuleToken"] == "FL9A24D063AC00"
    )
    assert target["SolvingState"] == 1
