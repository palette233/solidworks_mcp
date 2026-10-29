"""Review and compile G000's flexible four-relation installation on new bases.

The released Project05 G000/A000 interface is not a generic three-plane pose.
It preserves the exact external bundle used by the source prototype:

* one support-plane coincidence;
* one orientation-plane parallel relation;
* one longitudinal distance relation; and
* one Free slot relation between the G000 slot face and a base cylinder axis.

This module inventories stable base-axis candidates and can rank them against
the released G000/A000 semantic station.  Ranking is review evidence only: an
exact axis and longitudinal offset must still be explicitly confirmed before a
non-prototype CAD validation package can be compiled.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

from .hybrid_plane_axis_slot_selection import (
    BASE_SPECS as FRAME_BASE_SPECS,
    _axis_candidates,
    _digest,
    _endpoint_index,
    _plane_frame,
    _read,
    _surface_type,
    _unit,
    _dot,
    _subtract,
    _vector,
)
from .mechanical_interface_contracts import (
    FLEX_CALIBRATION_FAMILY,
    FLEX_CALIBRATION_RECIPE_ID,
    FLEX_CALIBRATION_ROLES,
    MechanicalInterfaceContractError,
    build_flexible_calibration_contract,
    instantiate_connection_template,
    match_interface_contracts,
)


CATALOG_SCHEMA = "flexible-calibration-slot-candidate-catalog/v1"
SELECTION_SCHEMA = "flexible-calibration-slot-selection/v1"
MODULE_DEFINITION_ID = "project05::G000"
MODULE_TOKEN = "G000"
MODULE_ROLE = "Calibration"
MODULE_RELEASE = "relation-v58-project05-g000-static-four-relation-driving-20261014"
MODULE_CATALOG = (
    "demo/global_assembly_catalog/coverage-v2/"
    "g000-four-relation-candidate-v1/face_endpoint_catalog.json"
)
MODULE_ENDPOINTS = {
    "support_plane": "face:g000:92d258df83131ec3",
    "orientation_datum": "face:g000:1b805ca7ddfe8670",
    # The source distance relation deliberately reuses the same side plane.
    "longitudinal_datum": "face:g000:1b805ca7ddfe8670",
    "slot_locator": "face:g000:c65b7646a96a5e0c",
}
GENERIC_VARIANT = "g000_reviewed_flexible_slot_datum/v1"
REFERENCE_BASE_LOCATOR_RADIUS_METERS = 0.0025
REFERENCE_BASE_FRAME_CATALOG = (
    "demo/semantic_ports/project05_p000_locator_discovery_v1/"
    "a000-p000-support-leaf-face-catalog.json"
)
REFERENCE_BASE_FRAME_ENDPOINTS = {
    "longitudinal": "face:fl9c254098a000.001-1:288089408c864285",
    "lateral": "face:fl9c254098a000.001-1:d38d71808a7006af",
}


BASE_SPECS = {
    definition_id: copy.deepcopy(spec)
    for definition_id, spec in FRAME_BASE_SPECS.items()
    if definition_id in {
        "project01::JJ00",
        "project02::A600",
        "project03::AA00",
    }
}
BASE_SPECS["project05::A000"] = {
    "token": "A000",
    "catalog": MODULE_CATALOG,
    "support": "face:a000:6fa65c2382da2d47",
    "orientation": "face:a000:dd9b3d0af3790a28",
    "longitudinal": None,
    "release": MODULE_RELEASE,
    "releasedSlotLocator": "face:a000:aabecbe1ad0e7c8b",
    "releasedLongitudinalOffsetMeters": 0.482,
}


def _finite_nonnegative(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise MechanicalInterfaceContractError(
            f"{label} must be finite and non-negative"
        )
    return float(value)


def _validate_module_bundle(index: dict[str, dict[str, Any]]) -> None:
    support = index.get(MODULE_ENDPOINTS["support_plane"])
    orientation = index.get(MODULE_ENDPOINTS["orientation_datum"])
    locator = index.get(MODULE_ENDPOINTS["slot_locator"])
    if not support or _surface_type(support) != "Plane":
        raise MechanicalInterfaceContractError("G000 support plane is missing")
    if not orientation or _surface_type(orientation) != "Plane":
        raise MechanicalInterfaceContractError("G000 orientation plane is missing")
    if not locator or _surface_type(locator) != "Cylinder":
        raise MechanicalInterfaceContractError("G000 slot cylinder face is missing")
    support_normal = _unit(
        (support.get("Endpoint") or {}).get("FaceNormalLocal"),
        "G000 support normal",
    )
    orientation_normal = _unit(
        (orientation.get("Endpoint") or {}).get("FaceNormalLocal"),
        "G000 orientation normal",
    )
    locator_axis = _unit(
        (locator.get("Endpoint") or {}).get("CylinderAxisLocal"),
        "G000 slot axis",
    )
    if abs(_dot(support_normal, orientation_normal)) > 1e-5:
        raise MechanicalInterfaceContractError(
            "G000 support and orientation planes are not orthogonal"
        )
    if (
        abs(_dot(locator_axis, support_normal)) < 1.0 - 1e-5
        or abs(_dot(locator_axis, orientation_normal)) > 1e-5
    ):
        raise MechanicalInterfaceContractError(
            "G000 slot axis is inconsistent with its support/orientation frame"
        )


def build_g000_flexible_slot_candidate_catalog(workspace: Path) -> dict[str, Any]:
    """Return released A000 evidence plus review-only candidates on three bases."""

    workspace = workspace.resolve()
    module_catalog = _read(workspace / MODULE_CATALOG)
    _validate_module_bundle(_endpoint_index(module_catalog))
    base_slots: list[dict[str, Any]] = []
    for definition_id, spec in BASE_SPECS.items():
        catalog = _read(workspace / str(spec["catalog"]))
        index = _endpoint_index(catalog)
        coordinate_space = str(spec.get("coordinateSpace") or "local")
        frame = _plane_frame(
            index,
            support_id=str(spec["support"]),
            orientation_id=str(spec["orientation"]),
            longitudinal_id=(
                str(spec["longitudinal"]) if spec.get("longitudinal") else None
            ),
            coordinate_space=coordinate_space,
        )
        released_locator = spec.get("releasedSlotLocator")
        if released_locator:
            locator = index.get(str(released_locator))
            if not locator or _surface_type(locator) != "Cylinder":
                raise MechanicalInterfaceContractError(
                    "released G000/A000 slot locator is missing"
                )
            base_slots.append(
                {
                    "slotDefinitionId": definition_id,
                    "baseToken": spec["token"],
                    "state": "released_native_pair",
                    "sourceCatalogPath": spec["catalog"],
                    "supportEndpointId": spec["support"],
                    "orientationEndpointId": spec["orientation"],
                    "longitudinalEndpointId": spec["orientation"],
                    "releasedSlotLocatorEndpointId": released_locator,
                    "releasedLongitudinalOffsetMeters": spec[
                        "releasedLongitudinalOffsetMeters"
                    ],
                    "candidateAxisLineCount": 1,
                    "axisCandidates": [],
                    "requiresExplicitFlexibleSlotSelection": False,
                    "readyForReleasedCadExecution": True,
                }
            )
            continue
        axis_catalog_path = str(spec.get("axisCatalog") or spec["catalog"])
        axis_catalog = (
            catalog
            if axis_catalog_path == str(spec["catalog"])
            else _read(workspace / axis_catalog_path)
        )
        candidates = _axis_candidates(
            _endpoint_index(axis_catalog),
            frame,
            coordinate_space=coordinate_space,
            reference_radius_meters=REFERENCE_BASE_LOCATOR_RADIUS_METERS,
        )
        base_slots.append(
            {
                "slotDefinitionId": definition_id,
                "baseToken": spec["token"],
                "state": (
                    "explicit_flexible_slot_selection_required"
                    if candidates
                    else "flexible_slot_axis_not_found_in_authoritative_catalog"
                ),
                "sourceCatalogPath": spec["catalog"],
                "axisCandidateCatalogPath": axis_catalog_path,
                "candidateCoordinateSpace": coordinate_space,
                "supportEndpointId": spec["support"],
                "orientationEndpointId": spec["orientation"],
                # The distance relation uses the orientation plane, exactly as
                # in the released G000/A000 source bundle.
                "longitudinalEndpointId": spec["orientation"],
                "candidateAxisLineCount": len(candidates),
                "axisCandidates": candidates,
                "requiresExplicitFlexibleSlotSelection": bool(candidates),
                "readyForReleasedCadExecution": False,
                "selectionBoundary": (
                    "A stable cylinder is only a slot-locator candidate. Confirm its "
                    "purpose, side, exact endpoint and the longitudinal offset before CAD."
                ),
            }
        )
    core = {
        "schemaVersion": CATALOG_SCHEMA,
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "moduleToken": MODULE_TOKEN,
        "moduleRole": MODULE_ROLE,
        "interfaceFamily": FLEX_CALIBRATION_FAMILY,
        "recipeId": FLEX_CALIBRATION_RECIPE_ID,
        "moduleEndpointCatalogPath": MODULE_CATALOG,
        "moduleEndpointBindings": copy.deepcopy(MODULE_ENDPOINTS),
        "baseSlots": base_slots,
        "summary": {
            "baseSlotCount": len(base_slots),
            "releasedNativePairCount": sum(
                row["state"] == "released_native_pair" for row in base_slots
            ),
            "explicitFlexibleSlotSelectionRequiredCount": sum(
                row["state"] == "explicit_flexible_slot_selection_required"
                for row in base_slots
            ),
            "axisNotFoundCount": sum(
                row["state"]
                == "flexible_slot_axis_not_found_in_authoritative_catalog"
                for row in base_slots
            ),
            "candidateAxisLineCount": sum(
                int(row["candidateAxisLineCount"])
                for row in base_slots
                if row["state"] == "explicit_flexible_slot_selection_required"
            ),
        },
        "claimBoundary": (
            "This catalog preserves G000's four-relation flexible installation "
            "topology. Candidate cylinders and offsets are not mechanical approval, "
            "pair release, fastening evidence, collision evidence or production evidence."
        ),
    }
    return {**core, "catalogDigest": _digest(core)}


def build_g000_native_station_reference(workspace: Path) -> dict[str, Any]:
    """Measure the released A000 slot axis in the common semantic base frame.

    The prototype coordinates are recommendation evidence only.  They are not
    written into a contract and cannot authorize CAD execution.
    """

    workspace = workspace.resolve()
    native_catalog = _read(workspace / MODULE_CATALOG)
    frame_catalog = _read(workspace / REFERENCE_BASE_FRAME_CATALOG)
    if str(native_catalog.get("SourceAssemblyPath") or "").casefold() != str(
        frame_catalog.get("SourceAssemblyPath") or ""
    ).casefold():
        raise MechanicalInterfaceContractError(
            "G000 native locator and semantic base frame do not share one source assembly"
        )
    native_index = _endpoint_index(native_catalog)
    frame_index = _endpoint_index(frame_catalog)
    locator_id = str(BASE_SPECS["project05::A000"]["releasedSlotLocator"])
    locator = native_index.get(locator_id)
    if not locator or _surface_type(locator) != "Cylinder":
        raise MechanicalInterfaceContractError("G000 native A000 locator is missing")
    origin = _vector(
        (locator.get("Endpoint") or {}).get("CylinderOriginWorld"),
        "G000 native locator origin",
    )

    def coordinate(role: str) -> float:
        endpoint_id = REFERENCE_BASE_FRAME_ENDPOINTS[role]
        plane = frame_index.get(endpoint_id)
        if not plane or _surface_type(plane) != "Plane":
            raise MechanicalInterfaceContractError(
                f"G000 native semantic {role} plane is missing"
            )
        endpoint = plane.get("Endpoint") or {}
        center = _vector(endpoint.get("FaceCenterWorld"), f"{role} plane center")
        normal = _unit(endpoint.get("FaceNormalWorld"), f"{role} plane normal")
        return _dot(_subtract(origin, center), normal)

    core = {
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "baseDefinitionId": "project05::A000",
        "selectedAxisEndpointId": locator_id,
        "semanticAxisPositionMeters": {
            "longitudinal": round(coordinate("longitudinal"), 12),
            "lateral": round(coordinate("lateral"), 12),
        },
        "longitudinalOffsetMeters": float(
            BASE_SPECS["project05::A000"]["releasedLongitudinalOffsetMeters"]
        ),
        "nativeEndpointCatalogPath": MODULE_CATALOG,
        "baseFrameEndpointCatalogPath": REFERENCE_BASE_FRAME_CATALOG,
        "prototypePoseUsedForMeasurement": True,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
        "reviewOnly": True,
        "targetEnvelopeVerified": False,
    }
    return {**core, "referenceDigest": _digest(core)}


def rank_g000_flexible_slot_candidates(
    workspace: Path,
    catalog: dict[str, Any],
    slot_definition_id: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank target-base axes against the released G000/A000 semantic station."""

    if catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported flexible calibration candidate catalog"
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MechanicalInterfaceContractError("G000 ranking limit must be positive")
    slots = [
        row
        for row in catalog.get("baseSlots") or []
        if row.get("slotDefinitionId") == slot_definition_id
    ]
    if len(slots) != 1 or slots[0].get("state") != (
        "explicit_flexible_slot_selection_required"
    ):
        raise MechanicalInterfaceContractError(
            "G000 ranking requires one unresolved target-base slot"
        )
    reference = build_g000_native_station_reference(workspace)
    position = reference["semanticAxisPositionMeters"]
    ranked: list[dict[str, Any]] = []
    for candidate in slots[0].get("axisCandidates") or []:
        longitudinal_delta = float(candidate["longitudinalMeters"]) - float(
            position["longitudinal"]
        )
        lateral_delta = float(candidate["lateralMeters"]) - float(
            position["lateral"]
        )
        ranked.append(
            {
                **copy.deepcopy(candidate),
                "distanceFromNativeSemanticAxisMeters": math.sqrt(
                    longitudinal_delta * longitudinal_delta
                    + lateral_delta * lateral_delta
                ),
                "longitudinalDeltaMeters": longitudinal_delta,
                "lateralDeltaMeters": lateral_delta,
                "nativeStationReferenceDigest": reference["referenceDigest"],
            }
        )
    ranked.sort(
        key=lambda row: (
            float(row["distanceFromNativeSemanticAxisMeters"]),
            abs(float(row["cylinderRadiusMeters"]) - REFERENCE_BASE_LOCATOR_RADIUS_METERS),
            str(row["endpointId"]),
        )
    )
    return ranked[:limit]


def compile_g000_flexible_slot_selection(
    workspace: Path,
    *,
    slot_definition_id: str,
    selected_axis_endpoint_id: str,
    longitudinal_offset_meters: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Compile one explicitly reviewed axis/offset into a four-mate candidate."""

    if evidence.get("confirmed") is not True or not str(
        evidence.get("source") or ""
    ).strip():
        raise MechanicalInterfaceContractError(
            "flexible slot selection requires confirmed evidence with a source"
        )
    offset = _finite_nonnegative(
        longitudinal_offset_meters, "G000 longitudinal offset"
    )
    catalog = build_g000_flexible_slot_candidate_catalog(workspace)
    slots = [
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == slot_definition_id
    ]
    if (
        len(slots) != 1
        or slots[0]["state"] != "explicit_flexible_slot_selection_required"
    ):
        raise MechanicalInterfaceContractError(
            "G000 flexible slot candidate requires a reviewable unreleased base"
        )
    slot_row = slots[0]
    candidates = {
        str(row["endpointId"]): row for row in slot_row.get("axisCandidates") or []
    }
    if selected_axis_endpoint_id not in candidates:
        raise MechanicalInterfaceContractError(
            "selected G000 slot axis is not present in the requested base catalog"
        )
    module_release = _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / MODULE_RELEASE
        / "release-manifest.json"
    )
    base_spec = BASE_SPECS[slot_definition_id]
    base_release = _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / str(base_spec["release"])
        / "release-manifest.json"
    )
    module_port = {
        "portId": "G000.reviewed_flexible_slot_datum.v1",
        "moduleToken": MODULE_TOKEN,
        "endpointBindings": [
            {"role": role, "endpointId": endpoint_id}
            for role, endpoint_id in MODULE_ENDPOINTS.items()
        ],
    }
    slot_port = {
        "portId": f"{base_spec['token']}.reviewed_g000_flexible_slot.v1",
        "moduleToken": base_spec["token"],
        "endpointBindings": [
            {"role": "support_plane", "endpointId": base_spec["support"]},
            {
                "role": "orientation_datum",
                "endpointId": base_spec["orientation"],
            },
            {
                "role": "longitudinal_datum",
                "endpointId": base_spec["orientation"],
            },
            {"role": "slot_locator", "endpointId": selected_axis_endpoint_id},
        ],
    }
    module_contract = build_flexible_calibration_contract(
        port=module_port,
        release_manifest=module_release,
        side="moving_module",
        module_definition_id=MODULE_DEFINITION_ID,
        interface_variant_key=GENERIC_VARIANT,
        role_aliases={},
    )
    slot_contract = build_flexible_calibration_contract(
        port=slot_port,
        release_manifest=base_release,
        side="base_slot",
        module_definition_id=slot_definition_id,
        accepted_module_roles=[MODULE_ROLE],
        interface_variant_key=GENERIC_VARIANT,
        role_aliases={},
        longitudinal_offset_meters=offset,
    )
    for contract in (module_contract, slot_contract):
        contract["mechanicalBoundary"].update(
            {
                "requiresExplicitPairRelease": True,
                "placementMode": "reviewed_flexible_calibration_slot",
                "actualFasteningMethod": "not_verified",
                "locatorDiameterCompatibility": "not_evaluated",
                "productionReady": False,
            }
        )
        contract["contractId"] = "interface-contract/" + _digest(
            {key: value for key, value in contract.items() if key != "contractId"}
        )[:16]
    match = match_interface_contracts(module_contract, slot_contract)
    if match.get("compatible") is not True:
        raise MechanicalInterfaceContractError(
            "confirmed G000 flexible slot did not produce a compatible contract"
        )
    template = instantiate_connection_template(
        match, module_contract, slot_contract
    )
    core = {
        "schemaVersion": SELECTION_SCHEMA,
        "status": "ready_for_nonprototype_cad_validation",
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "slotDefinitionId": slot_definition_id,
        "selectedAxisEndpointId": selected_axis_endpoint_id,
        "longitudinalOffsetMeters": offset,
        "selectedAxisCandidate": copy.deepcopy(candidates[selected_axis_endpoint_id]),
        "selectionEvidence": copy.deepcopy(evidence),
        "moduleEndpointCatalogPath": MODULE_CATALOG,
        "slotEndpointCatalogPath": base_spec["catalog"],
        "slotFrameEndpointCatalogPath": base_spec["catalog"],
        "slotAxisEndpointCatalogPath": base_spec.get(
            "axisCatalog", base_spec["catalog"]
        ),
        "moduleContract": module_contract,
        "slotContract": slot_contract,
        "match": match,
        "instantiatedTemplate": template,
        "readyForReleasedCadExecution": False,
        "validationRequiredBeforeRelease": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "claimBoundary": (
            "The selected axis and distance authorize only a non-prototype CAD "
            "candidate. Dynamic states, fastening, diameter fit and collision are unverified."
        ),
    }
    return {**core, "selectionDigest": _digest(core)}


def compile_g000_flexible_slot_validation_package(
    workspace: Path,
    *,
    slot_definition_id: str,
    selected_axis_endpoint_id: str,
    longitudinal_offset_meters: float,
    evidence: dict[str, Any],
    initial_placement_variant: int = 1,
) -> dict[str, Any]:
    """Compile a reviewed G000 axis/offset into the common CAD graph format."""

    if (
        isinstance(initial_placement_variant, bool)
        or not isinstance(initial_placement_variant, int)
        or initial_placement_variant < 0
    ):
        raise MechanicalInterfaceContractError(
            "initial placement variant must be a non-negative integer"
        )
    selection = compile_g000_flexible_slot_selection(
        workspace,
        slot_definition_id=slot_definition_id,
        selected_axis_endpoint_id=selected_axis_endpoint_id,
        longitudinal_offset_meters=longitudinal_offset_meters,
        evidence=evidence,
    )
    from .parameterized_datum_placement import (  # local import avoids a cycle
        IDENTITY_TRANSFORM,
        VALIDATION_PACKAGE_SCHEMA,
        _base_wrapper_source,
        _mate_row,
        _module_record,
        _sha256_file,
    )

    workspace = workspace.resolve()
    module_contract = selection["moduleContract"]
    slot_contract = selection["slotContract"]
    template = selection["instantiatedTemplate"]
    module_catalog_path = workspace / str(selection["moduleEndpointCatalogPath"])
    slot_catalog_path = workspace / str(selection["slotEndpointCatalogPath"])
    slot_axis_catalog_path = workspace / str(
        selection["slotAxisEndpointCatalogPath"]
    )
    module_catalog = _read(module_catalog_path)
    slot_catalog = _read(slot_catalog_path)
    slot_axis_catalog = (
        slot_catalog
        if slot_axis_catalog_path == slot_catalog_path
        else _read(slot_axis_catalog_path)
    )

    def selected_rows(
        catalog_value: dict[str, Any], contract: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        index = _endpoint_index(catalog_value)
        selected: dict[str, dict[str, Any]] = {}
        for binding in contract.get("endpointBindings") or []:
            role = str(binding.get("role") or "")
            endpoint_id = str(binding.get("endpointId") or "")
            if role in selected or endpoint_id not in index:
                raise MechanicalInterfaceContractError(
                    f"flexible slot endpoint cannot be resolved: {role}/{endpoint_id}"
                )
            selected[role] = copy.deepcopy(index[endpoint_id])
        if set(selected) != set(FLEX_CALIBRATION_ROLES):
            raise MechanicalInterfaceContractError(
                "G000 validation requires the exact four endpoint roles"
            )
        return selected

    module_endpoints = selected_rows(module_catalog, module_contract)
    if slot_axis_catalog is slot_catalog:
        slot_record_catalog = slot_catalog
    else:
        slot_record_catalog = copy.deepcopy(slot_catalog)
        merged = _endpoint_index(slot_catalog)
        merged.update(_endpoint_index(slot_axis_catalog))
        slot_record_catalog["Endpoints"] = [
            copy.deepcopy(merged[key]) for key in sorted(merged)
        ]
        slot_record_catalog["EndpointCount"] = len(
            slot_record_catalog["Endpoints"]
        )
    slot_endpoints = selected_rows(slot_record_catalog, slot_contract)
    target_token = str(module_contract.get("moduleToken") or "")
    base_token = str(slot_contract.get("moduleToken") or "")
    target_module = _module_record(
        module_catalog, module_endpoints, target_token, nonprototype_target=True
    )
    # The authoritative Project05 G000 release declares the subassembly
    # flexible.  The face-only endpoint catalog does not carry module solving
    # semantics, so _module_record would otherwise synthesize a rigid record.
    # Preserve the released semantic explicitly: the four external mates must
    # locate the root while the internal mechanism remains flexible.
    target_module["SolvingState"] = 1
    target_module["SolvingStateName"] = "swComponentFlexibleSolving"
    base_module = _module_record(
        slot_record_catalog, slot_endpoints, base_token, nonprototype_target=False
    )
    if target_module.get("SourceTransform") != IDENTITY_TRANSFORM:
        raise MechanicalInterfaceContractError(
            "G000 target must start from identity before deterministic placement"
        )
    if not Path(str(target_module.get("Path") or "")).is_file():
        raise MechanicalInterfaceContractError("G000 source assembly is missing")
    cache_entry_path, source_assembly_path = _base_wrapper_source(
        workspace, base_token
    )
    mates = []
    for step in template.get("mateSteps") or []:
        row = _mate_row(
            step=step,
            target_token=target_token,
            base_token=base_token,
            target_endpoint=module_endpoints[str(step["endpointRoleA"])],
            base_endpoint=slot_endpoints[str(step["endpointRoleB"])],
        )
        if step["mateTypeName"] == "swMateSLOT":
            row["AdvancedOptions"] = copy.deepcopy(step.get("advancedOptions") or {})
            row["IsBasicTwoFaceRebuildable"] = False
            row["RebuildRejectionReason"] = None
        mates.append(row)
    if [row["MateTypeName"] for row in mates] != [
        "swMateCOINCIDENT",
        "swMatePARALLEL",
        "swMateDISTANCE",
        "swMateSLOT",
    ]:
        raise MechanicalInterfaceContractError(
            "G000 validation graph must preserve the four-relation topology"
        )
    policy = {
        "mode": "reviewed_flexible_calibration_slot",
        "selectedAxisEndpointId": selected_axis_endpoint_id,
        "longitudinalOffsetMeters": float(longitudinal_offset_meters),
        "selectionDigest": selection["selectionDigest"],
        "internalFlexibilityPreserved": True,
        "actualFasteningMethod": "not_verified",
        "directMechanicalCompatibilityClaim": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "templateId": template["templateId"],
    }
    effective_graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": None,
        "ModuleCount": 2,
        "InterModuleMateCount": 4,
        "Modules": [base_module, target_module],
        "Mates": mates,
        "BaseGraphPolicy": {
            "status": "reviewed_flexible_calibration_slot_validation_candidate",
            "caseAnchorAllowed": False,
            "prototypeTopLevelTargetPoseAllowed": False,
            "targetLeafPoseAnchorsAllowed": False,
        },
        "CaseAnchor": None,
        "TargetLeafPoseAnchors": [],
        "EditPolicy": {
            "baseModuleToken": base_token,
            "initialPlacementMode": "deterministic",
            "initialPlacementVariant": initial_placement_variant,
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [base_token],
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
            "fixCaseAnchorBeforeMates": False,
        },
        "FlexibleCalibrationSlotPolicy": policy,
    }
    unique_endpoint_rows: dict[str, dict[str, Any]] = {}
    for role in FLEX_CALIBRATION_ROLES:
        for row in (module_endpoints[role], slot_endpoints[role]):
            unique_endpoint_rows[str(row["EndpointId"])] = copy.deepcopy(row)
    selected_endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "CatalogMode": "flexible-calibration-slot-validation-selected-endpoints",
        "SourceMateFacesOnly": False,
        "ModuleCount": 2,
        "Modules": copy.deepcopy(effective_graph["Modules"]),
        "EndpointCount": len(unique_endpoint_rows),
        "Endpoints": [unique_endpoint_rows[key] for key in sorted(unique_endpoint_rows)],
    }
    package = {
        "schemaVersion": VALIDATION_PACKAGE_SCHEMA,
        "status": "ready_for_explicit_nonprototype_cad_validation",
        "placementMode": "reviewed_flexible_calibration_slot",
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "slotDefinitionId": slot_definition_id,
        "targetModuleToken": target_token,
        "baseModuleToken": base_token,
        "sourceAssemblyPath": str(source_assembly_path.resolve()),
        "sourceAssemblySha256": _sha256_file(source_assembly_path),
        "baseWrapperCacheEntryPath": str(cache_entry_path.resolve()),
        "baseWrapperCacheEntrySha256": _sha256_file(cache_entry_path),
        "moduleEndpointCatalogPath": str(module_catalog_path.resolve()),
        "slotEndpointCatalogPath": str(slot_catalog_path.resolve()),
        "slotFrameEndpointCatalogPath": str(slot_catalog_path.resolve()),
        "slotAxisEndpointCatalogPath": str(slot_axis_catalog_path.resolve()),
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": initial_placement_variant,
        "requiredInitialPlacementVariants": [1, 2],
        "externalPlacementRepeatabilityRequired": True,
        "externalPlacementRepeatabilityToleranceMeters": 1e-8,
        "externalPlacementRepeatabilityRotationTolerance": 1e-8,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "readyForReleasedCadExecution": False,
        "validationRequiredBeforeRelease": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "instantiatedTemplate": template,
        "positionParametersOverride": {
            "longitudinalOffsetMeters": float(longitudinal_offset_meters)
        },
        "flexibleSlotSelection": copy.deepcopy(selection),
        "effectiveGraph": effective_graph,
        "selectedEndpointCatalog": selected_endpoint_catalog,
        "claimBoundary": (
            "This package validates only G000's reviewed external four-relation "
            "placement. Internal dynamic states, fastening and collision remain separate."
        ),
    }
    return {**package, "packageDigest": _digest(package)}
