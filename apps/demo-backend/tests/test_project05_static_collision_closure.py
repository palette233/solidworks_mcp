from __future__ import annotations

import copy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_project05_static_collision_closure import build_closure, code, load  # noqa: E402


def inputs() -> dict:
    v1 = ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v1"
    v6 = ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v6"
    v7 = ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v7"
    stages = []
    for stage_id, root in [
        ("step00", v1), ("step01", v1), ("step02", v1),
        ("step03", v6), ("step04", v6), ("step05", v6),
        ("step06", v7), ("step07", v7), ("step08", v7),
    ]:
        stages.append(load(next(root.glob(f"{stage_id}_*.stage-result.json"))))
    return {
        "occupancy": load(ROOT / "demo/layout_previews/project05_module_occupancy.json"),
        "selected_solution": load(ROOT / "demo/layout_previews/project05_selected_solution.json"),
        "final_stage": stages[-1],
        "candidate_brep": load(v7 / "conditional_brep_with_baseline/step08_B000_cumulative_leaf_details_batch.json"),
        "prototype_brep": load(ROOT / "demo/layout_previews/project05_prototype_conditional_brep/FL9C254098AA00.001_leaf_details_batch.json"),
        "final_assembly": v7 / "step08_B000_cumulative.SLDASM",
        "stage_results": stages,
    }


def test_module_code_uses_terminal_project_token() -> None:
    assert code("FL9C254098D000.001-1") == "D000"
    assert code("FL9C251093N000.001-1") == "N000"


def test_project05_release_closure_accepts_verified_cad_evidence() -> None:
    result = build_closure(**inputs())
    assert result["success"] is True
    assert result["strictLeafAabbGate"]["success"] is True
    assert result["conditionalBrepGate"]["success"] is True
    assert result["finalCadGate"]["leafAuditedComponentCount"] == 11
    assert len(result["stageChain"]) == 9


def test_project05_release_closure_rejects_one_failed_exact_pair() -> None:
    values = inputs()
    candidate = copy.deepcopy(values["candidate_brep"])
    candidate["pairs"][0]["acceptance"]["accepted"] = False
    values["candidate_brep"] = candidate

    result = build_closure(**values)

    assert result["success"] is False
    assert result["conditionalBrepGate"]["success"] is False
