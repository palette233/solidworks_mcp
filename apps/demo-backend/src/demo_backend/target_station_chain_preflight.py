"""Thin, offline target-station gate for the existing staged-chain CLI.

Passing this gate is not a new CAD result. In strict mode the actual preceding
checkpoint must still match the bound read-only state immediately before run.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .goal_role_station_matched_slot_report import validate_role_station_witness
from .scanner_target_association import preflight_scanner_target_for_cumulative_chain


SCHEMA = "target-station-chain-preflight/v1"
STRICT = "target_role_station"
LEGACY = "cad_only_legacy"
KNOWN_ROLES = {"Transport", "Calibration", "Scanner", "Cleaning", "CleaningWeighing", "WasteCup"}
STATION_ROLES = {"Scanner", "Cleaning", "CleaningWeighing", "WasteCup"}
# Only unambiguous catalog categories may exempt a step or select scanner gates.
# Broad cleaning_weighing categories include WasteCup, so they grant no exemption.
CATEGORY_ROLES = {"transport": "Transport", "calibration": "Calibration", "scanner": "Scanner"}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("evidence path is missing")
    return (root / value).resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("evidence root must be an object")
    return value


def build_target_station_chain_preflight(
    workspace: Path, request: dict[str, Any], *, stage_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate the entire order before any NL context/job is materialized.

    stage_bindings are resolved by the existing immutable-release catalog, not
    guessed from display labels. Source/target use semantic project::token IDs;
    context membership uses the catalog's canonical moduleDefinitionIds.
    """
    root = workspace.resolve()
    mode = request.get("placementValidationMode", LEGACY)
    blockers: list[str] = []
    if mode not in {STRICT, LEGACY}:
        blockers.append("UNKNOWN_PLACEMENT_VALIDATION_MODE")
    files: dict[str, str] = {}

    def read_bound(value: Any) -> tuple[Path, dict[str, Any]]:
        path = _path(root, value)
        payload = _read(path)
        files[str(path)] = file_sha256(path)
        return path, payload

    rows: list[dict[str, Any]] = []
    contexts: list[str] = []
    semantic_context: list[str] = []
    context_definitions: dict[str, dict[str, Any]] = {}
    bindings_by_id = {row.get("stageId"): row for row in stage_bindings}
    if len(bindings_by_id) != len(stage_bindings):
        blockers.append("DUPLICATE_STAGE_BINDING")
    for step in request.get("steps") or []:
        stage_id = str(step.get("stageId") or "")
        binding = bindings_by_id.get(stage_id) or {}
        role = step.get("moduleRole") if isinstance(step.get("moduleRole"), str) else None
        errors: list[str] = []
        row: dict[str, Any] = {"stageId": stage_id, "moduleRole": role, "stationEvidenceRequired": mode == STRICT,
                               "targetStationValidated": False, "runtimeContextCheckRequired": False}
        if mode != STRICT:
            row.update(status="cad_only_legacy_not_station_validated", blockingReasonCodes=[])
            rows.append(row)
            continue
        if role not in KNOWN_ROLES:
            errors.append("MODULE_ROLE_MISSING_OR_UNKNOWN")
        source, target = binding.get("source"), binding.get("target")
        module_id, base_id = binding.get("moduleDefinitionId"), binding.get("baseModuleDefinitionId")
        if not all(isinstance(value, str) and value for value in (source, target, module_id, base_id)):
            errors.append("RESOLVED_MODULE_IDENTITIES_MISSING")
        if not contexts and base_id:
            contexts = [base_id]
            semantic_context = [target]
        elif contexts and contexts[0] != base_id:
            errors.append("CUMULATIVE_BASE_IDENTITY_CHANGED")
        elif semantic_context and semantic_context[0] != target:
            errors.append("CUMULATIVE_BASE_SEMANTIC_IDENTITY_CHANGED")
        prior_context = list(contexts)
        expected_context = [*prior_context, module_id] if module_id else prior_context
        expected_semantic_context = [*semantic_context, source] if source else list(semantic_context)
        row["sourceContextModuleDefinitionIds"] = prior_context
        row["contextModuleDefinitionIds"] = expected_context
        row["contextSemanticModuleIds"] = expected_semantic_context
        authoritative_role = None
        moving_definition: dict[str, Any] = {}
        try:
            release_path, release = read_bound(binding.get("releaseManifestPath"))
            if release.get("status") != "released_for_demo_relation_execution":
                errors.append("RELATION_RELEASE_NOT_EXECUTABLE")
            row["releaseManifestPath"] = str(release_path)
            row["releaseManifestSha256"] = files[str(release_path)]
            catalog_path, catalog = read_bound(release.get("releasedCatalogPath"))
            if files[str(catalog_path)] != release.get("releasedCatalogFileSha256"):
                errors.append("RELEASED_CATALOG_DIGEST_MISMATCH")
            moving_rows = [item for item in catalog.get("moduleDefinitions") or [] if item.get("moduleDefinitionId") == module_id]
            base_rows = [item for item in catalog.get("moduleDefinitions") or [] if item.get("moduleDefinitionId") == base_id]
            if len(moving_rows) != 1 or len(base_rows) != 1:
                errors.append("RELEASED_CATALOG_MODULE_IDENTITY_MISSING")
            else:
                moving_definition = moving_rows[0]
                explicit_role = moving_definition.get("moduleRole")
                authoritative_role = explicit_role if explicit_role in KNOWN_ROLES else CATEGORY_ROLES.get(moving_definition.get("category"))
                context_definitions.setdefault(base_id, base_rows[0])
                if authoritative_role is not None and role != authoritative_role:
                    errors.append("MODULE_ROLE_CONFLICTS_WITH_RELEASED_CATALOG")
        except (OSError, ValueError, TypeError) as exc:
            release = {}
            errors.append("RELATION_RELEASE_MISSING:" + str(exc))
        station_required = authoritative_role not in {"Transport", "Calibration"}
        row["stationEvidenceRequired"] = station_required
        row["authoritativeModuleRole"] = authoritative_role
        row["roleAuthority"] = "released_catalog_exact_role_or_unambiguous_category" if authoritative_role else "no_exemption_all_station_checks_required"
        row["resolvedContextDefinitions"] = [
            {"moduleDefinitionId": definition_id, "cadSourcePaths": [item.get("path") for item in context_definitions.get(definition_id, {}).get("cadSources") or [] if item.get("path")]}
            for definition_id in prior_context
        ]
        if station_required:
            evidence = step.get("stationEvidence")
            if not isinstance(evidence, dict):
                errors.append("STATION_EVIDENCE_REQUIRED")
            else:
                try:
                    cad_path, cad = read_bound(evidence.get("cadResultPath"))
                    graph_path, _ = read_bound(evidence.get("effectiveGraphPath"))
                    witness_path, witness = read_bound(evidence.get("witnessPath"))
                    result = validate_role_station_witness(
                        root, case_id=str(evidence.get("caseId") or ""), source=str(source or ""), target=str(target or ""),
                        cad_result_path=cad_path, effective_graph_path=graph_path, witness_path=witness_path,
                    )
                    row["stationValidation"] = result
                    if result.get("bindingVerified") is not True or result.get("passed") is not True:
                        errors.append("STATION_WITNESS_NOT_PASSED")
                    cad_sha = files[str(cad_path)]
                    if not any(item.get("passed") is True and item.get("fileSha256") == cad_sha
                               for item in release.get("validationEvidence") or []):
                        errors.append("RELEASE_DOES_NOT_BIND_STATION_CAD_RESULT")
                    ids = witness.get("contextModuleDefinitionIds")
                    if not isinstance(ids, list) or sorted(ids) != sorted(expected_context):
                        errors.append("STATION_WITNESS_CONTEXT_MEMBERSHIP_MISMATCH")
                    for check in (witness.get("checks") or {}).values():
                        for item in check.get("evidence") or []:
                            path = _path(root, item.get("path"))
                            files[str(path)] = file_sha256(path)
                    output = _path(root, cad.get("outputAssemblyPath"))
                    files[str(output)] = file_sha256(output)
                    state_path, state = read_bound(evidence.get("contextStatePath"))
                    if witness.get("contextStateSha256") != files[str(state_path)]:
                        errors.append("STATION_WITNESS_CONTEXT_STATE_DIGEST_MISMATCH")
                    components = (state.get("observed") or {}).get("components")
                    state_checks = state.get("checks")
                    if (state.get("success") is not True or (state.get("observed") or {}).get("readOnly") is not True
                            or not isinstance(state_checks, dict) or not state_checks or not all(value is True for value in state_checks.values())
                            or not isinstance(components, list) or len(components) != len(prior_context)):
                        errors.append("SOURCE_CONTEXT_READONLY_STATE_INVALID")
                    elif any(not isinstance(item.get("transform"), list) or len(item["transform"]) != 16 or any(
                        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                        for value in item["transform"]) for item in components):
                        errors.append("SOURCE_CONTEXT_COMPONENT_POSE_MISSING")
                    instances = witness.get("sourceContextInstances")

                    def identities(items):
                        if not isinstance(items, list) or any(not isinstance(item, dict) or not item.get("name") or not item.get("sourcePath") for item in items):
                            return None
                        pairs = [(str(item["name"]), str(item["sourcePath"]).replace("\\", "/").casefold()) for item in items]
                        return sorted(pairs) if len(set(pairs)) == len(pairs) else None

                    instance_ids, observed_ids = identities(instances), identities(components)
                    if instance_ids is None or observed_ids is None or instance_ids != observed_ids or len(instance_ids) != len(prior_context):
                        errors.append("SOURCE_CONTEXT_INSTANCE_IDENTITY_MISMATCH")
                    mapped_definitions = []
                    for component in components if isinstance(components, list) else []:
                        component_path = str(component.get("sourcePath") or "").replace("\\", "/").casefold()
                        matches = [item["moduleDefinitionId"] for item in row["resolvedContextDefinitions"] if component_path and component_path in [str(path).replace("\\", "/").casefold() for path in item["cadSourcePaths"]]]
                        if len(matches) != 1:
                            errors.append("SOURCE_CONTEXT_COMPONENT_NOT_IN_RELEASED_DEFINITIONS")
                        else:
                            mapped_definitions.append(matches[0])
                    if sorted(mapped_definitions) != sorted(prior_context):
                        errors.append("SOURCE_CONTEXT_CANONICAL_MEMBERSHIP_MISMATCH")
                    source_assembly = _path(root, state.get("assemblyPath"))
                    source_sha = file_sha256(source_assembly)
                    files[str(source_assembly)] = source_sha
                    if state.get("assemblySha256") != source_sha:
                        errors.append("SOURCE_CONTEXT_ASSEMBLY_DIGEST_MISMATCH")
                    if (not cad.get("sourceAssemblyPath") or _path(root, cad["sourceAssemblyPath"]) != source_assembly
                            or cad.get("sourceAssemblySha256Before") != source_sha or cad.get("sourceAssemblySha256After") != source_sha):
                        errors.append("STATION_CAD_SOURCE_CONTEXT_BINDING_MISMATCH")
                    row["sourceCheckpointBinding"] = {"assemblyPath": str(source_assembly), "assemblySha256": source_sha,
                                                       "contextStatePath": str(state_path), "contextStateSha256": files[str(state_path)]}
                    row["runtimeContextCheckRequired"] = True
                except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                    errors.append("STATION_EVIDENCE_UNREADABLE_OR_INCOMPLETE:" + str(exc))
            if role == "Scanner" or authoritative_role == "Scanner":
                scanner = step.get("scannerTargetEvidence")
                if not isinstance(scanner, dict):
                    errors.append("SCANNER_TARGET_EVIDENCE_REQUIRED")
                else:
                    try:
                        _, association = read_bound(scanner.get("associationPath"))
                        _, evaluation = read_bound(scanner.get("evaluationPath"))
                        planned = scanner.get("plannedComponents")
                        if not isinstance(planned, list) or sorted(item.get("moduleDefinitionId", "") for item in planned) != sorted(expected_semantic_context):
                            errors.append("SCANNER_PLANNED_CONTEXT_MEMBERSHIP_MISMATCH")
                        result = preflight_scanner_target_for_cumulative_chain(
                            evaluation=evaluation, association=association, planned_components=planned if isinstance(planned, list) else [],
                            world_frame_id=str(scanner.get("worldFrameId") or ""), allow_prototype_proxy=scanner.get("allowPrototypeProxy") is True,
                        )
                        row["scannerTargetValidation"] = result
                        if result.get("processCandidateCompileAllowed") is not True:
                            errors.append("SCANNER_TARGET_PREFLIGHT_NOT_PASSED")
                    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                        errors.append("SCANNER_TARGET_EVIDENCE_INVALID:" + str(exc))
        row["blockingReasonCodes"] = errors
        row["targetStationValidated"] = station_required and not errors
        row["status"] = "blocked_before_chain_compile" if errors else "station_evidence_preflight_passed" if station_required else "released_role_not_in_station_gate_scope"
        blockers.extend(f"{stage_id}:{error}" for error in errors)
        rows.append(row)
        contexts = expected_context
        semantic_context = expected_semantic_context
        if moving_definition:
            context_definitions[module_id] = moving_definition
    required = [row for row in rows if row["stationEvidenceRequired"]]
    core = {"schemaVersion": SCHEMA, "placementValidationMode": mode, "requestDigest": digest(request),
            "stageBindingsDigest": digest(stage_bindings), "stageBindings": stage_bindings,
            "stages": rows, "blockingReasonCodes": blockers, "readyForCadCompilation": not blockers,
            "targetStationValidated": mode == STRICT and bool(required) and not blockers,
            "status": "blocked_before_chain_compile" if blockers else "preflight_passed_not_executed" if mode == STRICT else "cad_only_legacy_not_station_validated",
            "inputFiles": [{"path": path, "sha256": value} for path, value in sorted(files.items())],
            "cadStarted": False, "liveChainStationValidationPassed": False,
            "boundary": "Offline source-context preflight only. Runtime predecessor byte identity and post-CAD placement require independent checks; no new CAD success is asserted."}
    return {**core, "preflightDigest": digest(core)}


def revalidate_target_station_preflight(workspace: Path, request: dict, preflight: dict) -> dict:
    if preflight.get("schemaVersion") != SCHEMA or preflight.get("preflightDigest") != digest({k: v for k, v in preflight.items() if k != "preflightDigest"}):
        raise ValueError("target-station preflight digest is invalid")
    if preflight.get("requestDigest") != digest(request):
        raise ValueError("target-station request changed; recompile with new evidence")
    for source in preflight.get("inputFiles") or []:
        path = _path(workspace, source.get("path"))
        if not path.is_file() or file_sha256(path) != source.get("sha256"):
            raise ValueError("target-station input evidence changed: " + str(path))
    current = build_target_station_chain_preflight(workspace, request, stage_bindings=preflight.get("stageBindings") or [])
    if current != preflight or current.get("readyForCadCompilation") is not True:
        raise ValueError("target-station preflight is stale or blocked")
    return current


def validate_stage_source_checkpoint(preflight: dict, stage_id: str, source_checkpoint: dict | None) -> None:
    """Require exact pre-add assembly bytes, not merely the same module IDs."""
    if preflight.get("placementValidationMode") != STRICT:
        return
    row = next((row for row in preflight["stages"] if row["stageId"] == stage_id), None)
    if row is None:
        raise ValueError("target-station stage binding missing")
    if not row["stationEvidenceRequired"]:
        return
    expected = row.get("sourceCheckpointBinding") or {}
    actual = source_checkpoint or {}
    if not actual.get("assemblyPath") or not actual.get("assemblySha256"):
        raise ValueError("strict station runtime source checkpoint unavailable")
    path = Path(actual["assemblyPath"]).resolve()
    if not path.is_file() or file_sha256(path) != actual["assemblySha256"] or actual["assemblySha256"] != expected.get("assemblySha256"):
        raise ValueError("strict station runtime predecessor differs from bound context state")
