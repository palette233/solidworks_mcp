"""Batch transport station recommendations from reviewed target measurements.

Recommendations are deliberately unconfirmed and cannot start CAD.  They turn
an evidence inventory into a compact engineering decision queue without
creating one script or rule per exact module/base pair.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA = "transport-station-engineering-review-queue/v1"
POSITION_PACKET_SCHEMA = "parameterized-datum-position-parameters/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_transport_station_review_queue(gap_report: dict[str, Any]) -> dict[str, Any]:
    if gap_report.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap report")
    recommendations: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    rows = sorted(
        [row for row in gap_report.get("queue") or [] if row.get("role") == "Transport"],
        key=lambda row: (
            str(row.get("targetBaseDefinitionId") or ""),
            str(row.get("sourceModuleDefinitionId") or ""),
        ),
    )
    for row in rows:
        category = row.get("gapCategory")
        authority = row.get("authority") or {}
        released_authority_ready = bool(
            category == "reusable_measurement_needs_semantic_binding"
            and authority.get("ready") is True
        )
        parameterized_trial_ready = bool(
            category == "mechanical_interface_authority_missing"
            and authority.get("ready") is False
            and authority.get("status")
            == "datum_fallback_requires_explicit_position_parameters"
        )
        if not released_authority_ready and not parameterized_trial_ready:
            blocked.append({
                "sourceModuleDefinitionId": row.get("sourceModuleDefinitionId"),
                "targetBaseDefinitionId": row.get("targetBaseDefinitionId"),
                "reason": category or "TRANSPORT_GAP_NOT_REVIEW_READY",
            })
            continue
        assets = [
            asset for asset in row.get("targetMeasurementAssets") or []
            if isinstance(asset.get("nativeStationParametersMeters"), dict)
        ]
        if len(assets) != 1:
            blocked.append({
                "sourceModuleDefinitionId": row.get("sourceModuleDefinitionId"),
                "targetBaseDefinitionId": row.get("targetBaseDefinitionId"),
                "reason": "TARGET_NATIVE_STATION_OR_INTERFACE_AUTHORITY_NOT_UNIQUE",
            })
            continue
        asset = assets[0]
        parameters = asset["nativeStationParametersMeters"]
        if set(parameters) != {"longitudinal", "lateral", "supportGap"}:
            raise ValueError("transport native station parameters incomplete")
        file_evidence = [
            value for value in asset.get("fileEvidence") or []
            if value.get("exists") is True
            and isinstance(value.get("path"), str)
            and len(str(value.get("sha256") or "")) == 64
        ]
        if parameterized_trial_ready and not file_evidence:
            blocked.append({
                "sourceModuleDefinitionId": row.get("sourceModuleDefinitionId"),
                "targetBaseDefinitionId": row.get("targetBaseDefinitionId"),
                "reason": "TARGET_NATIVE_STATION_EVIDENCE_FILE_MISSING",
            })
            continue
        recommendations.append({
            "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": row["targetBaseDefinitionId"],
            "nativeRoleModuleDefinitionId": asset["nativeRoleModuleDefinitionId"],
            "recommendedPositionParametersMeters": parameters,
            "basis": "target_base_reviewed_native_transport_station",
            "interfaceAuthority": {
                "status": authority.get("status"),
                "relationExecutionMode": (
                    authority.get("relationExecutionMode")
                    if released_authority_ready
                    else "datum_placement_demo"
                ),
                "releaseManifestPath": authority.get("releaseManifestPath"),
                "requiresNewParameterizedDatumRelease": parameterized_trial_ready,
            },
            "nativeStationEvidenceDigest": asset.get("nativeStationEvidenceDigest"),
            "targetNativeStationEvidence": file_evidence,
            "status": "recommendation_pending_engineering_confirmation",
            "confirmationTemplate": {
                "confirmed": False,
                "confirmTargetStationReuse": False,
                "confirmTrackAndWorkAreaFit": False,
                "authorizationScope": None,
                "confirmedBy": None,
                "confirmedAt": None,
            },
            "cadLaunchAllowed": False,
            "prototypePoseAllowedAsCadExecutionAuthority": False,
            "targetEnvelopeVerified": False,
            "requiredAfterConfirmation": [
                "compile_exact_pair_candidate_with_existing_generic_builder",
                "nonprototype_initial_pose_real_CAD",
                "active_mates_and_required_DOF_check",
                "save_close_reopen",
                "transport_work_area_and_scanner_target_postcheck",
            ],
            "boundary": (
                "The target native station supplies review-only signed parameters. "
                "It does not prove that the replacement transport track, work areas, "
                "carrier interfaces or envelope are functionally interchangeable."
            ),
        })
    core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_engineering_review" if recommendations else "no_review_ready_transport_pairs",
        "recommendations": recommendations,
        "blocked": blocked,
        "summary": {
            "transportGapCount": len(rows),
            "recommendationCount": len(recommendations),
            "blockedCount": len(blocked),
            "confirmedCount": 0,
        },
        "sourceGapReportDigest": _digest(gap_report),
        "cadStarted": False,
        "claimBoundary": (
            "Unconfirmed review queue only. No prototype pose is copied and no "
            "station rule, CAD result, fastening or process approval is created."
        ),
    }
    return {**core, "queueDigest": _digest(core)}


def _validated_position_packet(packet: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Authenticate an immutable exact-pair position confirmation packet."""

    if packet.get("schemaVersion") != POSITION_PACKET_SCHEMA:
        raise ValueError("unsupported transport position confirmation packet")
    core = {key: value for key, value in packet.items() if key != "decisionPacketDigest"}
    if _digest(core) != packet.get("decisionPacketDigest"):
        raise ValueError("transport position confirmation packet digest mismatch")
    rows = packet.get("pairs")
    if not isinstance(rows, list) or packet.get("confirmedPairCount") != len(rows):
        raise ValueError("transport position confirmation packet count mismatch")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(key) or key in result or row.get("confirmed") is not True:
            raise ValueError(f"invalid or duplicate transport confirmation: {key}")
        if not all(str(row.get(field) or "").strip()
                   for field in ("source", "confirmedBy", "confirmedAt")):
            raise ValueError(f"transport confirmation provenance is incomplete: {key}")
        for field in ("confirmTargetStationReuse", "confirmTrackAndWorkAreaFit"):
            if field in row and not isinstance(row[field], bool):
                raise ValueError(f"transport confirmation flag is invalid: {key}:{field}")
        if row.get("confirmTrackAndWorkAreaFit") is False and (
            row.get("confirmTargetStationReuse") is not True
            or row.get("authorizationScope") != "nonprototype_cad_trial_only"
        ):
            raise ValueError(f"transport trial authorization is incomplete: {key}")
        parameters = row.get("parametersMeters")
        if not isinstance(parameters, dict) or set(parameters) != {
            "longitudinal", "lateral", "supportGap"
        }:
            raise ValueError(f"transport confirmation parameters are incomplete: {key}")
        result[key] = row
    return result


def apply_transport_station_confirmation_packets(
    review_queue: dict[str, Any], packets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply exact, authenticated decisions without promoting them to CAD evidence.

    A confirmation closes only the engineering choice to reuse the recorded
    target-native station.  It does not prove a new CAD run or a target-station
    postcheck.  A true native-role pair does not need cross-project replacement
    confirmation, but it still needs current saved-output station verification.
    """

    if review_queue.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported transport station review queue")
    core = {key: value for key, value in review_queue.items() if key != "queueDigest"}
    if _digest(core) != review_queue.get("queueDigest"):
        raise ValueError("transport station review queue digest mismatch")
    confirmed: dict[tuple[str, str], dict[str, Any]] = {}
    confirmed_digests: dict[tuple[str, str], str] = {}
    packet_digests: list[str] = []
    for packet in packets:
        packet_digest = str(packet.get("decisionPacketDigest") or "")
        packet_digests.append(packet_digest)
        for key, row in _validated_position_packet(packet).items():
            previous = confirmed.get(key)
            if previous is not None and previous != row:
                raise ValueError(f"conflicting transport confirmations: {key}")
            confirmed[key] = row
            confirmed_digests[key] = packet_digest

    result = deepcopy(review_queue)
    native_count = 0
    confirmed_count = 0
    still_pending = 0
    for row in result.get("recommendations") or []:
        key = (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"])
        if row["sourceModuleDefinitionId"] == row.get("nativeRoleModuleDefinitionId"):
            native_count += 1
            row["status"] = "native_station_requires_current_saved_output_station_postcheck"
            row["readyForCadValidation"] = False
            row["nextAction"] = (
                "verify_native_transport_station_in_current_saved_output_or_run_"
                "nonprototype_cad_then_station_postcheck"
            )
            continue
        decision = confirmed.get(key)
        if decision is None:
            still_pending += 1
            continue
        if decision["parametersMeters"] != row["recommendedPositionParametersMeters"]:
            raise ValueError(f"confirmed transport parameters differ from current review: {key}")
        confirmed_count += 1
        track_fit_confirmed = decision.get("confirmTrackAndWorkAreaFit", True)
        target_station_reuse_confirmed = decision.get(
            "confirmTargetStationReuse", True
        )
        trial_only = track_fit_confirmed is False
        row["status"] = (
            "target_native_station_trial_authorized_requires_cad_validation"
            if trial_only
            else "engineering_confirmation_recorded_requires_target_station_postcheck"
        )
        row["confirmationTemplate"] = {
            "confirmed": True,
            "confirmTargetStationReuse": target_station_reuse_confirmed,
            "confirmTrackAndWorkAreaFit": track_fit_confirmed,
            "authorizationScope": decision.get("authorizationScope"),
            "source": decision["source"],
            "confirmedBy": decision["confirmedBy"],
            "confirmedAt": decision["confirmedAt"],
            "decisionPacketDigest": confirmed_digests[key],
        }
        row["readyForCadValidation"] = False
        row["nextAction"] = (
            "run_nonprototype_cad_then_check_track_and_work_area_before_publication"
            if trial_only
            else "reuse_existing_nonprototype_cad_when_authenticated_or_run_new_cad_"
                 "then_execute_target_station_postcheck"
        )
    result["status"] = "decisions_applied_requires_cad_or_station_postcheck"
    result["summary"] = {
        **result.get("summary", {}),
        "confirmedCount": confirmed_count,
        "nativeStationCount": native_count,
        "pendingEngineeringConfirmationCount": still_pending,
    }
    result["confirmationPacketDigests"] = sorted(set(packet_digests))
    result["cadStarted"] = False
    result["claimBoundary"] = (
        "Exact historical confirmations and native-station identities are applied only "
        "to refine the next action. They do not prove current CAD, target-station "
        "postchecks, track compatibility, fastening or production approval."
    )
    result.pop("queueDigest", None)
    result["queueDigest"] = _digest({
        key: value for key, value in result.items() if key != "queueDigest"
    })
    return result


def build_transport_station_trial_authorization_packet(
    review_queue: dict[str, Any],
    *,
    exact_pairs: list[tuple[str, str]],
    source: str,
    authorized_by: str,
    authorized_at: str,
) -> dict[str, Any]:
    """Authorize bounded CAD trials from measured target-native stations.

    This deliberately does *not* confirm track/work-area fit.  It only records
    that the exact measured target station may seed a non-prototype CAD trial.
    The resulting packet can never be interpreted as a released interface or
    target-station validation.
    """

    if review_queue.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported transport station review queue")
    core = {key: value for key, value in review_queue.items() if key != "queueDigest"}
    if _digest(core) != review_queue.get("queueDigest"):
        raise ValueError("transport station review queue digest mismatch")
    if not exact_pairs or len(set(exact_pairs)) != len(exact_pairs):
        raise ValueError("transport trial pair selection is empty or duplicated")
    if not all(str(value or "").strip() for value in (
        source, authorized_by, authorized_at
    )):
        raise ValueError("transport trial authorization provenance is incomplete")
    recommendations = {
        (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"]): row
        for row in review_queue.get("recommendations") or []
    }
    records = []
    for pair in sorted(exact_pairs):
        row = recommendations.get(pair)
        authority = (row or {}).get("interfaceAuthority") or {}
        if (
            row is None
            or authority.get("status")
            != "datum_fallback_requires_explicit_position_parameters"
            or authority.get("requiresNewParameterizedDatumRelease") is not True
            or authority.get("releaseManifestPath") is not None
        ):
            raise ValueError(
                f"transport pair is not eligible for a target-native trial: {pair}"
            )
        parameters = row.get("recommendedPositionParametersMeters")
        if not isinstance(parameters, dict) or set(parameters) != {
            "longitudinal", "lateral", "supportGap"
        }:
            raise ValueError(f"transport trial position is incomplete: {pair}")
        records.append({
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "confirmed": True,
            "confirmTargetStationReuse": True,
            "confirmTrackAndWorkAreaFit": False,
            "authorizationScope": "nonprototype_cad_trial_only",
            "source": source,
            "confirmedBy": authorized_by,
            "confirmedAt": authorized_at,
            "parametersMeters": deepcopy(parameters),
            "evidenceBasis": "measured_target_native_role_station_trial",
            "nativeStationEvidenceDigest": row.get(
                "nativeStationEvidenceDigest"
            ),
        })
    packet_core = {
        "schemaVersion": POSITION_PACKET_SCHEMA,
        "sourceReviewDigest": review_queue["queueDigest"],
        "confirmedPairCount": len(records),
        "pairs": records,
        "claimBoundary": (
            "Exact-pair authorization for non-prototype CAD trials only. Target "
            "station reuse is authorized, but track/work-area fit, fastening, "
            "collision/B-rep and production suitability remain unconfirmed."
        ),
    }
    return {**packet_core, "decisionPacketDigest": _digest(packet_core)}
