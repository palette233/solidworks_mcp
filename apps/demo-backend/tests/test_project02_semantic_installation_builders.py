from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_project02_a180_semantic_installation as a180_builder
import build_project02_a800_semantic_installation as a800_builder
from demo_backend.face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan


def test_a800_plan_exposes_two_driving_mates_and_explicit_case_anchor() -> None:
    graph = a800_builder.read_json(a800_builder.SOURCE_GRAPH)
    endpoints = build_face_endpoint_catalog_from_source_mates(
        graph, a800_builder.SOURCE_MATE_NAMES
    )
    catalog = a800_builder.build_semantic_catalog(graph, endpoints)
    binding = catalog["positioningStandardBinding"]
    assert binding["moduleToken"] == "A800"
    assert binding["ruleId"] == "A600-A800-inferred-positioning-v1"
    assert binding["coarseLayoutUseAllowed"] is True
    assert binding["productionUseAllowed"] is False
    base = a800_builder.build_base_graph(graph)
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "test-a800",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": ["A800"],
        "componentToAdd": a800_builder.find_module(graph, "A800"),
        "connections": [{
            "connectionId": "A800-installed-on-A600",
            "portAId": "A800.frame_installation",
            "portBId": "A600.a800_installation",
            "templateId": "A800_to_A600_source_installation",
        }],
    }
    result = build_semantic_assembly_plan(base, catalog, endpoints, request)
    assert result["summary"]["generatedMateNames"] == ["重合35", "宽度9"]
    assert result["summary"]["caseAnchoredModuleTokens"] == ["A800"]


def test_a180_plan_keeps_slot_read_only_and_registers_optical_ports() -> None:
    graph = a180_builder.read_json(a180_builder.SOURCE_GRAPH)
    endpoints = build_face_endpoint_catalog_from_source_mates(
        graph, a180_builder.SOURCE_MATE_NAMES
    )
    catalog = a180_builder.build_catalog(graph, endpoints)
    binding = catalog["positioningStandardBinding"]
    assert binding["moduleToken"] == "A180"
    assert binding["ruleId"] == "A600-A180-mechanical-A800-optical-positioning-v1"
    template = catalog["connectionTemplates"][0]
    assert [step["mateName"] for step in template["mateSteps"]] == ["重合34", "距离24"]
    assert catalog["readOnlySourceRelations"][0]["mateName"] == "槽口3"
    assert {port["portId"] for port in catalog["functionalPorts"]} == {
        "A180.scan_optical",
        "A800.barcode_target",
    }
    profile = catalog["functionalConstraintProfiles"][0]
    assert profile["workingDistanceMeters"]["minimum"] == 0.100
    assert profile["workingDistanceMeters"]["maximum"] == 0.160
    assert profile["requiresLineOfSight"] is True
