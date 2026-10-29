import json
from pathlib import Path

from demo_backend.project01_gn00_two_hole_port import (
    build_project01_gn00_two_hole_candidate,
)
from demo_backend.global_cad_driving_evidence import assess_driving_insert_evidence


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "demo/semantic_ports/project01_GN00_fourth_increment_v1"
DISCOVERY = (
    ROOT
    / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00"
)
TARGET = (
    ROOT
    / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json"
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _build():
    return build_project01_gn00_two_hole_candidate(
        _read(SOURCE / "assembly_plan_effective.json"),
        _read(SOURCE / "face_endpoint_catalog.json"),
        _read(SOURCE / "semantic_port_catalog.json"),
        _read(DISCOVERY / "gn00-primary-mount-leaf-face-catalog.json"),
        _read(DISCOVERY / "gn00-support-mount-leaf-face-catalog.json"),
        _read(TARGET),
        _read(DISCOVERY / "secondary_datum_discovery_two_leaves.json"),
    )


def test_candidate_removes_transport_provider_and_all_pose_anchors():
    result = _build()
    summary = result["summary"]
    assert summary["providerRolesBefore"] == ["Base", "Transport"]
    assert summary["providerRolesAfter"] == ["Base"]
    assert summary["drivingMateCount"] == 3
    assert summary["expectedResidualDof"] == 0
    assert summary["casePoseAnchorCount"] == 0
    assert summary["leafPoseAnchorCount"] == 0
    assert summary["semanticPortPublished"] is False

    graph = result["effectiveGraph"]
    assert [mate["MateName"] for mate in graph["Mates"]] == [
        "重合6",
        "同心11",
        "MCP_GRAPH_GN00_SECONDARY_AXIS",
    ]
    assert all("SS00" not in mate["ModuleTokens"] for mate in graph["Mates"])
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"].get("targetLeafPoseAnchors", []) == []


def test_candidate_port_is_one_plane_two_holes_on_base_only():
    result = _build()
    ports = result["semanticCatalog"]["ports"]
    assert len(ports) == 2
    for port in ports:
        assert port["providerRoles"] == ["Base"]
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


def test_candidate_uses_unique_independent_secondary_axis_and_six_endpoints():
    result = _build()
    secondary = result["summary"]["secondaryAxis"]
    assert secondary["axisLineDistanceMeters"] == 0.0
    assert secondary["primaryIndependenceMeters"] == 0.204
    assert secondary["movingRadiusMeters"] == 0.0032500000000000003
    assert secondary["targetRadiusMeters"] == 0.0025000000000000022
    catalog = result["endpointCatalog"]
    assert catalog["EndpointCount"] == 6
    assert len(catalog["Endpoints"]) == 6
    assert all(
        row["Endpoint"].get("SourceAssemblyPersistentReferenceBase64")
        for row in catalog["Endpoints"]
    )


def test_real_nonprototype_checkpoint_is_a_release_candidate():
    result_path = (
        DISCOVERY
        / "two-hole-candidate-v1/"
        "project01_GN00_base_only_two_hole_checkpoint_v1.result.json"
    )
    assessment = assess_driving_insert_evidence(
        _read(result_path), expected_mate_count=3
    )

    assert assessment["status"] == "release_candidate"
    assert assessment["checkpointPassed"] is True
    assert assessment["portablePlacementProven"] is True
    assert assessment["constraintStateObservation"]["targetFullyConstrained"] is True
    assert assessment["blockers"] == []
