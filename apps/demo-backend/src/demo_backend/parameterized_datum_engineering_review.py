"""Build review-only recommendations for unresolved datum queue decisions.

The packet is role-aware.  When a target base already has one published
station for the same role, that station can be shown as a recommendation.  If
the base only has a stable datum frame, the packet asks for three explicit
position parameters and deliberately emits no guessed coordinates.  A
recommendation is never execution authority: every emitted input record keeps
``confirmed`` false until a mechanical engineer explicitly accepts it.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
    build_g000_native_station_reference,
    rank_g000_flexible_slot_candidates,
)
from .hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
    rank_f000_hybrid_axis_candidates,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .native_role_station_evidence import (
    build_native_role_station_evidence,
    index_native_role_stations,
)
from .parameterized_datum_placement import load_parameterized_datum_placement_catalog
from .parameterized_datum_validation_queue import (
    build_parameterized_datum_validation_queue,
)
from .two_axis_slot_selection import (
    build_two_axis_native_station_references,
    build_two_axis_slot_candidate_catalog,
    rank_two_axis_candidates_from_native_station,
)


SCHEMA = "parameterized-datum-engineering-review/v1"
MIXED_RECOMMENDATION_BATCH_SCHEMA = (
    "parameterized-datum-mixed-recommendation-batch/v1"
)
MANUAL_INPUT_BARRIER_SCHEMA = "parameterized-datum-manual-input-barrier/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _project(definition_id: str) -> str:
    return definition_id.split("::", 1)[0] if "::" in definition_id else ""


def _target_role_station(
    catalog: dict[str, Any],
    slot_definition_id: str,
    module_role: str,
    *,
    native_station_index: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    contracts = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == slot_definition_id
        and module_role in (row.get("acceptedModuleRoles") or [])
    ]
    if len(contracts) != 1:
        raise MechanicalInterfaceContractError(
            f"base datum slot does not resolve uniquely: {slot_definition_id}/{module_role}"
        )
    contract = contracts[0]
    presets = (contract.get("geometrySignature") or {}).get(
        "positionParametersByModuleDefinitionId"
    ) or {}
    native_rows = (native_station_index or {}).get(
        (slot_definition_id, module_role), []
    )
    same_project = [
        (definition_id, parameters)
        for definition_id, parameters in presets.items()
        if _project(str(definition_id)) == _project(slot_definition_id)
    ]
    if len(same_project) == 1:
        definition_id, parameters = same_project[0]
        selection_basis = "same_project_role_station"
    elif not same_project and len(native_rows) == 1:
        native = native_rows[0]
        return {
            "targetSlotContractId": contract["contractId"],
            "referenceModuleDefinitionId": native["moduleDefinitionId"],
            "parametersMeters": copy.deepcopy(native["parametersMeters"]),
            "parameterSource": "prototype_native_role_station_review_evidence",
            "notVendorDatum": True,
            "selectionBasis": "prototype_native_role_station_review_evidence",
            "nativeStationEvidence": copy.deepcopy(native),
            "prototypePoseUsedForRecommendation": True,
            "prototypePoseAllowedAsCadExecutionAuthority": False,
            "targetEnvelopeVerified": False,
        }
    elif not same_project and len(presets) == 1:
        definition_id, parameters = next(iter(presets.items()))
        selection_basis = "only_registered_role_station"
    elif not presets:
        if len(native_rows) > 1:
            return {
                "targetSlotContractId": contract["contractId"],
                "referenceModuleDefinitionId": None,
                "parametersMeters": None,
                "parameterSource": "multiple_prototype_native_role_stations",
                "notVendorDatum": True,
                "selectionBasis": "multiple_native_role_stations_require_choice",
                "candidateRoleStations": copy.deepcopy(native_rows),
            }
        return {
            "targetSlotContractId": contract["contractId"],
            "referenceModuleDefinitionId": None,
            "parametersMeters": None,
            "parameterSource": (contract.get("geometrySignature") or {}).get(
                "parameterSource"
            ),
            "notVendorDatum": True,
            "selectionBasis": "stable_datum_frame_without_registered_role_station",
        }
    else:
        expected_keys = {"longitudinal", "lateral", "supportGap"}
        candidates = []
        for definition_id, parameters in sorted(presets.items()):
            if not isinstance(parameters, dict) or set(parameters) != expected_keys:
                raise MechanicalInterfaceContractError(
                    f"registered role station is incomplete: {slot_definition_id}/{definition_id}"
                )
            candidates.append(
                {
                    "referenceModuleDefinitionId": str(definition_id),
                    "parametersMeters": copy.deepcopy(parameters),
                    "sameProjectAsTargetBase": (
                        _project(str(definition_id)) == _project(slot_definition_id)
                    ),
                }
            )
        return {
            "targetSlotContractId": contract["contractId"],
            "referenceModuleDefinitionId": None,
            "parametersMeters": None,
            "parameterSource": (contract.get("geometrySignature") or {}).get(
                "parameterSource"
            ),
            "notVendorDatum": True,
            "selectionBasis": "multiple_registered_role_stations_require_choice",
            "candidateRoleStations": candidates,
        }
    expected_keys = {"longitudinal", "lateral", "supportGap"}
    if not isinstance(parameters, dict) or set(parameters) != expected_keys:
        raise MechanicalInterfaceContractError(
            f"native scanner station is incomplete: {slot_definition_id}"
        )
    return {
        "targetSlotContractId": contract["contractId"],
        "referenceModuleDefinitionId": str(definition_id),
        "parametersMeters": copy.deepcopy(parameters),
        "parameterSource": (contract.get("geometrySignature") or {}).get(
            "parameterSource"
        ),
        "notVendorDatum": (contract.get("geometrySignature") or {}).get(
            "notVendorDatum"
        )
        is True,
        "selectionBasis": selection_basis,
    }


def _cross_base_module_station_consensus(
    catalog: dict[str, Any],
    *,
    target_slot_definition_id: str,
    module_definition_id: str,
    module_role: str,
    minimum_independent_bases: int = 2,
) -> dict[str, Any] | None:
    """Return a review-only station when multiple bases register one exact value.

    This is intentionally stricter than borrowing any one prototype station.
    The exact moving module must have the same semantic-axis coordinates on at
    least two other base definitions.  Divergent values yield no recommendation.
    """

    expected_keys = {"longitudinal", "lateral", "supportGap"}
    rows: list[tuple[str, dict[str, Any], str]] = []
    for contract in catalog.get("contracts") or []:
        base = str(contract.get("moduleDefinitionId") or "")
        if (
            contract.get("side") != "base_slot"
            or base == target_slot_definition_id
            or module_role not in (contract.get("acceptedModuleRoles") or [])
        ):
            continue
        geometry = contract.get("geometrySignature") or {}
        presets = geometry.get("positionParametersByModuleDefinitionId") or {}
        parameters = presets.get(module_definition_id)
        if parameters is None:
            continue
        if not isinstance(parameters, dict) or set(parameters) != expected_keys:
            raise MechanicalInterfaceContractError(
                "cross-base module station is incomplete: "
                f"{module_definition_id}/{base}"
            )
        rows.append((base, copy.deepcopy(parameters), str(contract["contractId"])))
    unique_bases = {base for base, _, _ in rows}
    if len(unique_bases) < minimum_independent_bases:
        return None
    values = {
        json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        for _, parameters, _ in rows
    }
    if len(values) != 1:
        return None
    parameters = rows[0][1]
    return {
        "targetSlotContractId": None,
        "referenceModuleDefinitionId": module_definition_id,
        "parametersMeters": parameters,
        "parameterSource": "cross_base_registered_module_station_consensus",
        "notVendorDatum": True,
        "selectionBasis": "cross_base_module_station_consensus",
        "sourceBaseDefinitionIds": sorted(unique_bases),
        "sourceSlotContractIds": sorted({contract_id for _, _, contract_id in rows}),
        "sourceStationCount": len(unique_bases),
        "targetEnvelopeVerified": False,
    }


def _exact_module_native_station_demo_projection(
    native_station_index: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    target_slot_definition_id: str,
    module_definition_id: str,
    module_role: str,
    target_slot_contract_id: str,
) -> dict[str, Any] | None:
    """Project one exact module's native semantic coordinates to a new base.

    This is an explicitly enabled Demo fallback.  It copies only the measured
    longitudinal/lateral/support-gap values into the target base's registered
    semantic frame.  It never copies a prototype transform and does not claim
    that the projected station is mechanically unique or envelope-safe.
    """

    rows = [
        row
        for candidates in native_station_index.values()
        for row in candidates
        if row.get("moduleDefinitionId") == module_definition_id
        and row.get("moduleRole") == module_role
        and row.get("baseDefinitionId") != target_slot_definition_id
    ]
    unique = {
        (
            str(row.get("baseDefinitionId") or ""),
            json.dumps(
                row.get("parametersMeters"),
                sort_keys=True,
                separators=(",", ":"),
            ),
        ): row
        for row in rows
    }
    if len(unique) != 1:
        return None
    source = next(iter(unique.values()))
    parameters = source.get("parametersMeters")
    if not isinstance(parameters, dict) or set(parameters) != {
        "longitudinal",
        "lateral",
        "supportGap",
    }:
        raise MechanicalInterfaceContractError(
            f"native Demo projection station is incomplete: {module_definition_id}"
        )
    return {
        "targetSlotContractId": target_slot_contract_id,
        "referenceModuleDefinitionId": module_definition_id,
        "referenceBaseDefinitionId": source["baseDefinitionId"],
        "parametersMeters": copy.deepcopy(parameters),
        "parameterSource": "exact_module_native_station_semantic_coordinate_projection_demo",
        "selectionBasis": "exact_module_native_station_semantic_coordinate_projection_demo",
        "nativeStationEvidence": copy.deepcopy(source),
        "prototypePoseUsedForRecommendation": True,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
        "semanticCoordinateValuesCopiedWithoutPrototypeTransform": True,
        "mechanicallyUniqueStationProven": False,
        "targetEnvelopeVerified": False,
        "actualFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
        "demoOnly": True,
    }


def build_parameterized_datum_engineering_review(
    workspace: Path,
    *,
    ranked_axis_limit: int = 5,
    allow_exact_module_native_station_demo_projection: bool = False,
) -> dict[str, Any]:
    """Return all unresolved review decisions without authorizing them."""

    if ranked_axis_limit < 1:
        raise MechanicalInterfaceContractError("ranked axis limit must be positive")
    workspace = workspace.resolve()
    catalog = load_parameterized_datum_placement_catalog(workspace)
    queue = build_parameterized_datum_validation_queue(workspace)
    hybrid = build_f000_hybrid_axis_slot_catalog(workspace)
    two_axis = build_two_axis_slot_candidate_catalog(workspace)
    two_axis_native_stations = build_two_axis_native_station_references(workspace)
    flexible_slot = build_g000_flexible_slot_candidate_catalog(workspace)
    native_station_evidence = build_native_role_station_evidence(
        workspace, catalog=catalog
    )
    native_station_index = index_native_role_stations(native_station_evidence)
    decisions: list[dict[str, Any]] = []

    for row in queue.get("pairs") or []:
        state = row.get("state")
        if state not in {
            "explicit_position_parameters_required",
            "explicit_axis_selection_required",
            "explicit_axis_pair_selection_required",
            "explicit_flexible_slot_selection_required",
        }:
            continue
        slot_definition_id = str(row["slotDefinitionId"])
        module_role = str(row["moduleRole"])
        station = (
            _target_role_station(
                catalog,
                slot_definition_id,
                module_role,
                native_station_index=native_station_index,
            )
            if state
            not in {
                "explicit_axis_pair_selection_required",
                "explicit_flexible_slot_selection_required",
            }
            else None
        )
        if (
            station is not None
            and station.get("parametersMeters") is None
            and state == "explicit_position_parameters_required"
        ):
            consensus = _cross_base_module_station_consensus(
                catalog,
                target_slot_definition_id=slot_definition_id,
                module_definition_id=str(row["moduleDefinitionId"]),
                module_role=module_role,
            )
            if consensus is not None:
                consensus["targetSlotContractId"] = station[
                    "targetSlotContractId"
                ]
                station = consensus
            elif allow_exact_module_native_station_demo_projection:
                projection = _exact_module_native_station_demo_projection(
                    native_station_index,
                    target_slot_definition_id=slot_definition_id,
                    module_definition_id=str(row["moduleDefinitionId"]),
                    module_role=module_role,
                    target_slot_contract_id=str(station["targetSlotContractId"]),
                )
                if projection is not None:
                    station = projection
        pair = {
            "moduleDefinitionId": str(row["moduleDefinitionId"]),
            "slotDefinitionId": slot_definition_id,
            "moduleRole": module_role,
        }
        if state == "explicit_position_parameters_required":
            parameters = station.get("parametersMeters")
            has_recommendation = isinstance(parameters, dict)
            multiple_role_stations = (
                station.get("selectionBasis")
                == "multiple_registered_role_stations_require_choice"
            )
            recommendation = {
                "decisionKind": "position_parameters",
                "status": (
                    "recommendation_pending_engineering_confirmation"
                    if has_recommendation
                    else "explicit_engineering_input_required"
                ),
                **pair,
                "basis": (
                    "cross_base_module_station_consensus"
                    if station.get("selectionBasis")
                    == "cross_base_module_station_consensus"
                    else "prototype_native_role_station_projection"
                    if station.get("selectionBasis")
                    == "prototype_native_role_station_review_evidence"
                    else "exact_module_native_station_semantic_coordinate_projection_demo"
                    if station.get("selectionBasis")
                    == "exact_module_native_station_semantic_coordinate_projection_demo"
                    else "target_base_registered_role_station_projection"
                    if has_recommendation
                    else "stable_target_base_frame_without_role_station"
                ),
                "reference": station,
                "recommendedParametersMeters": copy.deepcopy(parameters),
                "requiredPositionParameters": [
                    "longitudinal",
                    "lateral",
                    "supportGap",
                ],
                "confirmationTemplate": {
                    **pair,
                    "confirmed": False,
                    "source": (
                        "engineering_review_of_prototype_native_role_station"
                        if station.get("selectionBasis")
                        == "prototype_native_role_station_review_evidence"
                        else "user_authorized_exact_module_native_station_demo_projection"
                        if station.get("selectionBasis")
                        == "exact_module_native_station_semantic_coordinate_projection_demo"
                        else "engineering_review_of_target_registered_role_station"
                        if has_recommendation
                        else "engineering_input_required_for_stable_base_frame"
                    ),
                    "confirmedBy": None,
                    "confirmedAt": None,
                    "parametersMeters": copy.deepcopy(parameters),
                    "notes": (
                        "Cross-base consensus recommendation only; confirm that the "
                        "target base uses the same semantic frame and review the module "
                        "envelope before changing confirmed to true."
                        if station.get("selectionBasis")
                        == "cross_base_module_station_consensus"
                        else "Prototype-derived native role station recommendation only; "
                        "confirm that this target base station is appropriate for the selected "
                        "module. The prototype pose is evidence only and will not be used by CAD."
                        if station.get("selectionBasis")
                        == "prototype_native_role_station_review_evidence"
                        else "User-authorized Demo projection of this exact module's native "
                        "semantic coordinates into the target base frame. The prototype "
                        "transform is not copied; station uniqueness, envelope and fastening "
                        "remain unverified."
                        if station.get("selectionBasis")
                        == "exact_module_native_station_semantic_coordinate_projection_demo"
                        else "System recommendation only; confirm the role station, module "
                        "envelope and process intent before changing confirmed to true."
                        if has_recommendation
                        else "Multiple role stations are registered on this base. Select one "
                        "candidate station or enter all three position parameters; the system "
                        "will not choose a station implicitly."
                        if multiple_role_stations
                        else "No role station is registered on this base. Enter all three "
                        "position parameters and review the module envelope before confirmation."
                    ),
                },
            }
        elif state == "explicit_axis_selection_required":
            parameters = station.get("parametersMeters")
            if isinstance(parameters, dict):
                ranked = rank_f000_hybrid_axis_candidates(
                    hybrid,
                    slot_definition_id,
                    longitudinal_meters=float(parameters["longitudinal"]),
                    lateral_meters=float(parameters["lateral"]),
                    limit=ranked_axis_limit,
                )
                if not ranked:
                    raise MechanicalInterfaceContractError(
                        f"F000 base has no rankable axis candidate: {slot_definition_id}"
                    )
                selected = ranked[0]
                recommendation = {
                    "decisionKind": "axis_selection",
                    "status": "recommendation_pending_engineering_confirmation",
                    **pair,
                    "basis": "nearest_stable_axis_to_target_base_native_scanner_station",
                    "reference": station,
                    "requestedPositionMeters": {
                        "longitudinal": parameters["longitudinal"],
                        "lateral": parameters["lateral"],
                    },
                    "recommendedAxisEndpointId": selected["endpointId"],
                    "recommendedAxisDistanceMeters": selected[
                        "distanceFromRequestedPositionMeters"
                    ],
                    "rankedAxisCandidates": copy.deepcopy(ranked),
                    "confirmationTemplate": {
                        **pair,
                        "confirmed": False,
                        "source": "engineering_review_of_ranked_stable_base_axis",
                        "confirmedBy": None,
                        "confirmedAt": None,
                        "selectedAxisEndpointId": selected["endpointId"],
                        "requestedPositionMeters": {
                            "longitudinal": parameters["longitudinal"],
                            "lateral": parameters["lateral"],
                        },
                        "notes": (
                            "Nearest stable axis recommendation only. Confirm hole purpose, "
                            "installation side and scanner process intent before approval."
                        ),
                    },
                }
            else:
                slot = next(
                    row
                    for row in hybrid.get("baseSlots") or []
                    if row.get("slotDefinitionId") == slot_definition_id
                )
                recommendation = {
                    "decisionKind": "axis_selection",
                    "status": "explicit_engineering_position_and_axis_input_required",
                    **pair,
                    "basis": "stable_target_base_frame_without_registered_scanner_station",
                    "reference": station,
                    "requestedPositionMeters": None,
                    "recommendedAxisEndpointId": None,
                    "recommendedAxisDistanceMeters": None,
                    "rankedAxisCandidates": [],
                    "availableAxisLineCount": int(
                        slot.get("candidateAxisLineCount") or 0
                    ),
                    "axisCandidateCatalogPath": slot.get(
                        "axisCandidateCatalogPath"
                    ),
                    "confirmationTemplate": {
                        **pair,
                        "confirmed": False,
                        "source": "engineering_input_required_for_stable_base_axis_catalog",
                        "confirmedBy": None,
                        "confirmedAt": None,
                        "selectedAxisEndpointId": None,
                        "requestedPositionMeters": None,
                        "notes": (
                            "Multiple scanner stations are registered on this base. Select "
                            "the intended station first, then review and select one stable "
                            "cylinder endpoint; the system will not choose between stations "
                            "implicitly."
                            if station.get("selectionBasis")
                            == "multiple_registered_role_stations_require_choice"
                            else "No scanner station is registered on this base. Confirm the "
                            "desired longitudinal/lateral station first, then review and "
                            "select one stable cylinder endpoint; do not approve a nearest "
                            "hole without checking its purpose and installation side."
                        ),
                    },
                }
        elif state == "explicit_axis_pair_selection_required":
            families = [
                item
                for item in two_axis.get("families") or []
                if item.get("slotDefinitionId") == slot_definition_id
                and str(row["moduleDefinitionId"])
                in (item.get("moduleDefinitionIds") or [])
            ]
            if len(families) != 1:
                raise MechanicalInterfaceContractError(
                    "two-axis review pair does not resolve one candidate family"
                )
            family = families[0]
            ranked = rank_two_axis_candidates_from_native_station(
                workspace,
                two_axis,
                str(row["moduleDefinitionId"]),
                limit=ranked_axis_limit,
            )
            selected = ranked[0] if ranked else None
            native_reference = next(
                item
                for item in two_axis_native_stations["stations"]
                if item["moduleDefinitionId"] == row["moduleDefinitionId"]
            )
            recommendation = {
                "decisionKind": "axis_pair_selection",
                "status": (
                    "recommendation_pending_engineering_confirmation"
                    if selected is not None
                    else "explicit_engineering_axis_pair_input_required"
                ),
                **pair,
                "basis": (
                    "native_primary_secondary_station_ranked_A000_axis_pair"
                    if selected is not None
                    else "stable_A000_axis_pair_inventory_with_exact_spacing"
                ),
                "reference": {
                    "slotCatalogDigest": two_axis["catalogDigest"],
                    "sourceCatalogPath": two_axis["sourceCatalogPath"],
                    "supportEndpointId": two_axis["supportEndpointId"],
                    "requiredSpacingMeters": family["requiredSpacingMeters"],
                    "spacingToleranceMeters": two_axis[
                        "spacingToleranceMeters"
                    ],
                    "nativeStationReference": native_reference,
                },
                "recommendedCandidatePairId": (
                    selected["candidatePairId"] if selected is not None else None
                ),
                "recommendedAxisAssignment": (
                    selected["axisAssignment"] if selected is not None else None
                ),
                "recommendedPairRmsMeters": (
                    selected["twoPointRmsFromNativeStationMeters"]
                    if selected is not None
                    else None
                ),
                "candidatePairCount": len(family.get("axisPairCandidates") or []),
                "axisPairCandidates": ranked,
                "confirmationTemplate": {
                    **pair,
                    "confirmed": False,
                    "source": "engineering_review_of_A000_two_axis_slot",
                    "confirmedBy": None,
                    "confirmedAt": None,
                    "selectedCandidatePairId": (
                        selected["candidatePairId"] if selected is not None else None
                    ),
                    "notes": (
                        "The first pair is ranked by two-point RMS from this exact module's "
                        "released native primary/secondary station. Confirm the ordered pair, "
                        "axis assignment, hole purpose, installation side and module envelope; "
                        "the prototype pose is review evidence only."
                        if selected is not None
                        else "Confirm the exact ordered pair only after reviewing hole purpose, "
                        "installation side and module envelope. Matching spacing alone is "
                        "not a mechanical compatibility approval."
                    ),
                },
            }
        else:
            slots = [
                item
                for item in flexible_slot.get("baseSlots") or []
                if item.get("slotDefinitionId") == slot_definition_id
                and item.get("state")
                == "explicit_flexible_slot_selection_required"
            ]
            if len(slots) != 1:
                raise MechanicalInterfaceContractError(
                    "G000 flexible-slot review pair does not resolve one base inventory"
                )
            slot = slots[0]
            ranked = rank_g000_flexible_slot_candidates(
                workspace,
                flexible_slot,
                slot_definition_id,
                limit=ranked_axis_limit,
            )
            selected = ranked[0] if ranked else None
            native_reference = build_g000_native_station_reference(workspace)
            recommendation = {
                "decisionKind": "flexible_slot_selection",
                "status": (
                    "recommendation_pending_engineering_confirmation"
                    if selected is not None
                    else "explicit_engineering_axis_and_offset_input_required"
                ),
                **pair,
                "basis": "released_G000_four_relation_topology_plus_stable_base_axis_inventory",
                "reference": {
                    "slotCatalogDigest": flexible_slot["catalogDigest"],
                    "sourceCatalogPath": slot["sourceCatalogPath"],
                    "axisCandidateCatalogPath": slot["axisCandidateCatalogPath"],
                    "supportEndpointId": slot["supportEndpointId"],
                    "orientationEndpointId": slot["orientationEndpointId"],
                    "candidateAxisLineCount": slot["candidateAxisLineCount"],
                    "nativeStationReference": native_reference,
                },
                "rankedAxisCandidates": ranked,
                "recommendedAxisEndpointId": (
                    selected["endpointId"] if selected is not None else None
                ),
                "recommendedAxisDistanceMeters": (
                    selected["distanceFromNativeSemanticAxisMeters"]
                    if selected is not None
                    else None
                ),
                "recommendedLongitudinalOffsetMeters": (
                    native_reference["longitudinalOffsetMeters"]
                    if selected is not None
                    else None
                ),
                "confirmationTemplate": {
                    **pair,
                    "confirmed": False,
                    "source": "engineering_review_of_G000_flexible_slot_on_target_base",
                    "confirmedBy": None,
                    "confirmedAt": None,
                    "selectedAxisEndpointId": (
                        selected["endpointId"] if selected is not None else None
                    ),
                    "longitudinalOffsetMeters": (
                        native_reference["longitudinalOffsetMeters"]
                        if selected is not None
                        else None
                    ),
                    "notes": (
                        "Review-only projection of the released G000/A000 semantic axis and "
                        "482 mm offset. Confirm the exact cylinder purpose, slot reach, side "
                        "and module envelope; the prototype pose is not CAD authority."
                        if selected is not None
                        else "Select one exact stable base cylinder and enter the target "
                        "longitudinal offset. Do not copy the A000 value or approve a "
                        "nearest hole without reviewing purpose, side and module envelope."
                    ),
                },
            }
        recommendation["decisionDigest"] = _digest(recommendation)
        decisions.append(recommendation)

    decisions.sort(
        key=lambda row: (
            row["decisionKind"],
            row["moduleDefinitionId"],
            row["slotDefinitionId"],
        )
    )
    core = {
        "schemaVersion": SCHEMA,
        "sourceCatalogDigest": catalog["catalogDigest"],
        "sourceQueueDigest": queue["queueDigest"],
        "twoAxisSlotCatalogDigest": two_axis["catalogDigest"],
        "flexibleCalibrationSlotCatalogDigest": flexible_slot["catalogDigest"],
        "decisionCount": len(decisions),
        "positionDecisionCount": sum(
            row["decisionKind"] == "position_parameters" for row in decisions
        ),
        "axisDecisionCount": sum(
            row["decisionKind"] == "axis_selection" for row in decisions
        ),
        "axisPairDecisionCount": sum(
            row["decisionKind"] == "axis_pair_selection" for row in decisions
        ),
        "flexibleSlotDecisionCount": sum(
            row["decisionKind"] == "flexible_slot_selection" for row in decisions
        ),
        "allRecommendationsUnconfirmed": all(
            row["confirmationTemplate"]["confirmed"] is False for row in decisions
        ),
        "decisions": decisions,
        "nativeRoleStationEvidence": native_station_evidence,
        "twoAxisNativeStationEvidence": two_axis_native_stations,
        "claimBoundary": (
            "Exact-module native semantic coordinates may be projected only because the "
            "explicit Demo option is enabled; prototype transforms are never copied. These "
            "recommendations do not prove station uniqueness, target envelope, fastening, "
            "collision, process suitability or production readiness and require exact-pair "
            "confirmation plus non-prototype CAD validation."
            if allow_exact_module_native_station_demo_projection
            else "Recommendations reuse target-base registered role stations when available; "
            "rows without a role station intentionally contain no guessed coordinates. They "
            "do not prove model envelope, optical/process suitability, hole purpose, fastening, "
            "collision or production readiness and never authorize CAD until an engineer "
            "explicitly confirms each exact pair."
        ),
        "exactModuleNativeStationDemoProjectionEnabled": (
            allow_exact_module_native_station_demo_projection
        ),
    }
    core["reviewDigest"] = _digest(core)
    return core


def build_prioritized_mixed_recommendation_batch(
    review: dict[str, Any],
    *,
    limit: int = 8,
    exclude_pairs: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Select evidence-backed position, axis, axis-pair and flexible reviews.

    This is a human review packet, not execution evidence.  Combining decision
    kinds keeps the established 5--8 item batch size after earlier position
    releases have reduced the position-only recommendation pool.
    """

    if review.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    expected_digest = _digest(
        {key: value for key, value in review.items() if key != "reviewDigest"}
    )
    if review.get("reviewDigest") != expected_digest:
        raise MechanicalInterfaceContractError("engineering review digest mismatch")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 5 <= limit <= 8:
        raise MechanicalInterfaceContractError(
            "mixed recommendation batch limit must be between 5 and 8"
        )

    excluded = set(exclude_pairs or set())
    if any(
        not isinstance(pair, tuple)
        or len(pair) != 2
        or not all(isinstance(value, str) and value for value in pair)
        for pair in excluded
    ):
        raise MechanicalInterfaceContractError(
            "mixed recommendation exclusions must be exact nonempty pairs"
        )
    candidates: list[dict[str, Any]] = []
    for decision in review.get("decisions") or []:
        exact_pair = (
            str(decision.get("moduleDefinitionId") or ""),
            str(decision.get("slotDefinitionId") or ""),
        )
        if exact_pair in excluded:
            continue
        kind = decision.get("decisionKind")
        if kind == "position_parameters" and isinstance(
            decision.get("recommendedParametersMeters"), dict
        ):
            position_basis = decision.get("basis")
            evidence_class = (
                "target_base_registered_role_station"
                if position_basis == "target_base_registered_role_station_projection"
                else "prototype_native_role_station_review_evidence"
                if position_basis == "prototype_native_role_station_projection"
                else "exact_module_native_station_demo_projection"
                if position_basis
                == "exact_module_native_station_semantic_coordinate_projection_demo"
                else "exact_module_cross_base_consensus"
            )
            priority = {
                "target_base_registered_role_station": 1,
                "prototype_native_role_station_review_evidence": 2,
                "exact_module_native_station_demo_projection": 3,
                "exact_module_cross_base_consensus": 4,
            }[evidence_class]
            recommendation = {
                "parametersMeters": copy.deepcopy(
                    decision["recommendedParametersMeters"]
                )
            }
        elif kind == "axis_selection" and decision.get(
            "recommendedAxisEndpointId"
        ):
            evidence_class = "ranked_axis_at_registered_role_station"
            priority = 4
            recommendation = {
                "selectedAxisEndpointId": decision["recommendedAxisEndpointId"],
                "requestedPositionMeters": copy.deepcopy(
                    decision.get("requestedPositionMeters")
                ),
                "axisDistanceMeters": decision.get(
                    "recommendedAxisDistanceMeters"
                ),
            }
        elif kind == "axis_pair_selection" and decision.get(
            "recommendedCandidatePairId"
        ):
            evidence_class = "ranked_axis_pair_at_native_primary_secondary_station"
            priority = 5
            recommendation = {
                "selectedCandidatePairId": decision[
                    "recommendedCandidatePairId"
                ],
                "axisAssignment": decision.get("recommendedAxisAssignment"),
                "pairRmsMeters": decision.get("recommendedPairRmsMeters"),
            }
        elif kind == "flexible_slot_selection" and decision.get(
            "recommendedAxisEndpointId"
        ) and isinstance(decision.get("recommendedLongitudinalOffsetMeters"), (int, float)):
            evidence_class = "ranked_flexible_axis_at_native_semantic_station"
            priority = 6
            recommendation = {
                "selectedAxisEndpointId": decision["recommendedAxisEndpointId"],
                "longitudinalOffsetMeters": decision[
                    "recommendedLongitudinalOffsetMeters"
                ],
                "axisDistanceMeters": decision.get(
                    "recommendedAxisDistanceMeters"
                ),
            }
        else:
            continue
        candidates.append(
            {
                "decisionKind": kind,
                "moduleDefinitionId": decision["moduleDefinitionId"],
                "slotDefinitionId": decision["slotDefinitionId"],
                "moduleRole": decision["moduleRole"],
                "priorityTier": priority,
                "evidenceClass": evidence_class,
                "recommendation": recommendation,
                "reference": copy.deepcopy(decision.get("reference")),
                "sourceDecisionDigest": decision["decisionDigest"],
                "confirmationTemplate": copy.deepcopy(
                    decision["confirmationTemplate"]
                ),
            }
        )
    candidates.sort(
        key=lambda row: (
            row["priorityTier"],
            row["moduleDefinitionId"],
            row["slotDefinitionId"],
        )
    )
    selected = candidates[:limit]
    core = {
        "schemaVersion": MIXED_RECOMMENDATION_BATCH_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "availableRecommendationCount": len(candidates),
        "selectedRecommendationCount": len(selected),
        "deferredRecommendationCount": max(0, len(candidates) - len(selected)),
        "status": (
            "ready_for_engineering_review"
            if len(selected) >= 5
            else "insufficient_evidence_backed_recommendations_for_full_batch"
        ),
        "allRecommendationsUnconfirmed": all(
            row["confirmationTemplate"].get("confirmed") is False
            for row in selected
        ),
        "selected": selected,
        "deferred": candidates[limit:],
        "claimBoundary": (
            "This packet combines position, single-axis, two-axis and flexible-slot "
            "recommendations for human review only. It does not authorize CAD, fastening, "
            "collision or production use."
        ),
    }
    if excluded:
        core["excludedEarlierBatchPairs"] = [
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
            }
            for pair in sorted(excluded)
        ]
    core["batchDigest"] = _digest(core)
    return core


def build_manual_input_barrier(review: dict[str, Any]) -> dict[str, Any]:
    """Concentrate pairs for which the evidence chain cannot recommend a pose."""

    if review.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    expected_digest = _digest(
        {key: value for key, value in review.items() if key != "reviewDigest"}
    )
    if review.get("reviewDigest") != expected_digest:
        raise MechanicalInterfaceContractError("engineering review digest mismatch")

    pairs: list[dict[str, Any]] = []
    for decision in review.get("decisions") or []:
        if decision.get("status") != "explicit_engineering_input_required":
            continue
        if decision.get("decisionKind") != "position_parameters":
            raise MechanicalInterfaceContractError(
                "manual-input barrier currently supports position decisions only"
            )
        row = {
            "moduleDefinitionId": decision["moduleDefinitionId"],
            "slotDefinitionId": decision["slotDefinitionId"],
            "moduleRole": decision["moduleRole"],
            "requiredParametersMeters": [
                "longitudinal",
                "lateral",
                "supportGap",
            ],
            "knownEvidence": {
                "stableTargetBaseDatumFrame": True,
                "targetBaseRoleStation": None,
                "crossBaseExactModuleConsensus": None,
            },
            "whyNoRecommendation": (
                "The target base exposes a stable three-plane datum frame, but no unique "
                "same-interface role station or two-base exact-module consensus exists. "
                "A station from another interface family cannot be converted without an "
                "explicit semantic offset between that interface and this module datum."
            ),
            "requiredEngineeringAction": (
                "Enter all three target-base semantic coordinates, or reject the exact pair."
            ),
            "prototypeTopLevelPoseAllowed": False,
            "cadLaunchAllowed": False,
            "sourceDecisionDigest": decision["decisionDigest"],
        }
        row["barrierDigest"] = _digest(row)
        pairs.append(row)
    core = {
        "schemaVersion": MANUAL_INPUT_BARRIER_SCHEMA,
        "status": (
            "mechanical_confirmation_required" if pairs else "no_manual_input_barrier"
        ),
        "sourceReviewDigest": review["reviewDigest"],
        "pairCount": len(pairs),
        "pairs": pairs,
        "claimBoundary": (
            "These pairs are intentionally not auto-filled. Stable datum geometry makes an "
            "explicit position executable, but does not determine the mechanically intended "
            "station. Prototype top-level poses, nearest points and cross-interface-family "
            "stations are not accepted as substitutes."
        ),
    }
    core["barrierCatalogDigest"] = _digest(core)
    return core


def build_confirmation_templates(review: dict[str, Any]) -> tuple[dict, dict]:
    if review.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    position = {
        "schemaVersion": "parameterized-datum-position-parameters/v1",
        "pairs": [
            copy.deepcopy(row["confirmationTemplate"])
            for row in review["decisions"]
            if row["decisionKind"] == "position_parameters"
        ],
    }
    axes = {
        "schemaVersion": "hybrid-plane-axis-selection-evidence/v1",
        "pairs": [
            copy.deepcopy(row["confirmationTemplate"])
            for row in review["decisions"]
            if row["decisionKind"] == "axis_selection"
        ],
    }
    return position, axes


def build_axis_pair_confirmation_template(review: dict[str, Any]) -> dict[str, Any]:
    """Return a separate template for reviewed support-plane/two-axis choices."""

    if review.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    return {
        "schemaVersion": "two-axis-slot-selection-evidence/v1",
        "pairs": [
            copy.deepcopy(row["confirmationTemplate"])
            for row in review["decisions"]
            if row["decisionKind"] == "axis_pair_selection"
        ],
    }


def build_flexible_slot_confirmation_template(review: dict[str, Any]) -> dict[str, Any]:
    """Return exact G000 axis-plus-offset confirmation records."""

    if review.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    return {
        "schemaVersion": "flexible-calibration-slot-selection-evidence/v1",
        "pairs": [
            copy.deepcopy(row["confirmationTemplate"])
            for row in review["decisions"]
            if row["decisionKind"] == "flexible_slot_selection"
        ],
    }
