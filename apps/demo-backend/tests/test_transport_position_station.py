import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.station_rule_registry import validate_rule
from demo_backend.transport_position_station import (
    build_transport_position_station_candidates,
)
from demo_backend.station_rule_planner import transport_position_postcheck_status


def digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def packet(source="p1::T", base="p2::B"):
    core = {
        "schemaVersion": "parameterized-datum-position-parameters/v1",
        "sourceReviewDigest": "review",
        "confirmedPairCount": 1,
        "pairs": [{
            "moduleDefinitionId": source,
            "slotDefinitionId": base,
            "confirmed": True,
            "source": "user accepted",
            "confirmedBy": "user",
            "confirmedAt": "2026-10-26T12:00:00+08:00",
            "parametersMeters": {
                "longitudinal": 0.1, "lateral": 0.2, "supportGap": 0.0,
            },
        }],
        "claimBoundary": "confirmation only",
    }
    return {**core, "decisionPacketDigest": digest(core)}


def queue():
    recommendation = {
        "sourceModuleDefinitionId": "p1::T",
        "targetBaseDefinitionId": "p2::B",
        "nativeRoleModuleDefinitionId": "p2::NATIVE",
        "recommendedPositionParametersMeters": {
            "longitudinal": 0.1, "lateral": 0.2, "supportGap": 0.0,
        },
        "basis": "target_base_reviewed_native_transport_station",
        "interfaceAuthority": {
            "relationExecutionMode": "datum_placement_demo",
            "releaseManifestPath": "release.json",
        },
        "nativeStationEvidenceDigest": "evidence",
        "status": "recommendation_pending_engineering_confirmation",
        "confirmationTemplate": {"confirmed": False},
        "cadLaunchAllowed": False,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
        "boundary": "review only",
    }
    core = {
        "schemaVersion": "transport-station-engineering-review-queue/v1",
        "status": "ready_for_engineering_review",
        "recommendations": [recommendation],
        "blocked": [],
        "summary": {
            "transportGapCount": 1, "recommendationCount": 1,
            "blockedCount": 0, "confirmedCount": 0,
        },
        "sourceGapReportDigest": "gap",
        "cadStarted": False,
        "claimBoundary": "review only",
    }
    return {**core, "queueDigest": digest(core)}


def build():
    p = packet()
    return build_transport_position_station_candidates(
        review_queue=queue(),
        review_binding={"path": "review.json", "sha256": "a" * 64},
        confirmation_bindings=[{
            "path": "confirmation.json", "sha256": "b" * 64, "payload": p,
        }],
        base_registry={
            "schemaVersion": "target-station-rule-registry/v1",
            "scopePath": "scope.json",
            "rules": [],
        },
        config_directory_path="candidate/configs",
    )


def test_builds_one_candidate_without_cad_or_prototype_pose():
    result = build()
    assert result["candidateCount"] == 1
    assert result["cadStarted"] is False
    rule = result["candidateRules"][0]
    config = result["configs"][0]["payload"]
    assert rule["evaluator"]["kind"] == "transport_position_parameters"
    assert rule["validation"] == {"status": "candidate"}
    assert config["positionParametersMeters"]["lateral"] == 0.2
    assert config["engineeringConfirmation"]["confirmed"] is True
    assert "SourceTransform" not in json.dumps(result)


def test_existing_pair_and_parameter_tamper_fail_closed():
    p = packet()
    base = {
        "schemaVersion": "target-station-rule-registry/v1",
        "scopePath": "scope.json",
        "rules": [{
            "sourceModuleDefinitionId": "p1::T",
            "targetBaseDefinitionId": "p2::B",
        }],
    }
    kwargs = dict(
        review_queue=queue(),
        review_binding={"path": "review.json", "sha256": "a" * 64},
        confirmation_bindings=[{
            "path": "confirmation.json", "sha256": "b" * 64, "payload": p,
        }],
        base_registry=base,
        config_directory_path="candidate/configs",
    )
    with pytest.raises(ValueError, match="already has a station rule"):
        build_transport_position_station_candidates(**kwargs)
    p["pairs"][0]["parametersMeters"]["lateral"] = 9.0
    with pytest.raises(ValueError, match="digest mismatch"):
        build_transport_position_station_candidates(
            **{**kwargs, "base_registry": {**base, "rules": []}}
        )


def test_builds_exact_native_station_without_cross_project_confirmation():
    native_queue = queue()
    row = native_queue["recommendations"][0]
    row["sourceModuleDefinitionId"] = "project03::AE00"
    row["targetBaseDefinitionId"] = "project03::AA00"
    row["nativeRoleModuleDefinitionId"] = "project03::AE00"
    row["nativeStationEvidenceDigest"] = "c" * 64
    core = {key: value for key, value in native_queue.items() if key != "queueDigest"}
    native_queue["queueDigest"] = digest(core)

    result = build_transport_position_station_candidates(
        review_queue=native_queue,
        review_binding={"path": "review.json", "sha256": "a" * 64},
        confirmation_bindings=[],
        base_registry={
            "schemaVersion": "target-station-rule-registry/v1",
            "scopePath": "scope.json",
            "rules": [],
        },
        config_directory_path="candidate/configs",
    )

    assert result["candidateCount"] == 1
    config = result["configs"][0]["payload"]
    assert "engineeringConfirmation" not in config
    assert config["nativeStationAuthorization"]["authorized"] is True
    assert config["nativeStationAuthorization"]["kind"] == (
        "exact_native_role_station_identity"
    )
    assert "confirmationPacketPath" not in config["inputs"]


def test_builds_trial_candidate_without_claiming_track_fit_or_existing_release():
    review = queue()
    row = review["recommendations"][0]
    row["interfaceAuthority"] = {
        "status": "datum_fallback_requires_explicit_position_parameters",
        "relationExecutionMode": "datum_placement_demo",
        "releaseManifestPath": None,
        "requiresNewParameterizedDatumRelease": True,
    }
    row["targetNativeStationEvidence"] = [{
        "path": "native-station.json", "sha256": "c" * 64, "exists": True,
    }]
    review_core = {key: value for key, value in review.items()
                   if key != "queueDigest"}
    review["queueDigest"] = digest(review_core)
    p = packet()
    p_core = {key: value for key, value in p.items()
              if key != "decisionPacketDigest"}
    p_core["pairs"][0].update({
        "confirmTargetStationReuse": True,
        "confirmTrackAndWorkAreaFit": False,
        "authorizationScope": "nonprototype_cad_trial_only",
    })
    p = {**p_core, "decisionPacketDigest": digest(p_core)}
    applied = __import__(
        "demo_backend.transport_station_review_queue", fromlist=[
            "apply_transport_station_confirmation_packets"
        ]
    ).apply_transport_station_confirmation_packets(review, [p])
    result = build_transport_position_station_candidates(
        review_queue=applied,
        review_binding={"path": "review.json", "sha256": "a" * 64},
        confirmation_bindings=[{
            "path": "confirmation.json", "sha256": "b" * 64, "payload": p,
        }],
        base_registry={
            "schemaVersion": "target-station-rule-registry/v1",
            "scopePath": "scope.json",
            "rules": [],
        },
        config_directory_path="candidate/configs",
    )
    config = result["configs"][0]["payload"]
    assert "engineeringConfirmation" not in config
    assert "referenceReleasePath" not in config["inputs"]
    assert config["candidateAuthorization"]["trackAndWorkAreaFitConfirmed"] is False
    assert config["inputs"]["targetNativeStationEvidencePath"] == (
        "native-station.json"
    )


def test_trial_cad_closure_cannot_publish_before_transport_work_area_postcheck():
    trial = transport_position_postcheck_status({
        "candidateAuthorization": {
            "kind": "target_native_station_nonprototype_cad_trial",
            "trackAndWorkAreaFitConfirmed": False,
        }
    })
    assert trial == {
        "proxyGeometryPassed": False,
        "publicationBlockedReasonCode": (
            "TRANSPORT_TRACK_AND_WORK_AREA_POSTCHECK_REQUIRED"
        ),
    }
    assert transport_position_postcheck_status({
        "engineeringConfirmation": {"confirmed": True}
    }) == {
        "proxyGeometryPassed": True,
        "publicationBlockedReasonCode": None,
    }
