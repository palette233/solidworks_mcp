import json
from pathlib import Path

from demo_backend.project03_ag00_three_datum_port import (
    build_project03_ag00_three_datum_candidate,
)


ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC = ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_diagnostic_v1"
DISCOVERY = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-datum-discovery-v1"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _build():
    return build_project03_ag00_three_datum_candidate(
        _read(DIAGNOSTIC / "assembly_plan_effective.json"),
        _read(DIAGNOSTIC / "face_endpoint_catalog.json"),
        _read(DIAGNOSTIC / "semantic_port_catalog.json"),
        _read(DISCOVERY / "ag00_primary_mount_leaf_faces.json"),
        _read(DISCOVERY / "ag00_support_mount_leaf_faces.json"),
        _read(DISCOVERY / "aa00_ag00_mount_leaf_faces.json"),
        _read(DISCOVERY / "ag00_secondary_datum_discovery_v2.json"),
    )


def test_ag00_candidate_is_three_datum_and_zero_anchor():
    result = _build()
    summary = result["summary"]
    assert summary["status"] == "candidate_ready_for_nonanchor_cad_validation"
    assert summary["drivingMateCount"] == 3
    assert summary["expectedResidualDof"] == 0
    assert summary["casePoseAnchorCount"] == 0
    assert summary["leafPoseAnchorCount"] == 0
    assert summary["semanticPortPublished"] is False

    graph = result["effectiveGraph"]
    assert len(graph["Mates"]) == 3
    assert graph["Mates"][-1]["MateName"] == "MCP_GRAPH_AG00_SECONDARY_AXIS"
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"].get("targetLeafPoseAnchors", []) == []
    assert graph["NonprototypePreparation"]["targetModuleToken"] == (
        "FL9A24D063AG00"
    )


def test_ag00_candidate_semantic_port_uses_one_plane_and_two_holes():
    result = _build()
    ports = result["semanticCatalog"]["ports"]
    assert len(ports) == 2
    for port in ports:
        assert [row["role"] for row in port["endpointBindings"]] == [
            "support_plane",
            "primary_locating_hole",
            "secondary_locating_hole",
        ]
        assert port["portable"] is False
        assert port["status"] == "candidate-cad-validation-required"
    template = result["semanticCatalog"]["connectionTemplates"][0]
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert len(template["mateSteps"]) == 3


def test_candidate_endpoint_catalog_is_bounded_to_six_faces():
    result = _build()
    catalog = result["endpointCatalog"]
    assert catalog["EndpointCount"] == 6
    assert len(catalog["Endpoints"]) == 6
    assert all(
        row["Endpoint"].get("SourceAssemblyPersistentReferenceBase64")
        for row in catalog["Endpoints"]
    )

