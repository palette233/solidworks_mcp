"""Materialize confirmed or exact-native transport stations as rule candidates.

The module does not write files or launch CAD.  It converts an authenticated
batch review plus exact confirmation packets into the existing target-station
rule shape.  Every candidate remains ``validation.status=candidate`` until the
normal non-prototype CAD and save/reopen postcheck succeeds.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .transport_station_review_queue import (
    apply_transport_station_confirmation_packets,
)


SCHEMA = "transport-position-station-candidate-bundle/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_transport_position_station_candidates(
    *,
    review_queue: dict[str, Any],
    review_binding: dict[str, str],
    confirmation_bindings: list[dict[str, Any]],
    base_registry: dict[str, Any],
    config_directory_path: str,
) -> dict[str, Any]:
    """Create candidates for exact confirmations and native-role stations."""

    if base_registry.get("schemaVersion") != "target-station-rule-registry/v1":
        raise ValueError("unsupported base target-station registry")
    if not isinstance(review_binding.get("path"), str) or len(
        review_binding.get("sha256") or ""
    ) != 64:
        raise ValueError("transport review binding is incomplete")
    if not isinstance(config_directory_path, str) or not config_directory_path:
        raise ValueError("transport candidate config directory is missing")
    packets = [row.get("payload") for row in confirmation_bindings]
    if any(not isinstance(packet, dict) for packet in packets):
        raise ValueError("transport confirmation payload is missing")
    applied = apply_transport_station_confirmation_packets(review_queue, packets)
    binding_by_digest = {}
    for row in confirmation_bindings:
        path, sha256 = row.get("path"), row.get("sha256")
        packet = row["payload"]
        digest = packet.get("decisionPacketDigest")
        if not isinstance(path, str) or not path or not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError("transport confirmation file binding is incomplete")
        if digest in binding_by_digest:
            raise ValueError("duplicate transport confirmation packet digest")
        binding_by_digest[digest] = {"path": path, "sha256": sha256}

    existing_pairs = {
        (row.get("sourceModuleDefinitionId"), row.get("targetBaseDefinitionId"))
        for row in base_registry.get("rules") or []
    }
    configs: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    for row in applied.get("recommendations") or []:
        status = row.get("status")
        confirmed = status == (
            "engineering_confirmation_recorded_requires_target_station_postcheck"
        )
        trial_authorized = status == (
            "target_native_station_trial_authorized_requires_cad_validation"
        )
        native = status == (
            "native_station_requires_current_saved_output_station_postcheck"
        )
        if not confirmed and not trial_authorized and not native:
            continue
        source = row["sourceModuleDefinitionId"]
        base = row["targetBaseDefinitionId"]
        pair = (source, base)
        if pair in existing_pairs:
            raise ValueError(f"transport candidate pair already has a station rule: {pair}")
        confirmation = row.get("confirmationTemplate") or {}
        packet_binding = None
        if confirmed or trial_authorized:
            packet_binding = binding_by_digest.get(
                confirmation.get("decisionPacketDigest")
            )
            if packet_binding is None:
                raise ValueError(
                    f"transport confirmation packet file is not bound: {pair}"
                )
        rule_id = (
            "transport-position-"
            + source.replace("::", "-").lower()
            + "-to-"
            + base.replace("::", "-").lower()
            + "-v1"
        )
        config_path = f"{config_directory_path.rstrip('/')}/{rule_id}.json"
        release_path = row["interfaceAuthority"].get("releaseManifestPath")
        inputs = {
            "transportReviewPath": review_binding["path"],
        }
        input_sha256 = {
            "transportReviewPath": review_binding["sha256"],
        }
        if release_path:
            inputs["referenceReleasePath"] = release_path
        else:
            evidence = row.get("targetNativeStationEvidence") or []
            if not evidence:
                raise ValueError(
                    f"target native station evidence is missing: {pair}"
                )
            selected_evidence = evidence[0]
            inputs["targetNativeStationEvidencePath"] = selected_evidence["path"]
            input_sha256["targetNativeStationEvidencePath"] = selected_evidence[
                "sha256"
            ]
        if packet_binding is not None:
            inputs["confirmationPacketPath"] = packet_binding["path"]
            input_sha256["confirmationPacketPath"] = packet_binding["sha256"]
        config = {
            "schemaVersion": "transport-position-parameters-rule/v1",
            "ruleId": rule_id,
            "sourceModuleDefinitionId": source,
            "targetBaseDefinitionId": base,
            "nativeRoleModuleDefinitionId": row["nativeRoleModuleDefinitionId"],
            "positionParametersMeters": deepcopy(
                row["recommendedPositionParametersMeters"]
            ),
            "inputs": inputs,
            "inputSha256": input_sha256,
            "coordinateSystem": "target_base_semantic_longitudinal_lateral_support",
            "interpretationLimits": [
                "Position parameters are accepted for the exact module/base pair only.",
                "The source prototype world pose is not an execution authority.",
                "Track/work-area fit is a Demo engineering acceptance; actual process, fastening, collision and production are not verified.",
            ],
        }
        if confirmed:
            config["engineeringConfirmation"] = {
                key: deepcopy(confirmation.get(key)) for key in (
                    "confirmed", "source", "confirmedBy", "confirmedAt",
                    "decisionPacketDigest",
                )
            }
        elif trial_authorized:
            if (
                confirmation.get("confirmTargetStationReuse") is not True
                or confirmation.get("confirmTrackAndWorkAreaFit") is not False
                or confirmation.get("authorizationScope")
                != "nonprototype_cad_trial_only"
            ):
                raise ValueError(
                    f"transport trial authorization is incomplete: {pair}"
                )
            config["candidateAuthorization"] = {
                "authorized": True,
                "kind": "target_native_station_nonprototype_cad_trial",
                "targetStationReuseConfirmed": True,
                "trackAndWorkAreaFitConfirmed": False,
                "authorizationScope": "nonprototype_cad_trial_only",
                "source": confirmation.get("source"),
                "authorizedBy": confirmation.get("confirmedBy"),
                "authorizedAt": confirmation.get("confirmedAt"),
                "decisionPacketDigest": confirmation.get("decisionPacketDigest"),
                "nativeStationEvidenceDigest": row.get(
                    "nativeStationEvidenceDigest"
                ),
            }
        else:
            evidence_digest = str(row.get("nativeStationEvidenceDigest") or "")
            if (
                source != row.get("nativeRoleModuleDefinitionId")
                or source.split("::", 1)[0] != base.split("::", 1)[0]
                or len(evidence_digest) != 64
            ):
                raise ValueError(f"native transport station identity is invalid: {pair}")
            config["nativeStationAuthorization"] = {
                "authorized": True,
                "kind": "exact_native_role_station_identity",
                "sourceModuleDefinitionId": source,
                "targetBaseDefinitionId": base,
                "nativeStationEvidenceDigest": evidence_digest,
                "source": "authenticated_target_base_native_transport_station",
            }
        rule = {
            "ruleId": rule_id,
            "role": "Transport",
            "sourceModuleDefinitionId": source,
            "targetBaseDefinitionId": base,
            "evaluator": {
                "kind": "transport_position_parameters",
                "inputPath": config_path,
            },
            "placement": {"strategy": "target_role_region"},
            "validation": {"status": "candidate"},
        }
        configs.append({"path": config_path, "payload": config})
        rules.append(rule)
        existing_pairs.add(pair)
    merged = deepcopy(base_registry)
    merged.setdefault("rules", []).extend(rules)
    core = {
        "schemaVersion": SCHEMA,
        "status": "candidate_rules_prepared_no_cad",
        "candidateCount": len(rules),
        "configs": configs,
        "candidateRules": rules,
        "candidateRegistry": merged,
        "unresolvedEngineeringConfirmationCount": applied["summary"][
            "pendingEngineeringConfirmationCount"
        ],
        "nativeStationPostcheckCount": applied["summary"]["nativeStationCount"],
        "cadStarted": False,
        "claimBoundary": (
            "Candidate rules only. Engineering confirmation is not CAD proof; every "
            "candidate still requires non-prototype execution or authenticated saved-output "
            "reuse, active-mate verification, save/reopen and target-station postcheck."
        ),
    }
    return {**core, "bundleDigest": _digest(core)}
