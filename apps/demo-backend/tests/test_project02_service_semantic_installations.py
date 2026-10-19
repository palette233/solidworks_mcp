from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build_project02_service_semantic_installations.py"
SPEC = importlib.util.spec_from_file_location("service_semantic_installations", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_a700_keeps_full_source_mates_and_flexible_state() -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    endpoints = MODULE.build_face_endpoint_catalog_from_source_mates(
        graph, MODULE.MODULE_CONFIG["A700"]["mateNames"]
    )
    catalog = MODULE.build_catalog(graph, endpoints, "A700")
    template = catalog["connectionTemplates"][0]
    assert [item["mateName"] for item in template["mateSteps"]] == [
        "平行1", "平行2", "距离6", "重合38", "宽度10", "距离29"
    ]
    assert template["constraintEffect"]["requiredSolvingState"] == "flexible"
    assert len(catalog["maintenanceEnvelopeProfiles"]) == 4


def test_a700_builder_emits_explicit_parent_context_static_snapshot_branch(tmp_path: Path) -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    MODULE.build_module_artifacts(graph, "A700", tmp_path)
    effective = MODULE.read_json(tmp_path / "A700" / "static_snapshot_effective.json")
    target = next(item for item in effective["Modules"] if item["ModuleToken"] == "A700")
    assert effective["Mates"] == []
    assert effective["EditPolicy"]["caseAnchoredModuleTokens"] == ["A700"]
    assert target["SolvingStateName"] == "swComponentFlexibleSolving"
    assert len(effective["EditPolicy"]["targetLeafPoseAnchors"]) == 2
    policy = effective["SemanticAssemblyPlanAudit"]["staticSnapshotPolicy"]
    assert policy["motionSemanticsPreserved"] is False
    assert policy["requiresEngineerApprovalForProduction"] is True


def test_a700_builder_emits_real_mate_static_installation_branch(tmp_path: Path) -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    MODULE.build_module_artifacts(graph, "A700", tmp_path)
    effective = MODULE.read_json(
        tmp_path / "A700" / "static_installation_effective.json"
    )
    assert [item["MateName"] for item in effective["Mates"]] == [
        "平行1",
        "平行2",
        "距离6",
        "重合38",
        "宽度10",
        "距离29",
    ]
    assert effective["EditPolicy"]["caseAnchoredModuleTokens"] == ["A700"]
    assert len(effective["EditPolicy"]["targetLeafPoseAnchors"]) == 2
    policy = effective["SemanticAssemblyPlanAudit"]["staticInstallationPolicy"]
    assert policy["caseAnchorIsVendorDatum"] is False
    assert policy["motionSemanticsPreserved"] is False


def test_a300_keeps_three_source_mates_and_hard_service_approach() -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    endpoints = MODULE.build_face_endpoint_catalog_from_source_mates(
        graph, MODULE.MODULE_CONFIG["A300"]["mateNames"]
    )
    catalog = MODULE.build_catalog(graph, endpoints, "A300")
    assert [item["mateName"] for item in catalog["connectionTemplates"][0]["mateSteps"]] == [
        "距离19", "距离20", "重合39"
    ]
    assert catalog["maintenanceEnvelopeProfiles"][0]["enforcement"] == "hard"
    assert catalog["maintenanceEnvelopeProfiles"][0]["portableAfterModuleMove"] is False


def test_a300_uses_explicit_case_anchor_to_select_distance_branch(tmp_path: Path) -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    summary = MODULE.build_module_artifacts(graph, "A300", tmp_path)
    effective = MODULE.read_json(tmp_path / "A300" / "assembly_plan_effective.json")
    assert summary["caseAnchored"] is True
    assert effective["EditPolicy"]["caseAnchoredModuleTokens"] == ["A300"]
    assert effective["SemanticAssemblyPlanAudit"]["caseAnchorEvidence"]["notVendorDatum"] is True
    distance20 = next(item for item in effective["Mates"] if item["MateName"] == "距离20")
    assert distance20["AdvancedOptions"]["DistanceFlipDimension"] is False
    override = effective["SemanticAssemblyPlanAudit"]["mateCreationOverrides"][0]
    assert override["sourceDistanceFlipDimension"] is True
    assert override["normalizedAddMate5FlipDimension"] is False


def test_a100_exposes_three_frame_mates_and_flexible_state(tmp_path: Path) -> None:
    graph = MODULE.read_json(MODULE.SOURCE_GRAPH)
    summary = MODULE.build_module_artifacts(graph, "A100", tmp_path)
    catalog = MODULE.read_json(tmp_path / "A100" / "semantic_port_catalog.json")
    effective = MODULE.read_json(tmp_path / "A100" / "assembly_plan_effective.json")
    template = catalog["connectionTemplates"][0]
    assert [item["mateName"] for item in template["mateSteps"]] == [
        "重合8", "重合9", "距离9"
    ]
    assert template["constraintEffect"]["requiredSolvingState"] == "flexible"
    assert summary["caseAnchored"] is False
    assert effective["EditPolicy"]["caseAnchoredModuleTokens"] == []
    distance9 = next(item for item in effective["Mates"] if item["MateName"] == "距离9")
    assert distance9["AdvancedOptions"]["DistanceFlipDimension"] is False
    assert len(effective["EditPolicy"]["targetLeafPoseAnchors"]) >= 4
    snapshot_policy = effective["SemanticAssemblyPlanAudit"]["staticSnapshotPolicy"]
    assert snapshot_policy["motionSemanticsPreserved"] is False
    assert snapshot_policy["leafPoseAnchorCount"] == len(
        effective["EditPolicy"]["targetLeafPoseAnchors"]
    )
    target = next(item for item in effective["Modules"] if item["ModuleToken"] == "A100")
    assert target["SolvingStateName"] == "swComponentRigidSolving"
