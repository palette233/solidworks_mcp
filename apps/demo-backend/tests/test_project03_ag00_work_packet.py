from __future__ import annotations

import json
import copy
from pathlib import Path

from demo_backend.project03_incremental_work_packet import build_project03_ag00_work_packet


ROOT = Path(__file__).resolve().parents[3]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(*, anchored: bool) -> dict:
    return build_project03_ag00_work_packet(
        load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        Path(load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]),
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
        case_anchored=anchored,
    )


def test_ag00_diagnostic_packet_exposes_one_residual_rotation() -> None:
    result = build(anchored=False)
    assert result["summary"]["sourceMateTypes"] == ["swMateCOINCIDENT", "swMateCONCENTRIC"]
    assert result["summary"]["endpointCount"] == 4
    assert result["summary"]["expectedResidualDofWithoutAnchor"] == 1
    assert result["summary"]["serviceTargetCount"] == 6
    assert result["summary"]["diagnosticCadReady"] is True
    assert result["summary"]["staticCadReady"] is False
    assert result["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["serviceTargetValidation"]["targetCount"] == 6


def test_ag00_anchor_is_explicit_and_does_not_invent_a_third_mate() -> None:
    result = build(anchored=True)
    assert result["summary"]["staticCadReady"] is True
    assert result["effectiveGraph"]["InterModuleMateCount"] == 2
    assert result["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"] == ["FL9A24D063AG00"]
    boundary = result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["residualDofBoundary"]
    assert boundary["caseAnchorApplied"] is True
    assert "prototype" in boundary["caseAnchorAuthority"]


def test_ag00_versioned_anchor_is_independent_of_captured_top_level_pose() -> None:
    graph = load(ROOT / "demo/layout_previews/project03_module_mate_graph.json")
    parameters = load(ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json")
    prototype = Path(
        load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")[
            "sourceAssemblyPath"
        ]
    )
    services = load(ROOT / "demo/layout_previews/project03_service_points.json")
    perturbed = copy.deepcopy(graph)
    target = next(
        item
        for item in perturbed["Modules"]
        if item["ModuleToken"] == "FL9A24D063AG00"
    )
    target["SourceTransform"] = [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        9.0, 8.0, 7.0,
        1.0, 0.0, 0.0, 0.0,
    ]

    baseline = build_project03_ag00_work_packet(
        graph,
        prototype,
        services,
        case_anchored=True,
        calibrated_parameters=parameters,
    )
    changed = build_project03_ag00_work_packet(
        perturbed,
        prototype,
        services,
        case_anchored=True,
        calibrated_parameters=parameters,
    )
    baseline_target = next(
        item
        for item in baseline["effectiveGraph"]["Modules"]
        if item["ModuleToken"] == "FL9A24D063AG00"
    )
    changed_target = next(
        item
        for item in changed["effectiveGraph"]["Modules"]
        if item["ModuleToken"] == "FL9A24D063AG00"
    )
    assert changed_target["SourceTransform"] == baseline_target["SourceTransform"]
    assert changed["summary"]["calibratedAnchorApplied"] is True
    assert changed["summary"]["runtimePrototypeTopLevelPoseReadRequired"] is False
    boundary = changed["effectiveGraph"]["SemanticAssemblyPlanAudit"]["residualDofBoundary"]
    assert boundary["calibratedAnchor"]["authority"] == "prototype-calibrated-temporary"
    assert boundary["runtimePrototypeTopLevelPoseReadRequired"] is False
