import json
from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.cross_project_module_substitution import (
    CrossProjectModuleSubstitutionError,
    augment_catalog_with_role_and_port_overlay,
    build_cross_project_candidate_matrix,
    build_cross_project_substitution_catalog,
    build_module_role_overlay,
    compile_substitution_preview,
    compose_cross_project_effective_mate_graph,
    validate_module_role_overlay,
)
from demo_backend.global_module_catalog import validate_global_module_catalog
from demo_backend.main import preview_cross_project_module_substitution_api
from demo_backend.models import CrossProjectModuleSubstitutionPreviewRequest


WORKSPACE = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    WORKSPACE / "demo/global_assembly_catalog/v1/global_module_catalog.json"
)


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))


def test_role_overlay_covers_every_existing_module_without_mutating_source_catalog():
    catalog = _catalog()
    source_digest = catalog["catalogDigest"]
    overlay = build_module_role_overlay(catalog)

    validation = validate_module_role_overlay(overlay, catalog)

    assert validation["success"] is True
    assert overlay["moduleCount"] == 43
    assert all(
        row["roleReviewStatus"] == "accepted_by_user"
        for row in overlay["modules"]
    )
    assert catalog["catalogDigest"] == source_digest
    assert all("semanticRole" not in row for row in catalog["moduleDefinitions"])


def test_normalized_port_overlay_preserves_authoritative_fields_and_digest_validity():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)
    original_interfaces = {
        row["globalPortId"]: row.get("interfaceType")
        for row in catalog["semanticPorts"]
    }

    normalized = augment_catalog_with_role_and_port_overlay(catalog, overlay)

    assert validate_global_module_catalog(normalized)["success"] is True
    assert len(normalized["semanticPorts"]) == 74
    assert all(row.get("normalizedInterface") for row in normalized["semanticPorts"])
    assert {
        row["globalPortId"]: row.get("interfaceType")
        for row in normalized["semanticPorts"]
    } == original_interfaces


def test_a200_own_mount_and_child_slot_have_opposite_port_directions():
    catalog = _catalog()
    normalized = augment_catalog_with_role_and_port_overlay(
        catalog, build_module_role_overlay(catalog)
    )
    ports = {
        row["globalPortId"]: row["normalizedInterface"]
        for row in normalized["semanticPorts"]
    }
    own_mount = next(
        value for key, value in ports.items() if "a200-frame-installation" in key
    )
    child_slot = next(
        value for key, value in ports.items() if "a200-t401-2-installation" in key
    )

    assert own_mount["portDirection"] == "required"
    assert own_mount["portPurpose"] == "external_installation"
    assert own_mount["installationProfileId"].endswith("a200-frame-installation")
    assert child_slot["portDirection"] == "provided"
    assert child_slot["portPurpose"] == "child_module_slot"
    assert child_slot["canonicalInterfaceClass"] == "glue_supply_base_mount"
    assert child_slot["slotRole"] == "GlueSupply"


def test_project03_ah00_can_fill_project01_bd00_slot_and_compile_three_mates():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)

    candidate, report = build_cross_project_substitution_catalog(
        catalog,
        overlay,
        source_module="project03:AH00",
        replaced_module="project01:BD00",
    )
    preview = compile_substitution_preview(
        catalog,
        overlay,
        source_module="project03:AH00",
        replaced_module="project01:BD00",
        requirement="在项目01中使用项目03 AH00针头校准模组替换BD00。",
    )

    assert report["status"] == "ready_for_cad_dry_run"
    assert report["blockers"] == []
    assert report["canonicalInterfaceClass"] == "calibration_base_mount"
    assert report["sourceMateSignature"]["closed"] is True
    assert report["targetMateSignature"]["closed"] is True
    assert report["sourceMateSignature"]["signature"] == report["targetMateSignature"][
        "signature"
    ]
    geometry = report["locatingFeatureGeometry"]
    assert geometry["compatible"] is True
    assert geometry["differences"] == [
        {
            "roles": ["locating_hole_1", "locating_hole_2"],
            "sourceDistanceMeters": pytest.approx(0.05),
            "targetDistanceMeters": pytest.approx(0.05),
            "absoluteDifferenceMeters": pytest.approx(0.0, abs=1e-12),
        }
    ]
    assert validate_global_module_catalog(candidate)["success"] is True
    assert preview["status"] == "ready_for_effective_graph_composition"
    assert preview["success"] is True
    assert len(preview["context"]["instances"]) == 2
    assert len(preview["context"]["connections"]) == 1
    manifest = preview["cadTransactionManifest"]
    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["packetCount"] == 1
    assert manifest["blockers"] == []
    assert len(manifest["packets"][0]["connections"][0]["mates"]) == 3
    assert preview["cadStarted"] is False
    assert preview["effectiveMateGraphBound"] is False
    assert preview["collisionStatus"] == "not_evaluated"


def test_role_mismatch_is_rejected_before_cad_transaction_compilation():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)

    candidate, report = build_cross_project_substitution_catalog(
        catalog,
        overlay,
        source_module="project03:AH00",
        replaced_module="project01:SM00",
    )

    assert report["status"] == "blocked"
    assert "PRIMARY_ROLE_MISMATCH" in {row["code"] for row in report["blockers"]}
    assert report["derivedTemplateId"] is None
    assert len(candidate["connectionTemplates"]) == len(catalog["connectionTemplates"])


def test_scanner_spacing_mismatch_returns_adapter_action_without_starting_cad():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)

    preview = compile_substitution_preview(
        catalog,
        overlay,
        source_module="project03:AI00",
        replaced_module="project01:SM00",
        requirement="用项目03 AI00扫描模组替换项目01 SM00。",
    )

    assert preview["success"] is False
    assert preview["status"] == "blocked"
    assert preview["cadStarted"] is False
    disposition = preview["engineeringDisposition"]
    assert disposition["classification"] == (
        "known_pattern_mismatch_adapter_candidate"
    )
    assert disposition["directCombinationAllowed"] is False
    assert disposition["cadLaunchDecision"] == "fail_closed_before_cad"
    assert disposition["knownLocatingDifferences"] == [
        {
            "roles": ["locating_hole_1", "locating_hole_2"],
            "sourceDistanceMeters": pytest.approx(0.2),
            "targetDistanceMeters": pytest.approx(0.022),
            "absoluteDifferenceMeters": pytest.approx(0.178),
        }
    ]
    assert preview["userFailureExplanation"]["reasonCode"] == (
        "LOCATING_PATTERN_MISMATCH"
    )
    assert preview["userFailureExplanation"]["cadLaunchDecision"] == (
        "fail_closed_before_cad"
    )


def test_overlay_digest_change_is_detected():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)
    tampered = deepcopy(overlay)
    tampered["modules"][0]["primaryRole"] = "Tampered"

    with pytest.raises(CrossProjectModuleSubstitutionError, match="摘要不匹配"):
        validate_module_role_overlay(tampered, catalog)


def test_backend_api_exposes_offline_cross_project_substitution_preview():
    result = preview_cross_project_module_substitution_api(
        CrossProjectModuleSubstitutionPreviewRequest(
            sourceModule="project03:AH00",
            replacedModule="project01:BD00",
            requirement="在项目01中使用项目03 AH00针头校准模组替换BD00。",
        )
    )

    assert result["success"] is True
    assert result["status"] == "ready_for_effective_graph_composition"
    assert result["cadStarted"] is False
    assert result["cadTransactionManifest"]["packetCount"] == 1


def test_backend_api_explains_scanner_adapter_requirement_before_cad():
    result = preview_cross_project_module_substitution_api(
        CrossProjectModuleSubstitutionPreviewRequest(
            sourceModule="project03:AI00",
            replacedModule="project01:SM00",
            requirement="用项目03 AI00扫描模组替换项目01 SM00。",
        )
    )

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["cadStarted"] is False
    assert result["engineeringDisposition"]["classification"] == (
        "known_pattern_mismatch_adapter_candidate"
    )
    assert result["engineeringDisposition"]["knownLocatingDifferences"][0][
        "absoluteDifferenceMeters"
    ] == pytest.approx(0.178)
    assert result["userFailureExplanation"]["reasonCode"] == (
        "LOCATING_PATTERN_MISMATCH"
    )


@pytest.mark.parametrize(
    ("source_module", "replaced_module"),
    [
        ("project02:T401", "project01:GJ00"),
        ("project01:GJ00", "project02:T401"),
    ],
)
def test_t401_multi_profile_is_resolved_by_target_slot_context(
    source_module, replaced_module
):
    release = (
        WORKSPACE
        / "demo/global_assembly_catalog/releases/"
        "relation-v36-project02-nine-addon-portable-driving-20261011/"
        "global_module_catalog.json"
    )
    catalog = json.loads(release.read_text(encoding="utf-8-sig"))
    _, report = build_cross_project_substitution_catalog(
        catalog,
        build_module_role_overlay(catalog),
        source_module=source_module,
        replaced_module=replaced_module,
    )

    assert report["status"] == "blocked"
    assert report["sourceTemplateId"].endswith(
        (
            "t401-1-to-a600-nonanchor-driving-v1/6b6481abad"
            if source_module.endswith("T401")
            else "gj00-to-jj00-three-datum-installation/20ca3f8c0f"
        )
    )
    assert report["targetSlotTemplateId"].endswith(
        (
            "t401-1-to-a600-nonanchor-driving-v1/6b6481abad"
            if replaced_module.endswith("T401")
            else "gj00-to-jj00-three-datum-installation/20ca3f8c0f"
        )
    )
    assert {row["code"] for row in report["blockers"]} == {
        "MATE_TOPOLOGY_MISMATCH",
        "LOCATING_FEATURE_GEOMETRY_NOT_COMPARABLE",
    }


def test_cross_project_effective_graph_combines_ah00_with_jj00_without_pose_anchors():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)

    graph = compose_cross_project_effective_mate_graph(
        WORKSPACE,
        catalog,
        overlay,
        source_module="project03:AH00",
        replaced_module="project01:BD00",
    )

    assert graph["ModuleCount"] == 2
    assert graph["InterModuleMateCount"] == 3
    assert graph["BaseGraphPolicy"]["moduleTokens"] == ["JJ00"]
    assert {
        row["ModuleToken"] for row in graph["Modules"]
    } == {"JJ00", "FL9A24D063AH00"}
    assert [row["MateName"] for row in graph["Mates"]] == [
        "重合7",
        "同心12",
        "同心13",
    ]
    assert all(
        set(row["ModuleTokens"]) == {"JJ00", "FL9A24D063AH00"}
        for row in graph["Mates"]
    )
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["CrossProjectComposition"]["topLevelOrLeafPoseAnchorsUsed"] is False


def test_candidate_matrix_separates_ready_incompatible_and_missing_port_pairs():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)
    release_root = WORKSPACE / "demo/global_assembly_catalog/releases"
    release_names = [
        "relation-v38-project01-topology-bound-combination-driving-20261011",
        "relation-v36-project02-nine-addon-portable-driving-20261011",
        "relation-v39-project03-ab00-complete-driving-20261012",
        "relation-v28-project05-all-eight-addon-portable-driving-20261011",
    ]
    evidence_catalogs = [
        catalog,
        *[
            json.loads(
                (release_root / name / "global_module_catalog.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            for name in release_names
        ],
    ]

    matrix = build_cross_project_candidate_matrix(
        catalog,
        overlay,
        evidence_catalogs=evidence_catalogs,
        deferred_project_ids={"project06"},
    )

    def find(source_project, source_token, target_project, target_token):
        return next(
            row
            for row in matrix["rows"]
            if row["sourceProjectIds"] == [source_project]
            and row["sourceModuleTokens"] == [source_token]
            and row["targetProjectIds"] == [target_project]
            and row["targetModuleTokens"] == [target_token]
        )

    assert find("project03", "AH00", "project01", "BD00")["status"] == (
        "ready_for_effective_graph_composition"
    )
    assert find("project03", "AI00", "project01", "SM00")["status"] == (
        "incompatible"
    )
    assert find("project03", "AE00", "project01", "SS00")["status"] == (
        "ready_for_effective_graph_composition"
    )
    assert find("project05", "M000", "project06", "M000")["status"] == (
        "needs_endpoint_or_template"
    )
    a200_to_m000 = find("project02", "A200", "project05", "M000")
    assert a200_to_m000["status"] == "incompatible"
    assert a200_to_m000["sourceAtomicInstallationCount"] == 1
    assert a200_to_m000["targetAtomicInstallationCount"] == 1
    assert {
        blocker["code"] for blocker in a200_to_m000["blockers"]
    } == {
        "MATE_TOPOLOGY_MISMATCH",
        "LOCATING_FEATURE_GEOMETRY_NOT_COMPARABLE",
    }
    t401_to_gj00 = find("project02", "T401", "project01", "GJ00")
    assert t401_to_gj00["status"] == "incompatible"
    assert t401_to_gj00["sourceAtomicInstallationCount"] == 2
    assert t401_to_gj00["optimalCandidatePairCount"] == 1
    assert t401_to_gj00["selectedAssessment"]["sourceInstallation"][
        "installationProfileId"
    ].endswith("t401-t401-1-installation")
    assert t401_to_gj00["selectedAssessment"]["sourceInstallation"][
        "targetSlotProviderRole"
    ] == "Base"
    assert matrix["statusCounts"]["needs_template_disambiguation"] == 0
    assert matrix["statusCounts"]["needs_endpoint_or_template"] == 48
    assert matrix["activeStatusCounts"]["needs_endpoint_or_template"] == 0
    assert matrix["deferredDirectionalPairCount"] == 48
    assert matrix["statusCounts"]["ready_for_effective_graph_composition"] >= 2
    gn00_to_a700 = find("project01", "GN00", "project02", "A700")
    assert gn00_to_a700["status"] == "incompatible"
    assert gn00_to_a700["sourceInstallationProfileCount"] == 1
    assert gn00_to_a700["selectedAssessment"]["sourceInstallation"][
        "candidateKind"
    ] == "template_combination"
    assert gn00_to_a700["selectedAssessment"]["sourceInstallation"][
        "targetSlotProviderRoles"
    ] == ["Base", "Transport"]
    ab00_to_a100 = find("project03", "AB00", "project02", "A100")
    assert ab00_to_a100["status"] == "incompatible"
    assert ab00_to_a100["sourceInstallationProfileCount"] == 1
    assert ab00_to_a100["selectedAssessment"]["sourceInstallation"][
        "candidateKind"
    ] == "atomic_template"
    assert matrix["policy"]["immutableReleasesMutated"] is False


def test_candidate_matrix_separates_released_cross_project_execution_from_native_profiles():
    catalog = _catalog()
    overlay = build_module_role_overlay(catalog)
    release_root = WORKSPACE / "demo/global_assembly_catalog/releases"
    release_names = [
        "relation-v43-project01-jj00-project03-ae00-transport-driving-20261012",
        "relation-v42-project02-a600-ah00-operation-side-language-20261012",
        "relation-v39-project03-ab00-complete-driving-20261012",
        "relation-v28-project05-all-eight-addon-portable-driving-20261011",
    ]
    evidence_catalogs = [
        catalog,
        *[
            json.loads(
                (release_root / name / "global_module_catalog.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            for name in release_names
        ],
    ]
    matrix = build_cross_project_candidate_matrix(
        catalog,
        overlay,
        evidence_catalogs=evidence_catalogs,
        deferred_project_ids={"project06"},
        released_direct_executions=[
            {
                "status": "released_direct_execution",
                "releaseId": release_names[0],
                "globalTemplateId": (
                    "template/cross-project/ae00-to-project01-ss00-slot/97aed2cb02"
                ),
                "sourceModuleTemplateId": (
                    "template/project03/ae00-to-aa00-three-datum-installation/"
                    "3665a437a8"
                ),
                "targetSlotTemplateId": (
                    "template/project01/ss00-to-jj00-three-datum-installation/"
                    "c087ea93d1"
                ),
                "collisionStatus": "not_evaluated",
            },
            {
                "status": "released_direct_execution",
                "releaseId": release_names[1],
                "globalTemplateId": (
                    "template/project02/"
                    "ah00-to-a600-cross-project-three-datum-installat/a133494fd1"
                ),
                "sourceModuleTemplateId": None,
                "targetSlotTemplateId": None,
                "collisionStatus": "not_evaluated",
            },
        ],
    )

    def find(source_project, source_token, target_project, target_token):
        return next(
            row
            for row in matrix["rows"]
            if row["sourceProjectIds"] == [source_project]
            and row["sourceModuleTokens"] == [source_token]
            and row["targetProjectIds"] == [target_project]
            and row["targetModuleTokens"] == [target_token]
        )

    forward = find("project03", "AE00", "project01", "SS00")
    reverse = find("project01", "SS00", "project03", "AE00")
    calibration = find("project03", "AH00", "project01", "BD00")
    assert forward["status"] == "released_direct_execution"
    assert forward["releasedDirectExecution"]["releaseId"] == release_names[0]
    assert reverse["status"] == "ready_for_effective_graph_composition"
    assert calibration["status"] == "ready_for_effective_graph_composition"
    assert matrix["releasedDirectExecutionCount"] == 2
    assert matrix["activeStatusCounts"]["released_direct_execution"] == 1
    assert matrix["activeStatusCounts"]["needs_template_disambiguation"] == 0
    assert matrix["policy"][
        "crossProjectExecutionTemplatesExcludedFromNativeProfiles"
    ] is True
    role_summaries = {row["group"]: row for row in matrix["roleSummaries"]}
    assert role_summaries["Transport"]["activeStatusCounts"][
        "released_direct_execution"
    ] == 1
    assert role_summaries["Calibration"]["activeStatusCounts"][
        "ready_for_effective_graph_composition"
    ] >= 1
    assert matrix["projectPairSummaries"]


def test_project01_gn00_combination_context_port_direction_is_evidence_backed():
    release = WORKSPACE / (
        "demo/global_assembly_catalog/releases/"
        "relation-v38-project01-topology-bound-combination-driving-20261011/"
        "global_module_catalog.json"
    )
    catalog = json.loads(release.read_text(encoding="utf-8-sig"))
    normalized = augment_catalog_with_role_and_port_overlay(
        catalog, build_module_role_overlay(catalog)
    )
    port = next(
        row
        for row in normalized["semanticPorts"]
        if "SS00.gn00_anti_rotation" in (row.get("aliases") or [])
    )

    assert port["normalizedInterface"] == {
        "canonicalInterfaceClass": "service_station_base_mount",
        "portPurpose": "child_module_slot",
        "portDirection": "provided",
        "ownerRole": "Transport",
        "slotRole": "CleaningWeighing",
        "installationProfileId": None,
        "endpointRoles": ["anti_rotation_plane"],
        "sourceInterfaceType": "project01_gn00_anti_rotation",
        "reviewStatus": "evidence_backed_direction_override",
    }
