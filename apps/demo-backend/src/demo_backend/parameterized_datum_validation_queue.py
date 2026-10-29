"""Build an auditable CAD-validation queue for datum-placement pairs.

The queue is intentionally read-only with respect to SolidWorks.  It turns
every relevant pair in the parameterized datum catalog into one of four
explicit states:

* already released;
* ready for non-prototype CAD validation;
* waiting for explicit model-specific position parameters;
* blocked before CAD with a concrete diagnostic.

This keeps interface-family reuse separate from pair-specific release
authority.  A generated package is a candidate, never an implicit release.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .broad_combination_coverage import discover_global_relation_release_pairs
from .flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
    compile_g000_flexible_slot_validation_package,
)
from .hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
    compile_f000_hybrid_axis_validation_package,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import (
    compile_parameterized_datum_validation_package,
    load_parameterized_datum_placement_catalog,
)
from .parameterized_datum_position_language import (
    compile_parameterized_datum_position_instruction,
)
from .two_axis_slot_selection import (
    build_two_axis_slot_candidate_catalog,
    compile_two_axis_slot_validation_package,
)


QUEUE_SCHEMA = "parameterized-datum-validation-queue/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _project(definition_id: str) -> str:
    return definition_id.split("::", 1)[0] if "::" in definition_id else ""


def _token(definition_id: str) -> str:
    return definition_id.split("::", 1)[-1]


def _position_parameter_fallback_pairs(
    catalog: dict[str, Any],
) -> set[tuple[str, str]]:
    """Return pairs backed by a registered three-plane position fallback.

    A native two-axis inventory can still prove that its own recipe is not
    available. Once a separate, confirmed three-plane port exists, that
    negative native result must not hide the explicit-position fallback.
    """

    pairs: set[tuple[str, str]] = set()
    for match in catalog.get("compatibilityMatrix") or []:
        blocker_codes = {
            str(item.get("code") or "") for item in match.get("blockers") or []
        }
        if blocker_codes not in (
            {"MODULE_POSITION_PRESET_MISSING"},
            {"POSITION_PARAMETERS_MISSING"},
        ):
            continue
        pair = (
            str(match.get("moduleDefinitionId") or ""),
            str(match.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in pairs:
            raise MechanicalInterfaceContractError(
                f"parameterized fallback pair is empty or duplicated: {pair}"
            )
        pairs.add(pair)
    return pairs


def _directory_name(module_definition_id: str, slot_definition_id: str) -> str:
    return (
        "validation-"
        + _token(module_definition_id).lower()
        + "-"
        + _token(slot_definition_id).lower()
        + "-v1"
    )


def _validated_explicit_position_parameter_evidence(
    records: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Validate engineer-confirmed absolute station coordinates."""

    validated: dict[tuple[str, str], dict[str, Any]] = {}
    for pair, raw in (records or {}).items():
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
            or not isinstance(raw, dict)
        ):
            raise MechanicalInterfaceContractError(
                "explicit position parameter evidence has invalid pair identity"
            )
        if raw.get("confirmed") is not True:
            raise MechanicalInterfaceContractError(
                f"explicit position parameters are not confirmed: {pair}"
            )
        if not str(raw.get("source") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit position parameters have no source: {pair}"
            )
        parameters = raw.get("parametersMeters")
        instruction = str(raw.get("positionInstruction") or "").strip()
        if instruction:
            compiled = compile_parameterized_datum_position_instruction(
                instruction,
                current_parameters_meters=raw.get("currentParametersMeters"),
            )
            compiled_parameters = compiled["parametersMeters"]
            if parameters is not None and parameters != compiled_parameters:
                raise MechanicalInterfaceContractError(
                    f"explicit values differ from position instruction: {pair}"
                )
            raw = copy.deepcopy(raw)
            raw["parametersMeters"] = compiled_parameters
            raw["positionInstructionCompilation"] = compiled
            parameters = compiled_parameters
        if not isinstance(parameters, dict) or set(parameters) != {
            "longitudinal",
            "lateral",
            "supportGap",
        }:
            raise MechanicalInterfaceContractError(
                f"explicit position parameters must provide three metre values: {pair}"
            )
        validated[pair] = copy.deepcopy(raw)
    return validated


def _confirmed_position_reuses_pair_release(
    evidence: dict[str, Any], pair_release: dict[str, Any] | None
) -> bool:
    """A repeated confirmation is idempotent when it equals released CAD evidence."""

    resolution = (pair_release or {}).get("catalogResolution") or {}
    return bool(
        pair_release
        and pair_release.get("nonPrototypeCadValidated") is True
        and resolution.get("currentCatalogBindingsMatch") is True
        and evidence.get("parametersMeters")
        == resolution.get("positionParametersMeters")
    )


def _released_hybrid_axis_endpoint(
    workspace: Path, global_release: dict[str, Any] | None
) -> str | None:
    """Return the reviewed axis bound by an immutable hybrid-pair release.

    The broad release index intentionally stores only pair identity and release
    provenance. Hybrid F000 validation additionally needs the exact selected
    axis so a preserved confirmation is not mistaken for a new CAD candidate.
    Read that value from the already validated release manifest and fail closed
    when the release is outside the workspace or lacks non-prototype evidence.
    """

    workspace = workspace.resolve()
    for row in (global_release or {}).get("releaseEvidence") or []:
        raw_path = str(row.get("manifestPath") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = workspace / path
        try:
            path = path.resolve()
            path.relative_to(workspace)
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        metadata = document.get("releaseMetadata") or {}
        binding = metadata.get("parameterizedDatumPairBinding") or {}
        policy = metadata.get("supportPositionDemoPolicy") or {}
        selected = str(
            binding.get("selectedAxisEndpointId")
            or policy.get("selectedAxisEndpointId")
            or ""
        ).strip()
        if (
            selected
            and binding.get("nonPrototypeCadValidated") is True
            and binding.get("prototypeTopLevelTargetPoseUsed") is False
        ):
            return selected
    return None


def _validated_explicit_axis_selection_evidence(
    records: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    validated: dict[tuple[str, str], dict[str, Any]] = {}
    for pair, raw in (records or {}).items():
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
            or not isinstance(raw, dict)
        ):
            raise MechanicalInterfaceContractError(
                "explicit axis selection evidence has invalid pair identity"
            )
        if raw.get("confirmed") is not True:
            raise MechanicalInterfaceContractError(
                f"explicit axis selection is not confirmed: {pair}"
            )
        if not str(raw.get("source") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit axis selection has no source: {pair}"
            )
        if not str(raw.get("selectedAxisEndpointId") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit axis selection has no endpoint: {pair}"
            )
        validated[pair] = copy.deepcopy(raw)
    return validated


def _validated_explicit_axis_pair_selection_evidence(
    records: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Validate engineer-confirmed support-plane/two-axis slot choices."""

    validated: dict[tuple[str, str], dict[str, Any]] = {}
    for pair, raw in (records or {}).items():
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
            or not isinstance(raw, dict)
        ):
            raise MechanicalInterfaceContractError(
                "explicit axis-pair selection evidence has invalid pair identity"
            )
        if raw.get("confirmed") is not True:
            raise MechanicalInterfaceContractError(
                f"explicit axis-pair selection is not confirmed: {pair}"
            )
        if not str(raw.get("source") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit axis-pair selection has no source: {pair}"
            )
        if not str(raw.get("selectedCandidatePairId") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit axis-pair selection has no candidate pair id: {pair}"
            )
        validated[pair] = copy.deepcopy(raw)
    return validated


def _validated_explicit_flexible_slot_selection_evidence(
    records: dict[tuple[str, str], dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Validate an exact G000 base axis plus longitudinal distance decision."""

    validated: dict[tuple[str, str], dict[str, Any]] = {}
    for pair, raw in (records or {}).items():
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
            or not isinstance(raw, dict)
        ):
            raise MechanicalInterfaceContractError(
                "explicit flexible-slot evidence has invalid pair identity"
            )
        if raw.get("confirmed") is not True:
            raise MechanicalInterfaceContractError(
                f"explicit flexible-slot selection is not confirmed: {pair}"
            )
        if not str(raw.get("source") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit flexible-slot selection has no source: {pair}"
            )
        if not str(raw.get("selectedAxisEndpointId") or "").strip():
            raise MechanicalInterfaceContractError(
                f"explicit flexible-slot selection has no axis endpoint: {pair}"
            )
        offset = raw.get("longitudinalOffsetMeters")
        if (
            isinstance(offset, bool)
            or not isinstance(offset, (int, float))
            or not math.isfinite(float(offset))
            or float(offset) < 0
        ):
            raise MechanicalInterfaceContractError(
                f"explicit flexible-slot selection has no valid offset: {pair}"
            )
        validated[pair] = copy.deepcopy(raw)
    return validated


def build_parameterized_datum_validation_queue(
    workspace: Path,
    *,
    explicit_position_parameters: dict[tuple[str, str], dict[str, Any]] | None = None,
    explicit_axis_selections: dict[tuple[str, str], dict[str, Any]] | None = None,
    explicit_axis_pair_selections: dict[tuple[str, str], dict[str, Any]] | None = None,
    explicit_flexible_slot_selections: dict[
        tuple[str, str], dict[str, Any]
    ]
    | None = None,
) -> dict[str, Any]:
    """Return the current pair queue without starting or modifying CAD."""

    explicit_parameters = _validated_explicit_position_parameter_evidence(
        explicit_position_parameters
    )
    explicit_axes = _validated_explicit_axis_selection_evidence(
        explicit_axis_selections
    )
    explicit_axis_pairs = _validated_explicit_axis_pair_selection_evidence(
        explicit_axis_pair_selections
    )
    explicit_flexible_slots = _validated_explicit_flexible_slot_selection_evidence(
        explicit_flexible_slot_selections
    )
    catalog = load_parameterized_datum_placement_catalog(workspace)
    # Specialized moving-port families live outside the canonical three-plane
    # contract table.  Build their bounded inventories before release discovery
    # so an immutable exact-pair release remains visible even when a later
    # caller does not replay the historical engineering-confirmation packet.
    hybrid_catalog = build_f000_hybrid_axis_slot_catalog(workspace)
    two_axis_catalog = build_two_axis_slot_candidate_catalog(workspace)
    flexible_slot_catalog = build_g000_flexible_slot_candidate_catalog(workspace)
    position_fallback_pairs = _position_parameter_fallback_pairs(catalog)
    contracts = {
        str(row["contractId"]): row for row in catalog.get("contracts") or []
    }
    base_definition_ids = {
        str(row.get("moduleDefinitionId") or "")
        for row in contracts.values()
        if row.get("moduleRole") == "Base" and row.get("moduleDefinitionId")
    }
    known_definition_ids = {
        str(row.get("moduleDefinitionId") or "")
        for row in contracts.values()
        if row.get("moduleDefinitionId")
    }
    # F000 uses the hybrid support/orientation/axis recipe and therefore is not
    # one of the generic three-plane contracts.  Including it here keeps the
    # immutable-release lookup complete without making it a three-plane port.
    known_definition_ids.add("project05::F000")
    known_definition_ids.add("project05::G000")
    for slot in hybrid_catalog.get("baseSlots") or []:
        slot_definition_id = str(slot.get("slotDefinitionId") or "")
        if slot_definition_id:
            known_definition_ids.add(slot_definition_id)
            base_definition_ids.add(slot_definition_id)
    for family in two_axis_catalog.get("families") or []:
        slot_definition_id = str(family.get("slotDefinitionId") or "")
        if slot_definition_id:
            known_definition_ids.add(slot_definition_id)
            base_definition_ids.add(slot_definition_id)
        known_definition_ids.update(
            str(value)
            for value in family.get("moduleDefinitionIds") or []
            if str(value)
        )
    for slot in flexible_slot_catalog.get("baseSlots") or []:
        slot_definition_id = str(slot.get("slotDefinitionId") or "")
        if slot_definition_id:
            known_definition_ids.add(slot_definition_id)
            base_definition_ids.add(slot_definition_id)
    # Reviewed alternate recipes (notably the A000 two-axis families) may not
    # belong to the canonical three-plane datum contract set.  Their exact
    # confirmed pairs still need to discover an immutable direct release after
    # CAD succeeds so that a successor queue can retire the candidate instead
    # of scheduling it again.
    for evidence_pairs in (
        explicit_parameters,
        explicit_axes,
        explicit_axis_pairs,
        explicit_flexible_slots,
    ):
        for module_definition_id, slot_definition_id in evidence_pairs:
            known_definition_ids.add(module_definition_id)
            known_definition_ids.add(slot_definition_id)
            base_definition_ids.add(slot_definition_id)
    global_pair_releases = discover_global_relation_release_pairs(
        workspace,
        known_definition_ids=known_definition_ids,
        base_definition_ids=base_definition_ids,
    )
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    used_explicit_pairs: set[tuple[str, str]] = set()
    used_explicit_axis_pairs: set[tuple[str, str]] = set()
    used_explicit_two_axis_pairs: set[tuple[str, str]] = set()
    used_explicit_flexible_slots: set[tuple[str, str]] = set()
    for match in catalog.get("compatibilityMatrix") or []:
        if match.get("compatible") is not True:
            continue
        pair = (
            str(match.get("moduleDefinitionId") or ""),
            str(match.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen_pairs:
            raise MechanicalInterfaceContractError(
                f"compatible datum pair is missing identity or duplicated: {pair}"
            )
        seen_pairs.add(pair)
        module_contract = contracts.get(str(match.get("moduleContractId") or ""))
        slot_contract = contracts.get(str(match.get("slotContractId") or ""))
        if not module_contract or not slot_contract:
            raise MechanicalInterfaceContractError(
                f"compatible datum pair does not resolve contracts: {pair}"
            )
        base = {
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "moduleRole": module_contract.get("moduleRole"),
            "moduleToken": module_contract.get("moduleToken"),
            "baseToken": slot_contract.get("moduleToken"),
            "crossProject": _project(pair[0]) != _project(pair[1]),
            "interfaceFamily": match.get("interfaceFamily"),
            "recipeId": match.get("recipeId"),
            "proposedValidationDirectory": _directory_name(*pair),
            "physicalFasteningVerified": False,
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
        }
        global_release = global_pair_releases.get(pair)
        explicit_evidence = explicit_parameters.get(pair)
        if match.get("candidateReuseBlocked") is True:
            if explicit_evidence is not None:
                used_explicit_pairs.add(pair)
            rows.append(
                {
                    **base,
                    "state": "blocked_before_cad",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": False,
                    "candidateReuseBlocked": True,
                    "positionParameterEvidence": copy.deepcopy(explicit_evidence),
                    "blocker": copy.deepcopy(match.get("safetyBlocker") or {}),
                    "nextAction": "derive_and_review_a_different_role_station_recipe",
                }
            )
            continue
        if explicit_evidence is not None:
            reusable_pair_release = (
                match.get("pairReleaseEvidence")
                if match.get("existingPairReleaseReusable") is True
                else None
            )
            if _confirmed_position_reuses_pair_release(
                explicit_evidence, reusable_pair_release
            ):
                used_explicit_pairs.add(pair)
                rows.append(
                    {
                        **base,
                        "state": "released",
                        "readyForCadValidation": False,
                        "readyForReleasedCadExecution": True,
                        "pairReleaseEvidence": copy.deepcopy(reusable_pair_release),
                        "positionParameterEvidence": copy.deepcopy(explicit_evidence),
                        "explicitPositionParametersConfirmed": True,
                        "confirmedParametersAlreadyReleased": True,
                        "nextAction": "reuse_released_pair",
                    }
                )
                continue
            package = compile_parameterized_datum_validation_package(
                workspace,
                pair[0],
                pair[1],
                position_parameters=copy.deepcopy(
                    explicit_evidence["parametersMeters"]
                ),
            )
            used_explicit_pairs.add(pair)
            rows.append(
                {
                    **base,
                    "state": "ready_for_nonprototype_cad_validation",
                    "readyForCadValidation": True,
                    "readyForReleasedCadExecution": False,
                    "validationPackageDigest": package["packageDigest"],
                    "sourceAssemblyPath": package["sourceAssemblyPath"],
                    "moduleEndpointCatalogPath": package[
                        "moduleEndpointCatalogPath"
                    ],
                    "slotEndpointCatalogPath": package[
                        "slotEndpointCatalogPath"
                    ],
                    "positionParameters": copy.deepcopy(
                        explicit_evidence["parametersMeters"]
                    ),
                    "positionParametersOverride": copy.deepcopy(
                        explicit_evidence["parametersMeters"]
                    ),
                    "positionParameterEvidence": copy.deepcopy(explicit_evidence),
                    "positionInstructionCompilation": copy.deepcopy(
                        explicit_evidence.get("positionInstructionCompilation")
                    ),
                    "explicitPositionParametersConfirmed": True,
                    "promotedFromPositionParameterGap": False,
                    "supersedesExistingPairRelease": (
                        match.get("existingPairReleaseReusable") is True
                        or global_release is not None
                    ),
                    "nextAction": (
                        "run_nonprototype_cad_validate_save_reopen_then_publish"
                    ),
                }
            )
            continue
        if match.get("existingPairReleaseReusable") is True:
            evidence = copy.deepcopy(match.get("pairReleaseEvidence") or {})
            rows.append(
                {
                    **base,
                    "state": "released",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": True,
                    "pairReleaseEvidence": evidence,
                    "nextAction": "reuse_released_pair",
                }
            )
            continue
        if global_release is not None:
            rows.append(
                {
                    **base,
                    "state": "released",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": True,
                    "pairReleaseEvidence": copy.deepcopy(global_release),
                    "releaseSource": "immutable_global_relation_release",
                    "nextAction": "reuse_released_pair",
                }
            )
            continue
        try:
            package = compile_parameterized_datum_validation_package(
                workspace, pair[0], pair[1]
            )
        except (MechanicalInterfaceContractError, FileNotFoundError, OSError) as exc:
            rows.append(
                {
                    **base,
                    "state": "blocked_before_cad",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": False,
                    "blocker": {
                        "code": "VALIDATION_PACKAGE_COMPILATION_FAILED",
                        "detail": str(exc),
                    },
                    "nextAction": "repair_endpoint_parameter_or_source_evidence",
                }
            )
            continue
        rows.append(
            {
                **base,
                "state": "ready_for_nonprototype_cad_validation",
                "readyForCadValidation": True,
                "readyForReleasedCadExecution": False,
                "validationPackageDigest": package["packageDigest"],
                "sourceAssemblyPath": package["sourceAssemblyPath"],
                "moduleEndpointCatalogPath": package["moduleEndpointCatalogPath"],
                "slotEndpointCatalogPath": package["slotEndpointCatalogPath"],
                "positionParameters": {
                    step["mateName"]: step.get("distanceMeters")
                    for step in package["instantiatedTemplate"]["mateSteps"]
                    if step.get("distanceMeters") is not None
                },
                "nextAction": "run_nonprototype_cad_validate_save_reopen_then_publish",
            }
        )

    # F000 uses a real support/orientation/axis topology rather than three
    # planes.  Its native A000 pair remains in the contextual scanner catalog;
    # only the two cross-base axis choices belong in this validation queue.
    for slot in hybrid_catalog.get("baseSlots") or []:
        if slot.get("state") != "explicit_axis_selection_required":
            continue
        pair = (
            str(hybrid_catalog.get("moduleDefinitionId") or ""),
            str(slot.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen_pairs:
            raise MechanicalInterfaceContractError(
                f"hybrid axis pair is missing identity or duplicated: {pair}"
            )
        seen_pairs.add(pair)
        base = {
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "moduleRole": hybrid_catalog.get("moduleRole"),
            "moduleToken": hybrid_catalog.get("moduleToken"),
            "baseToken": slot.get("baseToken"),
            "crossProject": _project(pair[0]) != _project(pair[1]),
            "interfaceFamily": hybrid_catalog.get("interfaceFamily"),
            "recipeId": hybrid_catalog.get("recipeId"),
            "candidateKind": "reviewed_hybrid_plane_axis_datum",
            "proposedValidationDirectory": _directory_name(*pair),
            "physicalFasteningVerified": False,
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
            "candidateAxisLineCount": slot.get("candidateAxisLineCount"),
        }
        evidence = explicit_axes.get(pair)
        global_release = global_pair_releases.get(pair)
        released_axis = _released_hybrid_axis_endpoint(workspace, global_release)
        if released_axis and (
            evidence is None
            or str(evidence.get("selectedAxisEndpointId") or "") == released_axis
        ):
            if evidence is not None:
                used_explicit_axis_pairs.add(pair)
            rows.append(
                {
                    **base,
                    "state": "released",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": True,
                    "selectedAxisEndpointId": released_axis,
                    "pairReleaseEvidence": copy.deepcopy(global_release),
                    "releaseSource": "immutable_global_relation_release",
                    "axisSelectionEvidence": copy.deepcopy(evidence),
                    "explicitAxisSelectionConfirmed": evidence is not None,
                    "confirmedAxisAlreadyReleased": evidence is not None,
                    "nextAction": "reuse_released_pair",
                }
            )
            continue
        if evidence is None:
            rows.append(
                {
                    **base,
                    "state": "explicit_axis_selection_required",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": False,
                    "requiredAxisSelection": {
                        "selectedAxisEndpointId": "stable cylinder endpoint from the requested base",
                        "confirmed": True,
                        "source": "engineering review source",
                    },
                    "nextAction": (
                        "rank_axis_lines_by_semantic_position_then_confirm_one"
                    ),
                }
            )
            continue
        package = compile_f000_hybrid_axis_validation_package(
            workspace,
            slot_definition_id=pair[1],
            selected_axis_endpoint_id=str(evidence["selectedAxisEndpointId"]),
            evidence=evidence,
        )
        used_explicit_axis_pairs.add(pair)
        rows.append(
            {
                **base,
                "state": "ready_for_nonprototype_cad_validation",
                "readyForCadValidation": True,
                "readyForReleasedCadExecution": False,
                "validationPackageDigest": package["packageDigest"],
                "sourceAssemblyPath": package["sourceAssemblyPath"],
                "moduleEndpointCatalogPath": package["moduleEndpointCatalogPath"],
                "slotEndpointCatalogPath": package["slotEndpointCatalogPath"],
                "selectedAxisEndpointId": evidence["selectedAxisEndpointId"],
                "axisSelectionEvidence": copy.deepcopy(evidence),
                "explicitAxisSelectionConfirmed": True,
                "nextAction": (
                    "run_nonprototype_cad_validate_save_reopen_then_publish"
                ),
            }
        )

    # A000 exposes reviewable 50/58 mm cylinder-axis pairs for the already
    # released calibration and transport moving-port families.  Spacing is
    # only a candidate filter: an engineer must confirm the exact ordered pair
    # before an unpublished CAD package can be compiled.
    for family in two_axis_catalog.get("families") or []:
        for module_definition_id in family.get("moduleDefinitionIds") or []:
            pair = (
                str(module_definition_id),
                str(family.get("slotDefinitionId") or ""),
            )
            if not all(pair) or pair in seen_pairs:
                raise MechanicalInterfaceContractError(
                    f"two-axis candidate pair is missing identity or duplicated: {pair}"
                )
            seen_pairs.add(pair)
            base = {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "moduleRole": family.get("moduleRole"),
                "moduleToken": _token(pair[0]),
                "baseToken": two_axis_catalog.get("baseToken"),
                "crossProject": _project(pair[0]) != _project(pair[1]),
                "interfaceFamily": family.get("interfaceFamily"),
                "recipeId": family.get("recipeId"),
                "candidateKind": "reviewed_support_plane_two_axis_slot",
                "proposedValidationDirectory": _directory_name(*pair),
                "physicalFasteningVerified": False,
                "productionReady": False,
                "collisionOrBrep": "not_evaluated",
                "requiredAxisSpacingMeters": family.get("requiredSpacingMeters"),
                "candidateAxisPairCount": family.get("candidatePairCount"),
            }
            global_release = global_pair_releases.get(pair)
            if global_release is not None:
                if pair in explicit_axis_pairs:
                    used_explicit_two_axis_pairs.add(pair)
                rows.append(
                    {
                        **base,
                        "state": "released",
                        "readyForCadValidation": False,
                        "readyForReleasedCadExecution": True,
                        "pairReleaseEvidence": copy.deepcopy(global_release),
                        "releaseSource": "immutable_global_relation_release",
                        "axisPairSelectionEvidence": copy.deepcopy(
                            explicit_axis_pairs.get(pair)
                        ),
                        "explicitAxisPairSelectionConfirmed": (
                            pair in explicit_axis_pairs
                        ),
                        "confirmedAxisPairAlreadyReleased": (
                            pair in explicit_axis_pairs
                        ),
                        "nextAction": "reuse_released_pair",
                    }
                )
                continue
            evidence = explicit_axis_pairs.get(pair)
            if evidence is None:
                rows.append(
                    {
                        **base,
                        "state": "explicit_axis_pair_selection_required",
                        "readyForCadValidation": False,
                        "readyForReleasedCadExecution": False,
                        "requiredAxisPairSelection": {
                            "selectedCandidatePairId": (
                                "candidatePairId from the reviewed A000 catalog"
                            ),
                            "confirmed": True,
                            "source": "engineering review source",
                        },
                        "nextAction": (
                            "review_hole_purpose_and_installation_side_then_confirm_axis_pair"
                        ),
                    }
                )
                continue
            package = compile_two_axis_slot_validation_package(
                workspace,
                module_definition_id=pair[0],
                selected_candidate_pair_id=str(
                    evidence["selectedCandidatePairId"]
                ),
                evidence=evidence,
            )
            used_explicit_two_axis_pairs.add(pair)
            rows.append(
                {
                    **base,
                    "state": "ready_for_nonprototype_cad_validation",
                    "readyForCadValidation": True,
                    "readyForReleasedCadExecution": False,
                    "validationPackageDigest": package["packageDigest"],
                    "sourceAssemblyPath": (
                        package["effectiveMateGraph"]["SourceAssemblyPath"]
                    ),
                    "moduleEndpointCatalogPath": package[
                        "moduleEndpointCatalogPath"
                    ],
                    "slotEndpointCatalogPath": package[
                        "slotEndpointCatalogPath"
                    ],
                    "selectedCandidatePairId": evidence[
                        "selectedCandidatePairId"
                    ],
                    "axisPairSelectionEvidence": copy.deepcopy(evidence),
                    "explicitAxisPairSelectionConfirmed": True,
                    "nextAction": (
                        "run_nonprototype_cad_validate_save_reopen_then_publish"
                    ),
                }
            )

    for audit in two_axis_catalog.get("verifiedIncompatibilities") or []:
        pair = (
            str(audit.get("moduleDefinitionId") or ""),
            str(audit.get("slotDefinitionId") or ""),
        )
        # A reviewed three-plane fallback can later become an authenticated
        # global relation release while the historical native two-axis audit
        # remains (correctly) negative.  The release is a distinct, higher
        # priority installation strategy; do not let the old native audit
        # duplicate or override the already emitted released row.
        if pair in global_pair_releases:
            continue
        # The native 58 mm recipe remains unavailable, but an explicitly
        # confirmed three-plane port is a distinct installation strategy.
        # Leave the pair unseen so the generic loop below emits a position
        # decision instead of allowing the negative native audit to mask it.
        if pair in position_fallback_pairs:
            continue
        if not all(pair) or pair in seen_pairs:
            raise MechanicalInterfaceContractError(
                f"two-axis incompatibility is missing identity or duplicated: {pair}"
            )
        seen_pairs.add(pair)
        rows.append(
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "moduleRole": audit.get("moduleRole"),
                "moduleToken": _token(pair[0]),
                "baseToken": _token(pair[1]),
                "crossProject": _project(pair[0]) != _project(pair[1]),
                "interfaceFamily": "transport_plane_two_hole_mount/v1",
                "recipeId": "recipe/transport-plane-two-hole-rigid-mount/v1",
                "candidateKind": "authoritative_two_axis_inventory_audit",
                "physicalFasteningVerified": False,
                "productionReady": False,
                "collisionOrBrep": "not_evaluated",
                "requiredAxisSpacingMeters": audit["requiredSpacingMeters"],
                "candidateAxisLineCount": audit["candidateAxisLineCount"],
                "matchingAxisPairCount": audit["matchingAxisPairCount"],
                "state": "axis_pair_not_found_in_authoritative_catalog",
                "readyForCadValidation": False,
                "readyForReleasedCadExecution": False,
                "nextAction": audit["nextAction"],
                "claimBoundary": (
                    "No 58 mm pair exists in the current captured A600 axis inventory. "
                    "This does not prohibit a reviewed adapter, alternate interface or "
                    "newly captured mounting geometry."
                ),
            }
        )

    # G000 keeps its released flexible four-relation topology.  The target
    # base must supply a reviewed support/orientation frame and one exact
    # cylinder axis, while the longitudinal distance remains an explicit
    # engineering parameter.  This must not be degraded into three planar
    # datum mates merely to make the generic fallback accept it.
    for slot in flexible_slot_catalog.get("baseSlots") or []:
        if slot.get("state") == "released_native_pair":
            continue
        pair = (
            str(flexible_slot_catalog.get("moduleDefinitionId") or ""),
            str(slot.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen_pairs:
            raise MechanicalInterfaceContractError(
                f"G000 flexible-slot pair is missing identity or duplicated: {pair}"
            )
        seen_pairs.add(pair)
        base = {
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "moduleRole": flexible_slot_catalog.get("moduleRole"),
            "moduleToken": flexible_slot_catalog.get("moduleToken"),
            "baseToken": slot.get("baseToken"),
            "crossProject": _project(pair[0]) != _project(pair[1]),
            "interfaceFamily": flexible_slot_catalog.get("interfaceFamily"),
            "recipeId": flexible_slot_catalog.get("recipeId"),
            "candidateKind": "reviewed_flexible_calibration_slot",
            "proposedValidationDirectory": _directory_name(*pair),
            "physicalFasteningVerified": False,
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
            "candidateAxisLineCount": slot.get("candidateAxisLineCount"),
        }
        global_release = global_pair_releases.get(pair)
        if global_release is not None:
            if pair in explicit_flexible_slots:
                used_explicit_flexible_slots.add(pair)
            rows.append(
                {
                    **base,
                    "state": "released",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": True,
                    "pairReleaseEvidence": copy.deepcopy(global_release),
                    "releaseSource": "immutable_global_relation_release",
                    "flexibleSlotSelectionEvidence": copy.deepcopy(
                        explicit_flexible_slots.get(pair)
                    ),
                    "explicitFlexibleSlotSelectionConfirmed": (
                        pair in explicit_flexible_slots
                    ),
                    "confirmedFlexibleSlotAlreadyReleased": (
                        pair in explicit_flexible_slots
                    ),
                    "nextAction": "reuse_released_pair",
                }
            )
            continue
        if slot.get("state") == "flexible_slot_axis_not_found_in_authoritative_catalog":
            rows.append(
                {
                    **base,
                    "state": "flexible_slot_axis_not_found_in_authoritative_catalog",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": False,
                    "nextAction": "select_alternate_installation_strategy_or_capture_new_geometry",
                }
            )
            continue
        evidence = explicit_flexible_slots.get(pair)
        if evidence is None:
            rows.append(
                {
                    **base,
                    "state": "explicit_flexible_slot_selection_required",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": False,
                    "requiredFlexibleSlotSelection": {
                        "selectedAxisEndpointId": "stable cylinder endpoint from the requested base",
                        "longitudinalOffsetMeters": "finite non-negative metre value",
                        "confirmed": True,
                        "source": "engineering review source",
                    },
                    "nextAction": "review_axis_purpose_and_longitudinal_station_then_confirm",
                }
            )
            continue
        package = compile_g000_flexible_slot_validation_package(
            workspace,
            slot_definition_id=pair[1],
            selected_axis_endpoint_id=str(evidence["selectedAxisEndpointId"]),
            longitudinal_offset_meters=float(
                evidence["longitudinalOffsetMeters"]
            ),
            evidence=evidence,
        )
        used_explicit_flexible_slots.add(pair)
        rows.append(
            {
                **base,
                "state": "ready_for_nonprototype_cad_validation",
                "readyForCadValidation": True,
                "readyForReleasedCadExecution": False,
                "validationPackageDigest": package["packageDigest"],
                "sourceAssemblyPath": package["sourceAssemblyPath"],
                "moduleEndpointCatalogPath": package["moduleEndpointCatalogPath"],
                "slotEndpointCatalogPath": package["slotEndpointCatalogPath"],
                "selectedAxisEndpointId": evidence["selectedAxisEndpointId"],
                "longitudinalOffsetMeters": evidence[
                    "longitudinalOffsetMeters"
                ],
                "flexibleSlotSelectionEvidence": copy.deepcopy(evidence),
                "explicitFlexibleSlotSelectionConfirmed": True,
                "nextAction": "run_nonprototype_cad_validate_save_reopen_then_publish",
            }
        )

    # A registered three-plane module may be geometrically usable while still
    # lacking a model-specific station position. Keep this distinct from a
    # missing face capture and from an incompatible interface.
    for match in catalog.get("compatibilityMatrix") or []:
        blocker_codes = {
            str(item.get("code") or "") for item in match.get("blockers") or []
        }
        if blocker_codes not in (
            {"MODULE_POSITION_PRESET_MISSING"},
            {"POSITION_PARAMETERS_MISSING"},
        ):
            continue
        pair = (
            str(match.get("moduleDefinitionId") or ""),
            str(match.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen_pairs:
            continue
        module_contract = contracts.get(str(match.get("moduleContractId") or ""))
        slot_contract = contracts.get(str(match.get("slotContractId") or ""))
        if not module_contract or not slot_contract:
            raise MechanicalInterfaceContractError(
                f"parameter-required pair does not resolve contracts: {pair}"
            )
        evidence = explicit_parameters.get(pair)
        if evidence is not None:
            package = compile_parameterized_datum_validation_package(
                workspace,
                pair[0],
                pair[1],
                position_parameters=copy.deepcopy(evidence["parametersMeters"]),
            )
            seen_pairs.add(pair)
            used_explicit_pairs.add(pair)
            rows.append(
                {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "moduleRole": module_contract.get("moduleRole"),
                    "moduleToken": module_contract.get("moduleToken"),
                    "baseToken": slot_contract.get("moduleToken"),
                    "crossProject": _project(pair[0]) != _project(pair[1]),
                    "interfaceFamily": match.get("interfaceFamily"),
                    "recipeId": match.get("recipeId"),
                    "proposedValidationDirectory": _directory_name(*pair),
                    "physicalFasteningVerified": False,
                    "productionReady": False,
                    "collisionOrBrep": "not_evaluated",
                    "state": "ready_for_nonprototype_cad_validation",
                    "readyForCadValidation": True,
                    "readyForReleasedCadExecution": False,
                    "validationPackageDigest": package["packageDigest"],
                    "sourceAssemblyPath": package["sourceAssemblyPath"],
                    "moduleEndpointCatalogPath": package[
                        "moduleEndpointCatalogPath"
                    ],
                    "slotEndpointCatalogPath": package["slotEndpointCatalogPath"],
                    "positionParameters": copy.deepcopy(
                        evidence["parametersMeters"]
                    ),
                    "positionParametersOverride": copy.deepcopy(
                        evidence["parametersMeters"]
                    ),
                    "positionParameterEvidence": copy.deepcopy(evidence),
                    "positionInstructionCompilation": copy.deepcopy(
                        evidence.get("positionInstructionCompilation")
                    ),
                    "explicitPositionParametersConfirmed": True,
                    "promotedFromPositionParameterGap": True,
                    "supersedesExistingPairRelease": pair in global_pair_releases,
                    "nextAction": (
                        "run_nonprototype_cad_validate_save_reopen_then_publish"
                    ),
                }
            )
            continue
        global_release = global_pair_releases.get(pair)
        if global_release is not None:
            seen_pairs.add(pair)
            rows.append(
                {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "moduleRole": module_contract.get("moduleRole"),
                    "moduleToken": module_contract.get("moduleToken"),
                    "baseToken": slot_contract.get("moduleToken"),
                    "crossProject": _project(pair[0]) != _project(pair[1]),
                    "interfaceFamily": match.get("interfaceFamily"),
                    "recipeId": match.get("recipeId"),
                    "proposedValidationDirectory": _directory_name(*pair),
                    "physicalFasteningVerified": False,
                    "productionReady": False,
                    "collisionOrBrep": "not_evaluated",
                    "state": "released",
                    "readyForCadValidation": False,
                    "readyForReleasedCadExecution": True,
                    "pairReleaseEvidence": copy.deepcopy(global_release),
                    "releaseSource": "immutable_global_relation_release",
                    "releasedFromPositionParameterGap": True,
                    "nextAction": "reuse_released_pair",
                }
            )
            continue
        seen_pairs.add(pair)
        rows.append(
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "moduleRole": module_contract.get("moduleRole"),
                "moduleToken": module_contract.get("moduleToken"),
                "baseToken": slot_contract.get("moduleToken"),
                "crossProject": _project(pair[0]) != _project(pair[1]),
                "interfaceFamily": match.get("interfaceFamily"),
                "recipeId": match.get("recipeId"),
                "proposedValidationDirectory": _directory_name(*pair),
                "physicalFasteningVerified": False,
                "productionReady": False,
                "collisionOrBrep": "not_evaluated",
                "state": "explicit_position_parameters_required",
                "readyForCadValidation": False,
                "readyForReleasedCadExecution": False,
                "requiredPositionParameters": [
                    "longitudinal",
                    "lateral",
                    "supportGap",
                ],
                "positionParameterUnit": "metre",
                "nextAction": "confirm_three_position_parameters_then_compile_candidate",
            }
        )

    unused_explicit_pairs = sorted(set(explicit_parameters) - used_explicit_pairs)
    if unused_explicit_pairs:
        raise MechanicalInterfaceContractError(
            "explicit position parameter pair is not a supported datum combination: "
            + ", ".join(f"{module}->{slot}" for module, slot in unused_explicit_pairs)
        )
    unused_axis_pairs = sorted(set(explicit_axes) - used_explicit_axis_pairs)
    if unused_axis_pairs:
        raise MechanicalInterfaceContractError(
            "explicit axis selection pair is not a supported hybrid combination: "
            + ", ".join(
                f"{module}->{slot}" for module, slot in unused_axis_pairs
            )
        )
    unused_two_axis_pairs = sorted(
        set(explicit_axis_pairs) - used_explicit_two_axis_pairs
    )
    if unused_two_axis_pairs:
        raise MechanicalInterfaceContractError(
            "explicit axis-pair selection is not a supported two-axis combination: "
            + ", ".join(
                f"{module}->{slot}" for module, slot in unused_two_axis_pairs
            )
        )
    unused_flexible_slots = sorted(
        set(explicit_flexible_slots) - used_explicit_flexible_slots
    )
    if unused_flexible_slots:
        raise MechanicalInterfaceContractError(
            "explicit flexible-slot selection is not a supported G000 combination: "
            + ", ".join(
                f"{module}->{slot}" for module, slot in unused_flexible_slots
            )
        )

    state_rank = {
        "ready_for_nonprototype_cad_validation": 0,
        "explicit_position_parameters_required": 1,
        "explicit_axis_selection_required": 2,
        "explicit_axis_pair_selection_required": 3,
        "explicit_flexible_slot_selection_required": 4,
        "axis_pair_not_found_in_authoritative_catalog": 5,
        "flexible_slot_axis_not_found_in_authoritative_catalog": 6,
        "blocked_before_cad": 7,
        "released": 8,
    }
    rows.sort(
        key=lambda row: (
            state_rank[str(row["state"])],
            not bool(row["crossProject"]),
            str(row["moduleRole"]),
            str(row["moduleDefinitionId"]),
            str(row["slotDefinitionId"]),
        )
    )
    capture_gaps = copy.deepcopy(catalog.get("captureGaps") or [])
    confirmed_parameter_count = sum(
        row.get("explicitPositionParametersConfirmed") is True for row in rows
    )
    promoted_parameter_count = sum(
        row.get("promotedFromPositionParameterGap") is True for row in rows
    )
    released_parameter_gap_count = sum(
        row.get("releasedFromPositionParameterGap") is True for row in rows
    )
    confirmed_axis_count = sum(
        row.get("explicitAxisSelectionConfirmed") is True for row in rows
    )
    confirmed_axis_pair_count = sum(
        row.get("explicitAxisPairSelectionConfirmed") is True for row in rows
    )
    confirmed_flexible_slot_count = sum(
        row.get("explicitFlexibleSlotSelectionConfirmed") is True for row in rows
    )
    summary = {
        "listedPairCount": len(rows),
        "compatiblePairCount": int(catalog["summary"]["compatiblePairCount"]),
        "catalogCompatiblePairCount": int(
            catalog["summary"]["compatiblePairCount"]
        ),
        "effectiveCompatiblePairCount": (
            int(catalog["summary"]["compatiblePairCount"])
            + promoted_parameter_count
            + confirmed_axis_count
            + confirmed_axis_pair_count
            + confirmed_flexible_slot_count
            + released_parameter_gap_count
        ),
        "releasedPairCount": sum(row["state"] == "released" for row in rows),
        "readyForCadValidationCount": sum(
            row["state"] == "ready_for_nonprototype_cad_validation" for row in rows
        ),
        "blockedBeforeCadCount": sum(
            row["state"] == "blocked_before_cad" for row in rows
        ),
        "explicitPositionParametersRequiredCount": sum(
            row["state"] == "explicit_position_parameters_required" for row in rows
        ),
        "confirmedExplicitPositionParameterCount": confirmed_parameter_count,
        "explicitAxisSelectionRequiredCount": sum(
            row["state"] == "explicit_axis_selection_required" for row in rows
        ),
        "confirmedExplicitAxisSelectionCount": confirmed_axis_count,
        "explicitAxisPairSelectionRequiredCount": sum(
            row["state"] == "explicit_axis_pair_selection_required" for row in rows
        ),
        "confirmedExplicitAxisPairSelectionCount": confirmed_axis_pair_count,
        "explicitFlexibleSlotSelectionRequiredCount": sum(
            row["state"] == "explicit_flexible_slot_selection_required"
            for row in rows
        ),
        "confirmedExplicitFlexibleSlotSelectionCount": confirmed_flexible_slot_count,
        "axisPairNotFoundInAuthoritativeCatalogCount": sum(
            row["state"] == "axis_pair_not_found_in_authoritative_catalog"
            for row in rows
        ),
        "flexibleSlotAxisNotFoundInAuthoritativeCatalogCount": sum(
            row["state"]
            == "flexible_slot_axis_not_found_in_authoritative_catalog"
            for row in rows
        ),
        "alternateRecipeReleasedNativePairCount": int(
            catalog["summary"].get("alternateRecipeReleasedNativePairCount")
            or 0
        ),
        "crossProjectCompatiblePairCount": sum(
            row["crossProject"]
            and row["state"]
            not in {
                "explicit_position_parameters_required",
                "explicit_axis_selection_required",
                "explicit_axis_pair_selection_required",
                "explicit_flexible_slot_selection_required",
                "axis_pair_not_found_in_authoritative_catalog",
                "flexible_slot_axis_not_found_in_authoritative_catalog",
            }
            for row in rows
        ),
        "crossProjectReadyForCadValidationCount": sum(
            row["crossProject"]
            and row["state"] == "ready_for_nonprototype_cad_validation"
            for row in rows
        ),
        "crossProjectExplicitPositionParametersRequiredCount": sum(
            row["crossProject"]
            and row["state"] == "explicit_position_parameters_required"
            for row in rows
        ),
        "crossProjectExplicitAxisSelectionRequiredCount": sum(
            row["crossProject"]
            and row["state"] == "explicit_axis_selection_required"
            for row in rows
        ),
        "crossProjectExplicitAxisPairSelectionRequiredCount": sum(
            row["crossProject"]
            and row["state"] == "explicit_axis_pair_selection_required"
            for row in rows
        ),
        "crossProjectExplicitFlexibleSlotSelectionRequiredCount": sum(
            row["crossProject"]
            and row["state"] == "explicit_flexible_slot_selection_required"
            for row in rows
        ),
        "crossProjectAxisPairNotFoundInAuthoritativeCatalogCount": sum(
            row["crossProject"]
            and row["state"] == "axis_pair_not_found_in_authoritative_catalog"
            for row in rows
        ),
        "crossProjectFlexibleSlotAxisNotFoundInAuthoritativeCatalogCount": sum(
            row["crossProject"]
            and row["state"]
            == "flexible_slot_axis_not_found_in_authoritative_catalog"
            for row in rows
        ),
        "captureGapCount": len(capture_gaps),
    }
    queue = {
        "schemaVersion": QUEUE_SCHEMA,
        "sourceCatalogDigest": catalog["catalogDigest"],
        "twoAxisSlotCatalogDigest": two_axis_catalog["catalogDigest"],
        "flexibleCalibrationSlotCatalogDigest": flexible_slot_catalog[
            "catalogDigest"
        ],
        "summary": summary,
        "pairs": rows,
        "captureGaps": capture_gaps,
        "explicitPositionParameterEvidence": [
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                **copy.deepcopy(evidence),
            }
            for pair, evidence in sorted(explicit_parameters.items())
        ],
        "explicitAxisSelectionEvidence": [
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                **copy.deepcopy(evidence),
            }
            for pair, evidence in sorted(explicit_axes.items())
        ],
        "explicitAxisPairSelectionEvidence": [
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                **copy.deepcopy(evidence),
            }
            for pair, evidence in sorted(explicit_axis_pairs.items())
        ],
        "explicitFlexibleSlotSelectionEvidence": [
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                **copy.deepcopy(evidence),
            }
            for pair, evidence in sorted(explicit_flexible_slots.items())
        ],
        "executionPolicy": {
            "cadConcurrency": 1,
            "requireCleanSolidWorksSession": True,
            "candidateDoesNotAuthorizeNormalExecution": True,
            "releaseRequiresSaveCloseReopen": True,
            "releaseRequiresNonPrototypeInitialPose": True,
            "continueAfterFailure": False,
        },
        "claimBoundary": (
            "A ready row proves only that endpoints, parameters and immutable sources can be "
            "compiled. It becomes executable by normal assembly flows only after a successful "
            "non-prototype CAD run and pair release. Physical fastening, collision, B-rep and "
            "production approval remain separate."
        ),
    }
    queue["queueDigest"] = _digest(queue)
    return queue


def build_successor_parameterized_datum_validation_queue(
    workspace: Path,
    prior_queue: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild a queue after the canonical catalog advances.

    A successful exact-pair publication changes the canonical catalog digest,
    intentionally making the old queue stale.  This helper preserves only
    explicitly confirmed position/axis decisions from the authenticated parent
    queue, recomputes every pair state from the new catalog, and binds the new
    immutable queue to its parent.  It never copies CAD results or release
    authority from queue rows.
    """

    if prior_queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported prior validation queue")
    expected_prior_digest = _digest(
        {key: value for key, value in prior_queue.items() if key != "queueDigest"}
    )
    if prior_queue.get("queueDigest") != expected_prior_digest:
        raise MechanicalInterfaceContractError("prior validation queue digest mismatch")

    def evidence_map(field: str) -> dict[tuple[str, str], dict[str, Any]]:
        mapped: dict[tuple[str, str], dict[str, Any]] = {}
        for source in prior_queue.get(field) or []:
            row = copy.deepcopy(source)
            pair = (
                str(row.pop("moduleDefinitionId", "")),
                str(row.pop("slotDefinitionId", "")),
            )
            if not all(pair) or pair in mapped:
                raise MechanicalInterfaceContractError(
                    f"prior queue contains invalid or duplicate explicit evidence: {pair}"
                )
            mapped[pair] = row
        return mapped

    successor = build_parameterized_datum_validation_queue(
        workspace,
        explicit_position_parameters=evidence_map(
            "explicitPositionParameterEvidence"
        ),
        explicit_axis_selections=evidence_map("explicitAxisSelectionEvidence"),
        explicit_axis_pair_selections=evidence_map(
            "explicitAxisPairSelectionEvidence"
        ),
        explicit_flexible_slot_selections=evidence_map(
            "explicitFlexibleSlotSelectionEvidence"
        ),
    )
    prior_source_digest = str(prior_queue.get("sourceCatalogDigest") or "")
    source_catalog_advanced = (
        successor.get("sourceCatalogDigest") != prior_source_digest
    )
    prior_states = {
        (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        ): str(row.get("state") or "")
        for row in prior_queue.get("pairs") or []
    }
    successor_states = {
        (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        ): str(row.get("state") or "")
        for row in successor.get("pairs") or []
    }
    released_state_advanced = any(
        successor_states.get(pair) == "released"
        and prior_states.get(pair) != "released"
        for pair in successor_states
    )
    if not source_catalog_advanced and not released_state_advanced:
        raise MechanicalInterfaceContractError(
            "canonical datum catalog and authenticated exact-pair release state "
            "has not advanced; successor queue is unnecessary"
        )
    successor.pop("queueDigest", None)
    successor["lineage"] = {
        "parentQueueDigest": expected_prior_digest,
        "parentSourceCatalogDigest": prior_source_digest,
        "successorSourceCatalogDigest": successor["sourceCatalogDigest"],
        "reason": (
            "canonical_catalog_advanced_after_exact_pair_publication"
            if source_catalog_advanced
            else "authenticated_direct_pair_release_advanced_queue_state"
        ),
        "preservedExplicitPositionEvidenceCount": len(
            successor.get("explicitPositionParameterEvidence") or []
        ),
        "preservedExplicitAxisSelectionEvidenceCount": len(
            successor.get("explicitAxisSelectionEvidence") or []
        ),
        "preservedExplicitAxisPairSelectionEvidenceCount": len(
            successor.get("explicitAxisPairSelectionEvidence") or []
        ),
        "preservedExplicitFlexibleSlotSelectionEvidenceCount": len(
            successor.get("explicitFlexibleSlotSelectionEvidence") or []
        ),
    }
    successor["queueDigest"] = _digest(successor)
    return successor
