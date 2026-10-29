import copy
import json
from pathlib import Path

import pytest

from demo_backend import calibration_function_point as mod


ROOT = Path(__file__).resolve().parents[3]
SOURCES = Path("data/assembly_stations/calibration-function-point-sources-v1.json")
GAPS = ROOT / "demo/station_gap_batch_20261028/coverage-v12/gap-batch-v19/gap-queue.json"


def test_real_four_project_catalog_has_local_and_target_points_without_cad():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    assert {row["moduleDefinitionId"] for row in catalog["entries"]} == {
        "project01::BD00", "project02::A500", "project03::AH00", "project05::G000",
    }
    assert {row["nativeTargetBaseDefinitionId"] for row in catalog["entries"]} == {
        "project01::JJ00", "project02::A600", "project03::AA00", "project05::A000",
    }
    assert all(len(row["pointLocalMeters"]) == 3 for row in catalog["entries"])
    assert all(len(row["nativePointInBaseMeters"]) == 3 for row in catalog["entries"])
    assert all(len(row["nativeModuleSourceTransformForMeasurementOnly"]) == 16
               for row in catalog["entries"])
    assert all(len(row["nativeBaseSourceTransformForMeasurementOnly"]) == 16
               for row in catalog["entries"])
    assert all(row["engineeringConfirmed"] is False for row in catalog["entries"])
    assert catalog["cadExecuted"] is False

    config = mod._read(ROOT / SOURCES)
    specs = {row["moduleDefinitionId"]: row for row in config["entries"]}
    for entry in catalog["entries"]:
        spec = specs[entry["moduleDefinitionId"]]
        graph = mod._read(ROOT / spec["nativeGraphPath"])
        module_pose = mod._transform(mod._module(graph, spec["moduleToken"])["SourceTransform"])
        base_pose = mod._transform(mod._module(graph, spec["baseToken"])["SourceTransform"])
        projected = mod._point(mod._point(entry["pointLocalMeters"], module_pose), base_pose, inverse=True)
        assert projected == pytest.approx(entry["nativePointInBaseMeters"], abs=1e-9)


def test_real_gap_queue_is_screened_without_authorizing_cad():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    result = mod.screen_calibration_gap_pairs(
        ROOT, catalog, json.loads(GAPS.read_text(encoding="utf-8-sig")))
    assert result["summary"]["listedPairCount"] == 12
    assert (result["summary"]["evaluatedPairCount"]
            + result["summary"]["evidenceMissingPairCount"] == 12)
    assert (result["summary"]["passedPairCount"]
            + result["summary"]["mismatchedPairCount"]
            == result["summary"]["evaluatedPairCount"])
    assert sum(row["status"] == "historical_pair_pose_missing" for row in result["pairs"]) < 9
    assert all(row["cadLaunchAllowed"] is False for row in result["pairs"])
    assert all(row["newCadExecuted"] is False for row in result["pairs"])
    assert result["cadExecuted"] is False
    reports = mod.build_station_functional_screening_reports(result)
    assert len(reports) == result["summary"]["evaluatedPairCount"]
    assert all(report["screening"]["passed"] is False for report in reports)
    assert all(report["cadExecuted"] is False for report in reports)


def test_changed_service_point_or_duplicate_identity_fails_closed(monkeypatch):
    original = mod._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if Path(path).name == "project01_service_points.json":
            point = next(row for row in payload["servicePorts"] if row["id"] == "calibration-prism-target")
            point["capability"] = "unknown"
        return payload

    monkeypatch.setattr(mod, "_read", changed)
    with pytest.raises(ValueError, match="missing or ambiguous"):
        mod.build_calibration_function_point_catalog(ROOT, SOURCES)


def test_screening_rejects_missing_historical_graph():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    gaps = {"queue": [{"sourceModuleDefinitionId": "project01::BD00",
                       "targetBaseDefinitionId": "project02::A600",
                       "role": "Calibration", "validatedStationRule": False,
                       "historicalPairEvidence": {}}]}
    result = mod.screen_calibration_gap_pairs(ROOT, catalog, gaps)
    assert result["pairs"][0]["status"] == "historical_pair_pose_missing"
    assert result["pairs"][0]["passed"] is False


def test_planar_candidate_solver_preserves_support_and_does_not_hide_height_gap():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    result = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    assert result["summary"] == {
        "listedPairCount": 12,
        "datumUnavailablePairCount": 0,
        "topologySpecificDerivationRequiredPairCount": 0,
        "topologyCandidateReviewRequiredPairCount": 3,
        "topologyCandidateMismatchPairCount": 6,
        "planarProjectionPassedPairCount": 3,
        "heightDecisionRequiredPairCount": 3,
        "readyForCadValidationCount": 0,
    }
    rows = [row for row in result["candidates"]
            if row["sourceModuleDefinitionId"] == "project02::A500"]
    assert {row["targetBaseDefinitionId"] for row in rows} == {
        "project01::JJ00", "project03::AA00", "project05::A000",
    }
    for row in rows:
        assert row["status"] == "planar_candidate_requires_height_decision"
        assert row["functionPointPlanarProjectionPassed"] is True
        assert row["functionPointHeightPassed"] is False
        assert row["supportContactPreserved"] is True
        assert row["positionParametersMeters"]["supportGap"] == pytest.approx(0, abs=1e-9)
        assert row["planarErrorMeters"] == pytest.approx(0, abs=1e-9)
        assert abs(row["supportNormalOffsetMeters"]) > 0.2
        assert row["readyForCadValidation"] is False
        assert row["cadLaunchAllowed"] is False
        assert row["candidatePackage"]["prototypeTopLevelTargetPoseUsed"] is False
        assert row["candidatePackage"]["effectivePositionParameters"] == pytest.approx(
            row["positionParametersMeters"]
        )


def test_two_axis_solver_ranks_real_pairs_and_reports_function_mismatch():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    result = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    row = next(row for row in result["candidates"]
               if row["sourceModuleDefinitionId"] == "project01::BD00"
               and row["targetBaseDefinitionId"] == "project02::A600")
    assert row["status"] == "two_axis_stations_miss_target_function_point"
    assert row["interfaceTopology"] == "support_plane_plus_two_locating_axes"
    assert row["candidatePairCount"] == 7
    assert row["bestCandidate"]["planarErrorMeters"] == pytest.approx(
        0.0334033653512
    )
    assert row["readyForCadValidation"] is False
    assert row["cadLaunchAllowed"] is False


def test_flexible_slot_solver_derives_axis_and_offset_but_keeps_height_review():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    result = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    row = next(row for row in result["candidates"]
               if row["sourceModuleDefinitionId"] == "project05::G000"
               and row["targetBaseDefinitionId"] == "project02::A600")
    assert row["status"] == "flexible_slot_candidate_requires_height_and_axis_review"
    assert row["interfaceTopology"] == (
        "support_orientation_distance_plus_flexible_slot"
    )
    assert row["bestCandidate"]["planarErrorMeters"] == pytest.approx(
        0.00289039612989
    )
    assert row["bestCandidate"]["derivedLongitudinalOffsetMeters"] == pytest.approx(
        0.400279711734291
    )
    assert abs(row["bestCandidate"]["supportNormalOffsetMeters"]) > 0.25
    assert row["readyForCadValidation"] is False


def test_candidate_decision_index_binds_every_pair_without_cad_authority():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    report = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    index = mod.build_station_candidate_decision_index(
        report,
        report_path="demo/calibration-candidates.json",
        report_sha256="1" * 64,
    )
    assert index["schemaVersion"] == "station-candidate-decision-index/v1"
    assert len(index["entries"]) == 12
    assert all(row["cadLaunchAllowed"] is False for row in index["entries"])
    assert {row["candidateStatus"] for row in index["entries"]} == {
        "planar_candidate_requires_height_decision",
        "two_axis_stations_miss_target_function_point",
        "flexible_slot_candidate_requires_height_and_axis_review",
    }


def test_combined_candidate_report_normalizes_transport_without_confirmation():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    calibration = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    transport = {
        "schemaVersion": "transport-station-engineering-review-queue/v1",
        "queueDigest": "2" * 64,
        "recommendations": [{
            "sourceModuleDefinitionId": "project02::A800",
            "targetBaseDefinitionId": "project01::JJ00",
            "nativeRoleModuleDefinitionId": "project01::SS00",
            "recommendedPositionParametersMeters": {
                "longitudinal": 0.101, "lateral": 0.0185, "supportGap": 0.0,
            },
            "basis": "target_base_reviewed_native_transport_station",
            "nativeStationEvidenceDigest": "3" * 64,
            "status": "recommendation_pending_engineering_confirmation",
            "boundary": "review only",
        }],
    }
    report = mod.build_combined_station_candidate_decision_report(
        calibration, transport
    )
    assert report["summary"] == {
        "candidateCount": 13,
        "calibrationCandidateCount": 12,
        "transportRecommendationCount": 1,
        "scannerInstanceBindingCount": 0,
        "extensionCandidateCount": 0,
    }
    row = next(row for row in report["candidates"] if row["role"] == "Transport")
    assert row["cadLaunchAllowed"] is False
    assert row["readyForCadValidation"] is False
    assert row["recommendedPositionParametersMeters"]["longitudinal"] == pytest.approx(
        0.101
    )


def test_combined_candidate_report_preserves_exact_scanner_transport_binding():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    calibration = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    transport = {
        "schemaVersion": "transport-station-engineering-review-queue/v1",
        "queueDigest": "2" * 64,
        "recommendations": [],
    }
    scanner = {
        "schemaVersion": "scanner-transport-binding-review-queue/v1",
        "queueDigest": "4" * 64,
        "candidates": [{
            "sourceModuleDefinitionId": "project03::AI00",
            "targetBaseDefinitionId": "project01::JJ00",
            "transportModuleDefinitionId": "project01::SS00",
            "status": "ready_for_exact_chain_instance_selection",
            "candidateDigest": "5" * 64,
            "boundary": "proxy only",
        }],
    }
    report = mod.build_combined_station_candidate_decision_report(
        calibration, transport, scanner
    )
    assert report["summary"]["scannerInstanceBindingCount"] == 1
    row = next(row for row in report["candidates"] if row["role"] == "Scanner")
    assert row["transportModuleDefinitionId"] == "project01::SS00"
    assert row["status"] == "ready_for_exact_chain_instance_selection"
    assert row["cadLaunchAllowed"] is False


def test_combined_candidate_report_accepts_non_authoritative_extensions():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    calibration = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    transport = {
        "schemaVersion": "transport-station-engineering-review-queue/v1",
        "queueDigest": "2" * 64,
        "recommendations": [],
    }
    extension = {
        "schemaVersion": mod.EXTENSION_CANDIDATE_REPORT_SCHEMA,
        "reportDigest": "6" * 64,
        "candidates": [{
            "sourceModuleDefinitionId": "project02::A300",
            "targetBaseDefinitionId": "project01::JJ00",
            "role": "WasteCup",
            "interfaceTopology": "support_plane_function_point_mapping",
            "status": "mapping_selected_requires_station_candidate",
            "readyForCadValidation": False,
            "cadLaunchAllowed": False,
            "nextAction": "derive_station_candidate",
            "claimBoundary": "offline mapping only",
        }],
    }
    report = mod.build_combined_station_candidate_decision_report(
        calibration, transport, extension_reports=[extension]
    )
    assert report["summary"]["extensionCandidateCount"] == 1
    assert report["summary"]["candidateCount"] == 13
    assert report["sourceDigests"]["extensionReportDigests"] == ["6" * 64]
    row = next(row for row in report["candidates"] if row["role"] == "WasteCup")
    assert row["cadLaunchAllowed"] is False


def test_combined_candidate_report_rejects_extension_cad_authority():
    catalog = mod.build_calibration_function_point_catalog(ROOT, SOURCES)
    calibration = mod.derive_calibration_planar_station_candidates(ROOT, catalog)
    transport = {
        "schemaVersion": "transport-station-engineering-review-queue/v1",
        "queueDigest": "2" * 64,
        "recommendations": [],
    }
    extension = {
        "schemaVersion": mod.EXTENSION_CANDIDATE_REPORT_SCHEMA,
        "candidates": [{
            "sourceModuleDefinitionId": "project02::A300",
            "targetBaseDefinitionId": "project01::JJ00",
            "role": "WasteCup",
            "interfaceTopology": "support_plane_function_point_mapping",
            "status": "unsafe",
            "cadLaunchAllowed": True,
            "nextAction": "none",
            "claimBoundary": "invalid",
        }],
    }
    with pytest.raises(ValueError, match="cannot authorize CAD"):
        mod.build_combined_station_candidate_decision_report(
            calibration, transport, extension_reports=[extension]
        )


def test_calibration_station_decision_request_preserves_all_twelve_pending_choices():
    report = mod.build_calibration_station_decision_request(
        ROOT,
        "demo/station_gap_batch_20261028/coverage-v23/gap-batch-v46/gap-queue.json",
    )
    assert report["summary"]["decisionCount"] == 12
    assert report["summary"]["decisionKindCounts"] == {
        "function_point_height": 3,
        "replacement_mechanical_binding": 1,
        "slot_axis_offset_and_function_point_height": 3,
        "target_station_or_explicit_function_offset": 5,
    }
    assert report["summary"]["confirmedCount"] == 0
    assert all(row["cadLaunchAllowed"] is False for row in report["decisions"])
    height = next(
        row
        for row in report["decisions"]
        if row["decisionId"] == "project02::A500->project01::JJ00"
    )
    assert height["positionParametersMeters"]
    assert height["supportNormalOffsetMeters"] > 0.3
    revoked = next(
        row
        for row in report["decisions"]
        if row["decisionId"] == "project05::G000->project05::A000"
    )
    assert revoked["decisionKind"] == "replacement_mechanical_binding"
    assert "bestCandidate" not in revoked
