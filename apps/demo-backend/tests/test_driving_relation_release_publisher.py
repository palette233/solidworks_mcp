from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from demo_backend.driving_relation_release_publisher import (
    DrivingRelationReleasePublisherError,
    publish_driving_relation_release,
)
from demo_backend.global_relation_catalog_release import load_relation_catalog_release


WORKSPACE = Path(__file__).resolve().parents[3]


def project03_spec(release_id: str) -> dict:
    return {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project03",
        "drivingScope": "project03_AA00_fixed_environment_only",
        "catalogPath": (
            "demo/global_assembly_catalog/v1/"
            "global_module_catalog.combination-v1-preview.json"
        ),
        "templates": [
            {
                "legacyTemplateId": "AE00_to_AA00_three_datum_installation",
                "globalTemplateId": (
                    "template/project03/ae00-to-aa00-three-datum-installation/"
                    "3665a437a8"
                ),
                "evidencePath": (
                    "demo/global_assembly_catalog/v1/combination-v1-preview/"
                    "project03-ae00-checkpoint-v1/"
                    "project03-ae00-nonprototype-checkpoint.result.json"
                ),
                "expectedMateCount": 3,
            }
        ],
    }


def test_generic_publisher_creates_loadable_immutable_release(tmp_path):
    spec = project03_spec("test-project03-generic-driving")
    output_root = WORKSPACE / ".tmp" / tmp_path.name / "release-success"
    result = publish_driving_relation_release(WORKSPACE, spec, output_root=output_root)

    assert result["success"] is True
    assert result["validationEvidenceCount"] == 1
    assert result["solidWorksExecutedInThisPublish"] is False
    catalog, manifest = load_relation_catalog_release(
        Path(result["manifestPath"]), workspace_root=WORKSPACE
    )
    assert catalog["catalogDigest"] == result["catalogDigest"]
    assert manifest["scope"]["authorizedDrivingTemplateIds"] == result[
        "authorizedDrivingTemplateIds"
    ]
    shutil.rmtree(WORKSPACE / ".tmp" / tmp_path.name)


def test_generic_publisher_fails_closed_on_wrong_expected_mate_count(tmp_path):
    spec = deepcopy(project03_spec("test-project03-bad-evidence"))
    spec["templates"][0]["expectedMateCount"] = 4
    output_root = WORKSPACE / ".tmp" / tmp_path.name / "release-failure"

    with pytest.raises(DrivingRelationReleasePublisherError, match="驱动证据未通过"):
        publish_driving_relation_release(WORKSPACE, spec, output_root=output_root)


def project01_combination_spec(release_id: str) -> dict:
    gn00_evidence = (
        "demo/global_assembly_catalog/v1/relation-v2-preview/"
        "project01-gn00-current-insert-v2/cad-result.json"
    )
    return {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project01",
        "drivingScope": "project01_JJ00_HL00_SS00_then_GN00_declared_bundle_only",
        "catalogPath": (
            "demo/global_assembly_catalog/v1/"
            "global_module_catalog.combination-v1-preview.json"
        ),
        "templates": [
            {
                "legacyTemplateId": "SS00_to_JJ00_three_datum_installation",
                "globalTemplateId": (
                    "template/project01/ss00-to-jj00-three-datum-installation/"
                    "c087ea93d1"
                ),
                "evidencePath": (
                    "demo/global_assembly_catalog/v1/relation-v2-preview/"
                    "project01-ss00-current-insert-v1/cad-result.json"
                ),
                "expectedMateCount": 3,
            },
            {
                "legacyTemplateId": "GN00_to_JJ00_primary",
                "globalTemplateId": (
                    "template/project01/gn00-to-jj00-primary/8ff522aead"
                ),
                "evidencePath": gn00_evidence,
                "expectedMateCount": 3,
                "requireDeclaredClosed": False,
            },
            {
                "legacyTemplateId": "GN00_SS00_standalone_parallel",
                "globalTemplateId": (
                    "template/project01/gn00-ss00-standalone-parallel/5df3a32e59"
                ),
                "evidencePath": gn00_evidence,
                "expectedMateCount": 3,
                "requireDeclaredClosed": False,
            },
        ],
        "authorizedTemplateCombinationIds": [
            "combination/project01/gn00-primary-plus-ss00-anti-rotation/18004cfdec"
        ],
    }


def test_generic_publisher_supports_exact_combination_with_shared_evidence(tmp_path):
    spec = project01_combination_spec("test-project01-generic-combination")
    spec["relationTopologyAuditPath"] = (
        "demo/global_assembly_catalog/relation-topology-audit-v1.json"
    )
    spec["requiredMechanicalEdges"] = [
        {
            "moduleTokens": ["GN00", "SS00"],
            "requirePoseAnchorFreeEvidence": True,
        }
    ]
    output_root = WORKSPACE / ".tmp" / tmp_path.name / "release-combination"
    result = publish_driving_relation_release(WORKSPACE, spec, output_root=output_root)

    assert result["success"] is True
    assert result["templateCount"] == 3
    assert result["validationEvidenceCount"] == 2
    _, manifest = load_relation_catalog_release(
        Path(result["manifestPath"]), workspace_root=WORKSPACE
    )
    assert manifest["scope"]["authorizedTemplateCombinationIds"] == spec[
        "authorizedTemplateCombinationIds"
    ]
    assert result["relationTopologyAttested"] is True
    assert manifest["relationTopologyAttestation"]["projectId"] == "project01"
    assert manifest["relationTopologyAttestation"]["requiredMechanicalEdges"] == spec[
        "requiredMechanicalEdges"
    ]
    shutil.rmtree(WORKSPACE / ".tmp" / tmp_path.name)


def test_generic_publisher_rejects_process_only_dependency_as_mechanical_edge(
    tmp_path,
):
    spec = project01_combination_spec("test-project01-invented-edge")
    spec["relationTopologyAuditPath"] = (
        "demo/global_assembly_catalog/relation-topology-audit-v1.json"
    )
    spec["requiredMechanicalEdges"] = [
        {"moduleTokens": ["BD00", "GN00"], "requirePoseAnchorFreeEvidence": True}
    ]

    with pytest.raises(DrivingRelationReleasePublisherError, match="驱动证据未通过"):
        publish_driving_relation_release(
            WORKSPACE,
            spec,
            output_root=WORKSPACE / ".tmp" / tmp_path.name / "invented-edge",
        )


def test_generic_publisher_fails_closed_on_unknown_combination(tmp_path):
    spec = project01_combination_spec("test-project01-bad-combination")
    spec["authorizedTemplateCombinationIds"] = ["combination/missing"]
    output_root = WORKSPACE / ".tmp" / tmp_path.name / "release-bad-combination"

    with pytest.raises(DrivingRelationReleasePublisherError, match="驱动证据未通过"):
        publish_driving_relation_release(WORKSPACE, spec, output_root=output_root)


def test_project03_cross_project_cumulative_release_authorizes_both_independent_slots():
    manifest_path = WORKSPACE / (
        "demo/global_assembly_catalog/releases/"
        "relation-v47-project03-aa00-project01-calibration-transport-driving-20261012/"
        "release-manifest.json"
    )
    catalog, manifest = load_relation_catalog_release(
        manifest_path,
        workspace_root=WORKSPACE,
    )
    authorized = set(manifest["scope"]["authorizedDrivingTemplateIds"])

    assert authorized == {
        "template/cross-project/bd00-to-project03-ah00-slot/f215aabb1a",
        "template/cross-project/ss00-to-project03-ae00-slot/fbc7749921",
    }
    assert manifest["scope"]["collisionOrBrepRelease"] is False
    assert authorized.issubset(
        {
            row["globalTemplateId"]
            for row in catalog["connectionTemplates"]
        }
    )


def test_project01_cross_project_complete_chain_release_has_exact_three_templates():
    manifest_path = WORKSPACE / (
        "demo/global_assembly_catalog/releases/"
        "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014/"
        "release-manifest.json"
    )
    catalog, manifest = load_relation_catalog_release(
        manifest_path,
        workspace_root=WORKSPACE,
    )
    authorized = set(manifest["scope"]["authorizedDrivingTemplateIds"])

    assert authorized == {
        "template/cross-project/ae00-to-project01-ss00-slot/97aed2cb02",
        "template/cross-project/ah00-to-project01-bd00-slot/6ef3e3ad8d",
        "template/project01/sm00-to-jj00-three-datum-installation/3cc07ef613",
    }
    assert manifest["scope"]["collisionOrBrepRelease"] is False
    assert authorized.issubset(
        {
            row["globalTemplateId"]
            for row in catalog["connectionTemplates"]
        }
    )
