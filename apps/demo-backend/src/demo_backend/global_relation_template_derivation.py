"""Derive standalone read-only relations from calibrated installation bundles.

Some legacy project catalogs record a dimensional relation inside a compound
installation template.  That is valid evidence for the dimension, but the
compound template must never be replayed merely to verify one relation.  This
module copies one explicitly ``validate_only`` mate into a new, independently
selectable template while preserving the original endpoint and provenance
evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from .global_module_catalog import validate_global_module_catalog
from .global_relation_semantics import normalize_template_relation_profile


class GlobalRelationTemplateDerivationError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:56] or "relation"


def derive_standalone_validation_relation(
    source_catalog: dict[str, Any],
    *,
    source_global_template_id: str,
    mate_name: str,
    observation_of_existing_mate: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a signed candidate catalog plus derivation evidence.

    Only a single, already read-only ``validate_only`` mate can be extracted.
    The function deliberately refuses to turn a driving installation mate into
    an independent relation because that would change mechanical semantics.
    """

    validate_global_module_catalog(source_catalog)
    templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in source_catalog.get("connectionTemplates") or []
    }
    source = templates.get(str(source_global_template_id or ""))
    if source is None:
        raise GlobalRelationTemplateDerivationError("源连接模板不存在。")
    matches = [
        row
        for row in source.get("mateSteps") or []
        if str(row.get("mateName") or "") == str(mate_name or "")
    ]
    if len(matches) != 1:
        raise GlobalRelationTemplateDerivationError("待拆分配合步骤必须唯一。")
    step = deepcopy(matches[0])
    source_application_mode = str(
        step.get("applicationMode") or "driving"
    ).casefold()
    if source_application_mode != "validate_only" and not observation_of_existing_mate:
        raise GlobalRelationTemplateDerivationError(
            "只允许从复合模板提取已声明为validate_only的步骤。"
        )
    if observation_of_existing_mate:
        step["applicationMode"] = "validate_only"

    relation_kind = normalize_template_relation_profile(
        {"mateSteps": [step], "purposes": ["verification"]}
    )["relationKinds"]
    if len(relation_kind) != 1:
        raise GlobalRelationTemplateDerivationError("无法唯一识别待拆分关系类型。")
    kind = relation_kind[0]
    purposes = ["spacing"] if kind == "distance" else ["verification"]
    provenance = deepcopy(source.get("provenance") or {})
    derivation_key = {
        "sourceGlobalTemplateId": source_global_template_id,
        "mateName": mate_name,
        "mateStep": step,
        "provenance": provenance,
        "mode": (
            "existing_mate_observation"
            if observation_of_existing_mate
            else "extract_validate_only"
        ),
    }
    suffix = _digest(derivation_key)[:10]
    project_id = str(provenance.get("projectId") or "project-global")
    legacy_id = f"{source.get('legacyTemplateId')}_{mate_name}_standalone_validation"
    template_id = (
        f"template/{_slug(project_id)}/{_slug(legacy_id)}/{suffix}"
    )
    derived = {
        "globalTemplateId": template_id,
        "legacyTemplateId": legacy_id,
        "purposes": purposes,
        "interfaceTypeA": source.get("interfaceTypeA"),
        "interfaceTypeB": source.get("interfaceTypeB"),
        "candidatePortIdsA": deepcopy(source.get("candidatePortIdsA") or []),
        "candidatePortIdsB": deepcopy(source.get("candidatePortIdsB") or []),
        "constraintEffect": {
            "purpose": "Read-only verification of one calibrated relation on existing components.",
            "fullyLocatesAddedComponent": False,
            "expectedResidualDof": None,
            "relationVerificationOnly": True,
        },
        "mateSteps": [step],
        "provenance": {
            **provenance,
            "derivedFromGlobalTemplateId": source_global_template_id,
            "derivedMateName": mate_name,
            "sourceApplicationMode": source_application_mode,
            "derivationPolicy": (
                "read-only-observation-of-existing-source-mate/v1"
                if observation_of_existing_mate
                else "extract-existing-validate-only-step/v1"
            ),
        },
    }

    catalog = deepcopy(source_catalog)
    catalog["connectionTemplates"] = sorted(
        [*(catalog.get("connectionTemplates") or []), derived],
        key=lambda row: str(row.get("globalTemplateId") or ""),
    )
    source_compatibility = [
        row
        for row in source_catalog.get("compatibility") or []
        if row.get("globalTemplateId") == source_global_template_id
    ]
    if not source_compatibility:
        raise GlobalRelationTemplateDerivationError("源模板没有兼容端口证据。")
    derived_compatibility = [
        {
            **deepcopy(row),
            "globalTemplateId": template_id,
            "purpose": purposes[0],
            "directional": False,
        }
        for row in source_compatibility
    ]
    catalog["compatibility"] = sorted(
        [*(catalog.get("compatibility") or []), *derived_compatibility],
        key=lambda row: (
            str(row.get("portAId") or ""),
            str(row.get("portBId") or ""),
            str(row.get("globalTemplateId") or ""),
        ),
    )
    summary = deepcopy(catalog.get("summary") or {})
    summary["connectionTemplateCount"] = len(catalog["connectionTemplates"])
    summary["compatibilityCount"] = len(catalog["compatibility"])
    catalog["summary"] = summary
    catalog.pop("catalogDigest", None)
    catalog["catalogDigest"] = _digest(catalog)
    validate_global_module_catalog(catalog)

    evidence = {
        "schemaVersion": "standalone-validation-template-derivation/v1",
        "status": "ready",
        "sourceCatalogDigest": source_catalog.get("catalogDigest"),
        "candidateCatalogDigest": catalog["catalogDigest"],
        "sourceGlobalTemplateId": source_global_template_id,
        "derivedGlobalTemplateId": template_id,
        "mateName": mate_name,
        "relationKind": kind,
        "applicationMode": "validate_only",
        "derivationMode": (
            "existing_mate_observation"
            if observation_of_existing_mate
            else "extract_validate_only"
        ),
        "sourceSemanticsChanged": False,
        "solidWorksExecuted": False,
    }
    evidence["evidenceDigest"] = _digest(evidence)
    return catalog, evidence
