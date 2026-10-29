"""Data-driven, read-only scanner rules bound to an exact saved current state.

Paths in rules are repository-relative, not relative to the rule file. A rule
selects evidence, never a placement or a CAD authority. Every current instance
is matched by its reference source file; repeated instances require selectors.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from .scanner_target_association import (
    _digest, _path, bind_scanner_target_to_current_context,
    build_scanner_target_association, evaluate_scanner_target_in_current_context,
    preflight_scanner_target_for_cumulative_chain,
)

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RULE = "data/assembly_stations/scanner-ai00-ss00-aa00-v1.json"
RULE_SCHEMA = "scanner-target-rule/v1"
ROLES = {"scanner": "sourceModuleDefinitionId", "transport": "transportModuleDefinitionId",
         "targetBase": "targetBaseDefinitionId"}
GRAPH_INPUTS = {"scanner": "scannerGraphPath", "transport": "transportGraphPath",
                "targetBase": "targetBaseGraphPath"}


def _read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _definition(value: str) -> tuple[str, str]:
    parts = str(value or "").split("::")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Expected exact project::module definition identity")
    return parts[0], parts[1]


def _module(graph: dict, definition: str) -> dict:
    _, token = _definition(definition)
    rows = [row for row in graph.get("Modules") or []
            if str(row.get("ModuleToken") or "").upper().endswith(token.upper())]
    if len(rows) != 1 or not rows[0].get("Path") or not rows[0].get("HierarchyPath"):
        raise ValueError(f"Ambiguous or missing reference module {definition}")
    return rows[0]


def _pointer(value: dict, pointer: str):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Optical measurement requires an explicit JSON pointer")
    try:
        for key in pointer.split("/")[1:]:
            key = key.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
    except (KeyError, ValueError, IndexError, TypeError) as exc:
        raise ValueError("Optical measurement pointer does not resolve") from exc
    if not isinstance(value, dict):
        raise ValueError("Optical measurement pointer must select one measurement")
    return deepcopy(value)


def build_current_scanner_target(
    *, state_path: Path | str, authorize_prototype_estimate: bool = False,
    rule_path: Path | str | None = None, rule: dict | None = None,
    instance_selectors: dict[str, str] | None = None,
    repository_root: Path | str | None = None,
) -> dict:
    """Recompute one rule against saved CAD poses without opening CAD.

Required rule inputs: processEvidencePath, scannerGraphPath,
transportGraphPath, targetFaceCatalogPath, targetBaseGraphPath. Optional
inputSha256 pins those files. Optional opticalMeasurementSelector selects a
specific measured optical head from opticalGeometryPath via jsonPointer;
module identity/part membership and scanner model are checked before reuse.
Selectors are role -> exact observed component name; no nearest-pose fallback.
"""
    started = time.perf_counter()
    root = Path(repository_root or ROOT).resolve()
    if rule is not None and rule_path is not None:
        raise ValueError("Provide rule or rule_path, not both")
    rule_evidence = None
    if rule is None:
        resolved_rule = (root / (rule_path or DEFAULT_RULE)).resolve()
        rule, sha = _read(resolved_rule)
        rule_evidence = {"path": str(resolved_rule), "sha256": sha}
    rule = deepcopy(rule)
    if rule.get("schemaVersion") != RULE_SCHEMA or not rule.get("ruleId"):
        raise ValueError("Unsupported or unnamed scanner target rule")
    definitions = {role: rule.get(key) for role, key in ROLES.items()}
    for definition in [*definitions.values(), rule.get("referenceBaseDefinitionId")]:
        _definition(definition)
    inputs, evidence = {}, {}
    required = {*GRAPH_INPUTS.values(), "processEvidencePath", "targetFaceCatalogPath"}
    if not required.issubset(rule.get("inputs") or {}):
        raise ValueError("Scanner rule is missing reference input paths")
    for key, relative in rule["inputs"].items():
        path = (root / relative).resolve()
        value, sha = _read(path)
        expected = (rule.get("inputSha256") or {}).get(key)
        if expected is not None and expected != sha:
            raise ValueError(f"Scanner rule input hash changed: {key}")
        inputs[key], evidence[key] = value, {"path": str(path), "sha256": sha}
    reference_modules = {role: _module(inputs[GRAPH_INPUTS[role]], definition)
                         for role, definition in definitions.items()}
    process = deepcopy(inputs["processEvidencePath"])
    transport = process.get("targetTransport") or {}
    if f"{transport.get('projectId')}::{transport.get('moduleToken')}" != definitions["transport"]:
        raise ValueError("Different transport module needs its own process geometry")
    if _definition(rule["referenceBaseDefinitionId"])[0] != transport.get("projectId"):
        raise ValueError("Reference base must belong to the measured transport frame")
    optical = None
    selector = rule.get("opticalMeasurementSelector")
    if selector is not None:
        optical_report = inputs.get("opticalGeometryPath") or {}
        optical = _pointer(optical_report, selector.get("jsonPointer"))
        project, token = _definition(definitions["scanner"])
        if optical_report.get("projectId") != project or not str(optical.get("componentName", "")).startswith(
            reference_modules["scanner"]["HierarchyPath"] + "/"):
            raise ValueError("Optical head does not belong to the reference scanner module")
        # A model-specific working range cannot be transferred to another model.
        model = selector.get("scannerModel")
        distance = (process.get("readOnlyChecks") or {}).get("workingDistanceRangeEvidence") or {}
        model_token = str(model or "").rsplit(" ", 1)[-1]
        if not model or model != optical_report.get("scannerModel") or not re.search(
            r"(?<![A-Za-z0-9_-])" + re.escape(model_token) + r"(?![A-Za-z0-9_-])", str(distance.get("authority", ""))):
            raise ValueError("Scanner model does not match working-distance evidence")
        process["sourceScanner"] = {"projectId": project, "moduleToken": token,
            "opticalOriginWorldMeters": optical.get("opticalOriginWorldMeters"),
            "opticalDirectionWorld": optical.get("opticalDirectionWorld"),
            "cadBeamEndpointProxyWorldMeters": optical.get("targetProxyWorldMeters")}
    scanner = process.get("sourceScanner") or {}
    if f"{scanner.get('projectId')}::{scanner.get('moduleToken')}" != definitions["scanner"]:
        raise ValueError("Different scanner module needs its own process geometry")
    reference = build_scanner_target_association(
        prior_process_evidence=process, scanner_graph=inputs["scannerGraphPath"],
        target_transport_graph=inputs["transportGraphPath"], target_face_catalog=inputs["targetFaceCatalogPath"],
        scanner_module_token=_definition(definitions["scanner"])[1],
        transport_module_token=_definition(definitions["transport"])[1],
        target_base_module_token=_definition(rule["referenceBaseDefinitionId"])[1],
        prototype_estimate_authorized=authorize_prototype_estimate, scanner_optical_evidence=optical,
    )
    reference.pop("associationDigest")
    reference["ruleBinding"] = {"ruleId": rule["ruleId"], "ruleDigest": _digest(rule),
                                "ruleEvidence": rule_evidence, "sourceEvidenceIndex": evidence,
                                "opticalMeasurementSelector": deepcopy(selector)}
    reference["associationDigest"] = _digest(reference)
    state_path = (root / state_path).resolve()
    state, state_sha = _read(state_path)
    observed = state.get("observed") or {}
    if state.get("success") is not True or observed.get("readOnly") is not True:
        raise ValueError("A successful read-only current CAD state is required")
    assembly = (root / state["assemblyPath"]).resolve()
    if not state.get("assemblySha256") or _file_hash(assembly) != state["assemblySha256"]:
        raise ValueError("Current state assembly hash changed")
    selectors = {**(rule.get("instanceSelectors") or {}), **(instance_selectors or {})}
    if set(selectors) - set(ROLES) or any(not isinstance(v, str) or not v for v in selectors.values()):
        raise ValueError("Instance selectors must map scanner/transport/targetBase to exact names")
    observed_components = observed.get("components") or []
    components, selection = [], {}
    for role, definition in definitions.items():
        matches = [row for row in observed_components if _path(row.get("sourcePath")) ==
                   _path(reference_modules[role]["Path"])]
        if role in selectors:
            matches = [row for row in matches if row.get("name") == selectors[role]]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one current {definition} source-part instance; "
                             f"{len(matches)} matches; provide an explicit {role} instance selector")
        row = matches[0]
        if not row.get("name") or sum(r.get("name") == row["name"] for r in observed_components) != 1:
            raise ValueError("Current component names must resolve uniquely")
        expected_config = (rule.get("configurations") or {}).get(role)
        if expected_config is not None and row.get("configuration") != expected_config:
            raise ValueError(f"Current {role} configuration does not match the rule")
        components.append({"instanceId": row["name"], "moduleDefinitionId": definition,
                           "transform": row.get("transform"), "sourcePath": row["sourcePath"],
                           "configuration": row.get("configuration")})
        selection[role] = row["name"]
    context = {"kind": "read_only_saved_cad_state", "sourcePath": str(state_path),
               "sourceSha256": state_sha, "assemblyPath": str(assembly),
               "assemblySha256": state["assemblySha256"], "observedAtUtc": state.get("finishedAtUtc"),
               "observedTopLevelComponentCount": len(observed_components)}
    association = bind_scanner_target_to_current_context(
        reference_association=reference, scanner_reference_graph=inputs["scannerGraphPath"],
        current_components=components, selection=selection, world_frame_id=str(assembly), context_evidence=context)
    evaluation = evaluate_scanner_target_in_current_context(association=association)
    preflight = preflight_scanner_target_for_cumulative_chain(
        association=association, evaluation=evaluation, planned_components=components,
        world_frame_id=str(assembly), allow_prototype_proxy=authorize_prototype_estimate)
    return {"association": association, "evaluation": evaluation, "preflight": preflight,
        "contextComponents": components, "sourceEvidenceIndex": evidence,
        "summary": {"status": evaluation["status"], "case": rule["ruleId"],
            "ruleId": rule["ruleId"], "ruleDigest": _digest(rule), "instanceSelection": selection,
            "sourceStatePath": str(state_path), "sourceAssemblyPath": str(assembly),
            "processCandidateCompileAllowed": preflight["processCandidateCompileAllowed"],
            "processProxyChecks": evaluation["selectedCandidate"]["processProxyChecks"],
            "newCadExecuted": False, "measuredScanSuccess": False, "mechanicalReleaseCheckRequired": True,
            "remainingEvidence": association["engineeringEvidenceMissing"]},
        "timing": {"completedAtUtc": datetime.now(timezone.utc).isoformat(),
                   "offlineDurationSeconds": time.perf_counter()-started, "cadSeconds": 0}}


def validate_current_scanner_target_report(*, report: dict, **current_inputs) -> dict:
    """Rebuild from current files/poses; reject stale reports, even old passes."""
    try:
        fresh = build_current_scanner_target(**current_inputs)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        return {"passed": False, "blockingReasonCodes": ["SCANNER_CURRENT_CONTEXT_INVALID"], "detail": str(exc)}
    fields = ("association", "evaluation", "preflight", "contextComponents", "sourceEvidenceIndex", "summary")
    changed = [field for field in fields if report.get(field) != fresh[field]]
    return {"passed": not changed, "blockingReasonCodes": ["SCANNER_CURRENT_REPORT_STALE"] if changed else [],
            "changedFields": changed, "processProxyValidationPassed": fresh["evaluation"]["processProxyValidationPassed"]}
