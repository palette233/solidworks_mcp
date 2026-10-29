from pathlib import Path

import pytest

from demo_backend.scanner_target_rule_composition import (
    build_scanner_rule_composition_batch,
    compose_scanner_target_rule,
)
from demo_backend.station_rule_planner import plan_station_chain


ROOT = Path(__file__).resolve().parents[3]


def test_compose_ai00_scanner_with_jj00_target_station():
    result = compose_scanner_target_rule(
        repository_root=ROOT,
        source_rule_path=ROOT / "data/assembly_stations/scanner-ai00-ss00-aa00-v1.json",
        target_rule_path=ROOT / "data/assembly_stations/scanner-sm00-ss00-jj00-v1.json",
        rule_id="scanner-ai00-ss00-jj00-v1",
    )
    assert result["sourceModuleDefinitionId"] == "project03::AI00"
    assert result["transportModuleDefinitionId"] == "project01::SS00"
    assert result["targetBaseDefinitionId"] == "project01::JJ00"
    assert result["status"] == "review_candidate_requires_current_saved_context"
    assert result["cadLaunchAllowed"] is False
    assert result["inputs"]["scannerGraphPath"].endswith(
        "packet-003-attempt-01/execution-effective-mate-graph.json"
    )
    assert result["inputs"]["targetBaseGraphPath"] == (
        "demo/layout_previews/project01_module_mate_graph.json"
    )


def test_compose_sm00_scanner_with_aa00_target_station():
    result = compose_scanner_target_rule(
        repository_root=ROOT,
        source_rule_path=ROOT / "data/assembly_stations/scanner-sm00-ss00-jj00-v1.json",
        target_rule_path=ROOT / "data/assembly_stations/scanner-ai00-ss00-aa00-v1.json",
        rule_id="scanner-sm00-ss00-aa00-v1",
    )
    assert result["sourceModuleDefinitionId"] == "project01::SM00"
    assert result["targetBaseDefinitionId"] == "project03::AA00"
    assert result["opticalMeasurementSelector"]["jsonPointer"] == "/scanners/1"
    assert "opticalGeometryPath" in result["inputs"]


def test_composition_rejects_same_native_rule():
    path = ROOT / "data/assembly_stations/scanner-ai00-ss00-aa00-v1.json"
    with pytest.raises(ValueError, match="different scanner"):
        compose_scanner_target_rule(
            repository_root=ROOT,
            source_rule_path=path,
            target_rule_path=path,
            rule_id="scanner-ai00-ss00-aa00-duplicate",
        )


@pytest.mark.parametrize(
    ("base_project", "base_token", "scanner_project", "scanner_token"),
    [
        ("project01", "JJ00", "project03", "AI00"),
        ("project03", "AA00", "project01", "SM00"),
    ],
)
def test_composed_rule_is_plannable_with_exact_transport_dependency(
    base_project, base_token, scanner_project, scanner_token
):
    request = {
        "chainId": f"test-{scanner_token.lower()}-{base_token.lower()}",
        "baseSelection": {
            "projectId": base_project,
            "moduleToken": base_token,
            "confirmed": True,
        },
        "stationRegistryPath": "data/assembly_stations/station-rules-v31.json",
        "allowPrototypeEstimate": True,
        "placementValidationMode": "target_role_station",
        "steps": [
            {
                "stageId": "s01-transport",
                "moduleRole": "Transport",
                "moduleSelection": {
                    "projectId": "project01",
                    "moduleToken": "SS00",
                    "confirmed": True,
                },
            },
            {
                "stageId": "s02-scanner",
                "moduleRole": "Scanner",
                "moduleSelection": {
                    "projectId": scanner_project,
                    "moduleToken": scanner_token,
                    "confirmed": True,
                },
            },
        ],
    }
    result = plan_station_chain(ROOT, request, prepare_candidates=True)
    assert result["planningComplete"] is True
    assert result["plannedStageCount"] == 2
    scanner = result["stages"][1]["plan"]
    assert scanner["geometry"]["status"] == "requires_current_saved_cad_state"
    assert scanner["instanceBinding"]["instances"]["Transport"] == {
        "instanceId": "s01-transport",
        "moduleDefinitionId": "project01::SS00",
        "role": "Transport",
    }
    assert scanner["targetStationValidated"] is False


def test_batch_finds_only_same_transport_same_reference_candidates():
    result = build_scanner_rule_composition_batch(
        repository_root=ROOT,
        binding_queue_path=ROOT
        / "demo/station_gap_batch_20261028/coverage-v14/scanner-transport-binding-v5.json",
        registry_path=ROOT / "data/assembly_stations/station-rules-v32.json",
    )
    assert result["summary"] == {
        "inputMissingContextCount": 13,
        "exactPointPairCandidateAvailableCount": 2,
        "compositionCandidateReadyCount": 2,
        "independentPointPairOrMeasurementRequiredCount": 9,
        "sourceOpticalProfileRequiredCount": 4,
        "sourceOpticalRoleAndDirectionSelectionRequiredCount": 0,
        "transportBarcodeTargetProfileRequiredCount": 4,
        "transportBarcodeTargetRoleSelectionRequiredCount": 0,
        "bothSourceAndTargetProfileRequiredCount": 1,
        "bothSourceAndTargetDecisionRequiredCount": 1,
    }
    ready = {
        (
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
            row["targetBaseDefinitionId"],
        )
        for row in result["rows"]
        if row["status"] == "composition_candidate_ready"
    }
    assert ready == {
        ("project03::AI00", "project01::SS00", "project01::JJ00"),
        ("project01::SM00", "project01::SS00", "project03::AA00"),
    }
    exact = {
        (
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
            row["targetBaseDefinitionId"],
            row["exactCandidateRuleId"],
        )
        for row in result["rows"]
        if row["status"] == "exact_point_pair_candidate_available"
    }
    assert exact == {
        (
            "project02::A180",
            "project01::SS00",
            "project01::JJ00",
            "scanner-a180-ss00-jj00-point-pair-v1",
        ),
        (
            "project02::A180",
            "project01::SS00",
            "project03::AA00",
            "scanner-a180-ss00-aa00-point-pair-v1",
        ),
    }
    assert result["cadStarted"] is False
    assert result["strictStationValidationAdded"] == 0


def test_batch_recognizes_normalized_a800_point_pair_family():
    result = build_scanner_rule_composition_batch(
        repository_root=ROOT,
        binding_queue_path=ROOT
        / "demo/station_gap_batch_20261028/coverage-v14/scanner-transport-binding-v5.json",
        registry_path=ROOT / "data/assembly_stations/station-rules-v34.json",
    )
    assert result["summary"] == {
        "inputMissingContextCount": 13,
        "exactPointPairCandidateAvailableCount": 4,
        "compositionCandidateReadyCount": 2,
        "independentPointPairOrMeasurementRequiredCount": 7,
        "sourceOpticalProfileRequiredCount": 4,
        "sourceOpticalRoleAndDirectionSelectionRequiredCount": 0,
        "transportBarcodeTargetProfileRequiredCount": 4,
        "transportBarcodeTargetRoleSelectionRequiredCount": 0,
        "bothSourceAndTargetProfileRequiredCount": 1,
        "bothSourceAndTargetDecisionRequiredCount": 1,
    }
    exact = {
        (
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
            row["targetBaseDefinitionId"],
        )
        for row in result["rows"]
        if row["status"] == "exact_point_pair_candidate_available"
    }
    assert {
        ("project01::SM00", "project02::A800", "project02::A600"),
        ("project03::AI00", "project02::A800", "project02::A600"),
    }.issubset(exact)
    missing = {
        (
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
        ): row["requiredNextEvidence"]
        for row in result["rows"]
        if row["status"] == "independent_point_pair_or_measurement_required"
    }
    assert missing[("project05::F000", "project01::SS00")] == [
        "source_scanner_local_optical_profile_and_role_selection"
    ]
    assert missing[("project01::SM00", "project05::D000")] == [
        "transport_local_barcode_target_profile_and_target_role"
    ]
    assert missing[("project05::F000", "project05::D000")] == [
        "source_scanner_local_optical_profile_and_role_selection",
        "transport_local_barcode_target_profile_and_target_role",
    ]
    assert result["strictStationValidationAdded"] == 0


def test_batch_reuses_d000_target_candidates_without_choosing_a_role():
    result = build_scanner_rule_composition_batch(
        repository_root=ROOT,
        binding_queue_path=ROOT
        / "demo/station_gap_batch_20261028/coverage-v14/scanner-transport-binding-v5.json",
        registry_path=ROOT / "data/assembly_stations/station-rules-v34.json",
        target_candidate_catalog_path=ROOT
        / "data/assembly_stations/scanner-target-candidates-d000-v1.json",
    )
    assert result["summary"]["transportBarcodeTargetProfileRequiredCount"] == 0
    assert result["summary"]["transportBarcodeTargetRoleSelectionRequiredCount"] == 4
    assert result["summary"]["bothSourceAndTargetProfileRequiredCount"] == 0
    assert result["summary"]["bothSourceAndTargetDecisionRequiredCount"] == 1
    d000 = [
        row
        for row in result["rows"]
        if row["transportModuleDefinitionId"] == "project05::D000"
    ]
    assert len(d000) == 4
    assert all(row["transportBarcodeTargetCandidateAvailable"] for row in d000)
    assert all(
        "transport_barcode_target_role_selection_from_candidate_catalog"
        in row["requiredNextEvidence"]
        for row in d000
    )
    assert all(row["status"] == "independent_point_pair_or_measurement_required" for row in d000)
    assert result["strictStationValidationAdded"] == 0


def test_batch_reuses_f000_and_d000_candidates_without_choosing_roles():
    result = build_scanner_rule_composition_batch(
        repository_root=ROOT,
        binding_queue_path=ROOT
        / "demo/station_gap_batch_20261028/coverage-v14/scanner-transport-binding-v5.json",
        registry_path=ROOT / "data/assembly_stations/station-rules-v34.json",
        target_candidate_catalog_path=ROOT
        / "data/assembly_stations/scanner-target-candidates-d000-v1.json",
        source_candidate_catalog_path=ROOT
        / "data/assembly_stations/scanner-source-candidates-f000-v1.json",
    )
    summary = result["summary"]
    assert summary["sourceOpticalProfileRequiredCount"] == 0
    assert summary["sourceOpticalRoleAndDirectionSelectionRequiredCount"] == 4
    assert summary["transportBarcodeTargetProfileRequiredCount"] == 0
    assert summary["transportBarcodeTargetRoleSelectionRequiredCount"] == 4
    assert summary["bothSourceAndTargetProfileRequiredCount"] == 0
    assert summary["bothSourceAndTargetDecisionRequiredCount"] == 1
    f000 = [
        row
        for row in result["rows"]
        if row["sourceModuleDefinitionId"] == "project05::F000"
    ]
    assert len(f000) == 4
    assert all(row["sourceOpticalCandidateAvailable"] for row in f000)
    assert all(
        "source_scanner_head_role_and_direction_selection_from_candidate_catalog"
        in row["requiredNextEvidence"]
        for row in f000
    )
    assert result["strictStationValidationAdded"] == 0
