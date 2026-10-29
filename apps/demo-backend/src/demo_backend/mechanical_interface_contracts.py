"""Project-independent mechanical interface contracts and mate instantiation.

The contract layer deliberately separates a module's installation port from a
base slot.  It can therefore decide compatibility from topology, dimensions
and orientation without relying on project IDs or a pre-authored module-pair
template.  A positive match only permits a semantic mate recipe to be
instantiated; a new cross-project pair still requires its own non-prototype CAD
evidence and an execution release.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "mechanical-interface-contract/v1"
MATCH_SCHEMA = "mechanical-interface-match/v1"
CATALOG_SCHEMA = "cleaning-weighing-interface-contract-catalog/v1"
TRANSPORT_CATALOG_SCHEMA = "transport-interface-contract-catalog/v1"
CALIBRATION_CATALOG_SCHEMA = "calibration-interface-contract-catalog/v1"
SCANNER_CATALOG_SCHEMA = "scanner-interface-contract-catalog/v1"
WASTECUP_CATALOG_SCHEMA = "wastecup-support-position-contract-catalog/v1"
CONTEXTUAL_TRANSPORT_CATALOG_SCHEMA = "contextual-transport-interface-contract-catalog/v1"
CONTEXTUAL_SCANNER_CATALOG_SCHEMA = "contextual-scanner-interface-contract-catalog/v1"
CCD_CATALOG_SCHEMA = "ccd-interface-contract-catalog/v1"
NATIVE_WASTECUP_CATALOG_SCHEMA = "native-wastecup-interface-contract-catalog/v1"
DATUM_PLACEMENT_CATALOG_SCHEMA = "parameterized-datum-placement-contract-catalog/v1"
INTERFACE_FAMILY = "plane_two_hole_rigid_mount/v1"
RECIPE_ID = "recipe/plane-two-hole-rigid-mount/v1"
REQUIRED_ROLES = (
    "support_plane",
    "primary_locating_hole",
    "secondary_locating_hole",
)
SUPPORT_POSITION_FAMILY = "support_plane_two_offset_position/v1"
SUPPORT_POSITION_RECIPE_ID = "recipe/support-plane-two-offset-position/v1"
NATIVE_WASTECUP_TWO_DISTANCE_FAMILY = (
    "native_wastecup_two_distance_support_mount/v1"
)
SUPPORT_POSITION_ROLES = (
    "support_datum",
    "longitudinal_datum",
    "lateral_datum",
)
DISTANCE_WIDTH_FAMILY = "plane_distance_width_transport_mount/v1"
DISTANCE_WIDTH_RECIPE_ID = "recipe/plane-distance-width-transport-mount/v1"
CALIBRATION_DISTANCE_WIDTH_FAMILY = "calibration_plane_distance_width_mount/v1"
CALIBRATION_DISTANCE_WIDTH_RECIPE_ID = "recipe/calibration-plane-distance-width-mount/v1"
DISTANCE_WIDTH_ROLES = (
    "support_plane",
    "longitudinal_datum",
    "width_datum_a",
    "width_datum_b",
)
PARTIAL_WIDTH_FAMILY = "plane_width_transport_mount_partial/v1"
PARTIAL_WIDTH_RECIPE_ID = "recipe/plane-width-transport-mount-partial/v1"
PARTIAL_WIDTH_ROLES = (
    "support_plane",
    "width_datum_a",
    "width_datum_b",
)
SCANNER_DISTANCE_SLOT_FAMILY = "scanner_support_distance_slot_mount/v1"
SCANNER_DISTANCE_SLOT_RECIPE_ID = "recipe/scanner-support-distance-slot-mount/v1"
SCANNER_DISTANCE_SLOT_ROLES = (
    "support_plane",
    "longitudinal_datum",
    "slot_locator",
)
SCANNER_PLANE_AXIS_FAMILY = "scanner_plane_parallel_axis_mount/v1"
SCANNER_PLANE_AXIS_RECIPE_ID = "recipe/scanner-plane-parallel-axis-mount/v1"
SCANNER_PLANE_AXIS_ROLES = (
    "support_plane",
    "orientation_datum",
    "locating_axis",
)
FLEX_CALIBRATION_FAMILY = "calibration_flexible_plane_parallel_distance_slot/v1"
FLEX_CALIBRATION_RECIPE_ID = "recipe/calibration-flexible-plane-parallel-distance-slot/v1"
FLEX_CALIBRATION_ROLES = (
    "support_plane",
    "orientation_datum",
    "longitudinal_datum",
    "slot_locator",
)
CLEANING_SLOT_FAMILY = "cleaning_plane_parallel_distance_slot/v1"
CLEANING_SLOT_RECIPE_ID = "recipe/cleaning-plane-parallel-distance-slot/v1"
CCD_PLANE_AXIS_FAMILY = "ccd_plane_parallel_axis_mount/v1"
CCD_PLANE_AXIS_RECIPE_ID = "recipe/ccd-plane-parallel-axis-mount/v1"
CCD_PLANE_AXIS_ROLES = SCANNER_PLANE_AXIS_ROLES
CCD_DUAL_SLOT_FAMILY = "ccd_support_dual_slot_mount/v1"
CCD_DUAL_SLOT_RECIPE_ID = "recipe/ccd-support-dual-slot-mount/v1"
CCD_DUAL_SLOT_ROLES = (
    "support_plane",
    "slot_locator_a",
    "slot_locator_b",
)
NATIVE_WASTECUP_FAMILY = "wastecup_plane_parallel_slot_distance_mount/v1"
NATIVE_WASTECUP_RECIPE_ID = "recipe/wastecup-plane-parallel-slot-distance-mount/v1"


class MechanicalInterfaceContractError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _finite_positive(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MechanicalInterfaceContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise MechanicalInterfaceContractError(f"{label} must be finite and positive")
    return result


def _released(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get("schemaVersion") == "global-relation-catalog-release/v1"
        and manifest.get("status") == "released_for_demo_relation_execution"
        and manifest.get("releaseId")
        and manifest.get("releaseDigest")
        and any(
            row.get("passed") is True
            and row.get("drivingInitialPoseIndependent") is True
            for row in manifest.get("validationEvidence") or []
        )
    )


def build_plane_two_hole_contract(
    *,
    port: dict[str, Any],
    summary: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_role: str,
    module_definition_id: str,
    accepted_module_roles: list[str] | None = None,
    interface_family: str = INTERFACE_FAMILY,
    recipe_id: str = RECIPE_ID,
    locating_axis_spacing_meters: float | None = None,
    role_aliases: dict[str, str] | None = None,
    axis_parallel_score: float | None = None,
    axis_relation_to_primary: float | None = None,
) -> dict[str, Any]:
    """Normalize one released legacy port into a reusable interface contract."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    if not _released(release_manifest):
        raise MechanicalInterfaceContractError("port has no released non-prototype CAD evidence")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    aliases = role_aliases or {}
    for binding in bindings:
        binding["role"] = aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in REQUIRED_ROLES
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 3:
        raise MechanicalInterfaceContractError(
            "plane/two-hole contract requires exactly one endpoint for each datum role"
        )
    secondary = summary.get("secondaryAxis") or {}
    spacing = _finite_positive(
        locating_axis_spacing_meters
        if locating_axis_spacing_meters is not None
        else secondary.get("primaryIndependenceMeters"),
        "locating axis spacing",
    )
    parallel_score = float(
        axis_parallel_score
        if axis_parallel_score is not None
        else secondary.get("axisParallelScore") or 0.0
    )
    primary_relation = float(
        axis_relation_to_primary
        if axis_relation_to_primary is not None
        else secondary.get("axisRelationToPrimary") or 0.0
    )
    if not math.isfinite(parallel_score) or not math.isfinite(primary_relation):
        raise MechanicalInterfaceContractError("axis orientation evidence is invalid")
    expected_dof = int(summary.get("expectedResidualDof", -1))
    contract_core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": interface_family,
        "recipeId": recipe_id,
        "side": side,
        "projectId": summary.get("projectId"),
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role,
        "acceptedModuleRoles": (
            sorted(set(accepted_module_roles or [])) if side == "base_slot" else []
        ),
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(REQUIRED_ROLES),
        "geometrySignature": {
            "locatingAxisSpacingMeters": spacing,
            "axisParallelScore": parallel_score,
            "axisRelationToPrimary": primary_relation,
            "orientationConvention": "support_normals_opposed_axes_concentric",
        },
        "constraintContract": {
            "expectedResidualDof": expected_dof,
            "fullyLocatesRigidModule": expected_dof == 0,
            "drivingMateCount": int(summary.get("drivingMateCount") or 0),
        },
        "releaseEvidence": {
            "releaseId": release_manifest["releaseId"],
            "releaseDigest": release_manifest["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "diameterAndFastenerFit": "not_verified_by_contract_layer",
            "actualFasteningMethod": "not_inferred",
            "collisionOrBrep": "not_evaluated",
        },
    }
    contract_core["contractId"] = "interface-contract/" + _digest(contract_core)[:16]
    return contract_core


def build_support_position_contract(
    *,
    port: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_role: str,
    module_definition_id: str,
    accepted_module_roles: list[str] | None = None,
    position_parameters_meters: dict[str, float] | None = None,
    position_parameters_by_module_definition_id: dict[str, dict[str, float]] | None = None,
    distance_flip_dimensions: dict[str, bool] | None = None,
    distance_flip_dimensions_by_module_definition_id: dict[str, dict[str, bool]] | None = None,
    finite_support_profiles_by_module_definition_id: dict[str, dict[str, Any]] | None = None,
    interface_family: str = SUPPORT_POSITION_FAMILY,
    role_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a datum-placement Demo contract without claiming physical fastening."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    if not _released(release_manifest):
        raise MechanicalInterfaceContractError("port has no released non-prototype CAD evidence")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    aliases = role_aliases or {}
    for binding in bindings:
        binding["role"] = aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in SUPPORT_POSITION_ROLES
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 3:
        raise MechanicalInterfaceContractError(
            "support-position contract requires exactly three orthogonal datum endpoints"
        )
    def normalized_parameters(raw: dict[str, Any], label: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for key in ("longitudinal", "lateral", "supportGap"):
            value = raw.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MechanicalInterfaceContractError(
                    f"{label} position parameter {key} must be numeric"
                )
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise MechanicalInterfaceContractError(
                    f"{label} position parameter {key} must be finite and non-negative"
                )
            result[key] = number
        return result

    def normalized_flips(raw: dict[str, Any], label: str) -> dict[str, bool]:
        expected = {"longitudinal", "lateral", "supportGap"}
        if set(raw) != expected or any(not isinstance(raw[key], bool) for key in expected):
            raise MechanicalInterfaceContractError(
                f"{label} distance flips require boolean longitudinal/lateral/supportGap values"
            )
        return {key: bool(raw[key]) for key in ("longitudinal", "lateral", "supportGap")}

    parameters: dict[str, float] = {}
    parameter_overrides: dict[str, dict[str, float]] = {}
    flips = normalized_flips(
        distance_flip_dimensions
        or {"longitudinal": False, "lateral": False, "supportGap": False},
        "default",
    )
    flip_overrides: dict[str, dict[str, bool]] = {}
    support_profiles: dict[str, dict[str, Any]] = {}
    if side == "base_slot":
        # A base datum frame may be registered before a role-specific station
        # position is known.  In that case the contract remains structurally
        # valid, but matching reports MODULE_POSITION_PRESET_MISSING and the
        # exact pair cannot compile until explicit parameters are confirmed.
        # Do not manufacture a zero-position preset merely to make the row
        # appear compatible.
        if position_parameters_meters is not None:
            parameters = normalized_parameters(position_parameters_meters, "default")
        for definition_id, raw in sorted(
            (position_parameters_by_module_definition_id or {}).items()
        ):
            if not definition_id:
                raise MechanicalInterfaceContractError(
                    "module-specific position preset requires a definition id"
                )
            parameter_overrides[definition_id] = normalized_parameters(
                raw, definition_id
            )
        for definition_id, raw in sorted(
            (distance_flip_dimensions_by_module_definition_id or {}).items()
        ):
            if not definition_id:
                raise MechanicalInterfaceContractError(
                    "module-specific distance flips require a definition id"
                )
            flip_overrides[definition_id] = normalized_flips(raw, definition_id)
        support_profiles = copy.deepcopy(
            finite_support_profiles_by_module_definition_id or {}
        )
    core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": interface_family,
        "recipeId": SUPPORT_POSITION_RECIPE_ID,
        "side": side,
        "projectId": module_definition_id.split("::", 1)[0] if "::" in module_definition_id else None,
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role,
        "acceptedModuleRoles": sorted(set(accepted_module_roles or [])) if side == "base_slot" else [],
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(SUPPORT_POSITION_ROLES),
        "geometrySignature": {
            "datumOrientationConvention": "three_orthogonal_planar_datums",
            "orthogonalDatumScore": 1.0,
            "positionParametersMeters": parameters,
            "positionParametersByModuleDefinitionId": parameter_overrides,
        },
        "constraintContract": {
            "expectedResidualDof": 0,
            "fullyLocatesRigidModule": True,
            "drivingMateCount": 3,
        },
        "releaseEvidence": {
            "releaseId": release_manifest["releaseId"],
            "releaseDigest": release_manifest["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "actualFasteningMethod": "not_verified",
            "directMechanicalCompatibilityClaim": False,
            # A datum-placement port proves that stable reference geometry exists.
            # It does not prove a newly selected module/base pair until that exact
            # pair has run from a non-prototype initial pose and been released.
            "requiresExplicitPairRelease": True,
            "placementMode": "parameterized_datum_placement",
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
        },
    }
    geometry = core["geometrySignature"]
    # Keep legacy contract identities stable unless direction/support metadata
    # is explicitly registered for this slot.  Runtime instantiation still
    # treats missing flip metadata as all-false.
    if distance_flip_dimensions is not None:
        geometry["distanceFlipDimensions"] = flips
    if flip_overrides:
        geometry["distanceFlipDimensionsByModuleDefinitionId"] = flip_overrides
    if support_profiles:
        geometry["finiteSupportProfilesByModuleDefinitionId"] = support_profiles
    core["contractId"] = "interface-contract/" + _digest(core)[:16]
    return core


def build_plane_distance_width_contract(
    *,
    port: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_role: str,
    module_definition_id: str,
    interface_variant_key: str,
    role_aliases: dict[str, str],
    accepted_module_roles: list[str] | None = None,
    longitudinal_offset_meters: float | None = None,
    interface_family: str = DISTANCE_WIDTH_FAMILY,
    recipe_id: str = DISTANCE_WIDTH_RECIPE_ID,
) -> dict[str, Any]:
    """Normalize support + longitudinal distance + width centering installation."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    if not _released(release_manifest):
        raise MechanicalInterfaceContractError("port has no released non-prototype CAD evidence")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    for binding in bindings:
        binding["role"] = role_aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in DISTANCE_WIDTH_ROLES
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 4:
        raise MechanicalInterfaceContractError(
            "plane/distance/width contract requires support, longitudinal and two width endpoints"
        )
    offset: float | None = None
    if side == "base_slot":
        value = longitudinal_offset_meters
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MechanicalInterfaceContractError("longitudinal offset must be numeric")
        offset = float(value)
        if not math.isfinite(offset) or offset < 0:
            raise MechanicalInterfaceContractError(
                "longitudinal offset must be finite and non-negative"
            )
    core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": interface_family,
        "recipeId": recipe_id,
        "side": side,
        "projectId": module_definition_id.split("::", 1)[0] if "::" in module_definition_id else None,
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role,
        "acceptedModuleRoles": sorted(set(accepted_module_roles or [])) if side == "base_slot" else [],
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(DISTANCE_WIDTH_ROLES),
        "geometrySignature": {
            "datumOrientationConvention": "support_distance_and_centered_width",
            "orientationScore": 1.0,
            "interfaceVariantKey": interface_variant_key,
            "longitudinalOffsetMeters": offset,
        },
        "constraintContract": {
            "expectedResidualDof": 0,
            "fullyLocatesRigidModule": True,
            "drivingMateCount": 3,
        },
        "releaseEvidence": {
            "releaseId": release_manifest["releaseId"],
            "releaseDigest": release_manifest["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "interfaceVariantKeyRequiresExplicitEvidence": True,
            "widthClearanceAndFastenerFit": "not_inferred",
            "collisionOrBrep": "not_evaluated",
        },
    }
    core["contractId"] = "interface-contract/" + _digest(core)[:16]
    return core


def build_partial_plane_width_contract(
    *,
    port: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_role: str,
    module_definition_id: str,
    role_aliases: dict[str, str],
    accepted_module_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Record an existing support/width port without pretending it closes pose."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    for binding in bindings:
        binding["role"] = role_aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in PARTIAL_WIDTH_ROLES
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 3:
        raise MechanicalInterfaceContractError(
            "partial plane/width contract requires support and two width endpoints"
        )
    core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": PARTIAL_WIDTH_FAMILY,
        "recipeId": PARTIAL_WIDTH_RECIPE_ID,
        "side": side,
        "projectId": module_definition_id.split("::", 1)[0] if "::" in module_definition_id else None,
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role,
        "acceptedModuleRoles": sorted(set(accepted_module_roles or [])) if side == "base_slot" else [],
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(PARTIAL_WIDTH_ROLES),
        "geometrySignature": {
            "datumOrientationConvention": "support_and_centered_width_missing_longitudinal",
            "orientationScore": 1.0,
            "missingDatumRole": "longitudinal_datum",
        },
        "constraintContract": {
            "expectedResidualDof": 1,
            "fullyLocatesRigidModule": False,
            "drivingMateCount": 2,
        },
        "releaseEvidence": {
            "releaseId": release_manifest.get("releaseId"),
            "releaseDigest": release_manifest.get("releaseDigest"),
            "nonPrototypeCadValidated": False,
            "evidenceBoundary": "source template explicitly requires project02 case pose anchor",
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "missingLongitudinalDatum": True,
            "casePoseAnchorForbiddenByDefault": True,
            "collisionOrBrep": "not_evaluated",
        },
    }
    core["contractId"] = "interface-contract/" + _digest(core)[:16]
    return core


def build_exact_three_relation_contract(
    *,
    port: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_role: str,
    module_definition_id: str,
    interface_family: str,
    recipe_id: str,
    topology_roles: tuple[str, str, str],
    interface_variant_key: str,
    role_aliases: dict[str, str],
    accepted_module_roles: list[str] | None = None,
    recipe_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register an exact released three-relation bundle for unusual mechanics."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    if not _released(release_manifest):
        raise MechanicalInterfaceContractError("port has no released non-prototype CAD evidence")
    if (interface_family, recipe_id, topology_roles) not in {
        (SCANNER_DISTANCE_SLOT_FAMILY, SCANNER_DISTANCE_SLOT_RECIPE_ID, SCANNER_DISTANCE_SLOT_ROLES),
        (SCANNER_PLANE_AXIS_FAMILY, SCANNER_PLANE_AXIS_RECIPE_ID, SCANNER_PLANE_AXIS_ROLES),
        (CCD_PLANE_AXIS_FAMILY, CCD_PLANE_AXIS_RECIPE_ID, CCD_PLANE_AXIS_ROLES),
        (CCD_DUAL_SLOT_FAMILY, CCD_DUAL_SLOT_RECIPE_ID, CCD_DUAL_SLOT_ROLES),
    }:
        raise MechanicalInterfaceContractError("unsupported exact three-relation interface")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    for binding in bindings:
        binding["role"] = role_aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in topology_roles
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 3:
        raise MechanicalInterfaceContractError(
            "exact three-relation contract requires one endpoint for every normalized role"
        )
    parameters = copy.deepcopy(recipe_parameters or {}) if side == "base_slot" else {}
    if recipe_id == SCANNER_DISTANCE_SLOT_RECIPE_ID and side == "base_slot":
        value = parameters.get("longitudinalOffsetMeters")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MechanicalInterfaceContractError("scanner longitudinal offset must be numeric")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise MechanicalInterfaceContractError(
                "scanner longitudinal offset must be finite and non-negative"
            )
        parameters["longitudinalOffsetMeters"] = value
    if recipe_id == CCD_DUAL_SLOT_RECIPE_ID and side == "base_slot":
        for key in ("slotAAdvancedOptions", "slotBAdvancedOptions"):
            options = parameters.get(key)
            if not isinstance(options, dict) or options.get("SlotConstraint") is None:
                raise MechanicalInterfaceContractError(
                    "CCD dual-slot recipe requires both source advanced-option bundles"
                )
    core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": interface_family,
        "recipeId": recipe_id,
        "side": side,
        "projectId": module_definition_id.split("::", 1)[0] if "::" in module_definition_id else None,
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role,
        "acceptedModuleRoles": sorted(set(accepted_module_roles or [])) if side == "base_slot" else [],
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(topology_roles),
        "geometrySignature": {
            "datumOrientationConvention": interface_family,
            "orientationScore": 1.0,
            "interfaceVariantKey": interface_variant_key,
            "recipeParameters": parameters,
        },
        "constraintContract": {
            "expectedResidualDof": 0,
            "fullyLocatesRigidModule": True,
            "drivingMateCount": 3,
        },
        "releaseEvidence": {
            "releaseId": release_manifest["releaseId"],
            "releaseDigest": release_manifest["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "exactBundleRequired": True,
            "crossVariantCompatibility": "not_inferred",
            "collisionOrBrep": "not_evaluated",
        },
    }
    core["contractId"] = "interface-contract/" + _digest(core)[:16]
    return core


def build_flexible_calibration_contract(
    *,
    port: dict[str, Any],
    release_manifest: dict[str, Any],
    side: str,
    module_definition_id: str,
    interface_variant_key: str,
    role_aliases: dict[str, str],
    accepted_module_roles: list[str] | None = None,
    longitudinal_offset_meters: float | None = None,
    module_role: str = "Calibration",
    interface_family: str = FLEX_CALIBRATION_FAMILY,
    recipe_id: str = FLEX_CALIBRATION_RECIPE_ID,
    internal_flexibility_preserved: bool = True,
) -> dict[str, Any]:
    """Register G000's exact external four-relation bundle without rigidifying internals."""

    if side not in {"moving_module", "base_slot"}:
        raise MechanicalInterfaceContractError("side must be moving_module or base_slot")
    if not _released(release_manifest):
        raise MechanicalInterfaceContractError("port has no released non-prototype CAD evidence")
    bindings = copy.deepcopy(port.get("endpointBindings") or [])
    for binding in bindings:
        binding["role"] = role_aliases.get(str(binding.get("role")), binding.get("role"))
    role_counts = {
        role: sum(row.get("role") == role and bool(row.get("endpointId")) for row in bindings)
        for role in FLEX_CALIBRATION_ROLES
    }
    if any(count != 1 for count in role_counts.values()) or len(bindings) != 4:
        raise MechanicalInterfaceContractError(
            "flexible calibration contract requires support, orientation, distance and slot endpoints"
        )
    offset: float | None = None
    if side == "base_slot":
        value = longitudinal_offset_meters
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MechanicalInterfaceContractError("calibration longitudinal offset must be numeric")
        offset = float(value)
        if not math.isfinite(offset) or offset < 0:
            raise MechanicalInterfaceContractError(
                "calibration longitudinal offset must be finite and non-negative"
            )
    core = {
        "schemaVersion": CONTRACT_SCHEMA,
        "interfaceFamily": interface_family,
        "recipeId": recipe_id,
        "side": side,
        "projectId": module_definition_id.split("::", 1)[0] if "::" in module_definition_id else None,
        "moduleDefinitionId": module_definition_id,
        "moduleToken": port.get("moduleToken"),
        "moduleRole": module_role if side == "moving_module" else "Base",
        "acceptedModuleRoles": sorted(set(accepted_module_roles or [])) if side == "base_slot" else [],
        "sourcePortId": port.get("portId"),
        "endpointBindings": bindings,
        "topologySignature": list(FLEX_CALIBRATION_ROLES),
        "geometrySignature": {
            "datumOrientationConvention": FLEX_CALIBRATION_FAMILY,
            "orientationScore": 1.0,
            "interfaceVariantKey": interface_variant_key,
            "longitudinalOffsetMeters": offset,
        },
        "constraintContract": {
            "expectedResidualDof": 0,
            "fullyLocatesRigidModule": True,
            "drivingMateCount": 4,
            "residualDofScope": "external_module_placement",
            "internalFlexibilityPreserved": internal_flexibility_preserved,
        },
        "releaseEvidence": {
            "releaseId": release_manifest["releaseId"],
            "releaseDigest": release_manifest["releaseDigest"],
            "nonPrototypeCadValidated": True,
        },
        "mechanicalBoundary": {
            "endpointGeometryRecovered": True,
            "staticDemoEvidence": True,
            "internalDynamicStates": (
                "not_evaluated" if internal_flexibility_preserved else "not_applicable"
            ),
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
        },
    }
    core["contractId"] = "interface-contract/" + _digest(core)[:16]
    return core


def match_interface_contracts(
    module_contract: dict[str, Any],
    slot_contract: dict[str, Any],
    *,
    spacing_tolerance_meters: float = 0.0002,
    orientation_tolerance: float = 1e-6,
    pair_release_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Match contracts without consulting project identity or a pair template."""

    spacing_tolerance_meters = _finite_positive(
        spacing_tolerance_meters, "spacing tolerance"
    )
    orientation_tolerance = _finite_positive(
        orientation_tolerance, "orientation tolerance"
    )
    blockers: list[dict[str, Any]] = []

    def block(code: str, detail: str) -> None:
        blockers.append({"code": code, "detail": detail})

    if module_contract.get("schemaVersion") != CONTRACT_SCHEMA or slot_contract.get(
        "schemaVersion"
    ) != CONTRACT_SCHEMA:
        block("UNSUPPORTED_CONTRACT_SCHEMA", "both endpoints must be v1 contracts")
    if module_contract.get("side") != "moving_module" or slot_contract.get(
        "side"
    ) != "base_slot":
        block("INVALID_INTERFACE_SIDES", "expected moving_module -> base_slot")
    if module_contract.get("interfaceFamily") != slot_contract.get("interfaceFamily"):
        block("INTERFACE_FAMILY_MISMATCH", "interface families differ")
    if module_contract.get("recipeId") != slot_contract.get("recipeId"):
        block("MATE_RECIPE_MISMATCH", "interface mate recipes differ")
    role = module_contract.get("moduleRole")
    if role not in (slot_contract.get("acceptedModuleRoles") or []):
        block("MODULE_ROLE_NOT_ACCEPTED", f"slot does not accept role {role}")
    module_topology = module_contract.get("topologySignature")
    slot_topology = slot_contract.get("topologySignature")
    module_topology_key = tuple(module_topology or [])
    slot_topology_key = tuple(slot_topology or [])
    if module_topology_key != slot_topology_key or module_topology_key not in {
        tuple(REQUIRED_ROLES),
        tuple(SUPPORT_POSITION_ROLES),
        tuple(DISTANCE_WIDTH_ROLES),
        tuple(PARTIAL_WIDTH_ROLES),
        tuple(SCANNER_DISTANCE_SLOT_ROLES),
        tuple(SCANNER_PLANE_AXIS_ROLES),
        tuple(CCD_DUAL_SLOT_ROLES),
        tuple(FLEX_CALIBRATION_ROLES),
    }:
        block("DATUM_TOPOLOGY_MISMATCH", "module and slot datum topologies differ")

    module_geometry = module_contract.get("geometrySignature") or {}
    slot_geometry = slot_contract.get("geometrySignature") or {}
    spacing_difference: float | None = None
    if module_topology_key == tuple(REQUIRED_ROLES) and slot_topology_key == tuple(REQUIRED_ROLES):
        module_spacing = float(module_geometry.get("locatingAxisSpacingMeters") or 0.0)
        slot_spacing = float(slot_geometry.get("locatingAxisSpacingMeters") or 0.0)
        spacing_difference = abs(module_spacing - slot_spacing)
        if spacing_difference > spacing_tolerance_meters:
            block(
                "LOCATING_FEATURE_SPACING_MISMATCH",
                f"spacing differs by {spacing_difference:.9f} m",
            )
        if module_geometry.get("orientationConvention") != slot_geometry.get("orientationConvention"):
            block("ORIENTATION_CONVENTION_MISMATCH", "datum conventions differ")
        for owner, geometry in (("module", module_geometry), ("slot", slot_geometry)):
            if abs(float(geometry.get("axisParallelScore") or 0.0) - 1.0) > orientation_tolerance:
                block("AXIS_DIRECTION_MISMATCH", f"{owner} axes are not parallel")
            if abs(float(geometry.get("axisRelationToPrimary") or 0.0) - 1.0) > orientation_tolerance:
                block("SECONDARY_AXIS_ORIENTATION_MISMATCH", f"{owner} secondary axis differs")
    elif module_topology_key == tuple(SUPPORT_POSITION_ROLES) and slot_topology_key == tuple(SUPPORT_POSITION_ROLES):
        if module_geometry.get("datumOrientationConvention") != slot_geometry.get("datumOrientationConvention"):
            block("ORIENTATION_CONVENTION_MISMATCH", "datum conventions differ")
        for owner, geometry in (("module", module_geometry), ("slot", slot_geometry)):
            if abs(float(geometry.get("orthogonalDatumScore") or 0.0) - 1.0) > orientation_tolerance:
                block("DATUM_ORTHOGONALITY_MISMATCH", f"{owner} datums are not orthogonal")
        parameters = slot_geometry.get("positionParametersMeters") or {}
        if set(parameters) != {"longitudinal", "lateral", "supportGap"}:
            block("POSITION_PARAMETERS_MISSING", "slot must define all position parameters")
        overrides = slot_geometry.get("positionParametersByModuleDefinitionId") or {}
        if overrides and module_contract.get("moduleDefinitionId") not in overrides:
            block(
                "MODULE_POSITION_PRESET_MISSING",
                "slot has no calibrated position parameters for this module",
            )
    elif module_topology_key in {tuple(DISTANCE_WIDTH_ROLES), tuple(PARTIAL_WIDTH_ROLES)} and module_topology_key == slot_topology_key:
        if module_geometry.get("datumOrientationConvention") != slot_geometry.get("datumOrientationConvention"):
            block("ORIENTATION_CONVENTION_MISMATCH", "datum conventions differ")
        for owner, geometry in (("module", module_geometry), ("slot", slot_geometry)):
            if abs(float(geometry.get("orientationScore") or 0.0) - 1.0) > orientation_tolerance:
                block("DATUM_ORIENTATION_MISMATCH", f"{owner} datum orientation is invalid")
        if module_topology_key == tuple(DISTANCE_WIDTH_ROLES):
            if module_geometry.get("interfaceVariantKey") != slot_geometry.get("interfaceVariantKey"):
                block("INTERFACE_VARIANT_MISMATCH", "width-interface variants differ")
            offset = slot_geometry.get("longitudinalOffsetMeters")
            if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(float(offset)) or float(offset) < 0:
                block("LONGITUDINAL_OFFSET_MISSING", "slot must define a finite non-negative offset")
    elif module_topology_key in {
        tuple(SCANNER_DISTANCE_SLOT_ROLES),
        tuple(SCANNER_PLANE_AXIS_ROLES),
        tuple(CCD_DUAL_SLOT_ROLES),
    } and module_topology_key == slot_topology_key:
        if module_geometry.get("datumOrientationConvention") != slot_geometry.get("datumOrientationConvention"):
            block("ORIENTATION_CONVENTION_MISMATCH", "scanner datum conventions differ")
        for owner, geometry in (("module", module_geometry), ("slot", slot_geometry)):
            if abs(float(geometry.get("orientationScore") or 0.0) - 1.0) > orientation_tolerance:
                block("DATUM_ORIENTATION_MISMATCH", f"{owner} datum orientation is invalid")
        if module_geometry.get("interfaceVariantKey") != slot_geometry.get("interfaceVariantKey"):
            block("INTERFACE_VARIANT_MISMATCH", "scanner mechanical variants differ")
        if module_topology_key == tuple(SCANNER_DISTANCE_SLOT_ROLES):
            parameters = slot_geometry.get("recipeParameters") or {}
            value = parameters.get("longitudinalOffsetMeters")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                block("LONGITUDINAL_OFFSET_MISSING", "scanner slot must define the longitudinal offset")
        if module_topology_key == tuple(CCD_DUAL_SLOT_ROLES):
            parameters = slot_geometry.get("recipeParameters") or {}
            if not all(
                isinstance(parameters.get(key), dict)
                and parameters[key].get("SlotConstraint") is not None
                for key in ("slotAAdvancedOptions", "slotBAdvancedOptions")
            ):
                block("SLOT_PARAMETERS_MISSING", "CCD slot must preserve both advanced-option bundles")
    elif module_topology_key == tuple(FLEX_CALIBRATION_ROLES) and slot_topology_key == tuple(FLEX_CALIBRATION_ROLES):
        if module_geometry.get("datumOrientationConvention") != slot_geometry.get("datumOrientationConvention"):
            block("ORIENTATION_CONVENTION_MISMATCH", "calibration datum conventions differ")
        if module_geometry.get("interfaceVariantKey") != slot_geometry.get("interfaceVariantKey"):
            block("INTERFACE_VARIANT_MISMATCH", "calibration mechanical variants differ")
        for owner, geometry in (("module", module_geometry), ("slot", slot_geometry)):
            if abs(float(geometry.get("orientationScore") or 0.0) - 1.0) > orientation_tolerance:
                block("DATUM_ORIENTATION_MISMATCH", f"{owner} datum orientation is invalid")
        offset = slot_geometry.get("longitudinalOffsetMeters")
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(float(offset)) or float(offset) < 0:
            block("LONGITUDINAL_OFFSET_MISSING", "calibration slot must define the longitudinal offset")
    for owner, contract in (("module", module_contract), ("slot", slot_contract)):
        closure = contract.get("constraintContract") or {}
        if closure.get("fullyLocatesRigidModule") is not True or int(
            closure.get("expectedResidualDof", -1)
        ) != 0:
            block("INCOMPLETE_CONSTRAINT_CONTRACT", f"{owner} port does not close rigid pose")
        evidence = contract.get("releaseEvidence") or {}
        if evidence.get("nonPrototypeCadValidated") is not True:
            block("PORT_EVIDENCE_NOT_RELEASED", f"{owner} port is not released")

    compatible = not blockers
    requires_explicit_pair_release = bool(
        (module_contract.get("mechanicalBoundary") or {}).get(
            "requiresExplicitPairRelease"
        )
        or (slot_contract.get("mechanicalBoundary") or {}).get(
            "requiresExplicitPairRelease"
        )
    )
    same_release = (
        not requires_explicit_pair_release
        and not (module_contract.get("releaseEvidence") or {}).get("geometryProvenanceOnly", False)
        and not (slot_contract.get("releaseEvidence") or {}).get("geometryProvenanceOnly", False)
        and
        (module_contract.get("releaseEvidence") or {}).get("releaseId")
        == (slot_contract.get("releaseEvidence") or {}).get("releaseId")
    )
    release_resolution = (pair_release_evidence or {}).get("catalogResolution") or {}
    current_position_parameters = (
        (slot_geometry.get("positionParametersByModuleDefinitionId") or {}).get(
            module_contract.get("moduleDefinitionId")
        )
        or slot_geometry.get("positionParametersMeters")
        or {}
    )
    current_distance_flips = (
        (slot_geometry.get("distanceFlipDimensionsByModuleDefinitionId") or {}).get(
            module_contract.get("moduleDefinitionId")
        )
        or slot_geometry.get("distanceFlipDimensions")
        or {"longitudinal": False, "lateral": False, "supportGap": False}
    )
    resolved_support_position_release = bool(
        module_topology_key == tuple(SUPPORT_POSITION_ROLES)
        and pair_release_evidence
        and pair_release_evidence.get("moduleContractId")
        == module_contract.get("contractId")
        and release_resolution.get("currentCatalogBindingsMatch") is True
        and release_resolution.get("positionParametersMeters")
        == current_position_parameters
        and release_resolution.get("distanceFlipDimensions")
        == current_distance_flips
    )
    explicit_pair_release = bool(
        pair_release_evidence
        and pair_release_evidence.get("nonPrototypeCadValidated") is True
        and pair_release_evidence.get("releaseId")
        and pair_release_evidence.get("releaseDigest")
        and pair_release_evidence.get("moduleDefinitionId")
        == module_contract.get("moduleDefinitionId")
        and pair_release_evidence.get("slotDefinitionId")
        == slot_contract.get("moduleDefinitionId")
        and (
            not requires_explicit_pair_release
            or (
                (
                    pair_release_evidence.get("moduleContractId")
                    == module_contract.get("contractId")
                    and pair_release_evidence.get("slotContractId")
                    == slot_contract.get("contractId")
                )
                or resolved_support_position_release
            )
        )
    )
    reusable_release = compatible and (same_release or explicit_pair_release)
    core = {
        "schemaVersion": MATCH_SCHEMA,
        "moduleContractId": module_contract.get("contractId"),
        "slotContractId": slot_contract.get("contractId"),
        "moduleDefinitionId": module_contract.get("moduleDefinitionId"),
        "slotDefinitionId": slot_contract.get("moduleDefinitionId"),
        "moduleProjectId": module_contract.get("projectId"),
        "slotProjectId": slot_contract.get("projectId"),
        "projectIdentityUsedForCompatibility": False,
        "interfaceFamily": module_contract.get("interfaceFamily"),
        "checks": {
            "topologyMatches": not any(row["code"] == "DATUM_TOPOLOGY_MISMATCH" for row in blockers),
            "spacingDifferenceMeters": spacing_difference,
            "spacingToleranceMeters": spacing_tolerance_meters,
            "spacingMatches": spacing_difference is None or spacing_difference <= spacing_tolerance_meters,
            "orientationMatches": not any("ORIENTATION" in row["code"] or "DIRECTION" in row["code"] for row in blockers),
            "constraintContractComplete": not any(row["code"] == "INCOMPLETE_CONSTRAINT_CONTRACT" for row in blockers),
        },
        "compatible": compatible,
        "mateInstantiationAllowed": compatible,
        "requiresNewPairCadValidation": compatible and not reusable_release,
        "existingPairReleaseReusable": reusable_release,
        "pairReleaseEvidence": copy.deepcopy(pair_release_evidence),
        "directMechanicalCompatibilityClaimAllowed": False,
        "blockers": blockers,
        "status": (
            "released_pair_contract_match"
            if reusable_release
            else "compatible_contract_pending_pair_cad"
            if compatible
            else "incompatible"
        ),
        "boundary": (
            "A contract match may instantiate semantic mates. A new module/slot pair "
            "still needs non-prototype CAD validation and release; fastener fit and "
            "collision are outside this decision."
        ),
    }
    core["matchId"] = "interface-match/" + _digest(core)[:16]
    return core


def instantiate_connection_template(
    match: dict[str, Any],
    module_contract: dict[str, Any],
    slot_contract: dict[str, Any],
) -> dict[str, Any]:
    """Instantiate the generic recipe only after a compatible contract match."""

    if match.get("schemaVersion") != MATCH_SCHEMA or match.get(
        "mateInstantiationAllowed"
    ) is not True:
        raise MechanicalInterfaceContractError(
            "incompatible contracts cannot instantiate a mate template"
        )
    if match.get("moduleContractId") != module_contract.get("contractId") or match.get(
        "slotContractId"
    ) != slot_contract.get("contractId"):
        raise MechanicalInterfaceContractError("match is not bound to these contracts")
    prefix = "MCP_IFACE_" + _digest(
        [module_contract["contractId"], slot_contract["contractId"]]
    )[:8].upper()
    recipe_id = module_contract["recipeId"]
    if recipe_id == SUPPORT_POSITION_RECIPE_ID:
        geometry = slot_contract.get("geometrySignature") or {}
        overrides = geometry.get("positionParametersByModuleDefinitionId") or {}
        parameters = overrides.get(
            module_contract.get("moduleDefinitionId"),
            geometry.get("positionParametersMeters") or {},
        )
        flip_overrides = geometry.get(
            "distanceFlipDimensionsByModuleDefinitionId"
        ) or {}
        distance_flips = flip_overrides.get(
            module_contract.get("moduleDefinitionId"),
            geometry.get("distanceFlipDimensions")
            or {"longitudinal": False, "lateral": False, "supportGap": False},
        )
        mate_steps = [
            {
                "mateName": f"{prefix}_LONGITUDINAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "distanceMeters": parameters["longitudinal"],
                "distanceFlipDimension": distance_flips["longitudinal"],
                "endpointRoleA": "longitudinal_datum",
                "endpointRoleB": "longitudinal_datum",
            },
            {
                "mateName": f"{prefix}_LATERAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "distanceMeters": parameters["lateral"],
                "distanceFlipDimension": distance_flips["lateral"],
                "endpointRoleA": "lateral_datum",
                "endpointRoleB": "lateral_datum",
            },
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0 if parameters["supportGap"] == 0 else 5,
                "mateTypeName": "swMateCOINCIDENT" if parameters["supportGap"] == 0 else "swMateDISTANCE",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                **({} if parameters["supportGap"] == 0 else {"distanceMeters": parameters["supportGap"]}),
                **(
                    {}
                    if parameters["supportGap"] == 0
                    else {"distanceFlipDimension": distance_flips["supportGap"]}
                ),
                "endpointRoleA": "support_datum",
                "endpointRoleB": "support_datum",
            },
        ]
    elif recipe_id in {DISTANCE_WIDTH_RECIPE_ID, CALIBRATION_DISTANCE_WIDTH_RECIPE_ID}:
        parameters = slot_contract.get("geometrySignature") or {}
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_LONGITUDINAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "distanceMeters": parameters["longitudinalOffsetMeters"],
                "endpointRoleA": "longitudinal_datum",
                "endpointRoleB": "longitudinal_datum",
            },
            {
                "mateName": f"{prefix}_WIDTH",
                "mateType": 11,
                "mateTypeName": "swMateWIDTH",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoles": [
                    {"side": "B", "role": "width_datum_a"},
                    {"side": "B", "role": "width_datum_b"},
                    {"side": "A", "role": "width_datum_a"},
                    {"side": "A", "role": "width_datum_b"},
                ],
            },
        ]
    elif recipe_id == PARTIAL_WIDTH_RECIPE_ID:
        raise MechanicalInterfaceContractError(
            "partial plane/width contract cannot instantiate before longitudinal datum is supplied"
        )
    elif recipe_id == SCANNER_DISTANCE_SLOT_RECIPE_ID:
        parameters = (slot_contract.get("geometrySignature") or {}).get("recipeParameters") or {}
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_LONGITUDINAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "distanceMeters": parameters["longitudinalOffsetMeters"],
                "endpointRoleA": "longitudinal_datum",
                "endpointRoleB": "longitudinal_datum",
            },
            {
                "mateName": f"{prefix}_SLOT",
                "mateType": 21,
                "mateTypeName": "swMateSLOT",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "slot_locator",
                "endpointRoleB": "slot_locator",
                "advancedOptions": {
                    "SlotConstraint": 0,
                    "SlotDistance": 0,
                    "SlotPercent": 0,
                    "SlotFlipDirection": False,
                },
            },
        ]
    elif recipe_id in {SCANNER_PLANE_AXIS_RECIPE_ID, CCD_PLANE_AXIS_RECIPE_ID}:
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_ORIENTATION",
                "mateType": 3,
                "mateTypeName": "swMatePARALLEL",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "orientation_datum",
                "endpointRoleB": "orientation_datum",
            },
            {
                "mateName": f"{prefix}_AXIS",
                "mateType": 1,
                "mateTypeName": "swMateCONCENTRIC",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "locating_axis",
                "endpointRoleB": "locating_axis",
            },
        ]
    elif recipe_id == CCD_DUAL_SLOT_RECIPE_ID:
        parameters = (slot_contract.get("geometrySignature") or {}).get("recipeParameters") or {}
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_SLOT_A",
                "mateType": 21,
                "mateTypeName": "swMateSLOT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "slot_locator_a",
                "endpointRoleB": "slot_locator_a",
                "advancedOptions": copy.deepcopy(parameters["slotAAdvancedOptions"]),
            },
            {
                "mateName": f"{prefix}_SLOT_B",
                "mateType": 21,
                "mateTypeName": "swMateSLOT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "slot_locator_b",
                "endpointRoleB": "slot_locator_b",
                "advancedOptions": copy.deepcopy(parameters["slotBAdvancedOptions"]),
            },
        ]
    elif recipe_id in {
        FLEX_CALIBRATION_RECIPE_ID,
        CLEANING_SLOT_RECIPE_ID,
    }:
        parameters = slot_contract.get("geometrySignature") or {}
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_ORIENTATION",
                "mateType": 3,
                "mateTypeName": "swMatePARALLEL",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "orientation_datum",
                "endpointRoleB": "orientation_datum",
            },
            {
                "mateName": f"{prefix}_LONGITUDINAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "distanceMeters": parameters["longitudinalOffsetMeters"],
                "endpointRoleA": "longitudinal_datum",
                "endpointRoleB": "longitudinal_datum",
            },
            {
                "mateName": f"{prefix}_SLOT",
                "mateType": 21,
                "mateTypeName": "swMateSLOT",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "slot_locator",
                "endpointRoleB": "slot_locator",
                "advancedOptions": {
                    "SlotConstraint": 0,
                    "SlotDistance": 0,
                    "SlotPercent": 0,
                    "SlotFlipDirection": False,
                },
            },
        ]
    elif recipe_id == NATIVE_WASTECUP_RECIPE_ID:
        parameters = slot_contract.get("geometrySignature") or {}
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_ORIENTATION",
                "mateType": 3,
                "mateTypeName": "swMatePARALLEL",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "orientation_datum",
                "endpointRoleB": "orientation_datum",
            },
            {
                "mateName": f"{prefix}_SLOT",
                "mateType": 21,
                "mateTypeName": "swMateSLOT",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "slot_locator",
                "endpointRoleB": "slot_locator",
                "advancedOptions": {
                    "SlotConstraint": 0,
                    "SlotDistance": 0,
                    "SlotPercent": 0,
                    "SlotFlipDirection": False,
                },
            },
            {
                "mateName": f"{prefix}_LONGITUDINAL",
                "mateType": 5,
                "mateTypeName": "swMateDISTANCE",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "distanceMeters": parameters["longitudinalOffsetMeters"],
                "endpointRoleA": "longitudinal_datum",
                "endpointRoleB": "longitudinal_datum",
            },
        ]
    else:
        mate_steps = [
            {
                "mateName": f"{prefix}_SUPPORT",
                "mateType": 0,
                "mateTypeName": "swMateCOINCIDENT",
                "alignment": 1,
                "alignmentName": "swMateAlignANTI_ALIGNED",
                "endpointRoleA": "support_plane",
                "endpointRoleB": "support_plane",
            },
            {
                "mateName": f"{prefix}_PRIMARY",
                "mateType": 1,
                "mateTypeName": "swMateCONCENTRIC",
                # The support-plane mate already determines which side of the
                # mounting plane the module occupies.  Published BD00->AA00
                # and AH00->A600 CAD evidence both use aligned concentric
                # mates; forcing anti-aligned here creates an inconsistent
                # pair-specific solve even though the 50 mm hole patterns are
                # congruent.
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "primary_locating_hole",
                "endpointRoleB": "primary_locating_hole",
            },
            {
                "mateName": f"{prefix}_SECONDARY",
                "mateType": 1,
                "mateTypeName": "swMateCONCENTRIC",
                "alignment": 0,
                "alignmentName": "swMateAlignALIGNED",
                "endpointRoleA": "secondary_locating_hole",
                "endpointRoleB": "secondary_locating_hole",
            },
        ]
    core = {
        "schemaVersion": "instantiated-interface-template/v1",
        "recipeId": module_contract["recipeId"],
        "interfaceFamily": module_contract["interfaceFamily"],
        "modulePortId": module_contract["sourcePortId"],
        "slotPortId": slot_contract["sourcePortId"],
        "moduleContractId": module_contract["contractId"],
        "slotContractId": slot_contract["contractId"],
        "matchId": match["matchId"],
        "status": (
            "released-native-evidence-reuse"
            if match["existingPairReleaseReusable"]
            else "candidate-cross-pair-cad-validation-required"
        ),
        "executionAuthorizationRequired": True,
        "constraintEffect": {
            "fullyLocatesAddedComponent": True,
            "expectedResidualDof": 0,
        },
        "mateSteps": mate_steps,
        "boundary": match["boundary"],
    }
    core["templateId"] = "instantiated-template/" + _digest(core)[:16]
    return core


def plan_module_slot_connection(
    module_contract: dict[str, Any],
    slot_contracts: list[dict[str, Any]],
    *,
    selected_slot_contract_id: str | None = None,
    spacing_tolerance_meters: float = 0.0002,
    pair_release_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Find compatible base slots and instantiate a recipe after unambiguous selection.

    Multiple compatible slots are deliberately returned for human or upstream
    process selection.  The planner never picks the first item silently.
    """

    if not slot_contracts:
        raise MechanicalInterfaceContractError("at least one base slot is required")
    pair_index = {
        (row.get("moduleDefinitionId"), row.get("slotDefinitionId")): row
        for row in pair_release_evidence or []
    }
    rows = []
    for slot in slot_contracts:
        rows.append(
            match_interface_contracts(
                module_contract,
                slot,
                spacing_tolerance_meters=spacing_tolerance_meters,
                pair_release_evidence=pair_index.get(
                    (
                        module_contract.get("moduleDefinitionId"),
                        slot.get("moduleDefinitionId"),
                    )
                ),
            )
        )
    rows.sort(key=lambda row: (row["slotDefinitionId"], row["slotContractId"]))
    compatible = [row for row in rows if row["compatible"]]
    selected: dict[str, Any] | None = None
    status: str
    if selected_slot_contract_id:
        requested = [
            row for row in rows if row["slotContractId"] == selected_slot_contract_id
        ]
        if len(requested) != 1:
            raise MechanicalInterfaceContractError("selected base slot is not available")
        if requested[0]["compatible"] is not True:
            status = "selected_slot_incompatible"
        else:
            selected, status = requested[0], "selected_explicit_compatible_slot"
    elif len(compatible) == 1:
        selected, status = compatible[0], "selected_unique_compatible_slot"
    elif compatible:
        status = "needs_slot_confirmation"
    else:
        status = "no_compatible_slot"

    by_id = {row.get("contractId"): row for row in slot_contracts}
    template = (
        instantiate_connection_template(
            selected, module_contract, by_id[selected["slotContractId"]]
        )
        if selected
        else None
    )
    core = {
        "schemaVersion": "module-slot-connection-plan/v1",
        "moduleContractId": module_contract.get("contractId"),
        "candidateCount": len(rows),
        "compatibleCandidateCount": len(compatible),
        "status": status,
        "readyForTemplateCompilation": selected is not None,
        "selectedMatch": selected,
        "instantiatedTemplate": template,
        "candidates": rows,
        "decisionPolicy": (
            "select the sole compatible slot; require explicit selection when multiple "
            "compatible slots remain; fail closed when none match"
        ),
    }
    core["planDigest"] = _digest(core)
    return core


def validate_contract_catalog(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") not in {
        CATALOG_SCHEMA,
        TRANSPORT_CATALOG_SCHEMA,
        CALIBRATION_CATALOG_SCHEMA,
        SCANNER_CATALOG_SCHEMA,
        WASTECUP_CATALOG_SCHEMA,
        CONTEXTUAL_TRANSPORT_CATALOG_SCHEMA,
        CONTEXTUAL_SCANNER_CATALOG_SCHEMA,
        CCD_CATALOG_SCHEMA,
        NATIVE_WASTECUP_CATALOG_SCHEMA,
        DATUM_PLACEMENT_CATALOG_SCHEMA,
    }:
        raise MechanicalInterfaceContractError("unsupported contract catalog")
    digest = report.get("catalogDigest")
    core = {key: value for key, value in report.items() if key != "catalogDigest"}
    if digest != _digest(core):
        raise MechanicalInterfaceContractError("contract catalog digest mismatch")
    contracts = report.get("contracts") or []
    matches = report.get("compatibilityMatrix") or []
    modules = [row for row in contracts if row.get("side") == "moving_module"]
    slots = [row for row in contracts if row.get("side") == "base_slot"]
    if not modules or not slots or len(matches) != len(modules) * len(slots):
        raise MechanicalInterfaceContractError("contract matrix cardinality mismatch")
    summary = report.get("summary") or {}
    if int(summary.get("compatiblePairCount", -1)) != sum(
        row.get("compatible") is True for row in matches
    ):
        raise MechanicalInterfaceContractError("compatible pair count changed")


def load_cleaning_weighing_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/cleaning-weighing-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    return report


def load_transport_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/transport-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != TRANSPORT_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a transport contract catalog")
    return report


def load_calibration_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/calibration-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != CALIBRATION_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a calibration contract catalog")
    return report


def load_scanner_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/scanner-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != SCANNER_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a scanner contract catalog")
    return report


def load_wastecup_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/wastecup-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != WASTECUP_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a wastecup contract catalog")
    return report


def load_contextual_transport_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/contextual-transport-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != CONTEXTUAL_TRANSPORT_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a contextual transport contract catalog")
    return report


def load_contextual_scanner_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/contextual-scanner-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != CONTEXTUAL_SCANNER_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a contextual scanner contract catalog")
    return report


def load_ccd_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/ccd-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != CCD_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a CCD contract catalog")
    return report


def load_native_wastecup_contract_catalog(workspace: Path) -> dict[str, Any]:
    path = workspace / (
        "demo/cross_project_substitution/native-wastecup-interface-contract-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != NATIVE_WASTECUP_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("not a native wastecup contract catalog")
    return report


def load_parameterized_datum_placement_contract_catalog(
    workspace: Path,
) -> dict[str, Any]:
    """Load the non-fastening fallback used after native slot matching fails."""

    path = workspace / (
        "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "interface-contract-catalog.json"
    )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_contract_catalog(report)
    if report.get("schemaVersion") != DATUM_PLACEMENT_CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError(
            "not a parameterized datum-placement contract catalog"
        )
    return report


def plan_from_contract_catalog(
    report: dict[str, Any],
    module_definition_id: str,
    *,
    selected_slot_contract_id: str | None = None,
) -> dict[str, Any]:
    """Plan one module against every registered base slot in a catalog."""

    validate_contract_catalog(report)
    modules = [
        row
        for row in report["contracts"]
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == module_definition_id
    ]
    if len(modules) != 1:
        raise MechanicalInterfaceContractError(
            f"cannot uniquely resolve module contract: {module_definition_id}"
        )
    slots = [row for row in report["contracts"] if row.get("side") == "base_slot"]
    return plan_module_slot_connection(
        modules[0],
        slots,
        selected_slot_contract_id=selected_slot_contract_id,
        pair_release_evidence=report.get("releasedPairEvidence") or [],
    )
