from copy import deepcopy

import pytest

from demo_backend.cross_project_scanner_process_preflight import (
    CrossProjectScannerProcessPreflightError,
    build_scanner_process_preflight,
)


def _discovery():
    return {
        "schemaVersion": "cross-project-scanner-slot-discovery/v1",
        "discoveryDigest": "discovery",
        "sourceRelation": {
            "sourceProjectId": "project03",
            "sourceModuleToken": "AI00",
            "targetProjectId": "project01",
        },
        "selectedCandidate": {
            "directFit": True,
            "nativeStationDisplacementMeters": 0.35,
        },
    }


def _recovery():
    return {
        "schemaVersion": "cross-project-scanner-slot-endpoint-recovery/v1",
        "discoveryDigest": "discovery",
        "evidenceDigest": "recovery",
        "allRecovered": True,
    }


def _catalog(with_process_geometry=True):
    ports = []
    if with_process_geometry:
        ports = [
            {
                "globalPortId": "ai00-optical",
                "category": "functional",
                "functionalGeometry": {
                    "geometryType": "point_axis",
                    "parameters": {
                        "minWorkingDistanceMeters": 0.05,
                        "maxWorkingDistanceMeters": 0.2,
                    },
                },
                "provenance": [
                    {"projectId": "project03", "moduleToken": "AI00"}
                ],
            },
            {
                "globalPortId": "ss00-barcode",
                "displayName": "SS00 barcode target",
                "category": "functional",
                "functionalGeometry": {"geometryType": "point_plane"},
                "provenance": [
                    {"projectId": "project01", "moduleToken": "SS00"}
                ],
            },
        ]
    return {"schemaVersion": "global-module-catalog/v1", "semanticPorts": ports}


def test_missing_process_geometry_fails_closed_before_cad():
    report = build_scanner_process_preflight(
        _discovery(), _recovery(), _catalog(False), target_process_module_token="SS00"
    )
    assert report["status"] == "blocked_before_cad_missing_functional_semantics"
    assert report["cadInsertionAllowed"] is False
    assert report["missingEvidence"] == [
        "scanner_optical_origin_and_axis",
        "scanner_working_distance_range",
        "target_transport_barcode_point",
    ]
    assert report["project06Included"] is False


def test_complete_process_geometry_advances_only_to_pose_evaluation():
    report = build_scanner_process_preflight(
        _discovery(), _recovery(), _catalog(), target_process_module_token="SS00"
    )
    assert report["status"] == (
        "ready_for_candidate_pose_and_optical_geometry_evaluation"
    )
    assert report["cadInsertionAllowed"] is False
    assert report["missingEvidence"] == []
    assert report["checks"]["candidatePoseTransformSolved"] is False


def test_mismatched_recovery_evidence_is_rejected():
    evidence = deepcopy(_recovery())
    evidence["discoveryDigest"] = "other"
    with pytest.raises(CrossProjectScannerProcessPreflightError):
        build_scanner_process_preflight(
            _discovery(), evidence, _catalog(), target_process_module_token="SS00"
        )


def test_digest_is_deterministic():
    first = build_scanner_process_preflight(
        _discovery(), _recovery(), _catalog(), target_process_module_token="SS00"
    )
    second = build_scanner_process_preflight(
        _discovery(), _recovery(), _catalog(), target_process_module_token="SS00"
    )
    assert first["preflightDigest"] == second["preflightDigest"]
