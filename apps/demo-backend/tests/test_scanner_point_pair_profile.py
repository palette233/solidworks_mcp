import json
from pathlib import Path

import pytest

from demo_backend.scanner_point_pair_binding import (
    _point_to_world,
    _reproject_direction,
    evaluate_scanner_point_pair_in_saved_context,
)
from demo_backend.scanner_point_pair_profile import (
    build_a180_ss00_point_pair_profile,
    build_point_pair_profile_from_scanner_rule_and_direct_target,
    build_scanner_point_pair_rule,
    build_scanner_optical_source_candidate_catalog,
    build_transport_barcode_target_candidate_catalog,
)
from demo_backend.station_rule_planner import plan_station_chain


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "demo/layout_previews/project02_scanner_barcode_points.json"
TARGET = ROOT / "demo/cross_project_substitution/cumulative-project03-v2/scanner-transport-process-validation.json"
CATALOG = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
PROFILE = ROOT / "data/assembly_stations/scanner-point-pair-a180-ss00-v1.json"
PROJECT05_OPTICAL = ROOT / "demo/layout_previews/project05_optical_geometry.json"
PROJECT05_GRAPH = ROOT / "demo/layout_previews/project05_module_mate_graph.json"


def test_project05_d000_target_candidates_are_local_and_fail_closed():
    catalog = build_transport_barcode_target_candidate_catalog(
        repository_root=ROOT,
        optical_geometry_path=PROJECT05_OPTICAL,
        module_graph_path=PROJECT05_GRAPH,
        transport_module_definition_id="project05::D000",
        catalog_id="test-project05-d000-barcode-targets",
    )
    assert catalog["roleSelectionRequired"] is True
    assert catalog["prototypePoseAllowedAsCadExecutionAuthority"] is False
    assert catalog["cadStarted"] is False
    assert [row["targetRole"] for row in catalog["candidates"]] == [
        "carrier-barcode",
        "four-product-barcodes",
    ]
    for row in catalog["candidates"]:
        assert row["roleEngineeringConfirmed"] is False
        assert row["readyForPointPairRule"] is False
        assert _point_to_world(
            row["localBarcodeTargetMeters"], row["referenceTransform"]
        ) == pytest.approx(row["prototypeWorldTargetMetersForAuditOnly"], abs=1e-12)


def test_project05_f000_source_candidates_preserve_all_role_and_sign_choices():
    catalog = build_scanner_optical_source_candidate_catalog(
        repository_root=ROOT,
        optical_geometry_path=PROJECT05_OPTICAL,
        module_graph_path=PROJECT05_GRAPH,
        scanner_module_definition_id="project05::F000",
        catalog_id="test-project05-f000-optical-sources",
    )
    assert catalog["roleAndDirectionSelectionRequired"] is True
    assert catalog["prototypePoseAllowedAsCadExecutionAuthority"] is False
    assert catalog["cadStarted"] is False
    assert len(catalog["candidates"]) == 8
    choices = {
        (row["sourceBeamId"], row["targetRole"], row["directionSignChoice"])
        for row in catalog["candidates"]
    }
    assert len(choices) == 8
    for row in catalog["candidates"]:
        assert row["roleEngineeringConfirmed"] is False
        assert row["directionSignEngineeringConfirmed"] is False
        assert row["readyForPointPairRule"] is False
        assert _point_to_world(
            row["localOpticalOriginMeters"], row["referenceTransform"]
        ) == pytest.approx(row["prototypeWorldOriginForAuditOnly"], abs=1e-12)


def test_profile_converts_points_to_owning_module_frames():
    profile = build_a180_ss00_point_pair_profile(
        source_measurement_path=SOURCE, target_process_path=TARGET
    )
    assert profile["sourceScanner"]["moduleDefinitionId"] == "project02::A180"
    assert profile["targetTransport"]["moduleDefinitionId"] == "project01::SS00"
    assert profile["targetTransport"]["targetKind"] == "barcode_lane_proxy_at_scan_station"
    assert profile["targetTransport"]["engineeringConfirmed"] is False
    local = profile["targetTransport"]["localBarcodeTargetMeters"]
    transform = profile["targetTransport"]["referenceTransform"]
    world = _point_to_world(local, transform)
    process = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    frame = process["targetTransport"]["installationFrameWorld"]
    station = process["readOnlyChecks"]["barcodeLaneTargetAtScannerStationMeters"]
    expected = [
        frame["origin"][axis]
        + station[0] * frame["flowAxis"][axis]
        + station[1] * frame["transverseAxis"][axis]
        + station[2] * frame["upAxis"][axis]
        for axis in range(3)
    ]
    assert world == pytest.approx(expected, abs=1e-12)


def test_profile_rule_reprojects_in_synthetic_current_context(tmp_path):
    profile = build_a180_ss00_point_pair_profile(
        source_measurement_path=SOURCE, target_process_path=TARGET
    )
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    # The builder only accepts repository evidence; use the real generated path
    # contract below after replacing the temporary path in a direct rule.
    rule = {
        "schemaVersion": "scanner-local-point-pair-rule/v1",
        "ruleId": "synthetic-a180-ss00-jj00",
        "sourceModuleDefinitionId": "project02::A180",
        "transportModuleDefinitionId": "project01::SS00",
        "targetBaseDefinitionId": "project01::JJ00",
        "componentSourcePaths": {"scanner": "a180", "transport": "ss00", "targetBase": "jj00"},
        "workingDistanceRangeEvidence": profile["workingDistanceRangeEvidence"],
        "crossTrackToleranceMeters": profile["crossTrackToleranceMeters"],
    }
    target_transform = profile["targetTransport"]["referenceTransform"]
    target_world = _point_to_world(profile["targetTransport"]["localBarcodeTargetMeters"], target_transform)
    scanner_rotation = [1, 0, 0, 0, 1, 0, 0, 0, 1]
    scanner_transform = scanner_rotation + [0, 0, 0, 1, 0, 0, 0]
    direction = _reproject_direction(
        profile["sourceScanner"]["opticalDirectionWorld"],
        profile["sourceScanner"]["referenceTransform"],
        scanner_transform,
    )
    local = profile["sourceScanner"]["localOpticalOriginMeters"]
    desired_origin = [target_world[i] - 0.1 * direction[i] for i in range(3)]
    scanner_transform[9:12] = [desired_origin[i] - local[i] for i in range(3)]
    state = {
        "success": True,
        "assemblySha256": "a" * 64,
        "observed": {
            "readOnly": True,
            "components": [
                {"name": "a180-1", "sourcePath": "a180", "transform": scanner_transform},
                {"name": "ss00-1", "sourcePath": "ss00", "transform": target_transform},
                {"name": "jj00-1", "sourcePath": "jj00", "transform": [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]},
            ],
        },
    }
    result = evaluate_scanner_point_pair_in_saved_context(
        rule=rule,
        measurement=profile,
        saved_state=state,
        state_path="synthetic-state",
        state_sha256="b" * 64,
        assembly_sha256="a" * 64,
    )
    assert result["geometry"]["requiredWorkingDistanceMeters"] == pytest.approx(0.1)
    assert result["geometry"]["crossTrackErrorMeters"] == pytest.approx(0, abs=1e-12)
    assert result["processProxyValidationPassed"] is True
    assert result["targetEvidenceKind"] == "barcode_lane_proxy_at_scan_station"
    assert result["targetEngineeringConfirmed"] is False


@pytest.mark.parametrize(
    ("base", "rule_id"),
    [
        ("project01::JJ00", "scanner-a180-ss00-jj00-point-pair-v1"),
        ("project03::AA00", "scanner-a180-ss00-aa00-point-pair-v1"),
    ],
)
def test_rule_builder_binds_exact_catalog_sources_after_profile_is_materialized(
    base, rule_id
):
    rule = build_scanner_point_pair_rule(
            repository_root=ROOT,
            profile_path=PROFILE,
            module_catalog_path=CATALOG,
            target_base_definition_id=base,
            rule_id=rule_id,
    )
    assert rule["sourceModuleDefinitionId"] == "project02::A180"
    assert rule["transportModuleDefinitionId"] == "project01::SS00"
    assert rule["targetBaseDefinitionId"] == base
    assert rule["prototypePoseAllowedAsCadExecutionAuthority"] is False


@pytest.mark.parametrize(
    ("base_project", "base_token"),
    [("project01", "JJ00"), ("project03", "AA00")],
)
def test_materialized_point_pair_rule_plans_with_exact_ss00_dependency(
    base_project, base_token
):
    request = {
        "chainId": f"test-a180-ss00-{base_token.lower()}",
        "baseSelection": {
            "projectId": base_project,
            "moduleToken": base_token,
            "confirmed": True,
        },
        "stationRegistryPath": "data/assembly_stations/station-rules-v32.json",
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
                    "projectId": "project02",
                    "moduleToken": "A180",
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


@pytest.mark.parametrize(
    ("rule_name", "scanner_definition"),
    [
        ("scanner-sm00-ss00-jj00-v1.json", "project01::SM00"),
        ("scanner-ai00-ss00-aa00-v1.json", "project03::AI00"),
    ],
)
def test_existing_scanner_optics_can_pair_with_direct_a800_target(
    rule_name, scanner_definition
):
    profile = build_point_pair_profile_from_scanner_rule_and_direct_target(
        repository_root=ROOT,
        scanner_rule_path=ROOT / "data/assembly_stations" / rule_name,
        target_measurement_path=SOURCE,
        profile_id=f"test-{scanner_definition.split('::')[1].lower()}-a800",
    )
    assert profile["sourceScanner"]["moduleDefinitionId"] == scanner_definition
    assert profile["targetTransport"]["moduleDefinitionId"] == "project02::A800"
    assert profile["targetTransport"]["targetKind"] == "direct_cad_face"
    assert profile["targetTransport"]["engineeringConfirmed"] is True
    reference = profile["sourceScanner"]["referenceTransform"]
    local = profile["sourceScanner"]["localOpticalOriginMeters"]
    reconstructed = _point_to_world(local, reference)
    rule = json.loads(
        (ROOT / "data/assembly_stations" / rule_name).read_text(encoding="utf-8")
    )
    if rule.get("opticalMeasurementSelector"):
        optical = json.loads(
            (ROOT / rule["inputs"]["opticalGeometryPath"]).read_text(encoding="utf-8")
        )["scanners"][1]["opticalOriginWorldMeters"]
    else:
        process = json.loads(
            (ROOT / rule["inputs"]["processEvidencePath"]).read_text(encoding="utf-8")
        )
        optical = process["sourceScanner"]["opticalOriginWorldMeters"]
    assert reconstructed == pytest.approx(optical, abs=1e-12)
    assert profile["cadStarted"] is False
