"""Unified read-only planning over every registered mechanical interface catalog."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
    load_ccd_contract_catalog,
    load_native_wastecup_contract_catalog,
    load_calibration_contract_catalog,
    load_cleaning_weighing_contract_catalog,
    load_contextual_scanner_contract_catalog,
    load_contextual_transport_contract_catalog,
    load_scanner_contract_catalog,
    load_transport_contract_catalog,
    load_wastecup_contract_catalog,
    plan_from_contract_catalog,
)
from .parameterized_datum_placement import (
    load_parameterized_datum_placement_catalog,
    plan_parameterized_datum_placement,
)
from .global_relation_catalog_release import load_relation_catalog_release
from .candidate_reuse_safety_supersession import (
    candidate_reuse_safety_blocks,
    load_candidate_reuse_safety_supersessions,
    revoked_datum_release_identifiers,
)
from .relation_driving_safety import (
    assess_relation_driving_safety,
    validate_relation_driving_safety_registry,
)


REGISTRY_SCHEMA = "global-interface-contract-registry/v1"
PLAN_SCHEMA = "global-interface-contract-plan/v1"
AUTHORITY_SCHEMA = "preferred-released-interface-authority/v1"
RELATION_SAFETY_PATH = "demo/global_assembly_catalog/relation-driving-safety-v1.json"

CatalogLoader = Callable[[Path], dict[str, Any]]
CATALOG_LOADERS: tuple[tuple[str, CatalogLoader], ...] = (
    ("cleaning-weighing", load_cleaning_weighing_contract_catalog),
    ("transport", load_transport_contract_catalog),
    ("calibration", load_calibration_contract_catalog),
    ("scanner", load_scanner_contract_catalog),
    ("wastecup", load_wastecup_contract_catalog),
    ("contextual-transport", load_contextual_transport_contract_catalog),
    ("contextual-scanner", load_contextual_scanner_contract_catalog),
    ("ccd", load_ccd_contract_catalog),
    ("native-wastecup", load_native_wastecup_contract_catalog),
)


def _definition_identity_maps(
    workspace: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Bridge stable project aliases used by contracts to global CAD definition ids."""

    path = workspace / "demo/global_assembly_catalog/v1/global_module_catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8-sig"))
    alias_to_cad: dict[str, list[str]] = {}
    cad_to_alias: dict[str, list[str]] = {}
    for definition in catalog.get("moduleDefinitions") or []:
        cad_id = str(definition.get("moduleDefinitionId") or "")
        if not cad_id:
            continue
        for alias in definition.get("projectAliases") or []:
            if not isinstance(alias, dict):
                continue
            project_id = str(alias.get("projectId") or "")
            module_token = str(alias.get("moduleToken") or "")
            if not project_id or not module_token:
                continue
            contract_id = f"{project_id}::{module_token}"
            alias_to_cad.setdefault(contract_id, []).append(cad_id)
            cad_to_alias.setdefault(cad_id, []).append(contract_id)
    return (
        {key: sorted(set(value)) for key, value in alias_to_cad.items()},
        {key: sorted(set(value)) for key, value in cad_to_alias.items()},
    )


def load_registered_contract_catalogs(workspace: Path) -> list[tuple[str, dict[str, Any]]]:
    return [(key, loader(workspace)) for key, loader in CATALOG_LOADERS]


def build_global_interface_contract_registry(workspace: Path) -> dict[str, Any]:
    """Return a compact discovery index; it never starts or mutates CAD."""

    catalogs = load_registered_contract_catalogs(workspace)
    alias_to_cad, _ = _definition_identity_maps(workspace)
    modules: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    catalog_rows: list[dict[str, Any]] = []
    for key, report in catalogs:
        moving = [row for row in report["contracts"] if row.get("side") == "moving_module"]
        base_slots = [row for row in report["contracts"] if row.get("side") == "base_slot"]
        catalog_rows.append(
            {
                "catalogKey": key,
                "schemaVersion": report["schemaVersion"],
                "role": report["role"],
                "modulePortCount": len(moving),
                "baseSlotCount": len(base_slots),
            }
        )
        for contract in moving:
            modules.append(
                {
                    "catalogKey": key,
                    "moduleDefinitionId": contract["moduleDefinitionId"],
                    "cadModuleDefinitionIds": alias_to_cad.get(
                        contract["moduleDefinitionId"], []
                    ),
                    "moduleRole": contract["moduleRole"],
                    "contractId": contract["contractId"],
                    "sourcePortId": contract["sourcePortId"],
                    "interfaceFamily": contract["interfaceFamily"],
                    "recipeId": contract["recipeId"],
                }
            )
        for contract in base_slots:
            slots.append(
                {
                    "catalogKey": key,
                    "slotDefinitionId": contract["moduleDefinitionId"],
                    "cadModuleDefinitionIds": alias_to_cad.get(
                        contract["moduleDefinitionId"], []
                    ),
                    "contractId": contract["contractId"],
                    "sourcePortId": contract["sourcePortId"],
                    "acceptedModuleRoles": contract["acceptedModuleRoles"],
                    "interfaceFamily": contract["interfaceFamily"],
                    "recipeId": contract["recipeId"],
                }
            )
        for match in report["compatibilityMatrix"]:
            connections.append(
                {
                    "catalogKey": key,
                    "moduleDefinitionId": match["moduleDefinitionId"],
                    "slotDefinitionId": match["slotDefinitionId"],
                    "moduleContractId": match["moduleContractId"],
                    "slotContractId": match["slotContractId"],
                    "compatible": match["compatible"],
                    "released": match["existingPairReleaseReusable"],
                    "status": match["status"],
                    "blockers": match["blockers"],
                }
            )
    modules.sort(key=lambda row: (row["moduleDefinitionId"], row["catalogKey"]))
    slots.sort(key=lambda row: (row["slotDefinitionId"], row["catalogKey"], row["contractId"]))
    connections.sort(
        key=lambda row: (
            row["moduleDefinitionId"],
            row["slotDefinitionId"],
            row["catalogKey"],
        )
    )
    return {
        "schemaVersion": REGISTRY_SCHEMA,
        "catalogs": catalog_rows,
        "modules": modules,
        "slots": slots,
        "connections": connections,
        "summary": {
            "catalogCount": len(catalog_rows),
            "modulePortCount": len(modules),
            "baseSlotCount": len(slots),
            "candidatePairCount": len(connections),
            "compatiblePairCount": sum(row["compatible"] for row in connections),
            "releasedPairCount": sum(row["released"] for row in connections),
        },
        "boundary": (
            "The registry unifies discovery and planning only. A released pair may be compiled "
            "by the existing CAD pipeline; collision, B-rep and production certification remain "
            "separate validations."
        ),
    }


def plan_global_interface_connection(
    workspace: Path,
    module_definition_id: str,
    *,
    selected_slot_contract_id: str | None = None,
    selected_slot_definition_id: str | None = None,
) -> dict[str, Any]:
    """Resolve a module to its catalog, then reuse the catalog's fail-closed planner."""

    if selected_slot_contract_id and selected_slot_definition_id:
        raise MechanicalInterfaceContractError(
            "select a slot by contract id or definition id, not both"
        )
    requested_module_definition_id = module_definition_id
    _, cad_to_alias = _definition_identity_maps(workspace)
    resolved_module_ids = (
        cad_to_alias.get(module_definition_id, [])
        if module_definition_id.startswith("cad/")
        else [module_definition_id]
    )
    matching: list[tuple[str, dict[str, Any], str]] = []
    for key, report in load_registered_contract_catalogs(workspace):
        for resolved_module_id in resolved_module_ids:
            if any(
                row.get("side") == "moving_module"
                and row.get("moduleDefinitionId") == resolved_module_id
                for row in report["contracts"]
            ):
                matching.append((key, report, resolved_module_id))
    resolved_slot_ids = (
        cad_to_alias.get(selected_slot_definition_id, [])
        if selected_slot_definition_id
        and selected_slot_definition_id.startswith("cad/")
        else [selected_slot_definition_id]
        if selected_slot_definition_id
        else []
    )
    if len(matching) > 1 and resolved_slot_ids:
        matching = [
            (key, report, resolved_module_id)
            for key, report, resolved_module_id in matching
            if any(
                row.get("side") == "base_slot"
                and row.get("moduleDefinitionId") in resolved_slot_ids
                for row in report["contracts"]
            )
        ]
    if not matching:
        return {
            "schemaVersion": PLAN_SCHEMA,
            "moduleDefinitionId": requested_module_definition_id,
            "status": "module_not_registered",
            "readyForTemplateCompilation": False,
            "catalogCandidates": [],
            "detail": "no mechanical installation port is registered for this module",
        }
    if len(matching) != 1:
        return {
            "schemaVersion": PLAN_SCHEMA,
            "moduleDefinitionId": module_definition_id,
            "status": "needs_interface_confirmation",
            "readyForTemplateCompilation": False,
            "catalogCandidates": [key for key, _, _ in matching],
            "detail": "multiple installation ports are registered; choose an interface first",
        }

    key, report, resolved_module_definition_id = matching[0]
    requested_contract_id = selected_slot_contract_id
    if selected_slot_definition_id:
        slot_rows = [
            row
            for row in report["contracts"]
            if row.get("side") == "base_slot"
            and row.get("moduleDefinitionId") in resolved_slot_ids
        ]
        if len(slot_rows) == 1:
            requested_contract_id = slot_rows[0]["contractId"]
        elif len(slot_rows) > 1:
            # One physical base may publish several role-specific slots.  A
            # confirmed base definition is sufficient when exactly one of
            # those slots is compatible with the selected moving module.  A
            # previously released exact pair takes precedence over an
            # unpublished compatible candidate; true ambiguity still fails
            # closed and requires an explicit contract id.
            slot_ids = {row["contractId"] for row in slot_rows}
            compatible = [
                row
                for row in report.get("compatibilityMatrix") or []
                if row.get("moduleDefinitionId") == resolved_module_definition_id
                and row.get("slotContractId") in slot_ids
                and row.get("compatible") is True
            ]
            released = [
                row
                for row in compatible
                if row.get("existingPairReleaseReusable") is True
            ]
            selected_rows = released if len(released) == 1 else compatible
            if len(selected_rows) != 1:
                raise MechanicalInterfaceContractError(
                    "selected base definition has multiple compatible interface slots; "
                    "choose a slot contract explicitly"
                )
            requested_contract_id = selected_rows[0]["slotContractId"]
        else:
            raise MechanicalInterfaceContractError(
                "selected base definition is not available for this interface"
            )
    plan = plan_from_contract_catalog(
        report,
        resolved_module_definition_id,
        selected_slot_contract_id=requested_contract_id,
    )
    return {
        "schemaVersion": PLAN_SCHEMA,
        "catalogKey": key,
        "catalogSchemaVersion": report["schemaVersion"],
        "requestedModuleDefinitionId": requested_module_definition_id,
        "moduleDefinitionId": resolved_module_definition_id,
        "status": plan["status"],
        "readyForTemplateCompilation": plan["readyForTemplateCompilation"],
        "selectedMatch": plan["selectedMatch"],
        "instantiatedTemplate": plan["instantiatedTemplate"],
        "candidates": plan["candidates"],
        "catalogPlan": plan,
    }


def _is_datum_plan(plan: dict[str, Any] | None) -> bool:
    """The legacy wastecup catalog also contains non-fastening datum recipes."""

    selected = (plan or {}).get("selectedMatch") or {}
    template = (plan or {}).get("instantiatedTemplate") or {}
    policy = (template.get("constraintEffect") or {}).get(
        "supportPositionDemoPolicy"
    ) or {}
    return (
        selected.get("interfaceFamily") == "support_plane_two_offset_position/v1"
        or (plan or {}).get("placementMode")
        == "reviewed_hybrid_plane_axis_datum"
        or policy.get("mode")
        in {
            "parameterized_datum_placement",
            "reviewed_hybrid_plane_axis_datum",
        }
    )


def _plan_datum_connection_with_identity(
    workspace: Path,
    module_definition_id: str,
    *,
    selected_slot_definition_id: str | None = None,
) -> dict[str, Any]:
    """Resolve global CAD identities without choosing an arbitrary project alias."""

    _, cad_to_alias = _definition_identity_maps(workspace)
    module_ids = (
        cad_to_alias.get(module_definition_id, [])
        if module_definition_id.startswith("cad/")
        else [module_definition_id]
    )
    slot_ids = (
        cad_to_alias.get(selected_slot_definition_id, [])
        if selected_slot_definition_id and selected_slot_definition_id.startswith("cad/")
        else [selected_slot_definition_id]
    )
    report = load_parameterized_datum_placement_catalog(workspace)
    known_modules = {
        row["moduleDefinitionId"]
        for row in report["contracts"]
        if row.get("side") == "moving_module"
    } | {
        row["moduleDefinitionId"]
        for row in report.get("captureGaps") or []
    } | {
        row["moduleDefinitionId"]
        for row in report.get("alternateRecipeCandidates") or []
    }
    candidates = [
        plan_parameterized_datum_placement(
            workspace, module_id, selected_slot_definition_id=slot_id
        )
        for module_id in module_ids
        if module_id in known_modules
        for slot_id in slot_ids
    ]
    available = [
        row for row in candidates
        if row.get("status") not in {"module_not_registered", "datum_slot_not_registered_for_role"}
    ]
    if len(available) == 1:
        return {
            **available[0],
            "requestedModuleDefinitionId": module_definition_id,
            "requestedSlotDefinitionId": selected_slot_definition_id,
        }
    if len(available) > 1 or len(candidates) > 1:
        return {
            "status": "needs_interface_confirmation",
            "readyForTemplateCompilation": False,
            "readyForReleasedCadExecution": False,
            "moduleDefinitionId": module_definition_id,
            "selectedSlotDefinitionId": selected_slot_definition_id,
            "detail": "multiple project aliases match datum ports; choose an interface explicitly",
        }
    if candidates:
        return candidates[0]
    return {
        "status": "module_not_registered",
        "readyForTemplateCompilation": False,
        "readyForReleasedCadExecution": False,
        "moduleDefinitionId": module_definition_id,
        "selectedSlotDefinitionId": selected_slot_definition_id,
    }


def plan_preferred_interface_connection(
    workspace: Path,
    module_definition_id: str,
    *,
    selected_slot_definition_id: str,
    allow_datum_fallback: bool = True,
) -> dict[str, Any]:
    """Apply native/alternate mechanics first, then the explicit datum fallback.

    A datum candidate is never promoted to released CAD execution here.  The
    exact module/base pair must still pass a non-prototype CAD run and receive
    an immutable pair release.
    """

    native_error: str | None = None
    try:
        native = plan_global_interface_connection(
            workspace,
            module_definition_id,
            selected_slot_definition_id=selected_slot_definition_id,
        )
    except MechanicalInterfaceContractError as exc:
        native = None
        native_error = str(exc)
    selected = (native or {}).get("selectedMatch") or {}
    if (
        selected.get("compatible") is True
        and selected.get("existingPairReleaseReusable") is True
        and not _is_datum_plan(native)
    ):
        return {
            "schemaVersion": "preferred-interface-plan/v1",
            "status": "released_native_or_alternate_interface_ready",
            "selectedMode": "mechanical_interface",
            "readyForReleasedCadExecution": True,
            "nativePlan": native,
            "datumFallbackPlan": None,
            "decisionPolicy": [
                "native_mechanical_interface",
                "confirmed_alternate_mechanical_slot",
                "parameterized_datum_placement",
                "adapter_or_manual_resolution",
            ],
        }
    if not allow_datum_fallback:
        return {
            "schemaVersion": "preferred-interface-plan/v1",
            "status": "native_interface_unavailable_datum_fallback_disabled",
            "selectedMode": None,
            "readyForReleasedCadExecution": False,
            "nativePlan": native,
            "nativeError": native_error,
            "datumFallbackPlan": None,
        }
    # The older P000 support-position release is already in the unified
    # registry. Preserve it, but never label its datum recipe a native joint.
    if (
        _is_datum_plan(native)
        and selected.get("compatible") is True
        and selected.get("existingPairReleaseReusable") is True
    ):
        fallback = {
            **native,
            "status": "released_datum_placement_ready",
            "readyForReleasedCadExecution": True,
            "physicalFasteningVerified": False,
            "productionReady": False,
        }
    else:
        fallback = _plan_datum_connection_with_identity(
            workspace,
            module_definition_id,
            selected_slot_definition_id=selected_slot_definition_id,
        )
    return {
        "schemaVersion": "preferred-interface-plan/v1",
        "status": fallback["status"],
        "selectedMode": (
            "parameterized_datum_placement"
            if fallback.get("readyForTemplateCompilation") is True
            else None
        ),
        "readyForReleasedCadExecution": fallback.get(
            "readyForReleasedCadExecution", False
        ),
        "nativePlan": native,
        "nativeError": native_error,
        "datumFallbackPlan": fallback,
        "decisionPolicy": [
            "native_mechanical_interface",
            "confirmed_alternate_mechanical_slot",
            "parameterized_datum_placement",
            "adapter_or_manual_resolution",
        ],
    }


def _release_manifest_matches_pair_evidence(
    manifest: dict[str, Any], pair_evidence: dict[str, Any]
) -> bool:
    """Match ordinary releases and embedded exact-pair evidence bindings."""

    release_id = str(pair_evidence.get("releaseId") or "")
    release_digest = str(pair_evidence.get("releaseDigest") or "")
    metadata = manifest.get("releaseMetadata") or {}
    bindings = [
        metadata.get("parameterizedDatumPairBinding") or {},
        metadata.get("directInterfacePairBinding") or {},
    ]
    return bool(
        (release_id and manifest.get("releaseId") == release_id)
        or (release_digest and manifest.get("releaseDigest") == release_digest)
        or any(
            (release_id and binding.get("releaseId") == release_id)
            or (release_digest and binding.get("releaseDigest") == release_digest)
            for binding in bindings
        )
    )


def _released_template_safety_blockers(
    workspace: Path, template_ids: list[str] | set[str]
) -> list[dict[str, Any]]:
    """Apply the runtime revocation layer before returning CAD authority."""

    path = workspace / RELATION_SAFETY_PATH
    if not path.is_file():
        return []
    registry = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_relation_driving_safety_registry(registry)
    blockers: list[dict[str, Any]] = []
    for template_id in sorted(set(template_ids)):
        assessment = assess_relation_driving_safety(
            template_id, registry=registry
        )
        blockers.extend(assessment.get("blockers") or [])
    return blockers


def resolve_preferred_released_interface_authority(
    workspace: Path,
    module_definition_id: str,
    *,
    selected_slot_definition_id: str,
    allow_datum_fallback: bool = False,
) -> dict[str, Any]:
    """Resolve one confirmed module/base pair to its immutable release authority.

    This is the bridge between interface planning and the staged natural-language
    executor.  It never starts CAD.  Datum placement stays opt-in, and a released
    pair must map to exactly one immutable relation-catalog manifest.
    """

    preferred = plan_preferred_interface_connection(
        workspace,
        module_definition_id,
        selected_slot_definition_id=selected_slot_definition_id,
        allow_datum_fallback=allow_datum_fallback,
    )
    selected_mode = preferred.get("selectedMode")
    ready = preferred.get("readyForReleasedCadExecution") is True
    if not ready or selected_mode not in {
        "mechanical_interface",
        "parameterized_datum_placement",
    }:
        # A reviewed alternate slot may be published as an exact direct
        # mechanical interface before it is folded into a static role catalog.
        # The immutable release itself is sufficient authority for that exact
        # pair; it must never authorize a neighbouring or merely similar pair.
        release_root = workspace / "demo/global_assembly_catalog/releases"
        direct_matches: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
        for path in sorted(release_root.glob("*/release-manifest.json")):
            try:
                _, manifest = load_relation_catalog_release(
                    path, workspace_root=workspace
                )
            except (OSError, ValueError, MechanicalInterfaceContractError):
                continue
            pair = (manifest.get("releaseMetadata") or {}).get(
                "directInterfacePairBinding"
            ) or {}
            if (
                pair.get("moduleDefinitionId") == module_definition_id
                and pair.get("slotDefinitionId") == selected_slot_definition_id
                and pair.get("nonPrototypeCadValidated") is True
                and pair.get("directMechanicalInterfaceCompatible") is True
            ):
                direct_matches.append((path, manifest, pair))
        if len(direct_matches) == 1:
            path, manifest, pair = direct_matches[0]
            relative_path = path.resolve().relative_to(workspace.resolve())
            safety_blockers = _released_template_safety_blockers(
                workspace,
                set((manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []),
            )
            if safety_blockers:
                return {
                    "schemaVersion": AUTHORITY_SCHEMA,
                    "status": "released_driving_template_revoked",
                    "ready": False,
                    "moduleDefinitionId": module_definition_id,
                    "slotDefinitionId": selected_slot_definition_id,
                    "allowDatumFallback": allow_datum_fallback,
                    "releaseManifestPath": relative_path.as_posix(),
                    "safetyBlockers": safety_blockers,
                    "preferredPlan": preferred,
                }
            return {
                "schemaVersion": AUTHORITY_SCHEMA,
                "status": "released_exact_direct_interface_authority_ready",
                "ready": True,
                "moduleDefinitionId": module_definition_id,
                "slotDefinitionId": selected_slot_definition_id,
                "allowDatumFallback": allow_datum_fallback,
                "selectedMode": "mechanical_interface",
                "relationExecutionMode": "direct_installation",
                "releaseManifestPath": relative_path.as_posix(),
                "pairReleaseEvidence": pair,
                "preferredPlan": preferred,
                "boundary": (
                    "An authenticated exact-pair direct release supplies authority "
                    "while the reviewed alternate slot is not yet represented by a "
                    "static role catalog. No other pair inherits this authority; "
                    "fastening, collision/B-rep and production approval are excluded."
                ),
            }
        # Reviewed hybrid/flexible datum families are intentionally kept out
        # of the static three-plane contract catalog.  Their immutable exact-
        # pair relation release is still valid opt-in datum authority for that
        # pair, provided the caller explicitly allowed datum fallback.
        datum_matches: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
        if allow_datum_fallback:
            revoked_pair_release_ids, revoked_relation_release_ids = (
                revoked_datum_release_identifiers(workspace)
            )
            candidate_blocks = candidate_reuse_safety_blocks(workspace)
            safety_supersessions = load_candidate_reuse_safety_supersessions(
                workspace
            )
            for path in sorted(release_root.glob("*/release-manifest.json")):
                try:
                    _, manifest = load_relation_catalog_release(
                        path, workspace_root=workspace
                    )
                except (OSError, ValueError, MechanicalInterfaceContractError):
                    continue
                pair = (manifest.get("releaseMetadata") or {}).get(
                    "parameterizedDatumPairBinding"
                ) or {}
                pair_identity = (
                    str(pair.get("moduleDefinitionId") or ""),
                    str(pair.get("slotDefinitionId") or ""),
                )
                block = candidate_blocks.get(pair_identity)
                replacement = safety_supersessions.get(pair_identity)
                exact_replacement_authorized = block is None or bool(
                    replacement
                    and replacement.get("replacesSafetyReasonCode")
                    == block.get("reasonCode")
                    and replacement.get("pairReleaseId")
                    == pair.get("releaseId")
                    and replacement.get("relationReleaseId")
                    == manifest.get("releaseId")
                )
                if (
                    manifest.get("releaseId") not in revoked_relation_release_ids
                    and pair.get("releaseId") not in revoked_pair_release_ids
                    and exact_replacement_authorized
                    and pair.get("moduleDefinitionId") == module_definition_id
                    and pair.get("slotDefinitionId") == selected_slot_definition_id
                    and pair.get("nonPrototypeCadValidated") is True
                    and pair.get("prototypeTopLevelTargetPoseUsed") is False
                    and pair.get("caseAnchorUsed") is False
                ):
                    datum_matches.append((path, manifest, pair))
        if len(datum_matches) == 1:
            path, manifest, pair = datum_matches[0]
            relative_path = path.resolve().relative_to(workspace.resolve())
            safety_blockers = _released_template_safety_blockers(
                workspace,
                set((manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []),
            )
            if safety_blockers:
                return {
                    "schemaVersion": AUTHORITY_SCHEMA,
                    "status": "released_driving_template_revoked",
                    "ready": False,
                    "moduleDefinitionId": module_definition_id,
                    "slotDefinitionId": selected_slot_definition_id,
                    "allowDatumFallback": True,
                    "releaseManifestPath": relative_path.as_posix(),
                    "safetyBlockers": safety_blockers,
                    "preferredPlan": preferred,
                }
            return {
                "schemaVersion": AUTHORITY_SCHEMA,
                "status": "released_exact_datum_interface_authority_ready",
                "ready": True,
                "moduleDefinitionId": module_definition_id,
                "slotDefinitionId": selected_slot_definition_id,
                "allowDatumFallback": True,
                "selectedMode": "parameterized_datum_placement",
                "relationExecutionMode": "datum_placement_demo",
                "releaseManifestPath": relative_path.as_posix(),
                "pairReleaseEvidence": pair,
                "preferredPlan": preferred,
                "boundary": (
                    "An authenticated exact-pair reviewed datum release supplies "
                    "opt-in CAD placement authority while its specialized interface "
                    "family remains outside the static three-plane catalog. No other "
                    "pair inherits this authority; fastening, collision/B-rep and "
                    "production approval are excluded."
                ),
            }
        return {
            "schemaVersion": AUTHORITY_SCHEMA,
            "status": preferred.get("status") or "released_authority_unavailable",
            "ready": False,
            "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": selected_slot_definition_id,
            "allowDatumFallback": allow_datum_fallback,
            "preferredPlan": preferred,
        }

    selected_plan = (
        preferred.get("datumFallbackPlan")
        if selected_mode == "parameterized_datum_placement"
        else preferred.get("nativePlan")
    ) or {}
    selected_match = selected_plan.get("selectedMatch") or {}
    pair_evidence = selected_match.get("pairReleaseEvidence") or {}
    if not pair_evidence:
        return {
            "schemaVersion": AUTHORITY_SCHEMA,
            "status": "released_pair_evidence_missing",
            "ready": False,
            "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": selected_slot_definition_id,
            "allowDatumFallback": allow_datum_fallback,
            "preferredPlan": preferred,
        }

    release_root = workspace / "demo/global_assembly_catalog/releases"
    matches: list[Path] = []
    for path in sorted(release_root.glob("*/release-manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if _release_manifest_matches_pair_evidence(manifest, pair_evidence):
            matches.append(path)
    if len(matches) != 1:
        return {
            "schemaVersion": AUTHORITY_SCHEMA,
            "status": (
                "released_manifest_not_found"
                if not matches
                else "released_manifest_not_unique"
            ),
            "ready": False,
            "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": selected_slot_definition_id,
            "allowDatumFallback": allow_datum_fallback,
            "matchingReleaseManifestPaths": [str(path) for path in matches],
            "preferredPlan": preferred,
        }

    manifest_path = matches[0]
    catalog, authenticated_manifest = load_relation_catalog_release(manifest_path, workspace_root=workspace)
    aliases, _ = _definition_identity_maps(workspace)
    source_ids = set(aliases.get(module_definition_id, [module_definition_id]))
    base_ids = set(aliases.get(selected_slot_definition_id, [selected_slot_definition_id]))
    owners = {p.get("globalPortId"): p.get("moduleDefinitionId") for p in catalog.get("semanticPorts", [])}
    authorized = set((authenticated_manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or [])
    exact_templates = []
    for template in catalog.get("connectionTemplates", []):
        if template.get("globalTemplateId") not in authorized:
            continue
        a = {owners.get(p) for p in template.get("candidatePortIdsA", [])}
        b = {owners.get(p) for p in template.get("candidatePortIdsB", [])}
        if (a & source_ids and b & base_ids) or (b & source_ids and a & base_ids):
            exact_templates.append(template["globalTemplateId"])
    if not exact_templates:
        return {
            "schemaVersion": AUTHORITY_SCHEMA, "status": "released_pair_driving_template_missing",
            "ready": False, "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": selected_slot_definition_id, "allowDatumFallback": allow_datum_fallback,
            "releaseManifestPath": manifest_path.resolve().relative_to(workspace.resolve()).as_posix(),
            "preferredPlan": preferred,
        }
    safety_blockers = _released_template_safety_blockers(
        workspace, set(exact_templates)
    )
    if safety_blockers:
        return {
            "schemaVersion": AUTHORITY_SCHEMA,
            "status": "released_driving_template_revoked",
            "ready": False,
            "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": selected_slot_definition_id,
            "allowDatumFallback": allow_datum_fallback,
            "releaseManifestPath": manifest_path.resolve().relative_to(
                workspace.resolve()
            ).as_posix(),
            "safetyBlockers": safety_blockers,
            "preferredPlan": preferred,
        }
    relative_path = manifest_path.resolve().relative_to(workspace.resolve())
    execution_mode = (
        "datum_placement_demo"
        if selected_mode == "parameterized_datum_placement"
        else "direct_installation"
    )
    return {
        "schemaVersion": AUTHORITY_SCHEMA,
        "status": "released_interface_authority_ready",
        "ready": True,
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": selected_slot_definition_id,
        "allowDatumFallback": allow_datum_fallback,
        "selectedMode": selected_mode,
        "relationExecutionMode": execution_mode,
        "releaseManifestPath": relative_path.as_posix(),
        "pairReleaseEvidence": pair_evidence,
        "preferredPlan": preferred,
        "boundary": (
            "This authority selects an already released module/base pair. Datum "
            "placement remains explicitly opted in; collision, B-rep and actual "
            "fastening are not evaluated."
        ),
    }


def assess_global_assembly_context_interfaces(
    workspace: Path,
    context: dict[str, Any],
    *,
    relation_execution_mode: str | None = None,
) -> dict[str, Any]:
    """Check every planned context edge against the unified contract registry.

    This is a read-only CAD-start gate. It does not replace the released relation
    graph; it verifies that each graph edge also has a compatible mechanical
    module-port/base-slot contract.
    """

    mode = str(relation_execution_mode or "direct_installation").strip()
    if mode not in {"direct_installation", "datum_placement_demo"}:
        raise MechanicalInterfaceContractError(f"unsupported relation execution mode: {mode}")
    allow_datum = mode == "datum_placement_demo"
    instances = {
        str(row.get("instanceId") or ""): row
        for row in context.get("instances") or []
        if row.get("instanceId")
    }
    rows: list[dict[str, Any]] = []
    for connection in context.get("connections") or []:
        connection_id = str(connection.get("connectionId") or "")
        instance_a = instances.get(str(connection.get("instanceAId") or ""))
        instance_b = instances.get(str(connection.get("instanceBId") or ""))
        if not instance_a or not instance_b:
            rows.append(
                {
                    "connectionId": connection_id,
                    "status": "invalid_context_edge",
                    "ready": False,
                    "detail": "connection references an unknown instance",
                }
            )
            continue
        definition_a = str(instance_a.get("moduleDefinitionId") or "")
        definition_b = str(instance_b.get("moduleDefinitionId") or "")
        orientation: tuple[str, str] | None = None
        for moving_id, slot_id in ((definition_a, definition_b), (definition_b, definition_a)):
            discovery = plan_global_interface_connection(workspace, moving_id)
            if allow_datum and discovery.get("status") == "module_not_registered":
                discovery = _plan_datum_connection_with_identity(workspace, moving_id)
            if discovery.get("status") != "module_not_registered":
                orientation = (moving_id, slot_id)
                break
        if orientation is None:
            rows.append(
                {
                    "connectionId": connection_id,
                    "status": "module_interface_not_registered",
                    "ready": False,
                    "moduleDefinitionIds": [definition_a, definition_b],
                    "detail": "neither endpoint has a registered moving-module installation port",
                }
            )
            continue
        moving_id, slot_id = orientation
        try:
            if allow_datum:
                preferred = plan_preferred_interface_connection(
                    workspace, moving_id,
                    selected_slot_definition_id=slot_id,
                    allow_datum_fallback=True,
                )
                plan = preferred.get("datumFallbackPlan") or preferred.get("nativePlan") or {}
                selected_mode = preferred.get("selectedMode")
            else:
                plan = plan_global_interface_connection(
                    workspace,
                    moving_id,
                    selected_slot_definition_id=slot_id,
                )
                selected_mode = (
                    "parameterized_datum_placement"
                    if _is_datum_plan(plan)
                    else "mechanical_interface"
                )
        except MechanicalInterfaceContractError as exc:
            rows.append(
                {
                    "connectionId": connection_id,
                    "status": "slot_interface_not_registered",
                    "ready": False,
                    "movingModuleDefinitionId": moving_id,
                    "slotModuleDefinitionId": slot_id,
                    "detail": str(exc),
                }
            )
            continue
        selected = plan.get("selectedMatch") or {}
        released = selected.get("existingPairReleaseReusable") is True
        compatible = selected.get("compatible") is True
        datum_requires_confirmation = _is_datum_plan(plan) and not allow_datum
        rows.append(
            {
                "connectionId": connection_id,
                "status": (
                    "explicit_datum_mode_required"
                    if datum_requires_confirmation
                    else "released_datum_placement_ready"
                    if compatible and released and selected_mode == "parameterized_datum_placement"
                    else "released_interface_ready"
                    if compatible and released
                    else "compatible_pair_requires_cad_release"
                    if compatible
                    else "mechanically_incompatible"
                ),
                "ready": compatible and released and not datum_requires_confirmation,
                "selectedMode": selected_mode,
                "relationExecutionMode": mode,
                "movingModuleDefinitionId": moving_id,
                "slotModuleDefinitionId": slot_id,
                "catalogKey": plan.get("catalogKey"),
                "selectedMatch": selected,
                "instantiatedTemplate": plan.get("instantiatedTemplate"),
            }
        )
    ready_count = sum(row.get("ready") is True for row in rows)
    return {
        "schemaVersion": "global-interface-context-preflight/v1",
        "contextId": context.get("contextId"),
        "relationExecutionMode": mode,
        "status": "ready" if rows and ready_count == len(rows) else "blocked",
        "cadStarted": False,
        "connectionCount": len(rows),
        "readyConnectionCount": ready_count,
        "blockedConnectionCount": len(rows) - ready_count,
        "connections": rows,
        "boundary": (
            "This preflight checks mechanical interface contracts and released pair evidence. "
            "Collision, B-rep, process reach and production certification are not evaluated."
        ),
    }
