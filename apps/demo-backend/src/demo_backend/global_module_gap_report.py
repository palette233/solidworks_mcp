"""Evidence-aware gap report for the active global module directory.

The existing port coverage matrix answers whether a catalog contains ports and
templates.  This report answers the stricter question used by the current
development line: whether a rigid add-on has immutable release authorization
and non-prototype CAD evidence that closes its external placement.

The report is deliberately read-only.  It never invents endpoints, modifies an
immutable release, launches SolidWorks, or treats collision/process validation
as part of installation-port readiness.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any, Iterable

from .global_module_catalog import validate_global_module_catalog
from .relation_driving_safety import BLOCKED_STATUS


GLOBAL_MODULE_GAP_REPORT_SCHEMA = "global-module-gap-report/v1"


class GlobalModuleGapReportError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _project_refs(definition: dict[str, Any]) -> list[str]:
    return sorted(
        {
            f"{str(row.get('projectId') or '').strip().lower()}:{str(row.get('moduleToken') or '').strip()}"
            for row in definition.get("projectAliases") or []
            if str(row.get("projectId") or "").strip()
            and str(row.get("moduleToken") or "").strip()
        }
    )


def _template_is_complete(template: dict[str, Any]) -> bool:
    effect = template.get("constraintEffect") or {}
    return bool(effect.get("fullyLocatesAddedComponent")) and int(
        effect.get("expectedResidualDof", -1)
    ) == 0


def _assessment_passed(assessment: dict[str, Any] | None) -> bool:
    if not assessment:
        return False
    return bool(assessment.get("semanticPassed")) and bool(
        assessment.get("checkpointPassed")
    )


def _external_pose_closed(assessment: dict[str, Any] | None) -> bool:
    if not _assessment_passed(assessment):
        return False
    observation = assessment.get("constraintStateObservation") or {}
    return bool(observation.get("targetFullyConstrained")) or bool(
        observation.get("externalPlacementEquivalenceProven")
        or observation.get("externalPlacementEquivalencePassed")
    )


def _resolve_target_side(
    catalog: dict[str, Any],
    ports: dict[str, dict[str, Any]],
    *,
    port_a_id: str,
    port_b_id: str,
    assessment: dict[str, Any] | None,
    preferred_project_id: str | None,
) -> tuple[str, str, str, str]:
    """Resolve target/context without assuming that template side A is target.

    Historical catalogs contain both conventions.  The CAD assessment records
    the actual inserted token, so it is authoritative when available.
    """

    definition_a = str((ports.get(port_a_id) or {}).get("moduleDefinitionId") or "")
    definition_b = str((ports.get(port_b_id) or {}).get("moduleDefinitionId") or "")
    target_token = str((assessment or {}).get("targetModuleToken") or "").strip()
    preferred_project = str(preferred_project_id or "").strip().lower()
    target_definition = ""
    if target_token:
        matches: list[tuple[bool, str]] = []
        for definition in catalog.get("moduleDefinitions") or []:
            for alias in definition.get("projectAliases") or []:
                if str(alias.get("moduleToken") or "").strip().casefold() != target_token.casefold():
                    continue
                project_id = str(alias.get("projectId") or "").strip().lower()
                matches.append(
                    (
                        bool(preferred_project and project_id == preferred_project),
                        str(definition.get("moduleDefinitionId") or ""),
                    )
                )
        if matches:
            matches.sort(key=lambda row: (not row[0], row[1]))
            target_definition = matches[0][1]
    if target_definition == definition_b:
        return definition_b, definition_a, port_b_id, port_a_id
    return definition_a, definition_b, port_a_id, port_b_id


def _release_records(
    release_packages: Iterable[dict[str, Any]],
    *,
    safety_registry: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    catalogs: list[dict[str, Any]] = []
    blocked = {
        str(row.get("globalTemplateId") or "")
        for row in (safety_registry or {}).get("templates") or []
        if str(row.get("status") or "") == BLOCKED_STATUS
    }
    for package in release_packages:
        catalog = package.get("catalog") or {}
        manifest = package.get("manifest") or {}
        evidence = package.get("evidence") or {}
        validate_global_module_catalog(catalog)
        catalogs.append(catalog)
        templates = {
            str(row.get("globalTemplateId") or ""): row
            for row in catalog.get("connectionTemplates") or []
        }
        combinations = {
            str(row.get("globalCombinationId") or ""): row
            for row in catalog.get("templateCombinations") or []
        }
        ports = {
            str(row.get("globalPortId") or ""): row
            for row in catalog.get("semanticPorts") or []
        }
        compatibility = {
            str(row.get("globalTemplateId") or ""): row
            for row in catalog.get("compatibility") or []
        }
        legacy_by_template: dict[str, str] = {}
        for row in evidence.get("derivations") or []:
            template_id = str(
                (row.get("result") or {}).get("derivedGlobalTemplateId") or ""
            )
            legacy_id = str((row.get("entry") or {}).get("legacyTemplateId") or "")
            if template_id and legacy_id:
                legacy_by_template[template_id] = legacy_id
        assessments = evidence.get("cadAssessments") or {}
        preferred_project_id = str(evidence.get("projectId") or "")
        authorized = set(
            (manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []
        )
        for template_id in sorted(authorized):
            template = templates.get(template_id) or {}
            edge = compatibility.get(template_id) or {}
            port_a_id = str(edge.get("portAId") or "")
            port_b_id = str(edge.get("portBId") or "")
            if not port_a_id:
                port_a_id = str(next(iter(template.get("candidatePortIdsA") or []), ""))
            if not port_b_id:
                port_b_id = str(next(iter(template.get("candidatePortIdsB") or []), ""))
            legacy_id = str(
                template.get("legacyTemplateId")
                or legacy_by_template.get(template_id)
                or ""
            )
            assessment = assessments.get(legacy_id) if legacy_id else None
            (
                target_definition_id,
                context_definition_id,
                target_port_id,
                context_port_id,
            ) = _resolve_target_side(
                catalog,
                ports,
                port_a_id=port_a_id,
                port_b_id=port_b_id,
                assessment=assessment,
                preferred_project_id=preferred_project_id,
            )
            records.append(
                {
                    "authorizationKind": "template",
                    "releaseId": manifest.get("releaseId"),
                    "releaseManifestPath": package.get("manifestPath"),
                    "globalTemplateId": template_id,
                    "legacyTemplateId": legacy_id or None,
                    "targetModuleDefinitionId": target_definition_id,
                    "contextModuleDefinitionId": context_definition_id,
                    "targetPortId": target_port_id or None,
                    "contextPortId": context_port_id or None,
                    "templateComplete": _template_is_complete(template),
                    "cadAssessmentPresent": bool(assessment),
                    "cadAssessmentPassed": _assessment_passed(assessment),
                    "externalPoseClosed": _external_pose_closed(assessment),
                    "targetFullyConstrained": bool(
                        ((assessment or {}).get("constraintStateObservation") or {}).get(
                            "targetFullyConstrained"
                        )
                    ),
                    "runtimeSafetyBlocked": template_id in blocked,
                    "assessment": assessment,
                }
            )
        authorized_combinations = set(
            (manifest.get("scope") or {}).get("authorizedTemplateCombinationIds")
            or []
        )
        for combination_id in sorted(authorized_combinations):
            combination = combinations.get(combination_id) or {}
            primary_id = str(combination.get("primaryGlobalTemplateId") or "")
            primary = templates.get(primary_id) or {}
            edge = compatibility.get(primary_id) or {}
            port_a_id = str(edge.get("portAId") or "")
            port_b_id = str(edge.get("portBId") or "")
            if not port_a_id:
                port_a_id = str(next(iter(primary.get("candidatePortIdsA") or []), ""))
            if not port_b_id:
                port_b_id = str(next(iter(primary.get("candidatePortIdsB") or []), ""))
            member_legacy_ids = [
                str(value)
                for value in combination.get("memberLegacyTemplateIds") or []
                if str(value)
            ]
            member_assessments = [
                assessments.get(legacy_id) for legacy_id in member_legacy_ids
            ]
            primary_legacy_id = str(
                combination.get("primaryLegacyTemplateId")
                or primary.get("legacyTemplateId")
                or ""
            )
            primary_assessment = assessments.get(primary_legacy_id)
            member_ids = [
                str(value)
                for value in combination.get("memberGlobalTemplateIds") or []
                if str(value)
            ]
            combination_complete = bool(
                combination.get("fullyLocatesAddedComponent")
            ) and int(combination.get("expectedResidualDof", -1)) == 0
            all_member_assessments_passed = bool(member_assessments) and all(
                _assessment_passed(row) for row in member_assessments
            )
            (
                target_definition_id,
                context_definition_id,
                target_port_id,
                context_port_id,
            ) = _resolve_target_side(
                catalog,
                ports,
                port_a_id=port_a_id,
                port_b_id=port_b_id,
                assessment=primary_assessment,
                preferred_project_id=preferred_project_id,
            )
            records.append(
                {
                    "authorizationKind": "template_combination",
                    "releaseId": manifest.get("releaseId"),
                    "releaseManifestPath": package.get("manifestPath"),
                    "globalTemplateId": combination_id,
                    "legacyTemplateId": combination.get("legacyCombinationId"),
                    "memberGlobalTemplateIds": member_ids,
                    "memberLegacyTemplateIds": member_legacy_ids,
                    "targetModuleDefinitionId": target_definition_id,
                    "contextModuleDefinitionId": context_definition_id,
                    "targetPortId": target_port_id or None,
                    "contextPortId": context_port_id or None,
                    "templateComplete": combination_complete,
                    "cadAssessmentPresent": all(row is not None for row in member_assessments),
                    "cadAssessmentPassed": all_member_assessments_passed,
                    "externalPoseClosed": _external_pose_closed(primary_assessment),
                    "targetFullyConstrained": bool(
                        ((primary_assessment or {}).get("constraintStateObservation") or {}).get(
                            "targetFullyConstrained"
                        )
                    ),
                    "runtimeSafetyBlocked": any(value in blocked for value in member_ids),
                    "assessment": primary_assessment,
                }
            )
    return records, catalogs


def build_global_module_gap_report(
    base_catalog: dict[str, Any],
    release_packages: Iterable[dict[str, Any]],
    *,
    safety_registry: dict[str, Any] | None = None,
    empirical_evidence_audit: dict[str, Any] | None = None,
    active_project_ids: Iterable[str] = (
        "project01",
        "project02",
        "project03",
        "project05",
    ),
    deferred_module_refs: Iterable[str] = ("project02:A700",),
) -> dict[str, Any]:
    """Build a deterministic evidence-level module readiness and gap report."""

    validate_global_module_catalog(base_catalog)
    active_projects = {str(value).strip().lower() for value in active_project_ids}
    deferred_refs = {str(value).strip().lower() for value in deferred_module_refs}
    empirical_by_ref = {
        (
            f"{str(row.get('projectId') or '').strip().lower()}:"
            f"{str(row.get('moduleToken') or '').strip()}"
        ).lower(): row
        for row in (empirical_evidence_audit or {}).get("modules") or []
        if str(row.get("projectId") or "").strip()
        and str(row.get("moduleToken") or "").strip()
    }
    records, release_catalogs = _release_records(
        list(release_packages), safety_registry=safety_registry
    )
    catalogs = [base_catalog, *release_catalogs]

    definitions: dict[str, dict[str, Any]] = {}
    ports: dict[str, dict[str, Any]] = {}
    templates: dict[str, dict[str, Any]] = {}
    compatibility: dict[tuple[str, str, str], dict[str, Any]] = {}
    for catalog in catalogs:
        for row in catalog.get("moduleDefinitions") or []:
            definitions[str(row.get("moduleDefinitionId") or "")] = row
        for row in catalog.get("semanticPorts") or []:
            ports[str(row.get("globalPortId") or "")] = row
        for row in catalog.get("connectionTemplates") or []:
            templates[str(row.get("globalTemplateId") or "")] = row
        for row in catalog.get("compatibility") or []:
            compatibility[
                (
                    str(row.get("globalTemplateId") or ""),
                    str(row.get("portAId") or ""),
                    str(row.get("portBId") or ""),
                )
            ] = row

    target_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    context_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        target_records[record["targetModuleDefinitionId"]].append(record)
        context_records[record["contextModuleDefinitionId"]].append(record)

    module_rows: list[dict[str, Any]] = []
    for definition_id, definition in definitions.items():
        refs = _project_refs(definition)
        active_refs = [
            ref for ref in refs if ref.split(":", 1)[0].lower() in active_projects
        ]
        if not active_refs:
            continue
        is_base = any(
            bool(row.get("isBaseModule"))
            and str(row.get("projectId") or "").strip().lower() in active_projects
            for row in definition.get("projectAliases") or []
        )
        module_ports = [
            ports[port_id]
            for port_id in definition.get("portIds") or []
            if port_id in ports
        ]
        mechanical_ports = [
            row for row in module_ports if str(row.get("category") or "") == "mechanical"
        ]
        portable_mechanical_ports = [
            row
            for row in mechanical_ports
            if bool(row.get("portable"))
            and (row.get("endpointEvidence") or [])
            and all(
                endpoint.get("rolePortable") is not False
                for endpoint in row.get("endpointEvidence") or []
            )
        ]
        incoming_templates = []
        for edge in compatibility.values():
            template_id = str(edge.get("globalTemplateId") or "")
            port_a = ports.get(str(edge.get("portAId") or "")) or {}
            if str(port_a.get("moduleDefinitionId") or "") != definition_id:
                continue
            template = templates.get(template_id) or {}
            incoming_templates.append(
                {
                    "globalTemplateId": template_id,
                    "legacyTemplateId": template.get("legacyTemplateId"),
                    "complete": _template_is_complete(template),
                    "portableForTemplate": bool(edge.get("portableForTemplate")),
                }
            )
        target_tokens = {
            ref.split(":", 1)[1].casefold()
            for ref in active_refs
            if ":" in ref
        }
        declared_complete_templates = []
        for template_id, template in templates.items():
            legacy_id = str(template.get("legacyTemplateId") or "")
            is_named_target = any(
                legacy_id.casefold().startswith(f"{token}_to_")
                for token in target_tokens
            )
            if not is_named_target or not _template_is_complete(template):
                continue
            candidate_port_ids = {
                *(template.get("candidatePortIdsA") or []),
                *(template.get("candidatePortIdsB") or []),
            }
            if not any(
                str((ports.get(str(port_id)) or {}).get("moduleDefinitionId") or "")
                == definition_id
                for port_id in candidate_port_ids
            ):
                continue
            declared_complete_templates.append(
                {
                    "globalTemplateId": template_id,
                    "legacyTemplateId": legacy_id,
                }
            )
        released = target_records.get(definition_id, [])
        usable_released = [row for row in released if not row["runtimeSafetyBlocked"]]
        verified = [
            row
            for row in usable_released
            if row["templateComplete"]
            and row["cadAssessmentPassed"]
            and row["externalPoseClosed"]
        ]
        passed_but_open = [
            row
            for row in usable_released
            if row["cadAssessmentPassed"] and not row["externalPoseClosed"]
        ]
        explicitly_deferred = any(ref.lower() in deferred_refs for ref in active_refs)
        empirical_row = next(
            (
                empirical_by_ref[ref.lower()]
                for ref in active_refs
                if ref.lower() in empirical_by_ref
            ),
            None,
        )

        blockers: list[str] = []
        next_action = "none"
        if explicitly_deferred:
            status = "deferred"
            blockers.append("EXPLICITLY_DEFERRED_BY_CURRENT_SCOPE")
            next_action = "keep_deferred"
        elif is_base:
            provided_verified = [
                row
                for row in context_records.get(definition_id, [])
                if not row["runtimeSafetyBlocked"]
                and row["cadAssessmentPassed"]
                and row["externalPoseClosed"]
            ]
            if provided_verified:
                status = "context_provider_verified"
                next_action = "none"
            elif portable_mechanical_ports:
                status = "context_provider_release_pending"
                blockers.append("NO_VERIFIED_CONSUMER_EVIDENCE")
                next_action = "validate_one_rigid_consumer"
            else:
                status = "endpoint_missing"
                blockers.append("NO_PORTABLE_MECHANICAL_CONTEXT_PORT")
                next_action = "register_context_slot_endpoints"
        elif verified:
            status = "portable_verified"
            next_action = "none"
        elif (empirical_row or {}).get("state") == "complete_installation_bundle_required":
            status = "installation_bundle_repair_required"
            blockers.append("NONANCHOR_CAD_PROVES_EXTERNAL_DOF_REMAINS")
            next_action = "add_independent_installation_datum_then_rerun_cad"
        elif passed_but_open:
            status = "external_pose_evidence_required"
            blockers.append("EXTERNAL_PLACEMENT_NOT_CLOSED")
            next_action = "replace_or_complete_external_installation_bundle"
        elif any(row["runtimeSafetyBlocked"] for row in released):
            status = "runtime_safety_blocked"
            blockers.append("AUTHORIZED_TEMPLATE_REVOKED_AT_RUNTIME")
            next_action = "keep_blocked_until_new_external_pose_evidence"
        elif usable_released:
            status = "cad_evidence_missing"
            blockers.append("AUTHORIZED_TEMPLATE_WITHOUT_CURRENT_CAD_EVIDENCE")
            next_action = "run_nonprototype_cad_closure"
        elif any(row["complete"] and row["portableForTemplate"] for row in incoming_templates):
            status = "release_pending"
            blockers.append("COMPLETE_PORT_TEMPLATE_NOT_AUTHORIZED")
            next_action = "audit_and_publish_existing_template"
        elif declared_complete_templates:
            status = "compatibility_edge_missing"
            blockers.append("COMPLETE_TEMPLATE_NOT_LINKED_TO_COMPATIBILITY_EDGE")
            next_action = "register_template_compatibility_edge"
        elif portable_mechanical_ports:
            status = "template_missing"
            blockers.append("NO_COMPLETE_INSTALLATION_TEMPLATE")
            next_action = "compose_minimal_complete_mate_bundle"
        else:
            status = "endpoint_missing"
            blockers.append("NO_PORTABLE_MECHANICAL_INSTALLATION_ENDPOINTS")
            next_action = "recover_and_register_installation_endpoints"

        best_records = verified or passed_but_open or usable_released or released
        module_rows.append(
            {
                "moduleDefinitionId": definition_id,
                "projectModuleRefs": active_refs,
                "displayName": definition.get("displayName"),
                "category": definition.get("category"),
                "isBaseModule": is_base,
                "status": status,
                "blockers": blockers,
                "nextAction": next_action,
                "mechanicalPortCount": len(mechanical_ports),
                "portableMechanicalPortCount": len(portable_mechanical_ports),
                "completeInstallationTemplateCount": sum(
                    bool(row["complete"] and row["portableForTemplate"])
                    for row in incoming_templates
                ),
                "declaredCompleteTemplateCount": len(declared_complete_templates),
                "authorizedTemplateCount": len(released),
                "verifiedTemplateCount": len(verified),
                "bestEvidence": [
                    {
                        key: row.get(key)
                        for key in (
                            "authorizationKind",
                            "releaseId",
                            "releaseManifestPath",
                            "globalTemplateId",
                            "legacyTemplateId",
                            "cadAssessmentPassed",
                            "externalPoseClosed",
                            "targetFullyConstrained",
                            "runtimeSafetyBlocked",
                        )
                    }
                    for row in best_records[:3]
                ],
            }
        )

    status_order = {
        "endpoint_missing": 0,
        "template_missing": 1,
        "installation_bundle_repair_required": 2,
        "release_pending": 3,
        "cad_evidence_missing": 4,
        "external_pose_evidence_required": 5,
        "runtime_safety_blocked": 6,
        "portable_verified": 7,
        "context_provider_release_pending": 8,
        "context_provider_verified": 9,
        "deferred": 10,
    }
    category_priority = {
        "ccd": 0,
        "cleaning_weighing": 1,
        "positioning": 2,
        "gantry": 3,
        "glue_supply": 4,
        "transport": 5,
        "scanner": 6,
        "calibration": 7,
        "frame": 8,
    }
    module_rows.sort(
        key=lambda row: (
            status_order.get(str(row["status"]), 99),
            category_priority.get(str(row.get("category") or ""), 99),
            str(row["projectModuleRefs"]),
        )
    )
    completion_queue = [
        {
            "projectModuleRefs": row["projectModuleRefs"],
            "displayName": row["displayName"],
            "category": row["category"],
            "status": row["status"],
            "nextAction": row["nextAction"],
            "blockers": row["blockers"],
        }
        for row in module_rows
        if row["status"]
        not in {"portable_verified", "context_provider_verified", "deferred"}
    ]
    counts = Counter(str(row["status"]) for row in module_rows)
    report: dict[str, Any] = {
        "schemaVersion": GLOBAL_MODULE_GAP_REPORT_SCHEMA,
        "scope": {
            "activeProjectIds": sorted(active_projects),
            "deferredProjectIds": ["project06"],
            "deferredModuleRefs": sorted(deferred_refs),
            "excludedChecks": [
                "process_validity",
                "adapter_design",
                "collision",
                "brep",
                "dynamic_motion",
            ],
        },
        "claimBoundary": (
            "状态只覆盖外部机械安装端口、完整定位配合束、非原型CAD证据和发布授权；"
            "不代表工艺、碰撞、B-rep、动态运动或生产放行。"
        ),
        "summary": {
            "activeModuleCount": len(module_rows),
            "portableVerifiedCount": counts["portable_verified"],
            "contextProviderVerifiedCount": counts["context_provider_verified"],
            "deferredCount": counts["deferred"],
            "gapModuleCount": len(completion_queue),
            "statusCounts": dict(sorted(counts.items())),
        },
        "modules": module_rows,
        "completionQueue": completion_queue,
    }
    report["reportDigest"] = _digest(report)
    return report


def validate_global_module_gap_report(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schemaVersion") != GLOBAL_MODULE_GAP_REPORT_SCHEMA:
        raise GlobalModuleGapReportError("不支持的全目录模组缺口报告版本。")
    modules = report.get("modules")
    if not isinstance(modules, list):
        raise GlobalModuleGapReportError("缺口报告缺少modules数组。")
    ids = [str(row.get("moduleDefinitionId") or "") for row in modules]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise GlobalModuleGapReportError("moduleDefinitionId必须非空且唯一。")
    expected = _digest({key: value for key, value in report.items() if key != "reportDigest"})
    if report.get("reportDigest") != expected:
        raise GlobalModuleGapReportError("全目录模组缺口报告摘要不匹配。")
    return {
        "success": True,
        "schemaVersion": GLOBAL_MODULE_GAP_REPORT_SCHEMA,
        "activeModuleCount": len(modules),
        "reportDigest": expected,
    }
