"""Compose a cross-project scanner rule from authenticated native rules.

The source rule contributes scanner optical evidence.  The target rule
contributes the target-base graph and barcode-station reference.  Composition
is allowed only when both rules use the same transport definition and the same
measured reference frame.  The result is still a current-context candidate: it
does not start CAD or authorize a placement by itself.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from .scanner_point_pair_profile import (
    SOURCE_CANDIDATE_CATALOG_SCHEMA,
    TARGET_CANDIDATE_CATALOG_SCHEMA,
)


RULE_SCHEMA = "scanner-target-rule/v1"
POINT_PAIR_RULE_SCHEMA = "scanner-local-point-pair-rule/v1"
COMPOSITION_SCHEMA = "scanner-target-rule-composition/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _definition(value: Any) -> str:
    text = str(value or "")
    parts = text.split("::")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Expected an exact project::module definition")
    return text


def _authenticate_rule(root: Path, path: Path) -> dict[str, Any]:
    rule = _read(path)
    if rule.get("schemaVersion") != RULE_SCHEMA or not rule.get("ruleId"):
        raise ValueError("Unsupported or unnamed scanner target rule")
    for key in (
        "sourceModuleDefinitionId",
        "transportModuleDefinitionId",
        "targetBaseDefinitionId",
        "referenceBaseDefinitionId",
    ):
        _definition(rule.get(key))
    inputs = rule.get("inputs") or {}
    expected = rule.get("inputSha256") or {}
    required = {
        "processEvidencePath",
        "scannerGraphPath",
        "transportGraphPath",
        "targetFaceCatalogPath",
        "targetBaseGraphPath",
    }
    if not required.issubset(inputs) or set(inputs) != set(expected):
        raise ValueError("Scanner rule inputs or pinned hashes are incomplete")
    for key, relative in inputs.items():
        resolved = (root / relative).resolve()
        resolved.relative_to(root)
        if not resolved.is_file() or _sha(resolved) != expected[key]:
            raise ValueError(f"Scanner rule input changed: {key}")
    return rule


def _authenticate_point_pair_rule(root: Path, path: Path) -> dict[str, Any]:
    """Authenticate one normalized point-pair rule used by the batch report.

    The report is allowed to recognize an already materialized point-pair
    candidate, but it must not trust the registry entry alone.  The rule body,
    pinned profile and exact scanner/transport/base identities are rechecked so
    that a stale or hand-edited file cannot silently close a measurement gap.
    """

    rule = _read(path)
    if rule.get("schemaVersion") != POINT_PAIR_RULE_SCHEMA or not rule.get("ruleId"):
        raise ValueError("Unsupported or unnamed scanner point-pair rule")
    for key in (
        "sourceModuleDefinitionId",
        "transportModuleDefinitionId",
        "targetBaseDefinitionId",
    ):
        _definition(rule.get(key))
    inputs = rule.get("inputs") or {}
    expected = rule.get("inputSha256") or {}
    if set(inputs) != {"measurementPath"} or set(expected) != {"measurementPath"}:
        raise ValueError("Scanner point-pair rule input is incomplete")
    profile_path = (root / str(inputs["measurementPath"])).resolve()
    profile_path.relative_to(root)
    if not profile_path.is_file() or _sha(profile_path) != expected["measurementPath"]:
        raise ValueError("Scanner point-pair profile changed")
    measurement = _read(profile_path)
    body = dict(rule)
    digest = body.pop("ruleDigest", None)
    if measurement.get("schemaVersion") == "scanner-local-point-pair-profile/v1":
        if digest != _digest(body):
            raise ValueError("Scanner point-pair rule digest mismatch")
        if rule.get("prototypePoseAllowedAsCadExecutionAuthority") is not False:
            raise ValueError(
                "Point-pair rule does not explicitly forbid prototype pose authority"
            )
    elif measurement.get("schemaVersion") == "project02-scanner-barcode-points/v1":
        # The first Project02 rule predates the normalized profile and ruleDigest
        # fields.  Its measurement file is still hash-pinned and the evaluator
        # independently requires a direct persistent barcode face.  Accept this
        # exact legacy shape without weakening authentication of new profiles.
        if digest is not None:
            raise ValueError("Legacy scanner point-pair rule has an unexpected digest")
    else:
        raise ValueError("Unsupported scanner point-pair measurement schema")
    return rule


def _authenticate_target_candidate_catalog(root: Path, path: Path) -> dict[str, Any]:
    catalog = _read(path)
    if catalog.get("schemaVersion") != TARGET_CANDIDATE_CATALOG_SCHEMA:
        raise ValueError("Unsupported transport barcode target candidate catalog")
    body = dict(catalog)
    digest = body.pop("catalogDigest", None)
    if digest != _digest(body):
        raise ValueError("Transport barcode target candidate catalog digest mismatch")
    _definition(catalog.get("transportModuleDefinitionId"))
    if (
        catalog.get("roleSelectionRequired") is not True
        or catalog.get("prototypePoseAllowedAsCadExecutionAuthority") is not False
        or catalog.get("cadStarted") is not False
    ):
        raise ValueError("Transport target candidate catalog weakens required gates")
    for evidence in catalog.get("sourceEvidence") or []:
        evidence_path = Path(str(evidence.get("path") or "")).resolve()
        evidence_path.relative_to(root)
        if not evidence_path.is_file() or _sha(evidence_path) != evidence.get("sha256"):
            raise ValueError("Transport target candidate evidence changed")
    candidates = catalog.get("candidates") or []
    if len(candidates) < 1:
        raise ValueError("Transport target candidate catalog is empty")
    for candidate in candidates:
        if (
            candidate.get("roleEngineeringConfirmed") is not False
            or candidate.get("readyForPointPairRule") is not False
            or len(candidate.get("localBarcodeTargetMeters") or []) != 3
        ):
            raise ValueError("Transport target candidate is not fail-closed")
    return catalog


def _authenticate_source_candidate_catalog(root: Path, path: Path) -> dict[str, Any]:
    catalog = _read(path)
    if catalog.get("schemaVersion") != SOURCE_CANDIDATE_CATALOG_SCHEMA:
        raise ValueError("Unsupported scanner optical source candidate catalog")
    body = dict(catalog)
    digest = body.pop("catalogDigest", None)
    if digest != _digest(body):
        raise ValueError("Scanner optical source candidate catalog digest mismatch")
    _definition(catalog.get("scannerModuleDefinitionId"))
    if (
        catalog.get("roleAndDirectionSelectionRequired") is not True
        or catalog.get("prototypePoseAllowedAsCadExecutionAuthority") is not False
        or catalog.get("cadStarted") is not False
    ):
        raise ValueError("Scanner source candidate catalog weakens required gates")
    for evidence in catalog.get("sourceEvidence") or []:
        evidence_path = Path(str(evidence.get("path") or "")).resolve()
        evidence_path.relative_to(root)
        if not evidence_path.is_file() or _sha(evidence_path) != evidence.get("sha256"):
            raise ValueError("Scanner source candidate evidence changed")
    candidates = catalog.get("candidates") or []
    if len(candidates) < 1:
        raise ValueError("Scanner source candidate catalog is empty")
    for candidate in candidates:
        if (
            candidate.get("roleEngineeringConfirmed") is not False
            or candidate.get("directionSignEngineeringConfirmed") is not False
            or candidate.get("readyForPointPairRule") is not False
            or len(candidate.get("localOpticalOriginMeters") or []) != 3
            or len(candidate.get("localOpticalDirection") or []) != 3
        ):
            raise ValueError("Scanner source candidate is not fail-closed")
    return catalog


def compose_scanner_target_rule(
    *,
    repository_root: Path,
    source_rule_path: Path,
    target_rule_path: Path,
    rule_id: str,
) -> dict[str, Any]:
    """Return one immutable-evidence cross-project scanner rule candidate."""

    root = repository_root.resolve()
    source_path = source_rule_path.resolve()
    target_path = target_rule_path.resolve()
    source_path.relative_to(root)
    target_path.relative_to(root)
    source = _authenticate_rule(root, source_path)
    target = _authenticate_rule(root, target_path)
    if not rule_id or rule_id in {source["ruleId"], target["ruleId"]}:
        raise ValueError("A new rule id is required")
    if source["transportModuleDefinitionId"] != target["transportModuleDefinitionId"]:
        raise ValueError("Source and target scanner rules use different transports")
    if source["referenceBaseDefinitionId"] != target["referenceBaseDefinitionId"]:
        raise ValueError("Source and target scanner rules use different reference frames")
    if source["sourceModuleDefinitionId"] == target["sourceModuleDefinitionId"]:
        raise ValueError("Composition requires a different scanner and target native rule")

    selected_inputs = {
        "processEvidencePath": source["inputs"]["processEvidencePath"],
        "scannerGraphPath": source["inputs"]["scannerGraphPath"],
        "transportGraphPath": source["inputs"]["transportGraphPath"],
        "targetFaceCatalogPath": target["inputs"]["targetFaceCatalogPath"],
        "targetBaseGraphPath": target["inputs"]["targetBaseGraphPath"],
    }
    if source.get("opticalMeasurementSelector") is not None:
        if "opticalGeometryPath" not in source["inputs"]:
            raise ValueError("Optical selector has no pinned geometry input")
        selected_inputs["opticalGeometryPath"] = source["inputs"][
            "opticalGeometryPath"
        ]
    input_hashes = {
        key: _sha((root / relative).resolve())
        for key, relative in selected_inputs.items()
    }
    core: dict[str, Any] = {
        "schemaVersion": RULE_SCHEMA,
        "ruleId": rule_id,
        "sourceModuleDefinitionId": source["sourceModuleDefinitionId"],
        "targetBaseDefinitionId": target["targetBaseDefinitionId"],
        "transportModuleDefinitionId": source["transportModuleDefinitionId"],
        "referenceBaseDefinitionId": source["referenceBaseDefinitionId"],
        "evidenceGrade": "composed_native_proxy_requires_current_saved_context",
        "inputs": selected_inputs,
        "inputSha256": input_hashes,
        "interpretationLimits": [
            *deepcopy(source.get("interpretationLimits") or []),
            *deepcopy(target.get("interpretationLimits") or []),
            "Composition reuses authenticated scanner and target-station evidence only; it is not an insertion pose or CAD authority.",
            "The exact scanner, selected transport and target base must be rebound in one independently saved current CAD state.",
        ],
        "compositionEvidence": {
            "schemaVersion": COMPOSITION_SCHEMA,
            "sourceRulePath": source_path.relative_to(root).as_posix(),
            "sourceRuleSha256": _sha(source_path),
            "sourceRuleDigest": _digest(source),
            "targetRulePath": target_path.relative_to(root).as_posix(),
            "targetRuleSha256": _sha(target_path),
            "targetRuleDigest": _digest(target),
            "sameTransportRequired": True,
            "sameReferenceFrameRequired": True,
        },
        "status": "review_candidate_requires_current_saved_context",
        "cadLaunchAllowed": False,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
    }
    if source.get("opticalMeasurementSelector") is not None:
        core["opticalMeasurementSelector"] = deepcopy(
            source["opticalMeasurementSelector"]
        )
    core["compositionDigest"] = _digest(core)
    return core


def build_scanner_rule_composition_batch(
    *,
    repository_root: Path,
    binding_queue_path: Path,
    registry_path: Path,
    target_candidate_catalog_path: Path | None = None,
    source_candidate_catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Classify every missing scanner context using reusable native rules.

    Native scanner rules are deliberately restricted to non-composed
    ``scanner_target`` entries.  Already normalized exact point-pair rules are
    recognized separately: they close the *definition-level* measurement gap,
    but still require a current saved cumulative CAD context.
    """

    root = repository_root.resolve()
    queue_path = binding_queue_path.resolve()
    rules_path = registry_path.resolve()
    queue_path.relative_to(root)
    rules_path.relative_to(root)
    queue = _read(queue_path)
    registry = _read(rules_path)
    if queue.get("schemaVersion") != "scanner-transport-binding-review-queue/v1":
        raise ValueError("Unsupported scanner binding queue")
    if not isinstance(registry.get("rules"), list):
        raise ValueError("Unsupported station rule registry")
    target_candidate_catalog = None
    target_catalog_path = None
    if target_candidate_catalog_path is not None:
        target_catalog_path = target_candidate_catalog_path.resolve()
        target_catalog_path.relative_to(root)
        target_candidate_catalog = _authenticate_target_candidate_catalog(
            root, target_catalog_path
        )
    source_candidate_catalog = None
    source_catalog_path = None
    if source_candidate_catalog_path is not None:
        source_catalog_path = source_candidate_catalog_path.resolve()
        source_catalog_path.relative_to(root)
        source_candidate_catalog = _authenticate_source_candidate_catalog(
            root, source_catalog_path
        )

    native: list[dict[str, Any]] = []
    point_pair: list[dict[str, Any]] = []
    for entry in registry["rules"]:
        evaluator = entry.get("evaluator") or {}
        if entry.get("role") != "Scanner":
            continue
        config_path = (root / str(evaluator.get("inputPath") or "")).resolve()
        config_path.relative_to(root)
        if evaluator.get("kind") == "scanner_target":
            config = _authenticate_rule(root, config_path)
            if config.get("compositionEvidence") is not None:
                continue
            native.append({"entry": entry, "path": config_path, "config": config})
        elif evaluator.get("kind") == "scanner_point_pair":
            config = _authenticate_point_pair_rule(root, config_path)
            point_pair.append({"entry": entry, "path": config_path, "config": config})

    rows = []
    candidates = [
        row
        for row in queue.get("candidates") or []
        if row.get("status") == "new_cumulative_chain_context_required"
    ]
    for row in candidates:
        source_id = str(row.get("sourceModuleDefinitionId") or "")
        target_id = str(row.get("targetBaseDefinitionId") or "")
        transport_id = str(row.get("transportModuleDefinitionId") or "")
        exact_point_pair = [
            item
            for item in point_pair
            if item["config"]["sourceModuleDefinitionId"] == source_id
            and item["config"]["transportModuleDefinitionId"] == transport_id
            and item["config"]["targetBaseDefinitionId"] == target_id
        ]
        source_rules = [
            item for item in native if item["config"]["sourceModuleDefinitionId"] == source_id
        ]
        target_rules = [
            item for item in native if item["config"]["targetBaseDefinitionId"] == target_id
        ]
        blockers = []
        if len(exact_point_pair) > 1:
            blockers.append("EXACT_POINT_PAIR_RULE_AMBIGUOUS")
        candidate = None
        rule_id = (
            f"scanner-{source_id.split('::')[-1].lower()}-"
            f"{transport_id.split('::')[-1].lower()}-"
            f"{target_id.split('::')[-1].lower()}-v1"
        )
        exact_rule = exact_point_pair[0] if len(exact_point_pair) == 1 else None
        if exact_rule is None and not blockers:
            if len(source_rules) != 1:
                blockers.append("SOURCE_NATIVE_SCANNER_TARGET_RULE_MISSING_OR_AMBIGUOUS")
            if len(target_rules) != 1:
                blockers.append("TARGET_NATIVE_SCANNER_STATION_RULE_MISSING_OR_AMBIGUOUS")
        if exact_rule is None and not blockers:
            source = source_rules[0]["config"]
            target = target_rules[0]["config"]
            if source["transportModuleDefinitionId"] != transport_id:
                blockers.append("SOURCE_RULE_TRANSPORT_DIFFERS_FROM_SELECTED_TRANSPORT")
            if target["transportModuleDefinitionId"] != transport_id:
                blockers.append("TARGET_RULE_TRANSPORT_DIFFERS_FROM_SELECTED_TRANSPORT")
            if source["referenceBaseDefinitionId"] != target["referenceBaseDefinitionId"]:
                blockers.append("SOURCE_AND_TARGET_REFERENCE_FRAMES_DIFFER")
            if source_id == target["sourceModuleDefinitionId"]:
                blockers.append("NATIVE_RULE_ALREADY_COVERS_THIS_SCANNER_AND_BASE")
            if not blockers:
                candidate = compose_scanner_target_rule(
                    repository_root=root,
                    source_rule_path=source_rules[0]["path"],
                    target_rule_path=target_rules[0]["path"],
                    rule_id=rule_id,
                )
        source_profile_available = bool(source_rules) or any(
            item["config"]["sourceModuleDefinitionId"] == source_id
            for item in point_pair
        )
        source_candidate_available = bool(
            source_candidate_catalog is not None
            and source_candidate_catalog["scannerModuleDefinitionId"] == source_id
        )
        target_profile_available = any(
            item["config"]["transportModuleDefinitionId"] == transport_id
            for item in point_pair
        ) or any(
            item["config"]["transportModuleDefinitionId"] == transport_id
            for item in native
        )
        target_candidate_available = bool(
            target_candidate_catalog is not None
            and target_candidate_catalog["transportModuleDefinitionId"] == transport_id
        )
        required_next_evidence = []
        if exact_rule is None and candidate is None:
            if not source_profile_available and source_candidate_available:
                required_next_evidence.append(
                    "source_scanner_head_role_and_direction_selection_from_candidate_catalog"
                )
            elif not source_profile_available:
                required_next_evidence.append(
                    "source_scanner_local_optical_profile_and_role_selection"
                )
            if not target_profile_available and target_candidate_available:
                required_next_evidence.append(
                    "transport_barcode_target_role_selection_from_candidate_catalog"
                )
            elif not target_profile_available:
                required_next_evidence.append(
                    "transport_local_barcode_target_profile_and_target_role"
                )
            if source_profile_available and target_profile_available:
                required_next_evidence.append(
                    "normalized_point_pair_composition_required"
                )
        rows.append(
            {
                "sourceModuleDefinitionId": source_id,
                "transportModuleDefinitionId": transport_id,
                "targetBaseDefinitionId": target_id,
                "status": (
                    "exact_point_pair_candidate_available"
                    if exact_rule is not None
                    else (
                        "composition_candidate_ready"
                        if candidate is not None
                        else "independent_point_pair_or_measurement_required"
                    )
                ),
                "blockingReasonCodes": blockers,
                "sourceOpticalProfileAvailable": source_profile_available,
                "sourceOpticalCandidateAvailable": source_candidate_available,
                "sourceOpticalCandidateCatalogPath": (
                    source_catalog_path.relative_to(root).as_posix()
                    if source_candidate_available and source_catalog_path is not None
                    else None
                ),
                "transportBarcodeTargetProfileAvailable": target_profile_available,
                "transportBarcodeTargetCandidateAvailable": target_candidate_available,
                "transportBarcodeTargetCandidateCatalogPath": (
                    target_catalog_path.relative_to(root).as_posix()
                    if target_candidate_available and target_catalog_path is not None
                    else None
                ),
                "requiredNextEvidence": required_next_evidence,
                "exactCandidateRuleId": (
                    exact_rule["config"]["ruleId"] if exact_rule is not None else None
                ),
                "exactCandidateRulePath": (
                    exact_rule["path"].relative_to(root).as_posix()
                    if exact_rule is not None
                    else None
                ),
                "candidateRuleId": rule_id if candidate is not None else None,
                "candidateRule": candidate,
            }
        )
    rows.sort(
        key=lambda row: (
            row["targetBaseDefinitionId"],
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
        )
    )
    core = {
        "schemaVersion": "scanner-target-rule-composition-batch/v1",
        "rows": rows,
        "summary": {
            "inputMissingContextCount": len(rows),
            "exactPointPairCandidateAvailableCount": sum(
                row["status"] == "exact_point_pair_candidate_available" for row in rows
            ),
            "compositionCandidateReadyCount": sum(
                row["status"] == "composition_candidate_ready" for row in rows
            ),
            "independentPointPairOrMeasurementRequiredCount": sum(
                row["status"] == "independent_point_pair_or_measurement_required"
                for row in rows
            ),
            "sourceOpticalProfileRequiredCount": sum(
                "source_scanner_local_optical_profile_and_role_selection"
                in row["requiredNextEvidence"]
                for row in rows
            ),
            "sourceOpticalRoleAndDirectionSelectionRequiredCount": sum(
                "source_scanner_head_role_and_direction_selection_from_candidate_catalog"
                in row["requiredNextEvidence"]
                for row in rows
            ),
            "transportBarcodeTargetProfileRequiredCount": sum(
                "transport_local_barcode_target_profile_and_target_role"
                in row["requiredNextEvidence"]
                for row in rows
            ),
            "transportBarcodeTargetRoleSelectionRequiredCount": sum(
                "transport_barcode_target_role_selection_from_candidate_catalog"
                in row["requiredNextEvidence"]
                for row in rows
            ),
            "bothSourceAndTargetProfileRequiredCount": sum(
                "source_scanner_local_optical_profile_and_role_selection"
                in row["requiredNextEvidence"]
                and "transport_local_barcode_target_profile_and_target_role"
                in row["requiredNextEvidence"]
                for row in rows
            ),
            "bothSourceAndTargetDecisionRequiredCount": sum(
                any(
                    code
                    in {
                        "source_scanner_local_optical_profile_and_role_selection",
                        "source_scanner_head_role_and_direction_selection_from_candidate_catalog",
                    }
                    for code in row["requiredNextEvidence"]
                )
                and any(
                    code
                    in {
                        "transport_local_barcode_target_profile_and_target_role",
                        "transport_barcode_target_role_selection_from_candidate_catalog",
                    }
                    for code in row["requiredNextEvidence"]
                )
                for row in rows
            ),
        },
        "evidence": [
            {"path": queue_path.relative_to(root).as_posix(), "sha256": _sha(queue_path)},
            {"path": rules_path.relative_to(root).as_posix(), "sha256": _sha(rules_path)},
        ]
        + (
            [
                {
                    "path": target_catalog_path.relative_to(root).as_posix(),
                    "sha256": _sha(target_catalog_path),
                }
            ]
            if target_catalog_path is not None
            else []
        )
        + (
            [
                {
                    "path": source_catalog_path.relative_to(root).as_posix(),
                    "sha256": _sha(source_catalog_path),
                }
            ]
            if source_catalog_path is not None
            else []
        ),
        "cadStarted": False,
        "strictStationValidationAdded": 0,
        "claimBoundary": (
            "Read-only composition classification only. Ready candidates still need "
            "a real non-prototype cumulative CAD context, save/reopen and current "
            "scanner-target postcheck. Blocked rows must not copy prototype poses."
        ),
    }
    return {**core, "batchDigest": _digest(core)}
