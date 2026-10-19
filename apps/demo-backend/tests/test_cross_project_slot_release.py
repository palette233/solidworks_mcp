import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.cross_project_slot_release import (
    CrossProjectSlotReleaseError,
    LEGACY_TEMPLATE_ID,
    TRANSPORT_LEGACY_TEMPLATE_ID,
    augment_a600_ah00_template_with_operation_side_semantics,
    augment_release_catalog_with_cross_project_template,
    build_a600_ah00_driving_release_evidence,
    build_a600_ah00_operation_side_release_evidence,
    build_cross_project_direct_release_evidence,
    build_jj00_ae00_transport_release_evidence,
    augment_project02_release_catalog_with_a600_ah00_slot,
    finalize_a600_ah00_cross_project_slot,
)
from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_relation_catalog_release import (
    load_relation_catalog_release,
)


WORKSPACE = Path(__file__).resolve().parents[3]
ACQUISITION = (
    WORKSPACE
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
VALIDATION = ACQUISITION / "cad-validation-v1"
AH00 = WORKSPACE / "demo/semantic_ports/project03_AH00_fifth_increment_v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs() -> dict:
    plan = _read(VALIDATION / "candidate_validation_plan.json")
    graph_path = VALIDATION / "candidate_effective_mate_graph.json"
    result = _read(VALIDATION / "candidate_cad_result.json")
    return {
        "candidate": _read(ACQUISITION / "candidate_semantic_port.json"),
        "validation_plan": plan,
        "effective_graph": _read(graph_path),
        "effective_graph_file_sha256": _sha(graph_path),
        "cad_result": result,
        "output_assembly_sha256": "f" * 64,
        "current_source_sha256": copy.deepcopy(plan["sourceModuleSha256"]),
        "a600_face_catalog": _read(
            ACQUISITION / "a600-native-service-leaf-face-catalog-v1.json"
        ),
        "ah00_semantic_catalog": _read(AH00 / "semantic_port_catalog.json"),
        "ah00_face_catalog": _read(AH00 / "face_endpoint_catalog.json"),
        "endpoint_catalog_path": "face_endpoint_catalog.json",
        "effective_graph_path": (
            "demo/cross_project_substitution/alternate-slot-discovery-v1/"
            "project02_A600_calibration_slot_acquisition/cad-validation-v1/"
            "candidate_effective_mate_graph.json"
        ),
        "validation_evidence_path": "cross_project_slot_closure.json",
        "output_assembly_path": result["outputAssemblyPath"],
    }


def test_release_promotes_only_the_validated_six_endpoints_without_collision_claim():
    package = finalize_a600_ah00_cross_project_slot(**_inputs())

    closure = package["closure"]
    assert closure["status"] == "released_for_cross_project_semantic_installation"
    assert closure["productionReady"] is False
    assert all(closure["checks"].values())
    assert closure["scope"]["collisionOrBrep"] is False
    assert package["endpointCatalog"]["EndpointCount"] == 6
    semantic = package["semanticCatalog"]
    assert semantic["connectionTemplates"][0]["templateId"] == LEGACY_TEMPLATE_ID
    assert semantic["connectionTemplates"][0]["sideSemantics"] == ["operator_side"]
    assert semantic["releaseScope"]["collisionOrBrep"] == "not_evaluated"
    ports = {row["portId"]: row for row in semantic["ports"]}
    assert ports["A600.calibration_slot_candidate.operation_side"]["portable"] is True
    assert ports["A600.calibration_slot_candidate.operation_side"]["projectId"] == "project02"
    assert ports["AH00.frame_installation"]["projectId"] == "project03"


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        (
            lambda value: value["cad_result"]["toolResult"].__setitem__(
                "TargetCaseAnchored", True
            ),
            "targetWasNotCaseAnchored",
        ),
        (
            lambda value: value["cad_result"]["toolResult"].__setitem__(
                "CreatedMateCount", 2
            ),
            "threeOfThreeMatesCreated",
        ),
        (
            lambda value: value["cad_result"]["toolResult"].__setitem__(
                "ReopenedMateParametersMatch", False
            ),
            "saveCloseReopenPassed",
        ),
    ],
)
def test_release_fails_closed_on_invalid_cad_evidence(mutation, failed_check):
    values = _inputs()
    values["cad_result"] = copy.deepcopy(values["cad_result"])
    mutation(values)
    with pytest.raises(CrossProjectSlotReleaseError, match=failed_check):
        finalize_a600_ah00_cross_project_slot(**values)


def test_global_release_evidence_binds_the_two_portable_project_owners():
    catalog = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/v1/"
        "global_module_catalog.a600-ah00-cross-project-preview.json"
    )
    package = finalize_a600_ah00_cross_project_slot(**_inputs())
    evidence = build_a600_ah00_driving_release_evidence(
        catalog, package["closure"]
    )

    assert evidence["status"] == "ready"
    assert evidence["collisionStatus"] == "not_evaluated"
    assert len(evidence["authorizedDrivingTemplateIds"]) == 1
    assert all(evidence["checks"].values())


@pytest.mark.parametrize(
    "release_name",
    [
        "relation-v40-project02-a600-project03-ah00-driving-20261012",
        "relation-v41-project02-a600-project03-ah00-driving-20261012",
        "relation-v42-project02-a600-ah00-operation-side-language-20261012",
    ],
)
def test_immutable_slot_releases_reload_with_only_the_cross_project_template_authorized(
    release_name,
):
    manifest_path = (
        WORKSPACE
        / "demo/global_assembly_catalog/releases"
        / release_name
        / "release-manifest.json"
    )
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=WORKSPACE
    )
    authorized = manifest["scope"]["authorizedDrivingTemplateIds"]

    assert len(authorized) == 1
    assert manifest["scope"]["collisionOrBrepRelease"] is False
    assert next(
        row for row in catalog["connectionTemplates"]
        if row["globalTemplateId"] == authorized[0]
    )["legacyTemplateId"] == LEGACY_TEMPLATE_ID


def test_project02_lineage_merge_preserves_nine_addon_templates_and_adds_only_slot_assets():
    base = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v36-project02-nine-addon-portable-driving-20261011/"
        "global_module_catalog.json"
    )
    slot = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/v1/"
        "global_module_catalog.a600-ah00-cross-project-preview.json"
    )
    merged = augment_project02_release_catalog_with_a600_ah00_slot(base, slot)

    assert merged["summary"]["semanticPortCount"] == (
        base["summary"]["semanticPortCount"] + 1
    )
    assert merged["summary"]["connectionTemplateCount"] == (
        base["summary"]["connectionTemplateCount"] + 1
    )
    assert merged["summary"]["compatibilityCount"] == (
        base["summary"]["compatibilityCount"] + 2
    )
    assert {
        row["legacyTemplateId"] for row in base["connectionTemplates"]
    }.issubset(
        {row["legacyTemplateId"] for row in merged["connectionTemplates"]}
    )


def test_operation_side_semantics_do_not_change_the_validated_mate_bundle():
    release = WORKSPACE / (
        "demo/global_assembly_catalog/releases/"
        "relation-v41-project02-a600-project03-ah00-driving-20261012"
    )
    source = _read(release / "global_module_catalog.json")
    manifest = _read(release / "release-manifest.json")
    closure = _read(
        WORKSPACE
        / "demo/semantic_ports/project02_A600_project03_AH00_cross_project_slot_v1/"
        "cross_project_slot_closure.json"
    )
    candidate = augment_a600_ah00_template_with_operation_side_semantics(source)
    evidence = build_a600_ah00_operation_side_release_evidence(
        candidate,
        source_catalog=source,
        source_manifest=manifest,
        closure=closure,
    )

    old = next(
        row
        for row in source["connectionTemplates"]
        if row["legacyTemplateId"] == LEGACY_TEMPLATE_ID
    )
    new = next(
        row
        for row in candidate["connectionTemplates"]
        if row["legacyTemplateId"] == LEGACY_TEMPLATE_ID
    )
    assert new["globalTemplateId"] == old["globalTemplateId"]
    assert new["mateSteps"] == old["mateSteps"]
    assert new["sideSemantics"] == ["operator_side"]
    assert all(evidence["checks"].values())
    assert evidence["collisionStatus"] == "not_evaluated"


def test_operation_side_natural_language_selects_the_unique_released_slot():
    source = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v41-project02-a600-project03-ah00-driving-20261012/"
        "global_module_catalog.json"
    )
    catalog = augment_a600_ah00_template_with_operation_side_semantics(source)
    definitions = {
        str(alias.get("projectId") or "").lower()
        + ":"
        + str(alias.get("moduleToken") or "").lower(): row
        for row in catalog["moduleDefinitions"]
        for alias in row.get("projectAliases") or []
    }
    context = create_global_assembly_context(
        "operation-side-selection-test",
        catalog_digest=catalog["catalogDigest"],
    )
    base = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "先添加Project02 A600箱体作为基座。",
            "moduleDefinitionId": definitions["project02:a600"]["moduleDefinitionId"],
        },
    )
    context = apply_global_command_preview(
        context,
        base,
        preview_digest=base["previewDigest"],
        confirmed=True,
    )
    addition = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "把Project03 AH00校准模组安装到A600操作面侧校准槽位。",
            "moduleDefinitionId": definitions["project03:ah00"]["moduleDefinitionId"],
        },
    )

    assert addition["status"] == "ready"
    assert addition["blockers"] == []
    connection = addition["proposedPatch"]["connection"]
    assert connection["globalTemplateId"].endswith("/a133494fd1")
    assert "a600-calibration-slot-candidate-operation-side" in connection["portAId"]
    assert connection["relationIntent"]["parameters"]["sideQualifier"] == (
        "operator_side"
    )


def test_unknown_side_qualifier_still_fails_closed():
    source = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v41-project02-a600-project03-ah00-driving-20261012/"
        "global_module_catalog.json"
    )
    catalog = augment_a600_ah00_template_with_operation_side_semantics(source)
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == LEGACY_TEMPLATE_ID
    )
    template["sideSemantics"] = ["opposite_operator_side"]
    catalog.pop("catalogDigest")
    catalog["catalogDigest"] = hashlib.sha256(
        json.dumps(
            catalog,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(CrossProjectSlotReleaseError, match="冲突的方位语义"):
        augment_a600_ah00_template_with_operation_side_semantics(catalog)


def _transport_release_candidate() -> tuple[dict, dict]:
    base = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v38-project01-topology-bound-combination-driving-20261011/"
        "global_module_catalog.json"
    )
    substitution = _read(
        WORKSPACE
        / "demo/cross_project_substitution/transport-v1/"
        "cross_project_substitution_catalog.json"
    )
    cad_result = _read(
        WORKSPACE
        / "demo/cross_project_substitution/transport-v1/jobs/"
        "project03-job-e64acfa17a55/packet-runs/packet-001-attempt-01/"
        "cad-result.json"
    )
    return (
        augment_release_catalog_with_cross_project_template(
            base,
            substitution,
            legacy_template_id=TRANSPORT_LEGACY_TEMPLATE_ID,
        ),
        cad_result,
    )


def test_generic_cross_project_merge_reuses_project01_lineage_for_transport_slot():
    candidate, cad_result = _transport_release_candidate()
    evidence = build_jj00_ae00_transport_release_evidence(candidate, cad_result)

    templates = [
        row
        for row in candidate["connectionTemplates"]
        if row["legacyTemplateId"] == TRANSPORT_LEGACY_TEMPLATE_ID
    ]
    assert len(templates) == 1
    assert candidate["summary"]["connectionTemplateCount"] == 43
    assert candidate["summary"]["compatibilityCount"] == 68
    assert all(evidence["checks"].values())
    assert evidence["collisionStatus"] == "not_evaluated"
    assert evidence["authorizedDrivingTemplateIds"] == [
        templates[0]["globalTemplateId"]
    ]


def test_transport_natural_language_selects_jj00_ae00_cross_project_template():
    catalog, _ = _transport_release_candidate()
    definitions = {
        str(alias.get("projectId") or "").lower()
        + ":"
        + str(alias.get("moduleToken") or "").lower(): row
        for row in catalog["moduleDefinitions"]
        for alias in row.get("projectAliases") or []
    }
    context = create_global_assembly_context(
        "transport-cross-project-selection-test",
        catalog_digest=catalog["catalogDigest"],
    )
    base = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "先添加Project01 JJ00箱体作为基座。",
            "moduleDefinitionId": definitions["project01:jj00"][
                "moduleDefinitionId"
            ],
        },
    )
    context = apply_global_command_preview(
        context,
        base,
        preview_digest=base["previewDigest"],
        confirmed=True,
    )
    addition = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": (
                "把Project03 AE00传输模组安装到Project01 JJ00传输安装位。"
            ),
            "moduleDefinitionId": definitions["project03:ae00"][
                "moduleDefinitionId"
            ],
        },
    )

    assert addition["status"] == "ready"
    assert addition["blockers"] == []
    connection = addition["proposedPatch"]["connection"]
    assert connection["globalTemplateId"].endswith("/97aed2cb02")
    assert "ae00-frame-installation" in connection["portAId"]
    assert "jj00-transport-installation" in connection["portBId"]


def test_immutable_transport_release_reloads_with_only_transport_template_authorized():
    manifest_path = WORKSPACE / (
        "demo/global_assembly_catalog/releases/"
        "relation-v43-project01-jj00-project03-ae00-transport-driving-20261012/"
        "release-manifest.json"
    )
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=WORKSPACE
    )
    authorized = manifest["scope"]["authorizedDrivingTemplateIds"]

    assert len(authorized) == 1
    assert manifest["scope"]["collisionOrBrepRelease"] is False
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row["globalTemplateId"] == authorized[0]
    )
    assert template["legacyTemplateId"] == TRANSPORT_LEGACY_TEMPLATE_ID


def _generic_reverse_calibration_candidate() -> tuple[dict, dict, str]:
    base = _read(
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v39-project03-ab00-complete-driving-20261012/"
        "global_module_catalog.json"
    )
    substitution = _read(
        WORKSPACE
        / "demo/cross_project_substitution/"
        "calibration-project01-to-project03-v1/"
        "cross_project_substitution_catalog.json"
    )
    legacy_template_id = "cross_project_project01_BD00_to_project03_AH00_slot"
    cad_result = _read(
        WORKSPACE
        / "demo/global_assembly_contexts/manifest_jobs/"
        "project01-job-220a20fa0493/packet-runs/packet-001-attempt-01/"
        "cad-result.json"
    )
    return (
        augment_release_catalog_with_cross_project_template(
            base,
            substitution,
            legacy_template_id=legacy_template_id,
        ),
        cad_result,
        legacy_template_id,
    )


def test_generic_direct_release_evidence_accepts_reviewed_reverse_calibration():
    catalog, cad_result, legacy_template_id = (
        _generic_reverse_calibration_candidate()
    )
    evidence = build_cross_project_direct_release_evidence(
        catalog,
        cad_result,
        legacy_template_id=legacy_template_id,
        release_project_id="project03",
        source_project_id="project01",
        target_project_id="project03",
        driving_scope="project03_AA00_with_project01_BD00_calibration_slot",
        statement="测试反向校准槽位的通用发布证据。",
    )

    assert evidence["schemaVersion"] == "generic-driving-candidate-evidence/v1"
    assert evidence["status"] == "ready"
    assert evidence["collisionStatus"] == "not_evaluated"
    assert len(evidence["authorizedDrivingTemplateIds"]) == 1
    assert all(evidence["checks"].values())


def test_generic_direct_release_evidence_fails_closed_on_incomplete_mate_bundle():
    catalog, cad_result, legacy_template_id = (
        _generic_reverse_calibration_candidate()
    )
    cad_result = copy.deepcopy(cad_result)
    cad_result["toolResult"]["CreatedMateCount"] = 2

    with pytest.raises(
        CrossProjectSlotReleaseError,
        match="threeOfThreeMatesCreated",
    ):
        build_cross_project_direct_release_evidence(
            catalog,
            cad_result,
            legacy_template_id=legacy_template_id,
            release_project_id="project03",
            source_project_id="project01",
            target_project_id="project03",
            driving_scope="project03_AA00_with_project01_BD00_calibration_slot",
            statement="无效证据必须失败关闭。",
        )
