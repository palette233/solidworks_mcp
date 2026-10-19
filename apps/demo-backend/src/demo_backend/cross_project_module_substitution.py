"""Lightweight role/port overlay and cross-project module substitution planning.

The signed global module catalog remains the CAD evidence authority.  This
module adds a small, reviewable semantic overlay and derives one candidate
cross-project installation relation without rebuilding the underlying endpoint
catalogs.  Collision and B-rep checks are intentionally outside this scope.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from .global_assembly_transactions import (
    compile_global_assembly_transaction_dag,
)
from .global_cad_transaction_packets import (
    compile_global_cad_transaction_manifest,
)
from .global_module_catalog import validate_global_module_catalog
from .cross_project_interface_triage import build_blocked_substitution_disposition
from .assembly_user_failure import (
    build_assembly_user_failure,
    explain_candidate_matrix_row,
)


ROLE_OVERLAY_SCHEMA = "module-semantic-role-overlay/v1"
SUBSTITUTION_REPORT_SCHEMA = "cross-project-module-substitution-report/v1"
CANDIDATE_MATRIX_SCHEMA = "cross-project-module-candidate-matrix/v1"


# A small, reviewable correction layer for installation ports whose original
# endpoint role names do not encode target/context direction.  These are
# evidence-backed exceptions, not inferred CAD geometry: the Project01 GN00
# release declares SS00.gn00_anti_rotation as the context-side member of the
# released GN00 locating combination.
PORT_DIRECTION_ALIAS_OVERRIDES: dict[str, str] = {
    "ss00.gn00_anti_rotation": "provided",
}


class CrossProjectModuleSubstitutionError(ValueError):
    pass


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48] or "module"


def _project_alias(definition: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    normalized = str(project_id).strip().lower()
    return next(
        (
            alias
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").strip().lower() == normalized
        ),
        None,
    )


def resolve_module_reference(
    catalog: dict[str, Any], reference: str | dict[str, str]
) -> dict[str, Any]:
    """Resolve a module by definition id or an explicit project/token pair."""

    definitions = list(catalog.get("moduleDefinitions") or [])
    if isinstance(reference, str):
        text = reference.strip()
        direct = next(
            (row for row in definitions if row.get("moduleDefinitionId") == text), None
        )
        if direct is not None:
            return direct
        match = re.fullmatch(r"(?i)(project\d+)\s*[:/]\s*([a-z]+\d+)", text)
        if not match:
            raise CrossProjectModuleSubstitutionError(
                f"模组引用必须是moduleDefinitionId或projectNN:TOKEN：{reference}"
            )
        project_id, token = match.group(1).lower(), match.group(2).upper()
    else:
        project_id = str(reference.get("projectId") or "").strip().lower()
        token = str(reference.get("moduleToken") or "").strip().upper()
    matches = [
        row
        for row in definitions
        if any(
            str(alias.get("projectId") or "").strip().lower() == project_id
            and str(alias.get("moduleToken") or "").strip().upper() == token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(matches) != 1:
        raise CrossProjectModuleSubstitutionError(
            f"模组引用不能唯一解析：{project_id}:{token}，候选数={len(matches)}"
        )
    return matches[0]


def _role_profile(definition: dict[str, Any]) -> dict[str, Any]:
    name = str(definition.get("displayName") or "")
    category = str(definition.get("category") or "")
    if category == "frame":
        primary, display, capabilities = "Base", "设备机架/安装基座", ["base"]
    elif category == "transport":
        primary, display, capabilities = "Transport", "产品传输模组", ["transport"]
    elif category == "scanner":
        primary, display, capabilities = "Scanner", "条码扫描模组", ["barcode_scan"]
    elif category == "ccd":
        primary, display, capabilities = "CCD", "CCD视觉定位模组", ["vision_alignment"]
    elif category == "gantry":
        primary, display, capabilities = "Gantry", "XYZ龙门点胶模组", ["dispensing"]
    elif category == "glue_supply":
        primary, display, capabilities = "GlueSupply", "供胶系统", ["glue_supply"]
    elif category == "positioning":
        primary, display, capabilities = "Positioning", "载具顶升/旋转定位模组", ["carrier_positioning"]
    elif category == "calibration":
        primary = "Calibration"
        if "称重" in name:
            display, capabilities = "标定与称重组合模组", ["calibration", "weighing"]
        else:
            display, capabilities = "针头标定模组", ["calibration"]
    elif category == "cleaning_weighing":
        if "硬度" in name or "测试" in name:
            primary, display = "CleaningWeighing", "清洁与胶体检测组合模组"
            capabilities = ["cleaning", "weighing", "waste_collection", "inspection"]
        elif ("排胶" in name or "废胶" in name) and "清洁" not in name:
            primary, display = "WasteCup", "排胶/废胶收集模组"
            capabilities = ["waste_collection"]
        elif "针头清洁" in name or "自动" in name and "清洁" in name:
            primary, display = "Cleaning", "针头清洁模组"
            capabilities = ["cleaning"]
        else:
            primary, display = "CleaningWeighing", "清洁/称重组合模组"
            capabilities = ["cleaning", "weighing"]
    else:
        primary, display, capabilities = "Unclassified", "待分类", []
    return {
        "primaryRole": primary,
        "displayRole": display,
        "capabilities": capabilities,
    }


def build_module_role_overlay(catalog: dict[str, Any]) -> dict[str, Any]:
    """Build the accepted lightweight role layer for every catalog definition."""

    validate_global_module_catalog(catalog)
    modules: list[dict[str, Any]] = []
    for definition in catalog.get("moduleDefinitions") or []:
        role = _role_profile(definition)
        aliases = list(definition.get("projectAliases") or [])
        is_base = any(alias.get("isBaseModule") for alias in aliases)
        modules.append(
            {
                "moduleDefinitionId": definition["moduleDefinitionId"],
                "displayName": definition.get("displayName"),
                **role,
                "independentlyInstallable": True if is_base else None,
                "independentInstallReviewStatus": (
                    "confirmed_base" if is_base else "pending"
                ),
                "roleReviewStatus": "accepted_by_user",
                "roleReviewDate": "2026-10-12",
                "projectAliases": aliases,
            }
        )
    core = {
        "schemaVersion": ROLE_OVERLAY_SCHEMA,
        "sourceCatalogDigest": catalog.get("catalogDigest"),
        "moduleCount": len(modules),
        "modules": sorted(modules, key=lambda row: row["moduleDefinitionId"]),
        "policy": {
            "sourceCatalogMutated": False,
            "roleAndCapabilitySeparated": True,
            "independentInstallNotAutoConfirmed": True,
            "collisionOrBrepRequired": False,
        },
    }
    return {**core, "overlayDigest": _digest(core)}


def validate_module_role_overlay(
    overlay: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    if overlay.get("schemaVersion") != ROLE_OVERLAY_SCHEMA:
        raise CrossProjectModuleSubstitutionError("不支持的角色覆盖配置版本。")
    if overlay.get("sourceCatalogDigest") != catalog.get("catalogDigest"):
        raise CrossProjectModuleSubstitutionError("角色覆盖配置与全局目录摘要不匹配。")
    rows = list(overlay.get("modules") or [])
    ids = [str(row.get("moduleDefinitionId") or "") for row in rows]
    expected_ids = sorted(
        str(row.get("moduleDefinitionId") or "")
        for row in catalog.get("moduleDefinitions") or []
    )
    if sorted(ids) != expected_ids or len(ids) != len(set(ids)):
        raise CrossProjectModuleSubstitutionError("角色覆盖配置没有一一覆盖全局模组定义。")
    expected_digest = _digest(
        {key: value for key, value in overlay.items() if key != "overlayDigest"}
    )
    if overlay.get("overlayDigest") != expected_digest:
        raise CrossProjectModuleSubstitutionError("角色覆盖配置摘要不匹配。")
    return {"success": True, "moduleCount": len(rows), "overlayDigest": expected_digest}


def _template_signature(template: dict[str, Any]) -> dict[str, Any]:
    steps = [
        row
        for row in template.get("mateSteps") or []
        if row.get("applicationMode") != "validate_only"
    ]
    topology = [
        {
            "mateTypeName": row.get("mateTypeName"),
            "endpointRoleA": row.get("endpointRoleA"),
            "endpointRoleB": row.get("endpointRoleB"),
        }
        for row in steps
    ]
    effect = template.get("constraintEffect") or {}
    fully_locates = effect.get("fullyLocatesAddedComponent") is True
    residual = effect.get("expectedResidualDof")
    return {
        "topology": topology,
        "signature": "|".join(
            f"{row.get('mateTypeName')}:{row.get('endpointRoleA')}>{row.get('endpointRoleB')}"
            for row in steps
        ),
        "fullyLocatesAddedComponent": fully_locates,
        "expectedResidualDof": residual,
        "closed": fully_locates and residual == 0,
    }


def _locating_feature_geometry_signature(port: dict[str, Any]) -> dict[str, Any]:
    """Measure rigid invariants between locating features, not face centroids."""

    centers: dict[str, tuple[float, float, float]] = {}
    for endpoint in port.get("endpointEvidence") or []:
        role = str(endpoint.get("role") or "")
        center = endpoint.get("faceCenterLocal")
        if (
            ("locating_hole" in role or "locating_pin" in role)
            and isinstance(center, list)
            and len(center) == 3
        ):
            centers[role] = tuple(float(value) for value in center)
    spacings = []
    roles = sorted(centers)
    for index, role_a in enumerate(roles):
        for role_b in roles[index + 1 :]:
            spacings.append(
                {
                    "roleA": role_a,
                    "roleB": role_b,
                    "distanceMeters": math.dist(centers[role_a], centers[role_b]),
                }
            )
    return {
        "locatingFeatureCount": len(centers),
        "pairSpacings": spacings,
        "sufficientForSpacingCheck": bool(spacings),
    }


def _geometry_compatibility(
    source_port: dict[str, Any], target_port: dict[str, Any], *, tolerance: float = 1e-6
) -> dict[str, Any]:
    source = _locating_feature_geometry_signature(source_port)
    target = _locating_feature_geometry_signature(target_port)
    comparable = (
        source["sufficientForSpacingCheck"]
        and target["sufficientForSpacingCheck"]
        and len(source["pairSpacings"]) == len(target["pairSpacings"])
    )
    differences: list[dict[str, Any]] = []
    if comparable:
        for source_pair, target_pair in zip(
            source["pairSpacings"], target["pairSpacings"], strict=True
        ):
            differences.append(
                {
                    "roles": [source_pair["roleA"], source_pair["roleB"]],
                    "sourceDistanceMeters": source_pair["distanceMeters"],
                    "targetDistanceMeters": target_pair["distanceMeters"],
                    "absoluteDifferenceMeters": abs(
                        source_pair["distanceMeters"]
                        - target_pair["distanceMeters"]
                    ),
                }
            )
    return {
        "source": source,
        "target": target,
        "comparable": comparable,
        "toleranceMeters": tolerance,
        "compatible": comparable
        and all(
            row["absoluteDifferenceMeters"] <= tolerance for row in differences
        ),
        "differences": differences,
    }


def _installation_templates_for_definition(
    catalog: dict[str, Any], definition_id: str
) -> list[dict[str, Any]]:
    ports = {
        str(port.get("globalPortId") or ""): port
        for port in catalog.get("semanticPorts") or []
    }
    result = []
    for template in catalog.get("connectionTemplates") or []:
        if "installation" not in (template.get("purposes") or []):
            continue
        candidate_ids = {
            str(port_id)
            for key in ("candidatePortIdsA", "candidatePortIdsB")
            for port_id in template.get(key) or []
        }
        if any(
            (ports.get(port_id) or {}).get("moduleDefinitionId") == definition_id
            for port_id in candidate_ids
        ):
            result.append(template)
    return result


def _role_index(overlay: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["moduleDefinitionId"]): row for row in overlay.get("modules") or []
    }


def _canonical_class(primary_role: str) -> str:
    mapping = {
        "Transport": "transport_base_mount",
        "Scanner": "scanner_base_mount",
        "CCD": "ccd_base_mount",
        "Calibration": "calibration_base_mount",
        "Cleaning": "cleaning_base_mount",
        "CleaningWeighing": "service_station_base_mount",
        "WasteCup": "waste_cup_base_mount",
        "Gantry": "gantry_base_mount",
        "GlueSupply": "glue_supply_base_mount",
        "Positioning": "positioning_base_mount",
        "Base": "base_root",
    }
    return mapping.get(primary_role, "unclassified_mount")


def _installation_profile_id(port_id: str, primary_role: str) -> str:
    local = port_id.split("::port/", 1)[-1].rsplit("/", 1)[0]
    return f"installation-profile/{_slug(primary_role)}/{_slug(local)}"


def _port_direction_override(port: dict[str, Any]) -> str | None:
    for alias in port.get("aliases") or []:
        direction = PORT_DIRECTION_ALIAS_OVERRIDES.get(str(alias).casefold())
        if direction is not None:
            return direction
    return None


def augment_catalog_with_role_and_port_overlay(
    catalog: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    """Return a digest-valid catalog with non-destructive normalized metadata."""

    validate_module_role_overlay(overlay, catalog)
    result = deepcopy(catalog)
    roles = _role_index(overlay)
    definitions = {
        str(row["moduleDefinitionId"]): row
        for row in result.get("moduleDefinitions") or []
    }
    ports = {
        str(row["globalPortId"]): row for row in result.get("semanticPorts") or []
    }
    for definition_id, definition in definitions.items():
        role = roles[definition_id]
        definition["semanticRole"] = {
            key: deepcopy(role[key])
            for key in (
                "primaryRole",
                "displayRole",
                "capabilities",
                "roleReviewStatus",
                "independentlyInstallable",
                "independentInstallReviewStatus",
            )
        }

    template_membership: dict[str, list[dict[str, Any]]] = {}
    for template in result.get("connectionTemplates") or []:
        for key in ("candidatePortIdsA", "candidatePortIdsB"):
            for port_id in template.get(key) or []:
                template_membership.setdefault(str(port_id), []).append(template)
    counterpart_roles: dict[str, set[str]] = {}
    for edge in result.get("compatibility") or []:
        a, b = str(edge.get("portAId") or ""), str(edge.get("portBId") or "")
        for current, other in ((a, b), (b, a)):
            other_definition_id = str((ports.get(other) or {}).get("moduleDefinitionId") or "")
            other_role = (roles.get(other_definition_id) or {}).get("primaryRole")
            if other_role:
                counterpart_roles.setdefault(current, set()).add(str(other_role))

    for port_id, port in ports.items():
        definition_id = str(port.get("moduleDefinitionId") or "")
        role = roles.get(definition_id) or {}
        primary_role = str(role.get("primaryRole") or "Unclassified")
        memberships = template_membership.get(port_id) or []
        purposes = {
            str(purpose)
            for template in memberships
            for purpose in template.get("purposes") or []
        }
        endpoint_roles = sorted(
            {
                str(row.get("role") or "")
                for row in port.get("endpointEvidence") or []
                if str(row.get("role") or "")
            }
        )
        has_target_endpoint = any("_target_" in item for item in endpoint_roles)
        has_context_endpoint = any("_context_" in item for item in endpoint_roles)
        port_direction = None
        direction_override = _port_direction_override(port)
        if port.get("category") == "functional":
            purpose = "process"
        elif "installation" in purposes:
            if direction_override == "provided":
                port_direction = "provided"
                purpose = "child_module_slot"
            elif direction_override == "required":
                port_direction = "required"
                purpose = "external_installation"
            elif primary_role == "Base" or (has_context_endpoint and not has_target_endpoint):
                port_direction = "provided"
                purpose = (
                    "target_slot" if primary_role == "Base" else "child_module_slot"
                )
            else:
                port_direction = "required"
                purpose = "external_installation"
        elif purposes & {"spacing", "verification", "validation"}:
            purpose = "verification_reference"
            port_direction = "validation"
        else:
            purpose = "unclassified"
        slot_roles = sorted(counterpart_roles.get(port_id) or [])
        effective_role = (
            slot_roles[0]
            if port_direction == "provided" and len(slot_roles) == 1
            else primary_role
        )
        port["normalizedInterface"] = {
            "canonicalInterfaceClass": _canonical_class(effective_role),
            "portPurpose": purpose,
            "portDirection": port_direction,
            "ownerRole": primary_role,
            "slotRole": effective_role if port_direction in {"required", "provided"} else None,
            "installationProfileId": (
                _installation_profile_id(port_id, primary_role)
                if port_direction == "required"
                else None
            ),
            "endpointRoles": endpoint_roles,
            "sourceInterfaceType": port.get("interfaceType"),
            "reviewStatus": (
                "evidence_backed_direction_override"
                if direction_override is not None
                else "semi_automatic"
            ),
        }
    result["semanticOverlayBinding"] = {
        "schemaVersion": overlay["schemaVersion"],
        "overlayDigest": overlay["overlayDigest"],
        "sourceCatalogDigest": overlay["sourceCatalogDigest"],
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return result


def _directed_installation_member(
    ports: dict[str, dict[str, Any]],
    template: dict[str, Any],
    definition_id: str,
) -> dict[str, Any] | None:
    candidate_ids = {
        str(port_id)
        for key in ("candidatePortIdsA", "candidatePortIdsB")
        for port_id in template.get(key) or []
    }
    own = [
        port_id
        for port_id in candidate_ids
        if (ports.get(port_id) or {}).get("moduleDefinitionId") == definition_id
    ]
    other = [port_id for port_id in candidate_ids if port_id not in own]
    own_port = ports.get(own[0]) if len(own) == 1 else None
    other_port = ports.get(other[0]) if len(other) == 1 else None
    own_direction = ((own_port or {}).get("normalizedInterface") or {}).get(
        "portDirection"
    )
    other_direction = ((other_port or {}).get("normalizedInterface") or {}).get(
        "portDirection"
    )
    if (
        own_port is None
        or other_port is None
        or own_direction != "required"
        or other_direction != "provided"
    ):
        return None
    return {
        "template": template,
        "modulePort": own_port,
        "modulePorts": [own_port],
        "basePort": other_port,
        "basePorts": [other_port],
        "signature": _template_signature(template),
        "candidateKind": "atomic_template",
        "memberTemplateIds": [template.get("globalTemplateId")],
    }


def _atomic_installation_candidates(
    catalog: dict[str, Any], definition: dict[str, Any]
) -> list[dict[str, Any]]:
    ports = {
        str(port["globalPortId"]): port for port in catalog.get("semanticPorts") or []
    }
    candidates = [
        row
        for template in _installation_templates_for_definition(
            catalog, str(definition["moduleDefinitionId"])
        )
        if (
            row := _directed_installation_member(
                ports, template, str(definition["moduleDefinitionId"])
            )
        )
        is not None
    ]
    closed = [
        row
        for row in candidates
        if row["signature"]["closed"]
        and len(
            [
                step
                for step in row["template"].get("mateSteps") or []
                if step.get("applicationMode") != "validate_only"
            ]
        )
        >= 2
    ]
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in closed:
        key = (
            str(row["modulePort"].get("globalPortId") or ""),
            str(row["basePort"].get("globalPortId") or ""),
            _digest(row["template"].get("mateSteps") or []),
        )
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def _combination_installation_candidates(
    catalog: dict[str, Any], definition: dict[str, Any]
) -> list[dict[str, Any]]:
    ports = {
        str(port["globalPortId"]): port for port in catalog.get("semanticPorts") or []
    }
    templates = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    candidates: list[dict[str, Any]] = []
    for combination in catalog.get("templateCombinations") or []:
        if (
            combination.get("exactMemberSetRequired") is not True
            or combination.get("fullyLocatesAddedComponent") is not True
            or int(combination.get("expectedResidualDof", -1)) != 0
        ):
            continue
        member_ids = [
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        ]
        members: list[dict[str, Any]] = []
        for template_id in member_ids:
            template = templates.get(template_id)
            if template is None:
                members = []
                break
            member = _directed_installation_member(
                ports, template, str(definition["moduleDefinitionId"])
            )
            if member is None:
                members = []
                break
            members.append(member)
        if not members:
            continue
        primary_id = str(combination.get("primaryGlobalTemplateId") or member_ids[0])
        primary = next(
            (row for row in members if row["template"].get("globalTemplateId") == primary_id),
            members[0],
        )
        mate_steps = [
            deepcopy(step)
            for row in members
            for step in row["template"].get("mateSteps") or []
        ]
        synthetic_template = {
            "globalTemplateId": combination.get("globalCombinationId"),
            "legacyTemplateId": combination.get("legacyCombinationId"),
            "purposes": ["installation"],
            "candidatePortIdsA": [
                row["modulePort"].get("globalPortId") for row in members
            ],
            "candidatePortIdsB": [
                row["basePort"].get("globalPortId") for row in members
            ],
            "constraintEffect": {
                "fullyLocatesAddedComponent": True,
                "expectedResidualDof": 0,
            },
            "mateSteps": mate_steps,
            "provenance": deepcopy(combination.get("provenance") or {}),
        }
        signature = _template_signature(synthetic_template)
        driving_count = sum(
            step.get("applicationMode") != "validate_only" for step in mate_steps
        )
        if not signature["closed"] or driving_count < 2:
            continue
        candidates.append(
            {
                "template": synthetic_template,
                "modulePort": primary["modulePort"],
                "modulePorts": [row["modulePort"] for row in members],
                "basePort": primary["basePort"],
                "basePorts": [row["basePort"] for row in members],
                "signature": signature,
                "candidateKind": "template_combination",
                "memberTemplateIds": member_ids,
                "globalCombinationId": combination.get("globalCombinationId"),
            }
        )
    return candidates


def _installation_candidates(
    catalog: dict[str, Any], definition: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = [
        *_atomic_installation_candidates(catalog, definition),
        *_combination_installation_candidates(catalog, definition),
    ]
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("candidateKind") or ""),
            str(row["template"].get("globalTemplateId") or ""),
            _digest(row["template"].get("mateSteps") or []),
        )
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def _pair_projects(definition: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(alias.get("projectId") or "").strip().lower()
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").strip()
        }
    )


def _installation_summary(row: dict[str, Any]) -> dict[str, Any]:
    module_port = row["modulePort"]
    base_port = row["basePort"]
    module_interface = module_port.get("normalizedInterface") or {}
    base_interface = base_port.get("normalizedInterface") or {}
    target_provider_roles = sorted(
        {
            str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
            for port in row.get("basePorts") or [base_port]
            if str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
        }
    )
    return {
        "templateId": row["template"].get("globalTemplateId"),
        "candidateKind": row.get("candidateKind"),
        "memberTemplateIds": row.get("memberTemplateIds") or [],
        "modulePortId": module_port.get("globalPortId"),
        "targetSlotPortId": base_port.get("globalPortId"),
        "installationProfileId": module_interface.get("installationProfileId"),
        "canonicalInterfaceClass": module_interface.get("canonicalInterfaceClass"),
        "targetInterfaceClass": base_interface.get("canonicalInterfaceClass"),
        "targetSlotProviderRole": base_interface.get("ownerRole"),
        "targetSlotProviderRoles": target_provider_roles,
        "targetSlotPurpose": base_interface.get("portPurpose"),
        "mateSignature": row["signature"],
        "modulePortPortable": all(
            port.get("portable") is True
            for port in row.get("modulePorts") or [module_port]
        ),
        "targetSlotPortable": all(
            port.get("portable") is True
            for port in row.get("basePorts") or [base_port]
        ),
        "locatingFeatureGeometry": _locating_feature_geometry_signature(module_port),
    }


def _assess_installation_pair(
    source: dict[str, Any], target: dict[str, Any]
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    source_interface = source["modulePort"].get("normalizedInterface") or {}
    target_interface = target["basePort"].get("normalizedInterface") or {}
    if source_interface.get("canonicalInterfaceClass") != target_interface.get(
        "canonicalInterfaceClass"
    ):
        blockers.append(
            {
                "code": "CANONICAL_INTERFACE_CLASS_MISMATCH",
                "source": source_interface.get("canonicalInterfaceClass"),
                "target": target_interface.get("canonicalInterfaceClass"),
                "severity": "hard",
            }
        )
    source_provider_roles = sorted(
        {
            str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
            for port in source.get("basePorts") or [source["basePort"]]
            if str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
        }
    )
    target_provider_roles = sorted(
        {
            str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
            for port in target.get("basePorts") or [target["basePort"]]
            if str((port.get("normalizedInterface") or {}).get("ownerRole") or "")
        }
    )
    if source_provider_roles != target_provider_roles:
        blockers.append(
            {
                "code": "TARGET_SLOT_PROVIDER_ROLE_MISMATCH",
                "source": source_provider_roles,
                "target": target_provider_roles,
                "severity": "hard",
            }
        )
    if source["signature"]["signature"] != target["signature"]["signature"]:
        blockers.append(
            {
                "code": "MATE_TOPOLOGY_MISMATCH",
                "source": source["signature"]["signature"],
                "target": target["signature"]["signature"],
                "severity": "hard",
            }
        )
    if not all(
        port.get("portable") is True
        for port in source.get("modulePorts") or [source["modulePort"]]
    ):
        blockers.append({"code": "SOURCE_MODULE_PORT_NOT_PORTABLE", "severity": "hard"})
    if not all(
        port.get("portable") is True
        for port in target.get("basePorts") or [target["basePort"]]
    ):
        blockers.append({"code": "TARGET_SLOT_PORT_NOT_PORTABLE", "severity": "hard"})
    geometry = _geometry_compatibility(source["modulePort"], target["basePort"])
    if not geometry["comparable"]:
        blockers.append(
            {
                "code": "LOCATING_FEATURE_GEOMETRY_NOT_COMPARABLE",
                "severity": "review",
            }
        )
    elif not geometry["compatible"]:
        blockers.append(
            {
                "code": "LOCATING_FEATURE_SPACING_MISMATCH",
                "severity": "hard",
                "differences": geometry["differences"],
            }
        )
    hard_count = sum(row.get("severity") == "hard" for row in blockers)
    review_count = sum(row.get("severity") == "review" for row in blockers)
    return {
        "sourceInstallation": _installation_summary(source),
        "targetInstallation": _installation_summary(target),
        "locatingFeatureGeometry": geometry,
        "blockers": blockers,
        "hardBlockerCount": hard_count,
        "reviewBlockerCount": review_count,
        "score": hard_count * 100 + review_count * 10,
    }


def _select_atomic_installation_pair(
    catalog: dict[str, Any],
    source_definition: dict[str, Any],
    target_definition: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Select one context-compatible source/target installation profile pair."""

    source_candidates = _installation_candidates(catalog, source_definition)
    target_candidates = _installation_candidates(catalog, target_definition)
    if not source_candidates or not target_candidates:
        raise CrossProjectModuleSubstitutionError(
            "跨项目替换至少一侧缺少自身安装端口："
            f"source={len(source_candidates)}, target={len(target_candidates)}。"
        )
    assessments = [
        (source, target, _assess_installation_pair(source, target))
        for source in source_candidates
        for target in target_candidates
    ]
    assessments.sort(
        key=lambda item: (
            item[2]["score"],
            str(item[0]["template"].get("globalTemplateId")),
            str(item[1]["template"].get("globalTemplateId")),
        )
    )
    best_score = assessments[0][2]["score"]
    best = [item for item in assessments if item[2]["score"] == best_score]
    if len(best) != 1:
        raise CrossProjectModuleSubstitutionError(
            "跨项目替换仍有多个同等级安装配置，必须提供installationProfileId："
            f"候选对数={len(best)}。"
        )
    return best[0]


def build_cross_project_candidate_matrix(
    catalog: dict[str, Any],
    overlay: dict[str, Any],
    *,
    evidence_catalogs: list[dict[str, Any]] | None = None,
    deferred_project_ids: set[str] | None = None,
    released_direct_executions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rank every same-role, cross-project module replacement direction.

    Each project-specific release may contain richer endpoint/template evidence
    than the shared base catalog.  The matrix consumes those releases as
    evidence sources without mutating or pretending to merge their immutable
    publication histories.
    """

    validate_module_role_overlay(overlay, catalog)
    deferred_projects = {
        str(value).strip().lower()
        for value in (deferred_project_ids or set())
        if str(value).strip()
    }
    definitions = {
        str(row["moduleDefinitionId"]): row
        for row in catalog.get("moduleDefinitions") or []
    }
    roles = _role_index(overlay)
    sources = evidence_catalogs or [catalog]
    installations: dict[str, list[dict[str, Any]]] = {
        definition_id: [] for definition_id in definitions
    }
    evidence_digests: list[str] = []
    for evidence in sources:
        validate_global_module_catalog(evidence)
        evidence_digests.append(str(evidence.get("catalogDigest") or ""))
        evidence_overlay = build_module_role_overlay(evidence)
        normalized = augment_catalog_with_role_and_port_overlay(
            evidence, evidence_overlay
        )
        evidence_definitions = {
            str(row["moduleDefinitionId"]): row
            for row in normalized.get("moduleDefinitions") or []
        }
        for definition_id in definitions:
            definition = evidence_definitions.get(definition_id)
            if definition is None:
                continue
            for installation in _installation_candidates(normalized, definition):
                installation_template = installation.get("template") or {}
                installation_provenance = (
                    installation_template.get("provenance") or {}
                )
                # A released cross-project relation is an executable result,
                # not another native installation profile of the source
                # module.  Mixing it back into profile discovery creates a
                # false ambiguity (for example AE00 appears to have both its
                # AA00-native interface and the already composed JJ00 slot).
                if (
                    "cross_project_substitution"
                    in (installation_template.get("purposes") or [])
                    or installation_provenance.get("kind")
                    == "cross_project_template_composition"
                ):
                    continue
                row = deepcopy(installation)
                row["evidenceCatalogDigest"] = evidence.get("catalogDigest")
                installations[definition_id].append(row)
    for definition_id, rows in installations.items():
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (
                str(row["modulePort"].get("globalPortId") or ""),
                str(row["basePort"].get("globalPortId") or ""),
                _digest(row["template"].get("mateSteps") or []),
            )
            unique[key] = row
        installations[definition_id] = [unique[key] for key in sorted(unique)]

    rows: list[dict[str, Any]] = []
    definitions_list = sorted(definitions.values(), key=lambda row: row["moduleDefinitionId"])
    for source_definition in definitions_list:
        source_id = str(source_definition["moduleDefinitionId"])
        source_role = str((roles.get(source_id) or {}).get("primaryRole") or "")
        if source_role in {"", "Base", "Unclassified"}:
            continue
        source_projects = _pair_projects(source_definition)
        for target_definition in definitions_list:
            target_id = str(target_definition["moduleDefinitionId"])
            if target_id == source_id:
                continue
            target_role = str((roles.get(target_id) or {}).get("primaryRole") or "")
            if target_role != source_role:
                continue
            target_projects = _pair_projects(target_definition)
            if not source_projects or not target_projects or set(source_projects) & set(target_projects):
                continue
            source_candidates = installations.get(source_id) or []
            target_candidates = installations.get(target_id) or []
            blockers: list[dict[str, Any]] = []
            selected: dict[str, Any] | None = None
            if not source_candidates:
                blockers.append({"code": "SOURCE_INSTALLATION_PORT_OR_TEMPLATE_MISSING"})
            if not target_candidates:
                blockers.append({"code": "TARGET_SLOT_PORT_OR_TEMPLATE_MISSING"})
            if source_candidates and target_candidates:
                pair_assessments = [
                    _assess_installation_pair(source, target)
                    for source in source_candidates
                    for target in target_candidates
                ]
                pair_assessments.sort(
                    key=lambda item: (
                        item["score"],
                        str(item["sourceInstallation"]["templateId"]),
                        str(item["targetInstallation"]["templateId"]),
                    )
                )
                selected = pair_assessments[0]
                blockers.extend(selected["blockers"])
                best_score = selected["score"]
                equally_ranked = [
                    assessment
                    for assessment in pair_assessments
                    if assessment["score"] == best_score
                ]
                if len(equally_ranked) > 1:
                    blockers.append(
                        {
                            "code": "ATOMIC_INSTALLATION_TEMPLATE_DISAMBIGUATION_REQUIRED",
                            "sourceCandidateCount": len(source_candidates),
                            "targetCandidateCount": len(target_candidates),
                            "equallyRankedCandidatePairCount": len(equally_ranked),
                        }
                    )
            direct_matches = []
            if selected is not None:
                source_template_id = str(
                    selected["sourceInstallation"].get("templateId") or ""
                )
                target_template_id = str(
                    selected["targetInstallation"].get("templateId") or ""
                )
                direct_matches = [
                    deepcopy(row)
                    for row in (released_direct_executions or [])
                    if row.get("sourceModuleTemplateId") == source_template_id
                    and row.get("targetSlotTemplateId") == target_template_id
                    and row.get("status") == "released_direct_execution"
                ]
            codes = {row["code"] for row in blockers}
            if codes & {
                "SOURCE_INSTALLATION_PORT_OR_TEMPLATE_MISSING",
                "TARGET_SLOT_PORT_OR_TEMPLATE_MISSING",
            }:
                status = "needs_endpoint_or_template"
            elif selected is not None and selected["hardBlockerCount"] > 0:
                status = "incompatible"
            elif len(direct_matches) == 1 and not blockers:
                status = "released_direct_execution"
            elif "ATOMIC_INSTALLATION_TEMPLATE_DISAMBIGUATION_REQUIRED" in codes:
                status = "needs_template_disambiguation"
            elif selected is not None and selected["reviewBlockerCount"] > 0:
                status = "needs_mechanical_geometry_review"
            elif not blockers:
                status = "ready_for_effective_graph_composition"
            else:
                status = "incompatible"
            source_aliases = source_definition.get("projectAliases") or []
            target_aliases = target_definition.get("projectAliases") or []
            is_deferred = bool(
                deferred_projects & (set(source_projects) | set(target_projects))
            )
            matrix_row = {
                "sourceModuleDefinitionId": source_id,
                "sourceProjectIds": source_projects,
                "sourceModuleTokens": sorted(
                    str(row.get("moduleToken") or "") for row in source_aliases
                ),
                "targetModuleDefinitionId": target_id,
                "targetProjectIds": target_projects,
                "targetModuleTokens": sorted(
                    str(row.get("moduleToken") or "") for row in target_aliases
                ),
                "primaryRole": source_role,
                "status": status,
                "deferred": is_deferred,
                "sourceAtomicInstallationCount": len(source_candidates),
                "targetAtomicInstallationCount": len(target_candidates),
                "sourceInstallationProfileCount": len(source_candidates),
                "targetInstallationProfileCount": len(target_candidates),
                "optimalCandidatePairCount": (
                    len(equally_ranked)
                    if source_candidates and target_candidates
                    else 0
                ),
                "selectedAssessment": selected,
                "releasedDirectExecution": (
                    direct_matches[0] if len(direct_matches) == 1 else None
                ),
                "blockers": blockers,
            }
            user_failure = explain_candidate_matrix_row(matrix_row)
            if user_failure is not None:
                matrix_row["userFailureExplanation"] = user_failure
            rows.append(matrix_row)
    status_order = {
        "released_direct_execution": 0,
        "ready_for_effective_graph_composition": 1,
        "needs_mechanical_geometry_review": 2,
        "needs_template_disambiguation": 3,
        "needs_endpoint_or_template": 4,
        "incompatible": 5,
    }
    rows.sort(
        key=lambda row: (
            status_order[row["status"]],
            row["primaryRole"],
            row["sourceProjectIds"],
            row["sourceModuleTokens"],
            row["targetProjectIds"],
            row["targetModuleTokens"],
        )
    )
    status_counts = {
        status: sum(row["status"] == status for row in rows)
        for status in status_order
    }
    active_rows = [row for row in rows if not row["deferred"]]
    active_status_counts = {
        status: sum(row["status"] == status for row in active_rows)
        for status in status_order
    }

    def summarize(grouped_rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return [
            {
                "group": group,
                "directionalPairCount": len(group_rows),
                "activeDirectionalPairCount": sum(
                    not row["deferred"] for row in group_rows
                ),
                "statusCounts": {
                    status: sum(row["status"] == status for row in group_rows)
                    for status in status_order
                },
                "activeStatusCounts": {
                    status: sum(
                        row["status"] == status and not row["deferred"]
                        for row in group_rows
                    )
                    for status in status_order
                },
            }
            for group, group_rows in sorted(grouped_rows.items())
        ]

    by_role: dict[str, list[dict[str, Any]]] = {}
    by_project_pair: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_role.setdefault(str(row["primaryRole"]), []).append(row)
        project_pair = (
            f"{','.join(row['sourceProjectIds'])}"
            f"→{','.join(row['targetProjectIds'])}"
        )
        by_project_pair.setdefault(project_pair, []).append(row)
    ready_non_calibration = [
        row
        for row in active_rows
        if row["status"] == "ready_for_effective_graph_composition"
        and row["primaryRole"] != "Calibration"
    ]
    next_candidates = ready_non_calibration or [
        row
        for row in active_rows
        if row["status"] in {
            "ready_for_effective_graph_composition",
            "needs_mechanical_geometry_review",
            "needs_endpoint_or_template",
        }
        and row["primaryRole"] != "Calibration"
    ]
    unresolved_active_statuses = {
        "ready_for_effective_graph_composition",
        "needs_mechanical_geometry_review",
        "needs_template_disambiguation",
        "needs_endpoint_or_template",
    }
    unresolved_active_count = sum(
        active_status_counts[status] for status in unresolved_active_statuses
    )
    core = {
        "schemaVersion": CANDIDATE_MATRIX_SCHEMA,
        "sourceCatalogDigest": catalog.get("catalogDigest"),
        "roleOverlayDigest": overlay.get("overlayDigest"),
        "evidenceCatalogDigests": sorted(set(evidence_digests)),
        "releasedDirectExecutionCount": len(released_direct_executions or []),
        "releasedDirectExecutions": sorted(
            deepcopy(released_direct_executions or []),
            key=lambda row: (
                str(row.get("releaseId") or ""),
                str(row.get("globalTemplateId") or ""),
            ),
        ),
        "moduleDefinitionCount": len(definitions),
        "directionalPairCount": len(rows),
        "statusCounts": status_counts,
        "activeDirectionalPairCount": len(active_rows),
        "deferredDirectionalPairCount": len(rows) - len(active_rows),
        "activeStatusCounts": active_status_counts,
        "activeCoverageClosure": {
            "status": (
                "basic_active_coverage_closed"
                if unresolved_active_count == 0
                else "active_coverage_incomplete"
            ),
            "unresolvedDirectionalPairCount": unresolved_active_count,
            "releasedDirectionalPairCount": active_status_counts[
                "released_direct_execution"
            ],
            "explicitlyIncompatibleDirectionalPairCount": active_status_counts[
                "incompatible"
            ],
            "statement": (
                "当前开发范围内所有同角色有向组合均已归类为已发布直接执行或明确不兼容；"
                "延期项目不计入闭合，碰撞/B-rep未参与本阶段验收。"
                if unresolved_active_count == 0
                else "当前开发范围仍存在待发布、待复核、待消歧或待补端口/模板的组合。"
            ),
        },
        "roleSummaries": summarize(by_role),
        "projectPairSummaries": summarize(by_project_pair),
        "recommendedNextCandidates": next_candidates[:10],
        "rows": rows,
        "policy": {
            "sameRoleOnly": True,
            "crossProjectOnly": True,
            "atomicInstallationRequiresAtLeastTwoDrivingMateSteps": True,
            "installationPortDirectionRequired": True,
            "installationProfileSelectedByTargetContext": True,
            "hardIncompatibilityPrecedesTemplateDisambiguation": True,
            "declaredTemplateCombinationsAccepted": True,
            "deferredProjectIds": sorted(deferred_projects),
            "collisionOrBrepRequired": False,
            "missingGeometryIsReviewNotCompatibility": True,
            "immutableReleasesMutated": False,
            "crossProjectExecutionTemplatesExcludedFromNativeProfiles": True,
            "releasedDirectExecutionRequiresReleaseAuthorization": True,
        },
    }
    return {**core, "matrixDigest": _digest(core)}


def _graph_path_from_template(workspace: Path, template: dict[str, Any]) -> Path:
    provenance = template.get("provenance") or {}
    explicit = str(provenance.get("effectiveMateGraphPath") or "").strip()
    semantic = str(provenance.get("semanticCatalogPath") or "").strip()
    candidate = explicit or (
        semantic.rsplit("/", 1)[0] + "/assembly_plan_effective.json"
        if "/" in semantic
        else ""
    )
    if not candidate:
        raise CrossProjectModuleSubstitutionError("安装模板没有登记有效配合图来源。")
    path = Path(candidate)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    try:
        path.relative_to(workspace.resolve())
    except ValueError as exc:
        raise CrossProjectModuleSubstitutionError("有效配合图必须位于工作区内。") from exc
    if not path.is_file():
        raise CrossProjectModuleSubstitutionError(f"有效配合图不存在：{path}")
    return path


def _read_graph(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise CrossProjectModuleSubstitutionError(f"有效配合图根节点必须为对象：{path}")
    return value


def _graph_module_by_alias(graph: dict[str, Any], alias: str) -> dict[str, Any]:
    normalized = alias.strip().upper()
    modules = list(graph.get("Modules") or graph.get("modules") or [])
    exact = [
        row
        for row in modules
        if str(row.get("ModuleToken") or row.get("moduleToken") or "")
        .strip()
        .upper()
        == normalized
    ]
    if len(exact) == 1:
        return exact[0]
    suffix = [
        row
        for row in modules
        if str(row.get("ModuleToken") or row.get("moduleToken") or "")
        .strip()
        .upper()
        .endswith(normalized)
    ]
    if len(suffix) != 1:
        raise CrossProjectModuleSubstitutionError(
            f"有效配合图不能唯一解析模组别名：{alias}"
        )
    return suffix[0]


def _graph_mate_by_name(graph: dict[str, Any], mate_name: str) -> dict[str, Any]:
    matches = [
        row
        for row in graph.get("Mates") or graph.get("mates") or []
        if str(row.get("MateName") or row.get("mateName") or "") == mate_name
    ]
    if len(matches) != 1:
        raise CrossProjectModuleSubstitutionError(
            f"有效配合图不能唯一解析配合：{mate_name}"
        )
    return matches[0]


def _endpoint_for_token(mate: dict[str, Any], module_token: str) -> dict[str, Any]:
    normalized = module_token.strip().upper()
    matches = [
        row
        for row in mate.get("Endpoints") or mate.get("endpoints") or []
        if str(row.get("ModuleToken") or row.get("moduleToken") or "")
        .strip()
        .upper()
        == normalized
    ]
    if len(matches) != 1:
        raise CrossProjectModuleSubstitutionError(
            f"配合{mate.get('MateName')}不能唯一解析模组端点：{module_token}"
        )
    return deepcopy(matches[0])


def compose_cross_project_effective_mate_graph(
    workspace: Path,
    catalog: dict[str, Any],
    overlay: dict[str, Any],
    *,
    source_module: str | dict[str, str],
    replaced_module: str | dict[str, str],
) -> dict[str, Any]:
    """Compose one executable graph from a source module and a target slot graph."""

    normalized = augment_catalog_with_role_and_port_overlay(catalog, overlay)
    source = resolve_module_reference(normalized, source_module)
    replaced = resolve_module_reference(normalized, replaced_module)
    source_installation, target_installation, _ = _select_atomic_installation_pair(
        normalized,
        source,
        replaced,
    )
    source_alias = (source.get("projectAliases") or [{}])[0]
    replaced_alias = (replaced.get("projectAliases") or [{}])[0]
    target_base_definition = next(
        row
        for row in normalized.get("moduleDefinitions") or []
        if row["moduleDefinitionId"]
        == target_installation["basePort"]["moduleDefinitionId"]
    )
    target_project = str(replaced_alias.get("projectId") or "")
    target_base_alias = _project_alias(target_base_definition, target_project)
    if target_base_alias is None:
        raise CrossProjectModuleSubstitutionError("目标槽位基座缺少同项目别名。")

    source_graph_path = _graph_path_from_template(
        workspace, source_installation["template"]
    )
    target_graph_path = _graph_path_from_template(
        workspace, target_installation["template"]
    )
    source_graph = _read_graph(source_graph_path)
    target_graph = _read_graph(target_graph_path)
    source_module_row = _graph_module_by_alias(
        source_graph, str(source_alias.get("moduleToken") or "")
    )
    target_base_row = _graph_module_by_alias(
        target_graph, str(target_base_alias.get("moduleToken") or "")
    )
    replaced_module_row = _graph_module_by_alias(
        target_graph, str(replaced_alias.get("moduleToken") or "")
    )
    source_token = str(source_module_row.get("ModuleToken") or "")
    base_token = str(target_base_row.get("ModuleToken") or "")
    replaced_token = str(replaced_module_row.get("ModuleToken") or "")

    target_steps_by_role = {
        str(row.get("endpointRoleA") or row.get("endpointRoleB") or ""): row
        for row in target_installation["template"].get("mateSteps") or []
    }
    composed_mates: list[dict[str, Any]] = []
    for source_step in source_installation["template"].get("mateSteps") or []:
        role = str(
            source_step.get("endpointRoleA")
            or source_step.get("endpointRoleB")
            or ""
        )
        target_step = target_steps_by_role.get(role)
        if target_step is None:
            raise CrossProjectModuleSubstitutionError(
                f"目标槽位模板缺少端点角色：{role}"
            )
        source_mate = _graph_mate_by_name(
            source_graph, str(source_step.get("mateName") or "")
        )
        target_mate = _graph_mate_by_name(
            target_graph, str(target_step.get("mateName") or "")
        )
        source_endpoint = _endpoint_for_token(source_mate, source_token)
        base_endpoint = _endpoint_for_token(target_mate, base_token)
        composed = deepcopy(source_mate)
        composed["MateName"] = source_step.get("mateName")
        composed["MateType"] = source_step.get("mateType")
        composed["MateTypeName"] = source_step.get("mateTypeName")
        composed["Alignment"] = source_step.get("alignment")
        composed["AlignmentName"] = source_step.get("alignmentName")
        composed["Distance"] = source_step.get("distance")
        composed["Angle"] = source_step.get("angle")
        composed["Endpoints"] = [source_endpoint, base_endpoint]
        composed["ModuleTokens"] = [source_token, base_token]
        composed["ModuleHierarchyPaths"] = [
            source_endpoint.get("ModuleHierarchyPath"),
            base_endpoint.get("ModuleHierarchyPath"),
        ]
        composed["IsSuppressed"] = False
        composed["IsBasicTwoFaceRebuildable"] = True
        composed["RebuildRejectionReason"] = None
        composed["MateId"] = f"mate:cross-project:{_digest(composed)[:16]}"
        composed_mates.append(composed)

    graph = deepcopy(target_graph)
    graph["SourceAssemblyPath"] = None
    graph["Modules"] = [deepcopy(target_base_row), deepcopy(source_module_row)]
    graph["Mates"] = composed_mates
    graph["ModuleCount"] = 2
    graph["InterModuleMateCount"] = len(composed_mates)
    graph["BaseGraphPolicy"] = {
        "moduleTokens": [base_token],
        "source": "cross_project_slot_composition",
    }
    graph["EditPolicy"] = {
        "baseModuleToken": base_token,
        "initialPlacementMode": "deterministic",
        "sourceGraphImmutable": False,
        "fixedModuleTokens": [base_token],
        "caseAnchoredModuleTokens": [],
    }
    graph["SemanticAssemblyPlanAudit"] = {
        "planId": "cross-project-same-role-substitution-v1",
        "addedComponentHierarchyPath": source_module_row.get("HierarchyPath"),
        "generatedMateNames": [row.get("MateName") for row in composed_mates],
        "validationRelations": [],
        "executionMode": "cross_project_effective_graph_composition",
        "constraintAssessment": {
            "fullyLocatesAddedComponent": True,
            "expectedResidualDof": 0,
            "caseAnchoredModuleTokens": [],
        },
    }
    graph["CrossProjectComposition"] = {
        "sourceModuleDefinitionId": source["moduleDefinitionId"],
        "replacedModuleDefinitionId": replaced["moduleDefinitionId"],
        "targetBaseModuleDefinitionId": target_base_definition["moduleDefinitionId"],
        "sourceGraphPath": str(source_graph_path),
        "targetSlotGraphPath": str(target_graph_path),
        "sourceModuleToken": source_token,
        "replacedModuleToken": replaced_token,
        "targetBaseModuleToken": base_token,
        "sourceTemplateId": source_installation["template"]["globalTemplateId"],
        "targetSlotTemplateId": target_installation["template"]["globalTemplateId"],
        "topLevelOrLeafPoseAnchorsUsed": False,
    }
    graph["SavedJsonPath"] = None
    return graph


def build_cross_project_substitution_catalog(
    catalog: dict[str, Any],
    overlay: dict[str, Any],
    *,
    source_module: str | dict[str, str],
    replaced_module: str | dict[str, str],
    effective_mate_graph_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compose a source module port with a target project's occupied slot."""

    normalized = augment_catalog_with_role_and_port_overlay(catalog, overlay)
    source = resolve_module_reference(normalized, source_module)
    replaced = resolve_module_reference(normalized, replaced_module)
    roles = _role_index(overlay)
    source_role = roles[source["moduleDefinitionId"]]
    target_role = roles[replaced["moduleDefinitionId"]]
    blockers: list[dict[str, Any]] = []
    if source_role["primaryRole"] != target_role["primaryRole"]:
        blockers.append(
            {
                "code": "PRIMARY_ROLE_MISMATCH",
                "sourceRole": source_role["primaryRole"],
                "targetRole": target_role["primaryRole"],
            }
        )
    source_installation, target_installation, _ = _select_atomic_installation_pair(
        normalized,
        source,
        replaced,
    )
    source_interface = source_installation["modulePort"]["normalizedInterface"]
    target_interface = target_installation["basePort"]["normalizedInterface"]
    if source_interface["canonicalInterfaceClass"] != target_interface["canonicalInterfaceClass"]:
        blockers.append(
            {
                "code": "CANONICAL_INTERFACE_CLASS_MISMATCH",
                "source": source_interface["canonicalInterfaceClass"],
                "target": target_interface["canonicalInterfaceClass"],
            }
        )
    source_signature = source_installation["signature"]
    target_signature = target_installation["signature"]
    if source_signature["signature"] != target_signature["signature"]:
        blockers.append(
            {
                "code": "MATE_TOPOLOGY_MISMATCH",
                "source": source_signature["signature"],
                "target": target_signature["signature"],
            }
        )
    if not source_installation["modulePort"].get("portable"):
        blockers.append({"code": "SOURCE_MODULE_PORT_NOT_PORTABLE"})
    if not target_installation["basePort"].get("portable"):
        blockers.append({"code": "TARGET_SLOT_PORT_NOT_PORTABLE"})
    geometry_compatibility = _geometry_compatibility(
        source_installation["modulePort"], target_installation["basePort"]
    )
    if not geometry_compatibility["comparable"]:
        blockers.append({"code": "LOCATING_FEATURE_GEOMETRY_NOT_COMPARABLE"})
    elif not geometry_compatibility["compatible"]:
        blockers.append(
            {
                "code": "LOCATING_FEATURE_SPACING_MISMATCH",
                "differences": geometry_compatibility["differences"],
            }
        )

    source_alias = source.get("projectAliases", [{}])[0]
    target_alias = replaced.get("projectAliases", [{}])[0]
    base_definition_id = target_installation["basePort"]["moduleDefinitionId"]
    template_core = {
        "legacyTemplateId": (
            f"cross_project_{source_alias.get('projectId')}_{source_alias.get('moduleToken')}"
            f"_to_{target_alias.get('projectId')}_{target_alias.get('moduleToken')}_slot"
        ),
        "purposes": ["installation"],
        "interfaceTypeA": source_interface["canonicalInterfaceClass"],
        "interfaceTypeB": target_interface["canonicalInterfaceClass"],
        "candidatePortIdsA": [source_installation["modulePort"]["globalPortId"]],
        "candidatePortIdsB": [target_installation["basePort"]["globalPortId"]],
        "constraintEffect": {
            "purpose": "Install one reviewed cross-project module into an existing same-role slot.",
            "fullyLocatesAddedComponent": not blockers,
            "expectedResidualDof": 0 if not blockers else None,
        },
        "mateSteps": deepcopy(source_installation["template"].get("mateSteps") or []),
        "provenance": {
            "kind": "cross_project_template_composition",
            "projectId": source_alias.get("projectId"),
            "effectiveMateGraphPath": effective_mate_graph_path,
            "sourceModuleTemplateId": source_installation["template"]["globalTemplateId"],
            "targetSlotTemplateId": target_installation["template"]["globalTemplateId"],
            "sourceProjectId": source_alias.get("projectId"),
            "targetProjectId": target_alias.get("projectId"),
            "sideAProvenance": source_installation["template"].get("provenance"),
            "sideBProvenance": target_installation["template"].get("provenance"),
        },
    }
    template_id = (
        f"template/cross-project/{_slug(str(source_alias.get('moduleToken')))}-to-"
        f"{_slug(str(target_alias.get('projectId')))}-{_slug(str(target_alias.get('moduleToken')))}-slot/"
        f"{_digest(template_core)[:10]}"
    )
    template = {"globalTemplateId": template_id, **template_core}
    candidate = deepcopy(normalized)
    if not blockers:
        candidate["connectionTemplates"].append(template)
        candidate["connectionTemplates"].sort(key=lambda row: row["globalTemplateId"])
        candidate["compatibility"].append(
            {
                "portAId": source_installation["modulePort"]["globalPortId"],
                "portBId": target_installation["basePort"]["globalPortId"],
                "globalTemplateId": template_id,
                "purpose": "installation",
                "directional": True,
                "portableForTemplate": True,
                "compatibilityAuthority": "reviewed_cross_project_mvp",
            }
        )
        candidate["compatibility"].sort(
            key=lambda row: (
                str(row.get("portAId")),
                str(row.get("portBId")),
                str(row.get("globalTemplateId")),
            )
        )
    candidate["summary"] = {
        **candidate.get("summary", {}),
        "moduleDefinitionCount": len(candidate.get("moduleDefinitions") or []),
        "semanticPortCount": len(candidate.get("semanticPorts") or []),
        "connectionTemplateCount": len(candidate.get("connectionTemplates") or []),
        "compatibilityCount": len(candidate.get("compatibility") or []),
    }
    candidate.pop("catalogDigest", None)
    candidate["catalogDigest"] = _digest(candidate)
    validate_global_module_catalog(candidate)
    report_core = {
        "schemaVersion": SUBSTITUTION_REPORT_SCHEMA,
        "status": "ready_for_cad_dry_run" if not blockers else "blocked",
        "sourceModuleDefinitionId": source["moduleDefinitionId"],
        "replacedModuleDefinitionId": replaced["moduleDefinitionId"],
        "targetBaseModuleDefinitionId": base_definition_id,
        "sourceRole": source_role,
        "targetRole": target_role,
        "sourceModulePortId": source_installation["modulePort"]["globalPortId"],
        "targetSlotPortId": target_installation["basePort"]["globalPortId"],
        "sourceTemplateId": source_installation["template"]["globalTemplateId"],
        "targetSlotTemplateId": target_installation["template"]["globalTemplateId"],
        "derivedTemplateId": template_id if not blockers else None,
        "canonicalInterfaceClass": source_interface["canonicalInterfaceClass"],
        "sourceMateSignature": source_signature,
        "targetMateSignature": target_signature,
        "locatingFeatureGeometry": geometry_compatibility,
        "blockers": blockers,
        "boundary": {
            "solidWorksExecuted": False,
            "collisionOrBrepEvaluated": False,
            "productionReleased": False,
        },
    }
    report = {**report_core, "reportDigest": _digest(report_core)}
    return candidate, report


def compile_substitution_preview(
    catalog: dict[str, Any],
    overlay: dict[str, Any],
    *,
    source_module: str | dict[str, str],
    replaced_module: str | dict[str, str],
    requirement: str,
    effective_mate_graph_path: str | None = None,
) -> dict[str, Any]:
    """Compile a natural-language substitution into context, DAG and CAD manifest."""

    candidate, report = build_cross_project_substitution_catalog(
        catalog,
        overlay,
        source_module=source_module,
        replaced_module=replaced_module,
        effective_mate_graph_path=effective_mate_graph_path,
    )
    if report["status"] != "ready_for_cad_dry_run":
        return {
            "success": False,
            "status": "blocked",
            "requirement": requirement,
            "substitutionReport": report,
            "engineeringDisposition": build_blocked_substitution_disposition(report),
            "userFailureExplanation": build_assembly_user_failure(
                blockers=report.get("blockers") or [],
                status=report.get("status"),
                stage="natural_language_preview",
            ),
            "cadStarted": False,
        }
    source = resolve_module_reference(candidate, source_module)
    base = next(
        row
        for row in candidate.get("moduleDefinitions") or []
        if row["moduleDefinitionId"] == report["targetBaseModuleDefinitionId"]
    )
    context = create_global_assembly_context(
        f"cross-project-{_digest(requirement)[:12]}",
        display_name="跨项目同角色模组替换MVP",
        catalog_digest=candidate["catalogDigest"],
    )
    base_preview = preview_global_assembly_command(
        candidate,
        context,
        {"requirement": "建立目标项目基座上下文", "moduleDefinitionId": base["moduleDefinitionId"]},
    )
    if base_preview.get("status") != "ready":
        raise CrossProjectModuleSubstitutionError("目标基座上下文不能初始化。")
    context = apply_global_command_preview(
        context,
        base_preview,
        preview_digest=base_preview["previewDigest"],
        confirmed=True,
    )
    module_preview = preview_global_assembly_command(
        candidate,
        context,
        {"requirement": requirement, "moduleDefinitionId": source["moduleDefinitionId"]},
    )
    if module_preview.get("status") != "ready":
        return {
            "success": False,
            "status": module_preview.get("status"),
            "requirement": requirement,
            "substitutionReport": report,
            "preview": module_preview,
            "cadStarted": False,
        }
    context = apply_global_command_preview(
        context,
        module_preview,
        preview_digest=module_preview["previewDigest"],
        confirmed=True,
    )
    dag = compile_global_assembly_transaction_dag(candidate, context)
    manifest = compile_global_cad_transaction_manifest(candidate, context)
    graph_bound = all(
        connection.get("effectiveMateGraphCandidate")
        for packet in manifest.get("packets") or []
        for connection in packet.get("connections") or []
    )
    manifest_ready = manifest.get("status") == "ready_for_generic_executor_implementation"
    return {
        "success": manifest_ready,
        "status": (
            "ready_for_cad_execution"
            if manifest_ready and graph_bound
            else "ready_for_effective_graph_composition"
            if manifest_ready
            else "blocked_before_cad"
        ),
        "requirement": requirement,
        "candidateCatalogDigest": candidate["catalogDigest"],
        "substitutionReport": report,
        "context": context,
        "commandPreview": module_preview,
        "transactionDag": dag,
        "cadTransactionManifest": manifest,
        "cadStarted": False,
        "effectiveMateGraphBound": graph_bound,
        "collisionStatus": "not_evaluated",
    }

