"""Build reviewable transport-context work-area profiles.

The historical work-position artifacts describe process context around a
transport, not necessarily geometry owned by the bare transport module.  This
module keeps that distinction explicit.  It produces measured facts and a
review queue, but deliberately does not invent an engineering tolerance or
authorize CAD/publication.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any


PROFILE_SCHEMA = "transport-context-work-area-profile/v1"
COMPARISON_SCHEMA = "transport-work-area-compatibility-review/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _definition(value: Any, name: str) -> str:
    if not isinstance(value, str) or value.count("::") != 1:
        raise ValueError(f"{name} must be a project module definition id")
    project, token = value.split("::", 1)
    if not project or not token:
        raise ValueError(f"{name} must be a project module definition id")
    return value


def _validate_profile_digest(profile: dict[str, Any]) -> None:
    digest = profile.get("profileDigest")
    core = {key: value for key, value in profile.items() if key != "profileDigest"}
    if not isinstance(digest, str) or digest != _digest(core):
        raise ValueError("transport work-area profile digest mismatch")


def build_transport_context_work_area_profile(
    *,
    artifact: dict[str, Any],
    artifact_binding: dict[str, str],
    transport_definition_id: str,
    context_definition_ids: list[str],
    context_description: str,
) -> dict[str, Any]:
    """Normalize one measured prototype work-position artifact.

    ``context_definition_ids`` names the module subtree(s) that actually own
    the measured work positions.  It may include the transport itself, but it
    must not be silently replaced by the transport identity.
    """

    transport = _definition(transport_definition_id, "transport_definition_id")
    if not isinstance(context_definition_ids, list) or not context_definition_ids:
        raise ValueError("context_definition_ids must not be empty")
    context = [
        _definition(value, "context_definition_ids")
        for value in context_definition_ids
    ]
    if len(set(context)) != len(context):
        raise ValueError("context_definition_ids must be unique")
    if not isinstance(context_description, str) or not context_description.strip():
        raise ValueError("context_description is required")
    path = artifact_binding.get("path")
    sha256 = artifact_binding.get("sha256")
    if not isinstance(path, str) or not path or not isinstance(sha256, str) or len(sha256) != 64:
        raise ValueError("work-position artifact binding is incomplete")
    if artifact.get("projectId") != transport.split("::", 1)[0]:
        raise ValueError("work-position artifact project differs from transport")
    rows = artifact.get("workPositions")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("at least two measured work positions are required")
    if artifact.get("workPositionCount") != len(rows):
        raise ValueError("work-position count differs from artifact rows")

    normalized = []
    stable_ids = set()
    for index, row in enumerate(rows):
        stable_id = row.get("stableId")
        frame = row.get("installationFramePointMeters")
        if not isinstance(stable_id, str) or not stable_id or stable_id in stable_ids:
            raise ValueError("work-position stable ids must be present and unique")
        if not isinstance(frame, dict):
            raise ValueError("installation-frame point is missing")
        point = {
            axis: _finite(frame.get(axis), f"workPositions[{index}].{axis}")
            for axis in ("u", "v", "normal")
        }
        normalized.append({
            "stableId": stable_id,
            "sourceInstance": row.get("sourceInstance"),
            "sourceProcessSubtree": row.get("sourceProcessSubtree"),
            "semanticEvidence": row.get("semanticEvidence"),
            "installationFramePointMeters": point,
        })
        stable_ids.add(stable_id)
    normalized.sort(key=lambda row: row["installationFramePointMeters"]["u"])
    low = normalized[0]["installationFramePointMeters"]
    high = normalized[-1]["installationFramePointMeters"]
    du = high["u"] - low["u"]
    dv = high["v"] - low["v"]
    dn = high["normal"] - low["normal"]
    measured_center_separation = _finite(
        artifact.get("centerSeparationMeters"), "centerSeparationMeters"
    )
    metrics = {
        "longitudinalSpanMeters": abs(du),
        "transverseDeltaMeters": abs(dv),
        "normalDeltaMeters": abs(dn),
        "planSeparationMeters": math.hypot(du, dv),
        "artifactCenterSeparationMeters": measured_center_separation,
        "longitudinalMidpointMeters": (low["u"] + high["u"]) / 2.0,
        "transverseMidpointMeters": (low["v"] + high["v"]) / 2.0,
        "normalMidpointMeters": (low["normal"] + high["normal"]) / 2.0,
    }
    core = {
        "schemaVersion": PROFILE_SCHEMA,
        "transportModuleDefinitionId": transport,
        "workPositionContextDefinitionIds": context,
        "workPositionContextDescription": context_description.strip(),
        "workPositionsOwnedByBareTransport": set(context) == {transport},
        "coordinateSystem": "transport_installation_frame_u_v_normal",
        "workPositionCount": len(normalized),
        "orderedWorkPositions": normalized,
        "metrics": metrics,
        "sourceArtifact": {
            "path": path,
            "sha256": sha256,
            "schemaVersion": artifact.get("schemaVersion"),
            "authority": artifact.get("authority"),
            "engineeringConfirmed": artifact.get("engineeringConfirmed"),
        },
        "interpretationLimits": [
            *deepcopy(artifact.get("interpretationLimits") or []),
            "This profile describes a transport process context; it is not evidence that the bare transport owns every work position.",
            "Measured positions are coarse process targets and are not fastening, collision, carrier-interface or production approval.",
        ],
        "cadStarted": False,
        "claimBoundary": (
            "Measured context profile only. It does not authorize a cross-project "
            "transport replacement or a CAD publication."
        ),
    }
    return {**core, "profileDigest": _digest(core)}


def compare_transport_work_area_profiles(
    *,
    source_profile: dict[str, Any],
    target_profile: dict[str, Any],
    target_base_definition_id: str,
    candidate_rule_id: str,
) -> dict[str, Any]:
    """Compare measured facts without choosing an engineering tolerance."""

    _validate_profile_digest(source_profile)
    _validate_profile_digest(target_profile)
    target_base = _definition(target_base_definition_id, "target_base_definition_id")
    if not isinstance(candidate_rule_id, str) or not candidate_rule_id:
        raise ValueError("candidate_rule_id is required")
    if target_profile["transportModuleDefinitionId"].split("::", 1)[0] != target_base.split("::", 1)[0]:
        raise ValueError("target work-area profile project differs from target base")

    source_metrics = source_profile["metrics"]
    target_metrics = target_profile["metrics"]
    spacing_difference = abs(
        source_metrics["artifactCenterSeparationMeters"]
        - target_metrics["artifactCenterSeparationMeters"]
    )
    source_mid = source_metrics["longitudinalMidpointMeters"]
    target_mid = target_metrics["longitudinalMidpointMeters"]
    longitudinal_alignment_shift = target_mid - source_mid
    source_points = source_profile["orderedWorkPositions"]
    target_points = target_profile["orderedWorkPositions"]
    paired_residuals = []
    if len(source_points) == len(target_points):
        for source, target in zip(source_points, target_points):
            source_u = source["installationFramePointMeters"]["u"]
            target_u = target["installationFramePointMeters"]["u"]
            paired_residuals.append({
                "sourceStableId": source["stableId"],
                "targetStableId": target["stableId"],
                "longitudinalResidualAfterMidpointAlignmentMeters": (
                    source_u + longitudinal_alignment_shift - target_u
                ),
            })

    blockers = ["TRACK_AND_CARRIER_INTERFACE_EVIDENCE_REQUIRED"]
    if source_profile["workPositionCount"] != target_profile["workPositionCount"]:
        blockers.append("WORK_POSITION_COUNT_POLICY_REQUIRED")
    if spacing_difference > 1e-12:
        blockers.append("WORK_POSITION_SPACING_ACCEPTANCE_POLICY_REQUIRED")
    if (
        not source_profile["workPositionsOwnedByBareTransport"]
        or not target_profile["workPositionsOwnedByBareTransport"]
    ):
        blockers.append("WORK_POSITION_CONTEXT_SELECTION_REQUIRED")
    blockers.append("CURRENT_CAD_WORK_POSITION_REPROJECTION_REQUIRED")

    core = {
        "schemaVersion": COMPARISON_SCHEMA,
        "candidateRuleId": candidate_rule_id,
        "sourceTransportModuleDefinitionId": source_profile[
            "transportModuleDefinitionId"
        ],
        "targetNativeTransportModuleDefinitionId": target_profile[
            "transportModuleDefinitionId"
        ],
        "targetBaseDefinitionId": target_base,
        "sourceProfileDigest": source_profile["profileDigest"],
        "targetProfileDigest": target_profile["profileDigest"],
        "measuredComparison": {
            "sourceWorkPositionCount": source_profile["workPositionCount"],
            "targetWorkPositionCount": target_profile["workPositionCount"],
            "workPositionCountEqual": (
                source_profile["workPositionCount"]
                == target_profile["workPositionCount"]
            ),
            "sourceCenterSeparationMeters": source_metrics[
                "artifactCenterSeparationMeters"
            ],
            "targetCenterSeparationMeters": target_metrics[
                "artifactCenterSeparationMeters"
            ],
            "absoluteCenterSeparationDifferenceMeters": spacing_difference,
            "sourceTransverseDeltaMeters": source_metrics[
                "transverseDeltaMeters"
            ],
            "targetTransverseDeltaMeters": target_metrics[
                "transverseDeltaMeters"
            ],
            "sourceNormalDeltaMeters": source_metrics["normalDeltaMeters"],
            "targetNormalDeltaMeters": target_metrics["normalDeltaMeters"],
            "longitudinalMidpointAlignmentShiftMeters": (
                longitudinal_alignment_shift
            ),
            "pairedLongitudinalResiduals": paired_residuals,
        },
        "contextComparison": {
            "sourceContextDefinitionIds": source_profile[
                "workPositionContextDefinitionIds"
            ],
            "targetContextDefinitionIds": target_profile[
                "workPositionContextDefinitionIds"
            ],
            "sourceWorkPositionsOwnedByBareTransport": source_profile[
                "workPositionsOwnedByBareTransport"
            ],
            "targetWorkPositionsOwnedByBareTransport": target_profile[
                "workPositionsOwnedByBareTransport"
            ],
            "bareTransportOnlyCandidateCanReprojectBothContexts": (
                source_profile["workPositionsOwnedByBareTransport"]
                and target_profile["workPositionsOwnedByBareTransport"]
            ),
            "requiredSourceContextInstancesForCurrentCadReprojection": (
                source_profile["workPositionContextDefinitionIds"]
            ),
            "requiredTargetContextOrAuthenticatedBaseFrameForComparison": (
                target_profile["workPositionContextDefinitionIds"]
            ),
        },
        "status": "requires_engineering_threshold_or_context_selection",
        "blockingReasonCodes": blockers,
        "engineeringAcceptanceRecorded": False,
        "currentCadReprojectionCompleted": False,
        "publicationAllowed": False,
        "cadStarted": False,
        "nextActions": [
            "Decide whether the replacement scope is the bare transport or the transport plus its work-position context modules.",
            "If the scope is bare transport only, measure track/carrier interface geometry and do not claim that FF00/AD00/K000 work positions move with it.",
            "Define an explicit accepted work-position spacing/track/carrier policy; do not infer a tolerance from these measurements.",
            "After the required context instances exist in the non-prototype CAD chain, reproject their local work positions using actual saved transforms.",
        ],
        "claimBoundary": (
            "Measured comparison and review blockers only. No track/carrier fit, "
            "CAD closure, collision, fastening, process result or publication is claimed."
        ),
    }
    return {**core, "comparisonDigest": _digest(core)}
