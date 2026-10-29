"""Build an auditable parameterized-datum candidate inside a bounded role station.

This module is intentionally a thin planning layer.  It reuses an already
registered three-plane endpoint bundle, but it does *not* reuse the former
position recipe or its execution authority.  A new candidate is derived from
the target base's bounded native-role region and must still pass a fresh
non-prototype CAD/save/reopen validation before it can be published.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .finite_support_gate import evaluate_finite_support_gate
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import load_parameterized_datum_placement_catalog


SCHEMA = "bounded-role-station-candidate/v1"
CONFIG_SCHEMA = "bounded-role-station-config/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MechanicalInterfaceContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise MechanicalInterfaceContractError(f"{label} must be finite")
    return result


def _resolve(workspace: Path, raw: str, label: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    return path


def _pair_profile(
    workspace: Path, module_definition_id: str, slot_definition_id: str
) -> tuple[dict[str, Any], dict[str, bool]]:
    catalog = load_parameterized_datum_placement_catalog(workspace)
    module_rows = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == module_definition_id
    ]
    if len(module_rows) != 1:
        raise MechanicalInterfaceContractError(
            "bounded role station requires one registered moving datum port"
        )
    module_role = module_rows[0].get("moduleRole")
    slot_rows = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == slot_definition_id
        and module_role in (row.get("acceptedModuleRoles") or [])
    ]
    if len(slot_rows) != 1:
        raise MechanicalInterfaceContractError(
            "bounded role station requires one role-compatible base datum field"
        )
    geometry = slot_rows[0].get("geometrySignature") or {}
    profile = (
        geometry.get("finiteSupportProfilesByModuleDefinitionId") or {}
    ).get(module_definition_id)
    flips = (
        geometry.get("distanceFlipDimensionsByModuleDefinitionId") or {}
    ).get(module_definition_id)
    if not isinstance(profile, dict) or not isinstance(flips, dict):
        raise MechanicalInterfaceContractError(
            "bounded role station requires a finite-support profile and explicit distance directions"
        )
    return profile, {key: bool(value) for key, value in flips.items()}


def _parameter_for_coordinate(
    *, profile: dict[str, Any], role: str, coordinate: float, flipped: bool
) -> float:
    base = _finite((profile.get("baseDatumCoordinates") or {}).get(role), f"base.{role}")
    direction = _finite(
        (profile.get("distanceDirectionWhenNotFlipped") or {}).get(role),
        f"direction.{role}",
    )
    if direction not in {-1.0, 1.0}:
        raise MechanicalInterfaceContractError(f"direction.{role} must be -1 or 1")
    if flipped:
        direction *= -1.0
    distance = (coordinate - base) / direction
    if distance < 0 or not math.isfinite(distance):
        raise MechanicalInterfaceContractError(
            f"target {role} coordinate cannot be represented by a non-negative distance"
        )
    return distance


def build_bounded_role_station_candidate(
    workspace: Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Derive a new position candidate from a reviewed bounded native-role region."""

    workspace = workspace.resolve()
    if config.get("schemaVersion") != CONFIG_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported bounded role station config")
    module_definition_id = str(config.get("sourceModuleDefinitionId") or "")
    slot_definition_id = str(config.get("targetBaseDefinitionId") or "")
    if not module_definition_id or not slot_definition_id:
        raise MechanicalInterfaceContractError("bounded role station pair is incomplete")

    audit_path = _resolve(workspace, str(config.get("roleStationAuditPath") or ""), "role audit")
    expected_sha = str(config.get("roleStationAuditSha256") or "")
    if len(expected_sha) != 64 or _sha256(audit_path) != expected_sha:
        raise MechanicalInterfaceContractError("role station audit digest mismatch")
    audit = _read(audit_path)
    if audit.get("schemaVersion") != "project02-a700-native-role-station-audit/v1":
        raise MechanicalInterfaceContractError("unsupported native role station audit")
    if audit.get("replacementModuleDefinitionId") != module_definition_id:
        raise MechanicalInterfaceContractError("role station audit source mismatch")
    if audit.get("targetBaseDefinitionId") != slot_definition_id:
        raise MechanicalInterfaceContractError("role station audit target mismatch")
    if audit.get("replacementEnvelopeFitsRoleStation") is not True:
        raise MechanicalInterfaceContractError("replacement footprint does not fit the role station")

    strategy = str(config.get("selectionStrategy") or "interval_center")
    if strategy != "interval_center":
        raise MechanicalInterfaceContractError("unsupported bounded role station selection strategy")
    interval = audit.get("allowedReplacementDatumIntervalMeters") or {}
    min_x = _finite(interval.get("minX"), "interval.minX")
    max_x = _finite(interval.get("maxX"), "interval.maxX")
    min_y = _finite(interval.get("minY"), "interval.minY")
    max_y = _finite(interval.get("maxY"), "interval.maxY")
    if min_x > max_x or min_y > max_y:
        raise MechanicalInterfaceContractError("bounded role station interval is empty")
    target = {"longitudinal": (min_x + max_x) / 2.0, "lateral": (min_y + max_y) / 2.0}

    profile, flips = _pair_profile(workspace, module_definition_id, slot_definition_id)
    parameters = {
        "longitudinal": _parameter_for_coordinate(
            profile=profile,
            role="longitudinal",
            coordinate=target["longitudinal"],
            flipped=flips["longitudinal"],
        ),
        "lateral": _parameter_for_coordinate(
            profile=profile,
            role="lateral",
            coordinate=target["lateral"],
            flipped=flips["lateral"],
        ),
        "supportGap": 0.0,
    }
    finite_support = evaluate_finite_support_gate(
        module_definition_id=module_definition_id,
        slot_definition_id=slot_definition_id,
        profile=profile,
        position_parameters=parameters,
        distance_flip_dimensions=flips,
    )
    if finite_support.get("passed") is not True:
        raise MechanicalInterfaceContractError("bounded role station candidate leaves finite support")
    footprint = finite_support["predictedFootprint"]
    role_bounds = audit.get("nativeRoleStationBoundsMeters") or {}
    role_checks = {
        "minXInside": footprint["minX"] >= _finite(role_bounds.get("minX"), "role.minX"),
        "maxXInside": footprint["maxX"] <= _finite(role_bounds.get("maxX"), "role.maxX"),
        "minYInside": footprint["minY"] >= _finite(role_bounds.get("minY"), "role.minY"),
        "maxYInside": footprint["maxY"] <= _finite(role_bounds.get("maxY"), "role.maxY"),
    }
    if not all(role_checks.values()):
        raise MechanicalInterfaceContractError("derived footprint is outside the native role station")

    reference_release = _resolve(
        workspace, str(config.get("referenceEndpointReleasePath") or ""), "endpoint reference release"
    )
    release = _read(reference_release)
    binding = ((release.get("releaseMetadata") or {}).get("parameterizedDatumPairBinding") or {})
    if binding.get("moduleDefinitionId") != module_definition_id or binding.get(
        "slotDefinitionId"
    ) != slot_definition_id:
        raise MechanicalInterfaceContractError("endpoint reference release pair mismatch")

    former = audit.get("forbiddenFallback") or {}
    old_pair = (former.get("longitudinalMeters"), former.get("lateralMeters"))
    new_pair = (parameters["longitudinal"], parameters["lateral"])
    if all(isinstance(value, (int, float)) for value in old_pair) and all(
        abs(float(left) - float(right)) <= 1e-12 for left, right in zip(old_pair, new_pair, strict=True)
    ):
        raise MechanicalInterfaceContractError("bounded role station candidate reused the forbidden fallback")

    core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_explicit_nonprototype_cad_validation",
        "sourceModuleDefinitionId": module_definition_id,
        "targetBaseDefinitionId": slot_definition_id,
        "role": str(config.get("role") or ""),
        "selectionStrategy": strategy,
        "coordinateFrame": audit.get("coordinateFrame"),
        "targetDatumCoordinatesMeters": target,
        "positionParametersMeters": parameters,
        "distanceFlipDimensions": flips,
        "predictedFootprintMeters": footprint,
        "nativeRoleStationBoundsMeters": role_bounds,
        "nativeRoleStationContainment": {"passed": True, "axisChecks": role_checks},
        "finiteSupportGate": finite_support,
        "endpointReuse": {
            "scope": "endpoint_bundle_only_not_position_or_execution_authority",
            "referenceReleasePath": str(reference_release),
            "referenceReleaseSha256": _sha256(reference_release),
        },
        "replacesSafetyReasonCode": str(config.get("replacesSafetyReasonCode") or ""),
        "roleStationAudit": {
            "path": str(audit_path),
            "sha256": expected_sha,
            "auditDigest": audit.get("auditDigest"),
        },
        "cadLaunchAllowed": True,
        "normalReleasedExecutionAllowed": False,
        "validationRequiredBeforeRelease": True,
        "claimBoundary": (
            "The candidate reuses only stable three-plane endpoints and derives a new position "
            "inside the bounded native-role region.  It does not reuse the revoked position "
            "recipe or execution authority.  Collision/B-rep, fastening and functional process "
            "performance remain unverified."
        ),
    }
    core["candidateDigest"] = _digest(core)
    return core


def validate_bounded_role_station_candidate(
    candidate: dict[str, Any],
    *,
    module_definition_id: str,
    slot_definition_id: str,
    position_parameters: dict[str, float] | None,
    distance_flip_dimensions: dict[str, bool] | None,
    safety_block: dict[str, Any],
) -> None:
    """Validate the exact evidence before bypassing one revoked pair recipe."""

    if candidate.get("schemaVersion") != SCHEMA or candidate.get("status") != (
        "ready_for_explicit_nonprototype_cad_validation"
    ):
        raise MechanicalInterfaceContractError("invalid bounded role station authorization")
    if candidate.get("sourceModuleDefinitionId") != module_definition_id or candidate.get(
        "targetBaseDefinitionId"
    ) != slot_definition_id:
        raise MechanicalInterfaceContractError("bounded role station authorization pair mismatch")
    if candidate.get("replacesSafetyReasonCode") != safety_block.get("reasonCode"):
        raise MechanicalInterfaceContractError("bounded role station authorization does not replace current safety blocker")
    if candidate.get("cadLaunchAllowed") is not True or candidate.get(
        "normalReleasedExecutionAllowed"
    ) is not False:
        raise MechanicalInterfaceContractError("bounded role station authorization scope is invalid")
    expected_digest = candidate.get("candidateDigest")
    unsigned = {key: value for key, value in candidate.items() if key != "candidateDigest"}
    if not isinstance(expected_digest, str) or expected_digest != _digest(unsigned):
        raise MechanicalInterfaceContractError("bounded role station candidate digest mismatch")
    if candidate.get("positionParametersMeters") != position_parameters:
        raise MechanicalInterfaceContractError("bounded role station position parameters changed")
    if candidate.get("distanceFlipDimensions") != distance_flip_dimensions:
        raise MechanicalInterfaceContractError("bounded role station distance directions changed")
    if (candidate.get("nativeRoleStationContainment") or {}).get("passed") is not True:
        raise MechanicalInterfaceContractError("bounded role station containment is not proven")
    if (candidate.get("finiteSupportGate") or {}).get("passed") is not True:
        raise MechanicalInterfaceContractError("finite support containment is not proven")
