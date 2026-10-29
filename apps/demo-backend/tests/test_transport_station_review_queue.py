import copy
import json
from pathlib import Path
import pytest

from demo_backend.transport_station_review_queue import (
    apply_transport_station_confirmation_packets,
    build_transport_station_trial_authorization_packet,
    build_transport_station_review_queue,
)


ROOT = Path(__file__).resolve().parents[3]
GAP = ROOT / "demo/station_gap_batch_20261028/coverage-v6/gap-batch-v13/gap-queue.json"


def test_current_transport_gaps_become_one_unconfirmed_batch():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    result = build_transport_station_review_queue(gap)
    assert result["summary"] == {
        "transportGapCount": 12,
        "recommendationCount": 12,
        "blockedCount": 0,
        "confirmedCount": 0,
    }
    assert result["cadStarted"] is False
    assert all(row["confirmationTemplate"]["confirmed"] is False
               for row in result["recommendations"])
    assert all(row["cadLaunchAllowed"] is False
               for row in result["recommendations"])
    pair = next(row for row in result["recommendations"]
                if row["sourceModuleDefinitionId"] == "project01::SS00"
                and row["targetBaseDefinitionId"] == "project02::A600")
    assert pair["nativeRoleModuleDefinitionId"] == "project02::A800"
    assert pair["recommendedPositionParametersMeters"] == {
        "longitudinal": 0.3095,
        "lateral": 1.59,
        "supportGap": 0.0,
    }
    assert pair["prototypePoseAllowedAsCadExecutionAuthority"] is False


def test_missing_or_ambiguous_target_station_never_becomes_recommendation():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    changed = copy.deepcopy(gap)
    row = next(value for value in changed["queue"]
               if value.get("role") == "Transport"
               and value.get("gapCategory") == "reusable_measurement_needs_semantic_binding")
    row["targetMeasurementAssets"] = row["targetMeasurementAssets"] * 2
    result = build_transport_station_review_queue(changed)
    assert result["summary"]["recommendationCount"] == 11
    assert any(value["reason"] == "TARGET_NATIVE_STATION_OR_INTERFACE_AUTHORITY_NOT_UNIQUE"
               for value in result["blocked"])


def _packet(pair, parameters):
    import hashlib

    core = {
        "schemaVersion": "parameterized-datum-position-parameters/v1",
        "sourceReviewDigest": "review",
        "confirmedPairCount": 1,
        "pairs": [{
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "confirmed": True,
            "source": "explicit user confirmation",
            "confirmedBy": "user",
            "confirmedAt": "2026-10-26T12:18:33+08:00",
            "parametersMeters": parameters,
            "evidenceBasis": "accepted_review_recommendation",
        }],
        "claimBoundary": "confirmation only",
    }
    digest = hashlib.sha256(json.dumps(
        core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {**core, "decisionPacketDigest": digest}


def test_exact_confirmation_and_native_station_refine_next_action_without_cad_claim():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    queue = build_transport_station_review_queue(gap)
    selected = next(row for row in queue["recommendations"]
                    if row["sourceModuleDefinitionId"] != row["nativeRoleModuleDefinitionId"])
    native = next(row for row in queue["recommendations"]
                  if row["sourceModuleDefinitionId"] == row["nativeRoleModuleDefinitionId"])
    packet = _packet(
        (selected["sourceModuleDefinitionId"], selected["targetBaseDefinitionId"]),
        selected["recommendedPositionParametersMeters"],
    )
    result = apply_transport_station_confirmation_packets(queue, [packet])
    confirmed = next(row for row in result["recommendations"]
                     if row["sourceModuleDefinitionId"] == selected["sourceModuleDefinitionId"]
                     and row["targetBaseDefinitionId"] == selected["targetBaseDefinitionId"])
    native_result = next(row for row in result["recommendations"]
                         if row["sourceModuleDefinitionId"] == native["sourceModuleDefinitionId"]
                         and row["targetBaseDefinitionId"] == native["targetBaseDefinitionId"])
    assert confirmed["status"] == (
        "engineering_confirmation_recorded_requires_target_station_postcheck"
    )
    assert confirmed["confirmationTemplate"]["confirmed"] is True
    assert confirmed["cadLaunchAllowed"] is False
    assert native_result["status"] == (
        "native_station_requires_current_saved_output_station_postcheck"
    )
    assert result["cadStarted"] is False
    assert result["summary"]["confirmedCount"] == 1
    assert result["summary"]["nativeStationCount"] >= 1


def test_confirmation_parameter_mismatch_and_tamper_fail_closed():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    queue = build_transport_station_review_queue(gap)
    selected = next(row for row in queue["recommendations"]
                    if row["sourceModuleDefinitionId"] != row["nativeRoleModuleDefinitionId"])
    pair = (selected["sourceModuleDefinitionId"], selected["targetBaseDefinitionId"])
    packet = _packet(pair, {"longitudinal": 9.0, "lateral": 8.0, "supportGap": 0.0})
    with pytest.raises(ValueError, match="differ from current review"):
        apply_transport_station_confirmation_packets(queue, [packet])
    packet["pairs"][0]["confirmedBy"] = "tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        apply_transport_station_confirmation_packets(queue, [packet])


def test_explicit_position_fallback_becomes_reviewable_trial_not_released_authority():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    source = next(
        row for row in gap["queue"]
        if row.get("role") == "Transport"
        and len(row.get("targetMeasurementAssets") or []) == 1
    )
    trial = copy.deepcopy(source)
    trial["sourceModuleDefinitionId"] = "project01::SS00"
    trial["targetBaseDefinitionId"] = "project05::A000"
    trial["gapCategory"] = "mechanical_interface_authority_missing"
    trial["authority"] = {
        "ready": False,
        "status": "datum_fallback_requires_explicit_position_parameters",
        "relationExecutionMode": None,
        "releaseManifestPath": None,
    }
    asset = trial["targetMeasurementAssets"][0]
    asset["targetBaseDefinitionId"] = "project05::A000"
    asset["nativeRoleModuleDefinitionId"] = "project05::D000"
    asset["nativeStationParametersMeters"] = {
        "longitudinal": 0.092,
        "lateral": 1.3635,
        "supportGap": 0.0,
    }
    asset["nativeStationEvidenceDigest"] = "e" * 64
    asset["fileEvidence"] = [{
        "path": "evidence.json", "exists": True, "sha256": "f" * 64,
    }]
    changed = copy.deepcopy(gap)
    changed["queue"] = [trial]
    result = build_transport_station_review_queue(changed)
    assert result["summary"]["recommendationCount"] == 1
    recommendation = result["recommendations"][0]
    assert recommendation["interfaceAuthority"] == {
        "status": "datum_fallback_requires_explicit_position_parameters",
        "relationExecutionMode": "datum_placement_demo",
        "releaseManifestPath": None,
        "requiresNewParameterizedDatumRelease": True,
    }
    assert recommendation["targetNativeStationEvidence"][0]["path"] == (
        "evidence.json"
    )


def test_trial_only_decision_does_not_claim_track_fit():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    queue = build_transport_station_review_queue(gap)
    selected = next(
        row for row in queue["recommendations"]
        if row["sourceModuleDefinitionId"] != row["nativeRoleModuleDefinitionId"]
    )
    decision = _packet(
        (selected["sourceModuleDefinitionId"], selected["targetBaseDefinitionId"]),
        selected["recommendedPositionParametersMeters"],
    )
    decision_core = {key: value for key, value in decision.items()
                     if key != "decisionPacketDigest"}
    decision_core["pairs"][0].update({
        "confirmTargetStationReuse": True,
        "confirmTrackAndWorkAreaFit": False,
        "authorizationScope": "nonprototype_cad_trial_only",
    })
    import hashlib
    decision_digest = hashlib.sha256(json.dumps(
        decision_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    decision = {**decision_core, "decisionPacketDigest": decision_digest}
    result = apply_transport_station_confirmation_packets(queue, [decision])
    row = next(
        item for item in result["recommendations"]
        if item["sourceModuleDefinitionId"] == selected["sourceModuleDefinitionId"]
        and item["targetBaseDefinitionId"] == selected["targetBaseDefinitionId"]
    )
    assert row["status"] == (
        "target_native_station_trial_authorized_requires_cad_validation"
    )
    assert row["confirmationTemplate"]["confirmTrackAndWorkAreaFit"] is False


def test_builds_authenticated_trial_packet_only_for_explicit_fallback_pairs():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    queue = build_transport_station_review_queue(gap)
    trial = next(
        row for row in queue["recommendations"]
        if (row.get("interfaceAuthority") or {}).get(
            "requiresNewParameterizedDatumRelease"
        ) is True
    )
    pair = (
        trial["sourceModuleDefinitionId"], trial["targetBaseDefinitionId"]
    )
    packet = build_transport_station_trial_authorization_packet(
        queue,
        exact_pairs=[pair],
        source="active goal authorizes measured target-native trial",
        authorized_by="goal_owner",
        authorized_at="2026-10-28T23:30:00+08:00",
    )
    assert packet["confirmedPairCount"] == 1
    assert packet["pairs"][0]["confirmTrackAndWorkAreaFit"] is False
    assert packet["pairs"][0]["authorizationScope"] == (
        "nonprototype_cad_trial_only"
    )
    applied = apply_transport_station_confirmation_packets(queue, [packet])
    applied_row = next(
        row for row in applied["recommendations"]
        if row["sourceModuleDefinitionId"] == pair[0]
        and row["targetBaseDefinitionId"] == pair[1]
    )
    assert applied_row["status"] == (
        "target_native_station_trial_authorized_requires_cad_validation"
    )


def test_trial_packet_rejects_released_or_unlisted_pair():
    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    queue = build_transport_station_review_queue(gap)
    released = next(
        row for row in queue["recommendations"]
        if (row.get("interfaceAuthority") or {}).get(
            "requiresNewParameterizedDatumRelease"
        ) is not True
    )
    with pytest.raises(ValueError, match="not eligible"):
        build_transport_station_trial_authorization_packet(
            queue,
            exact_pairs=[(
                released["sourceModuleDefinitionId"],
                released["targetBaseDefinitionId"],
            )],
            source="not allowed",
            authorized_by="tester",
            authorized_at="2026-10-28T23:30:00+08:00",
        )
