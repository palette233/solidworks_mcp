from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project01_final_gantry_work_packets import (
    LM_CONTEXT,
    ZZ_CONTEXT,
    build_project01_lm00_work_packet,
    build_project01_zz00_work_packet,
)

ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = Path(r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_project01_final_gantry_packets_compile_two_explicit_actions() -> None:
    source = load(ROOT / "demo/layout_previews/project01_module_mate_graph.json")
    prior = load(
        ROOT
        / "demo/semantic_ports/project01_GJ00_sixth_increment_v1/assembly_plan_effective.json"
    )
    lm = build_project01_lm00_work_packet(
        source,
        prior,
        PROTOTYPE,
        load(
            ROOT
            / "demo/semantic_ports/project01_LM00_final_stage_action1_v1/prototype_LM00_subtree_poses.json"
        ),
    )
    zz = build_project01_zz00_work_packet(source, lm["effectiveGraph"], PROTOTYPE)
    assert lm["summary"]["baseModules"] == LM_CONTEXT
    assert lm["summary"]["sourceMateNames"] == ["重合2", "同心3", "同心2"]
    assert abs(lm["summary"]["locatingHoleSpacingMeters"] - 0.0355536566333197) < 1e-12
    assert lm["summary"]["safeToStartStaticCad"] is True
    assert lm["summary"]["targetInternalStateAnchorCount"] == 2
    assert lm["summary"]["targetSolvingState"] == "swComponentFlexibleSolving"
    assert len(lm["effectiveGraph"]["EditPolicy"]["targetLeafPoseAnchors"]) == 2
    assert all(
        row["fixAfterApply"] is False and row["solvingState"] == 1
        for row in lm["effectiveGraph"]["EditPolicy"]["targetLeafPoseAnchors"]
    )
    lm_module = next(row for row in lm["effectiveGraph"]["Modules"] if row["ModuleToken"] == "LM00")
    assert lm_module["SolvingState"] == 1
    assert zz["summary"]["baseModules"] == ZZ_CONTEXT
    assert zz["summary"]["sourceMateNames"] == ["同心21", "平行2", "重合11"]
    assert zz["summary"]["sourceMateTypes"] == [
        "swMateCONCENTRIC",
        "swMatePARALLEL",
        "swMateCOINCIDENT",
    ]
    assert zz["summary"]["endpointCount"] == 6
    assert zz["summary"]["expectedResidualDof"] == 0
    assert zz["summary"]["caseAnchoredStaticState"] is True
    assert zz["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"] == ["ZZ00"]
    assert zz["effectiveGraph"]["EditPolicy"]["fixCaseAnchorBeforeMates"] is True
    assert zz["summary"]["safeToStartStaticCad"] is True
    assert lm["effectiveGraph"]["ModuleCount"] == 9
    assert zz["effectiveGraph"]["ModuleCount"] == 10
