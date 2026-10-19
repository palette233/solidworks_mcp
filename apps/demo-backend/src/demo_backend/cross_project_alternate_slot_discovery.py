"""Discover registered alternate target slots before requesting an adapter."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .cross_project_module_substitution import (
    _assess_installation_pair,
    _installation_candidates,
    augment_catalog_with_role_and_port_overlay,
    build_module_role_overlay,
)
from .global_module_catalog import validate_global_module_catalog


SCHEMA = "cross-project-alternate-slot-discovery/v1"


class CrossProjectAlternateSlotDiscoveryError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _mechanical_candidate_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(candidate["modulePort"].get("globalPortId") or ""),
        str(candidate["basePort"].get("globalPortId") or ""),
        _digest(candidate["template"].get("mateSteps") or []),
    )


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
    """Keep immutable template identities even when mechanics are identical."""

    return (
        str(candidate["template"].get("globalTemplateId") or ""),
        *_mechanical_candidate_key(candidate),
    )


def _collect_evidence(
    catalogs: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    definitions: dict[str, dict[str, Any]] = {}
    installations: dict[
        str, dict[tuple[str, str, str, str], dict[str, Any]]
    ] = {}
    ports: dict[str, dict[str, Any]] = {}
    for catalog in catalogs:
        validate_global_module_catalog(catalog)
        normalized = augment_catalog_with_role_and_port_overlay(
            catalog, build_module_role_overlay(catalog)
        )
        for port in normalized.get("semanticPorts") or []:
            ports[str(port["globalPortId"])] = port
        for definition in normalized.get("moduleDefinitions") or []:
            definition_id = str(definition["moduleDefinitionId"])
            definitions[definition_id] = definition
            bucket = installations.setdefault(definition_id, {})
            for candidate in _installation_candidates(normalized, definition):
                bucket[_candidate_key(candidate)] = candidate
    return (
        definitions,
        {
            definition_id: [rows[key] for key in sorted(rows)]
            for definition_id, rows in installations.items()
        },
        ports,
    )


def _match_selected_candidate(
    candidates: list[dict[str, Any]], selected: dict[str, Any]
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in candidates
            if str(row["template"].get("globalTemplateId") or "")
            == str(selected.get("templateId") or "")
            and str(row["modulePort"].get("globalPortId") or "")
            == str(selected.get("modulePortId") or "")
        ),
        None,
    )


def build_alternate_slot_discovery(
    matrix: dict[str, Any],
    *,
    evidence_catalogs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Scan every registered provided port on the target base.

    Only topology-mismatch rows without a provider-architecture mismatch are
    scanned.  Existing native target slots are excluded; no face, hole or slot
    is inferred from unregistered CAD geometry.
    """

    if matrix.get("schemaVersion") != "cross-project-module-candidate-matrix/v1":
        raise CrossProjectAlternateSlotDiscoveryError("不支持的候选矩阵版本。")
    definitions, installations, ports = _collect_evidence(evidence_catalogs)
    result_rows: list[dict[str, Any]] = []
    for row in matrix.get("rows") or []:
        codes = {str(item.get("code") or "") for item in row.get("blockers") or []}
        if (
            row.get("status") != "incompatible"
            or row.get("deferred") is True
            or "MATE_TOPOLOGY_MISMATCH" not in codes
            or "TARGET_SLOT_PROVIDER_ROLE_MISMATCH" in codes
        ):
            continue
        selected = row.get("selectedAssessment") or {}
        selected_source = selected.get("sourceInstallation") or {}
        selected_target = selected.get("targetInstallation") or {}
        source_candidates = installations.get(
            str(row.get("sourceModuleDefinitionId") or ""), []
        )
        source_candidate = _match_selected_candidate(
            source_candidates, selected_source
        )
        native_slot_id = str(selected_target.get("targetSlotPortId") or "")
        native_slot = ports.get(native_slot_id)
        if source_candidate is None or native_slot is None:
            raise CrossProjectAlternateSlotDiscoveryError(
                "候选矩阵引用的安装配置不能在证据目录中恢复。"
            )
        target_base_id = str(native_slot.get("moduleDefinitionId") or "")
        source_role = str(row.get("primaryRole") or "")
        alternates: dict[tuple[str, str, str], dict[str, Any]] = {}
        for definition_id, candidates in installations.items():
            for candidate in candidates:
                base_port = candidate["basePort"]
                interface = base_port.get("normalizedInterface") or {}
                if (
                    str(base_port.get("moduleDefinitionId") or "") != target_base_id
                    or str(base_port.get("globalPortId") or "") == native_slot_id
                    or interface.get("portDirection") != "provided"
                    or interface.get("slotRole") != source_role
                ):
                    continue
                candidate_copy = deepcopy(candidate)
                candidate_copy["nativeModuleDefinitionId"] = definition_id
                # Several immutable releases may carry the same physical slot
                # under different template identities.  Preserve those
                # identities while collecting evidence, but assess each
                # mechanical slot only once.
                alternates[_mechanical_candidate_key(candidate)] = candidate_copy

        assessments = []
        for alternate in [alternates[key] for key in sorted(alternates)]:
            assessment = _assess_installation_pair(source_candidate, alternate)
            assessments.append(
                {
                    "alternateSlotPortId": alternate["basePort"].get("globalPortId"),
                    "alternateNativeModuleDefinitionId": alternate.get(
                        "nativeModuleDefinitionId"
                    ),
                    "alternateTemplateId": alternate["template"].get(
                        "globalTemplateId"
                    ),
                    "hardBlockerCount": assessment["hardBlockerCount"],
                    "reviewBlockerCount": assessment["reviewBlockerCount"],
                    "blockers": deepcopy(assessment["blockers"]),
                }
            )
        ready = [
            item
            for item in assessments
            if item["hardBlockerCount"] == 0 and item["reviewBlockerCount"] == 0
        ]
        review = [
            item
            for item in assessments
            if item["hardBlockerCount"] == 0 and item["reviewBlockerCount"] > 0
        ]
        if ready:
            status = "registered_alternate_slot_ready"
        elif review:
            status = "registered_alternate_slot_needs_geometry_review"
        elif assessments:
            status = "registered_alternate_slots_incompatible"
        else:
            status = "no_registered_alternate_slot"
        target_base = definitions.get(target_base_id) or {}
        result_rows.append(
            {
                "sourceModuleDefinitionId": row.get("sourceModuleDefinitionId"),
                "sourceProjectIds": deepcopy(row.get("sourceProjectIds") or []),
                "sourceModuleTokens": deepcopy(row.get("sourceModuleTokens") or []),
                "replacedModuleDefinitionId": row.get("targetModuleDefinitionId"),
                "targetProjectIds": deepcopy(row.get("targetProjectIds") or []),
                "targetModuleTokens": deepcopy(row.get("targetModuleTokens") or []),
                "primaryRole": source_role,
                "targetBaseModuleDefinitionId": target_base_id,
                "targetBaseAliases": deepcopy(target_base.get("projectAliases") or []),
                "nativeTargetSlotPortId": native_slot_id,
                "registeredAlternateSlotCount": len(assessments),
                "readyAlternateSlotCount": len(ready),
                "reviewAlternateSlotCount": len(review),
                "status": status,
                "alternateSlotAssessments": assessments,
            }
        )

    status_counts = {
        status: sum(item["status"] == status for item in result_rows)
        for status in (
            "registered_alternate_slot_ready",
            "registered_alternate_slot_needs_geometry_review",
            "registered_alternate_slots_incompatible",
            "no_registered_alternate_slot",
        )
    }
    core = {
        "schemaVersion": SCHEMA,
        "sourceMatrixDigest": matrix.get("matrixDigest"),
        "evidenceCatalogDigests": sorted(
            {str(catalog.get("catalogDigest") or "") for catalog in evidence_catalogs}
        ),
        "scannedDirectionalPairCount": len(result_rows),
        "statusCounts": status_counts,
        "rows": sorted(
            result_rows,
            key=lambda item: (
                item["primaryRole"],
                item["sourceProjectIds"],
                item["sourceModuleTokens"],
                item["targetProjectIds"],
                item["targetModuleTokens"],
            ),
        ),
        "policy": {
            "registeredPortsOnly": True,
            "nativeTargetSlotExcluded": True,
            "unregisteredGeometryInferred": False,
            "cadExecutionAuthorized": False,
            "collisionOrBrepRequired": False,
        },
    }
    return {**core, "discoveryDigest": _digest(core)}
