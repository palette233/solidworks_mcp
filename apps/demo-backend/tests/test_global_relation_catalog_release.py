import copy
import json
from pathlib import Path

import pytest

from demo_backend.global_relation_catalog_release import (
    GlobalRelationCatalogReleaseError,
    _driving_initial_pose_validation_passed,
    _validation_passed,
    build_relation_catalog_release,
    finalize_relation_catalog_release,
    load_relation_catalog_release,
    relation_catalog_release_binding,
)
from demo_backend.global_assembly_workbench import (
    GlobalAssemblyWorkbenchError,
    describe_released_relation_catalog,
    preflight_released_driving_relation,
    preview_released_relation_intent,
)
from demo_backend.models import GlobalRelationEditPreviewRequest
from demo_backend.global_cad_packet_executor import (
    GlobalCadPacketExecutionError,
    validate_cad_manifest_release_authority,
)


ROOT = Path(__file__).resolve().parents[3]


def test_current_project05_direct_mate_edit_is_only_static_replacement_evidence():
    payload = json.loads(
        (
            ROOT
            / "demo/global_assembly_catalog/v1/driving-v1-preview/"
            "project05_D000_A000_scoped_driving_v2/cad-cache/"
            "remate-current-v1.result.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert _validation_passed(payload) is True
    assert _driving_initial_pose_validation_passed(payload) is False


def test_checkpoint_accepts_clean_preexisting_target_source_session():
    payload = json.loads(
        (
            ROOT
            / "demo/semantic_ports/project05_p000_locator_discovery_v1/cad/"
            "project05-p000-derived-x-distance-checkpoint-v2.result.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert payload["targetSourceWasAlreadyOpen"] is True
    assert payload["targetSourceClosedAfterVerification"] is False
    assert payload["targetSourceSessionClean"] is True
    assert _validation_passed(payload) is True
    assert _driving_initial_pose_validation_passed(payload) is True


def test_project05_flexible_g000_checkpoint_is_valid_driving_evidence():
    payload = json.loads(
        (
            ROOT
            / "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project05-g000-checkpoint-v1/"
            "project05-g000-nonanchor-checkpoint.result.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert payload["toolResult"]["TargetFullyConstrained"] is False
    assert payload["toolResult"]["TargetConstraintStateAccepted"] is True
    assert _validation_passed(payload) is True
    assert _driving_initial_pose_validation_passed(payload) is True


def test_project05_flexible_checkpoint_requires_accepted_constraint_state():
    payload = json.loads(
        (
            ROOT
            / "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project05-g000-checkpoint-v1/"
            "project05-g000-nonanchor-checkpoint.result.json"
        ).read_text(encoding="utf-8-sig")
    )
    payload["toolResult"]["TargetConstraintStateAccepted"] = False

    assert _validation_passed(payload) is False
    assert _driving_initial_pose_validation_passed(payload) is False


def test_project03_ab00_context_insert_is_valid_driving_evidence():
    payload = json.loads(
        (
            ROOT
            / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1/cad/"
            "project03_AB00_complete_nonanchor_v1.result.json"
        ).read_text(encoding="utf-8-sig")
    )

    assert payload["toolResult"]["OriginalComponentRemoved"] is True
    assert payload["toolResult"]["IndependentComponentInserted"] is True
    assert payload["toolResult"]["TargetCaseAnchored"] is False
    assert payload["toolResult"]["CreatedMateCount"] == 3
    assert _validation_passed(payload) is True
    assert _driving_initial_pose_validation_passed(payload) is True


def test_project03_ab00_context_insert_rejects_incomplete_mate_rebuild():
    payload = json.loads(
        (
            ROOT
            / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1/cad/"
            "project03_AB00_complete_nonanchor_v1.result.json"
        ).read_text(encoding="utf-8-sig")
    )
    payload["toolResult"]["CreatedMateCount"] = 2

    assert _validation_passed(payload) is False
    assert _driving_initial_pose_validation_passed(payload) is False


def test_relation_v4_release_is_bound_to_three_real_cad_evidence_files():
    catalog, manifest = build_relation_catalog_release(
        catalog_path=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v4-preview.json",
        derivation_evidence_path=ROOT / "demo/global_assembly_catalog/v1/relation-v4-preview/derivation-evidence.json",
        validation_evidence_paths=[
            ROOT / "demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/cad-result.json",
            ROOT / "demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json",
            ROOT / "demo/global_assembly_contexts/project01-coincident-validation-v1/final-validation-report.json",
        ],
        release_id="relation-v4-test",
    )

    assert manifest["status"] == "released_for_demo_relation_execution"
    assert manifest["productionReady"] is False
    assert manifest["catalogDigest"] == catalog["catalogDigest"]
    assert len(manifest["derivedTemplateIds"]) == 3
    assert len(manifest["validationEvidence"]) == 3
    assert all(row["passed"] for row in manifest["validationEvidence"])
    assert manifest["scope"]["drivingRelationRelease"] is False
    assert manifest["scope"]["authorizedDrivingTemplateIds"] == []


def test_release_rejects_non_driving_or_unknown_template_authorization():
    kwargs = {
        "catalog_path": ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v4-preview.json",
        "derivation_evidence_path": ROOT
        / "demo/global_assembly_catalog/v1/relation-v4-preview/derivation-evidence.json",
        "validation_evidence_paths": [
            ROOT
            / "demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/cad-result.json",
            ROOT
            / "demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json",
            ROOT
            / "demo/global_assembly_contexts/project01-coincident-validation-v1/final-validation-report.json",
        ],
        "release_id": "relation-template-authorization-test",
    }
    _, baseline = build_relation_catalog_release(**kwargs)
    authorized_id = baseline["derivedTemplateIds"][0]
    with pytest.raises(GlobalRelationCatalogReleaseError, match="未声明可驱动位姿"):
        build_relation_catalog_release(
            **kwargs,
            authorized_driving_template_ids=[authorized_id],
        )
    with pytest.raises(GlobalRelationCatalogReleaseError, match="驱动授权只能"):
        build_relation_catalog_release(
            **kwargs,
            authorized_driving_template_ids=["template/not-in-this-release"],
        )


def test_finalized_release_is_portable_and_detects_published_catalog_tampering(tmp_path):
    catalog, manifest = build_relation_catalog_release(
        catalog_path=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v4-preview.json",
        derivation_evidence_path=ROOT / "demo/global_assembly_catalog/v1/relation-v4-preview/derivation-evidence.json",
        validation_evidence_paths=[
            ROOT / "demo/global_assembly_contexts/manifest_jobs/project03-job-ac77c693ae78/packet-runs/packet-002-attempt-02/cad-result.json",
            ROOT / "demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json",
            ROOT / "demo/global_assembly_contexts/project01-coincident-validation-v1/final-validation-report.json",
        ],
        release_id="relation-portable-test",
    )
    output = tmp_path / "release" / "global_module_catalog.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finalized = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=output,
        workspace_root=tmp_path,
    )
    manifest_path = output.parent / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(finalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded_catalog, loaded_manifest = load_relation_catalog_release(
        manifest_path,
        workspace_root=tmp_path,
    )
    assert loaded_catalog["catalogDigest"] == catalog["catalogDigest"]
    assert loaded_manifest["releasedCatalogRelativePath"] == "release/global_module_catalog.json"

    output.write_text(output.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(GlobalRelationCatalogReleaseError, match="文件摘要"):
        load_relation_catalog_release(manifest_path, workspace_root=tmp_path)


def test_default_release_drives_relation_intent_selection_and_api_accepts_verify():
    release = describe_released_relation_catalog(ROOT)
    coincident = preview_released_relation_intent(
        ROOT, {"requirement": "验证两个安装面重合"}
    )
    parallel = preview_released_relation_intent(
        ROOT, {"requirement": "验证两个基准面平行"}
    )
    distance = preview_released_relation_intent(
        ROOT, {"requirement": "验证两个安装面保持40mm距离"}
    )
    concentric = preview_released_relation_intent(
        ROOT, {"requirement": "验证两个孔同轴"}
    )
    unsupported = preview_released_relation_intent(
        ROOT, {"requirement": "验证两个安装面垂直"}
    )
    driving = preview_released_relation_intent(
        ROOT,
        {
            "requirement": "让两个安装面重合",
            "executionMode": "drive",
        },
    )

    assert release["releaseId"] == "relation-v5-20261011"
    assert release["releasedTemplateCount"] == 4
    assert release["scope"]["readOnlyCadVerification"] is True
    assert release["authorizedDrivingTemplateIds"] == []
    assert coincident["status"] == "ready_for_endpoint_selection"
    assert parallel["status"] == "ready_for_endpoint_selection"
    assert distance["status"] == "ready_for_endpoint_selection"
    assert concentric["status"] == "ready_for_endpoint_selection"
    assert all(
        len(row["matchingTemplates"]) == 1
        for row in (coincident, parallel, distance, concentric)
    )
    assert unsupported["status"] == "blocked"
    assert unsupported["blockers"][-1]["code"] == "NO_RELEASED_RELATION_TEMPLATE_MATCHED"
    assert driving["status"] == "blocked"
    assert "RELEASE_SCOPE_FORBIDS_DRIVING_RELATION" in {
        row["code"] for row in driving["blockers"]
    }
    assert driving["userFailureExplanation"]["reasonCode"] == (
        "DRIVING_RELATION_NOT_AUTHORIZED"
    )
    assert GlobalRelationEditPreviewRequest(operation="verify").operation == "verify"


def test_scoped_project05_release_is_revoked_without_initial_pose_independence():
    release_path = (
        "demo/global_assembly_catalog/releases/"
        "relation-v6-project05-driving-20261011/release-manifest.json"
    )
    with pytest.raises(
        GlobalAssemblyWorkbenchError,
        match="缺少非原型初始位姿CAD证据",
    ):
        describe_released_relation_catalog(ROOT, release_path)


def test_project05_v7_release_is_backed_by_independent_component_insertion():
    release_path = (
        "demo/global_assembly_catalog/releases/"
        "relation-v7-project05-driving-independent-20261011/release-manifest.json"
    )
    release = describe_released_relation_catalog(ROOT, release_path)
    preview = preview_released_relation_intent(
        ROOT,
        {
            "requirement": "在A000上安装D000输送模组",
            "executionMode": "drive",
            "releaseManifestPath": release_path,
        },
    )

    assert release["scope"]["drivingRelationRelease"] is True
    assert len(release["authorizedDrivingTemplateIds"]) == 1
    assert preview["status"] == "ready_for_endpoint_selection"
    assert [row["globalTemplateId"] for row in preview["matchingTemplates"]] == release[
        "authorizedDrivingTemplateIds"
    ]


def test_release_metadata_binds_one_isolated_execution_evidence_class():
    template_id = "template/project05/d000-to-a000-scoped-driving-v2/465c1f471a"
    _, manifest = build_relation_catalog_release(
        catalog_path=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.driving-v1-preview.json",
        derivation_evidence_path=ROOT
        / "demo/global_assembly_catalog/v1/driving-v1-preview/evidence.json",
        validation_evidence_paths=[
            ROOT
            / "demo/global_assembly_catalog/v1/driving-v1-preview/"
            "project05_D000_A000_scoped_driving_v2/cad-cache/"
            "fresh-insert-v1.result.json"
        ],
        release_id="relation-evidence-class-test",
        authorized_driving_template_ids=[template_id],
        release_metadata={
            "relationExecutionMode": "direct_installation",
            "templateEvidenceClasses": {template_id: "direct_installation"},
            "directMechanicalInterfaceCompatible": True,
        },
    )

    assert manifest["releaseMetadata"]["relationExecutionMode"] == (
        "direct_installation"
    )


def test_release_metadata_rejects_claim_inconsistent_with_template_purpose():
    template_id = "template/project05/d000-to-a000-scoped-driving-v2/465c1f471a"
    with pytest.raises(GlobalRelationCatalogReleaseError, match="证据类别不一致"):
        build_relation_catalog_release(
            catalog_path=ROOT
            / "demo/global_assembly_catalog/v1/global_module_catalog.driving-v1-preview.json",
            derivation_evidence_path=ROOT
            / "demo/global_assembly_catalog/v1/driving-v1-preview/evidence.json",
            validation_evidence_paths=[
                ROOT
                / "demo/global_assembly_catalog/v1/driving-v1-preview/"
                "project05_D000_A000_scoped_driving_v2/cad-cache/"
                "fresh-insert-v1.result.json"
            ],
            release_id="relation-invalid-evidence-class-test",
            authorized_driving_template_ids=[template_id],
            release_metadata={
                "relationExecutionMode": "datum_placement_demo",
                "templateEvidenceClasses": {template_id: "datum_placement_demo"},
                "directMechanicalInterfaceCompatible": False,
            },
        )


def test_wastecup_datum_demo_release_is_isolated_and_portably_bound():
    manifest_path = ROOT / (
        "demo/global_assembly_catalog/releases/"
        "relation-v63-project02-project05-wastecup-datum-demo-20261015/"
        "release-manifest.json"
    )
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=ROOT
    )
    binding = relation_catalog_release_binding(
        manifest, manifest_path=manifest_path, workspace_root=ROOT
    )

    assert catalog["catalogDigest"] == manifest["catalogDigest"]
    assert manifest["releaseMetadata"] == {
        "relationExecutionMode": "datum_placement_demo",
        "templateEvidenceClasses": {
            "template/project-global/p000-a600-wastecup-datum-demo/218ec01d59": (
                "datum_placement_demo"
            )
        },
        "directMechanicalInterfaceCompatible": False,
        "collisionOrBrep": "not_evaluated",
        "statement": (
            "只允许在显式datum_placement_demo模式下执行；"
            "默认direct_installation必须失败关闭。"
        ),
    }
    assert binding["releaseMetadata"] == manifest["releaseMetadata"]


def test_project05_v25_release_authorizes_p000_four_relation_bundle():
    release_path = (
        "demo/global_assembly_catalog/releases/"
        "relation-v25-project05-five-addon-portable-driving-20261011/"
        "release-manifest.json"
    )
    release = describe_released_relation_catalog(ROOT, release_path)

    assert len(release["authorizedDrivingTemplateIds"]) == 5
    assert (
        "template/project05/p000-to-a000-nonanchor-driving-v2/fa4ffa064d"
        in release["authorizedDrivingTemplateIds"]
    )
    assert release["scope"]["collisionOrBrepRelease"] is False


def test_project01_v10_release_authorizes_and_enforces_exact_template_combination():
    release_path = (
        "demo/global_assembly_catalog/releases/"
        "relation-v10-project01-combination-driving-20261011/release-manifest.json"
    )
    release = describe_released_relation_catalog(ROOT, release_path)
    combination_ids = release["scope"]["authorizedTemplateCombinationIds"]
    manifest = json.loads(
        (
            ROOT
            / "demo/global_assembly_contexts/"
            "project01-jj00-ss00-gn00-v10-combination-v1/"
            "cad-transaction-manifest.json"
        ).read_text(encoding="utf-8-sig")
    )

    authority = validate_cad_manifest_release_authority(ROOT, manifest)

    assert combination_ids == [
        "combination/project01/gn00-primary-plus-ss00-anti-rotation/18004cfdec"
    ]
    assert authority["authorizedTemplateCombinationIds"] == combination_ids
    assert authority["usedTemplateCombinationIds"] == combination_ids

    partial = copy.deepcopy(manifest)
    packet = partial["packets"][1]
    packet["connections"] = packet["connections"][:1]
    with pytest.raises(GlobalCadPacketExecutionError, match="部分成员"):
        validate_cad_manifest_release_authority(ROOT, partial)
