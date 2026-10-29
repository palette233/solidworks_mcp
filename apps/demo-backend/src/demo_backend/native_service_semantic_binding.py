"""Bind a native CleaningWeighing module's service subtrees to its own station.

This is an identity semantic binding for a module on its native base.  It
authenticates existing measurements and mechanical release evidence, but it
does not treat labels as a target-station CAD postcheck.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .calibration_function_point import EXTENSION_CANDIDATE_REPORT_SCHEMA
from .cleaning_service_region import (
    COMPLETE_SERVICE_SUBTREE_SOURCES,
    build_cleaning_service_capability_audit,
)
from .global_interface_contract_planner import (
    resolve_preferred_released_interface_authority,
)
from .role_station_geometry import _same_path


CONFIG_SCHEMA = "native-service-semantic-binding-batch/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(root: Path, value: str) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError(f"native service binding evidence is missing: {path}")
    return path


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    token = token.upper()
    rows = [
        row for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper().endswith(token)
    ]
    if len(rows) != 1:
        raise ValueError(f"native service module is missing or ambiguous: {token}")
    return rows[0]


def build_native_service_semantic_binding_report(
    workspace: Path, config: dict[str, Any]
) -> dict[str, Any]:
    root = workspace.resolve()
    if config.get("schemaVersion") != CONFIG_SCHEMA:
        raise ValueError("unsupported native service binding config schema")
    entries = config.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("native service binding config has no entries")
    candidates, evidence, seen = [], {}, set()
    for spec in entries:
        required = (
            "sourceModuleDefinitionId", "targetBaseDefinitionId",
            "nativeRoleModuleDefinitionId", "sourceToken", "targetBaseToken",
            "occupancyPath", "nativeGraphPath",
        )
        if any(not isinstance(spec.get(key), str) or not spec[key] for key in required):
            raise ValueError("native service binding entry is incomplete")
        key = (spec["sourceModuleDefinitionId"], spec["targetBaseDefinitionId"])
        if key in seen:
            raise ValueError(f"duplicate native service binding pair: {key}")
        seen.add(key)
        if spec["sourceModuleDefinitionId"] != spec["nativeRoleModuleDefinitionId"]:
            raise ValueError("native service identity binding requires the same source/native role")
        service = spec.get("serviceSubtrees")
        excluded = spec.get("excludedSubtrees")
        if (
            not isinstance(service, list) or not service
            or not isinstance(excluded, list) or not excluded
            or any(not isinstance(value, str) or not value for value in service + excluded)
            or set(service) & set(excluded)
        ):
            raise ValueError("native service subtrees must be explicit, nonempty and disjoint")
        occupancy_path = _file(root, spec["occupancyPath"])
        graph_path = _file(root, spec["nativeGraphPath"])
        occupancy, graph = _read(occupancy_path), _read(graph_path)
        source_token, base_token = spec["sourceToken"], spec["targetBaseToken"]
        try:
            capture = occupancy["modules"][source_token]
            base_capture = occupancy["modules"][base_token]
        except KeyError as error:
            raise ValueError("native service occupancy is missing source or base") from error
        source_module, base_module = _module(graph, source_token), _module(graph, base_token)
        if (
            capture.get("leafCoverageComplete") is not True
            or not _same_path(capture["filePath"], source_module["Path"])
            or not _same_path(base_capture["filePath"], base_module["Path"])
        ):
            raise ValueError("native service occupancy and graph identities differ")
        groups = {row.get("subtree"): row for row in capture.get("occupancyBoxes") or []}
        if set(groups) != set(service + excluded):
            raise ValueError("native service subtree partition is incomplete or changed")
        if any(groups[name].get("source") not in COMPLETE_SERVICE_SUBTREE_SOURCES for name in groups):
            raise ValueError("native service subtree lacks complete captured geometry")
        capability = build_cleaning_service_capability_audit(
            root,
            spec["sourceModuleDefinitionId"],
            spec["targetBaseDefinitionId"],
            [spec["nativeRoleModuleDefinitionId"]],
        )
        if capability["capabilityCoverage"]["passed"] is not True:
            raise ValueError("native service identity capability coverage failed")
        authority = resolve_preferred_released_interface_authority(
            root,
            spec["sourceModuleDefinitionId"],
            selected_slot_definition_id=spec["targetBaseDefinitionId"],
            allow_datum_fallback=False,
        )
        manifest_value = authority.get("releaseManifestPath")
        if (
            authority.get("ready") is not True
            or authority.get("selectedMode") != "mechanical_interface"
            or authority.get("relationExecutionMode") != "direct_installation"
            or not isinstance(manifest_value, str) or not manifest_value
        ):
            raise ValueError("native service pair lacks exact direct mechanical authority")
        manifest_path = _file(root, manifest_value)
        manifest = _read(manifest_path)
        validation = manifest.get("validationEvidence") or []
        validation = validation if isinstance(validation, list) else [validation]
        passed_evidence = []
        for row in validation:
            if row.get("passed") is not True:
                continue
            path = _file(root, row["path"])
            if _sha(path) != row.get("fileSha256"):
                raise ValueError("native service mechanical validation evidence changed")
            passed_evidence.append({"path": str(path), "sha256": _sha(path)})
        if not passed_evidence:
            raise ValueError("native service direct release has no passed validation evidence")
        for path in (occupancy_path, graph_path, manifest_path):
            evidence[str(path)] = {"path": str(path), "sha256": _sha(path)}
        for row in passed_evidence:
            evidence[row["path"]] = row
        candidates.append({
            "sourceModuleDefinitionId": spec["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": spec["targetBaseDefinitionId"],
            "role": "CleaningWeighing",
            "interfaceTopology": "native_direct_installation_with_identity_service_binding",
            "status": "native_service_identity_binding_ready_for_station_rule_and_readonly_postcheck",
            "readyForCadValidation": False,
            "cadLaunchAllowed": False,
            "serviceSubtreeMapping": {name: name for name in service},
            "excludedStructuralSubtrees": list(excluded),
            "capabilityCoverage": capability["capabilityCoverage"],
            "mechanicalAuthority": {
                "releaseManifestPath": manifest_value,
                "releaseDigest": authority.get("releaseDigest"),
            },
            "nextAction": (
                "materialize_native_station_rule_then_reopen_existing_cad_and_run_"
                "target_station_postcheck_without_reinserting_the_module"
            ),
            "claimBoundary": (
                "Identity binding proves that the complete measured native service subtrees "
                "and reviewed capabilities refer to the same module at its native base. It "
                "does not replace a current saved-output target-station postcheck or verify "
                "cleaning performance, fastening, collision/B-rep or production use."
            ),
        })
    report = {
        "schemaVersion": EXTENSION_CANDIDATE_REPORT_SCHEMA,
        "candidates": candidates,
        "summary": {
            "candidateCount": len(candidates),
            "identityBindingReadyCount": len(candidates),
        },
        "evidence": sorted(evidence.values(), key=lambda row: row["path"]),
        "cadExecuted": False,
        "boundary": "Native semantic identity binding only; station postcheck remains required.",
    }
    report["reportDigest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return report
