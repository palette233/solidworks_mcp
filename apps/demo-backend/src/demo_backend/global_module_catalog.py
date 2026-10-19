"""Build the project-independent module, semantic-port, and template catalog.

The catalog is an identity and connectivity index, not a declaration that two
modules with the same functional role are mechanically or process-equivalent.
Cross-project execution must still pass the relation-evidence policy and use a
released template.  For example, a single-track and a dual-track transport may
share the ``transport`` role while remaining different module definitions.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .project_assembly_profile import load_project_assembly_profile


GLOBAL_MODULE_CATALOG_SCHEMA = "global-module-catalog/v1"
GLOBAL_PORT_REGISTRY_SCHEMA = "global-semantic-port-registry/v1"
DEFAULT_PROJECT_IDS = ("project01", "project02", "project03", "project05", "project06")


class GlobalModuleCatalogError(ValueError):
    pass


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text[:48] or "module"


def _component_names(row: dict[str, Any]) -> list[str]:
    values = [row.get("componentName"), *(row.get("componentNames") or [])]
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized.casefold() not in {item.casefold() for item in result}:
            result.append(normalized)
    return result


def _definition_key(project_id: str, token: str, row: dict[str, Any]) -> tuple[str, ...]:
    names = sorted(value.casefold() for value in _component_names(row))
    if names:
        return ("component-set", *names)
    # A project/token fallback is intentionally not merged across projects.
    return ("project-token", project_id.casefold(), token.casefold())


def _definition_id(key: tuple[str, ...], row: dict[str, Any]) -> str:
    names = _component_names(row)
    label = names[0] if names else str(row.get("label") or key[-1])
    return f"cad/{_slug(label)}/{_digest(key)[:12]}"


def _module_alias_keys(token: str, row: dict[str, Any]) -> set[str]:
    """Return identifiers observed in legacy semantic catalogs for one profile module."""

    values = {str(token).strip().casefold()}
    for component_name in _component_names(row):
        stem = re.sub(r"\.sldasm$", "", component_name, flags=re.IGNORECASE)
        stem = re.sub(r"-\d+$", "", stem)
        stem = re.sub(r"\.\d+$", "", stem)
        values.add(stem.casefold())
        match = re.search(r"([a-z]{1,2}\d{2,4})$", stem, flags=re.IGNORECASE)
        if match:
            values.add(match.group(1).casefold())
    return {value for value in values if value}


def infer_module_category(label: str, aliases: Iterable[str] = ()) -> str:
    text = " ".join([str(label), *(str(item) for item in aliases)]).casefold()
    rules = (
        ("frame", ("箱体", "机架", "固定环境", "基座")),
        ("transport", ("传输", "输送", "transport", "回流")),
        ("scanner", ("扫描", "扫码", "条码", "scanner")),
        ("ccd", ("ccd", "视觉", "相机", "camera")),
        ("calibration", ("校准", "标定", "calibration")),
        ("cleaning_weighing", ("清洁", "称重", "排胶", "废胶", "硬度")),
        ("glue_supply", ("供胶", "胶水", "glue supply")),
        ("gantry", ("龙门", "点胶", "双阀", "z轴", "xyz")),
        ("positioning", ("顶升", "举升", "翻转", "定位")),
    )
    for category, words in rules:
        if any(word in text for word in words):
            return category
    return "functional"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalModuleCatalogError(f"无法读取JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GlobalModuleCatalogError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _declared_endpoint_catalog_path(
    semantic_path: Path,
    semantic: dict[str, Any],
    workspace: Path,
) -> Path:
    """Resolve an explicitly declared endpoint catalog before legacy fallback.

    Historical semantic-port packages usually placed
    ``face_endpoint_catalog.json`` beside the semantic catalog.  Newer packages
    can reference a shared face registry.  Only files inside the workspace are
    accepted so a signed global catalog never depends on an arbitrary external
    path.
    """

    declared = str(semantic.get("endpointCatalogPath") or "").strip()
    candidates: list[Path] = []
    if declared:
        raw = Path(declared)
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend([semantic_path.parent / raw, workspace / raw])
    candidates.append(semantic_path.with_name("face_endpoint_catalog.json"))
    workspace_root = workspace.resolve()
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(workspace_root)
        except ValueError:
            continue
        if resolved.is_file():
            return resolved
    return semantic_path.with_name("face_endpoint_catalog.json")


def _endpoint_index(endpoint_catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("EndpointId") or ""): item
        for item in endpoint_catalog.get("Endpoints") or []
        if str(item.get("EndpointId") or "")
    }


def _portable_mechanical_port(
    port: dict[str, Any], endpoint_by_id: dict[str, dict[str, Any]]
) -> tuple[bool, list[str], list[dict[str, Any]], list[str]]:
    reasons: list[str] = []
    endpoints: list[dict[str, Any]] = []
    module_paths: list[str] = []
    for binding in port.get("endpointBindings") or []:
        role = str(binding.get("role") or "")
        endpoint_id = str(binding.get("endpointId") or "")
        entry = endpoint_by_id.get(endpoint_id)
        if not entry:
            reasons.append(f"missing_endpoint:{endpoint_id}")
            endpoints.append(
                {
                    "role": role,
                    "endpointId": endpoint_id,
                    "rolePortable": False,
                    "portabilityReasons": [f"missing_endpoint:{endpoint_id}"],
                }
            )
            continue
        endpoint = entry.get("Endpoint") or {}
        module_path = str(entry.get("ModulePath") or "").strip()
        if module_path and module_path.casefold() not in {item.casefold() for item in module_paths}:
            module_paths.append(module_path)
        geometry_class = str(entry.get("GeometryClass") or "").casefold()
        has_local_fingerprint = bool(
            endpoint.get("FaceCenterLocal") is not None
            and endpoint.get("RelativeLeafHierarchyPath") is not None
            and endpoint.get("BodyIndex") is not None
            and endpoint.get("FaceIndexInBody") is not None
            and (geometry_class != "plane" or endpoint.get("FaceNormalLocal") is not None)
        )
        has_persistent_reference = bool(endpoint.get("SourceAssemblyPersistentReferenceBase64"))
        role_reasons: list[str] = []
        if not has_local_fingerprint:
            role_reasons.append(f"missing_local_fingerprint:{endpoint_id}")
        if not has_persistent_reference:
            role_reasons.append(f"missing_persistent_reference:{endpoint_id}")
        reasons.extend(role_reasons)
        endpoints.append(
            {
                "role": role,
                "endpointId": endpoint_id,
                "geometryClass": entry.get("GeometryClass"),
                "recoveryConfidence": entry.get("RecoveryConfidence"),
                "relativeLeafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
                "bodyIndex": endpoint.get("BodyIndex"),
                "faceIndexInBody": endpoint.get("FaceIndexInBody"),
                "faceArea": endpoint.get("FaceArea"),
                "faceCenterLocal": endpoint.get("FaceCenterLocal"),
                "faceNormalLocal": endpoint.get("FaceNormalLocal"),
                "hasPersistentReference": has_persistent_reference,
                "rolePortable": not role_reasons,
                "portabilityReasons": role_reasons,
            }
        )
    if not endpoints:
        reasons.append("no_endpoint_evidence")
    return not reasons, sorted(set(reasons)), endpoints, module_paths


def _portable_functional_port(port: dict[str, Any]) -> tuple[bool, list[str]]:
    local_keys = {
        "originInModuleBottomFrame",
        "pointInModuleBottomFrame",
        "axisInModuleFrame",
        "planeInModuleFrame",
        "regionInModuleFrame",
    }
    if any(port.get(key) is not None for key in local_keys):
        return True, []
    return False, ["functional_port_has_no_module_local_geometry"]


def build_global_module_catalog(
    workspace: Path,
    *,
    project_ids: Iterable[str] = DEFAULT_PROJECT_IDS,
    semantic_root: Path | None = None,
    additional_semantic_catalog_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    """Build a deterministic, cross-project catalog without inventing CAD identity.

    Module definitions are deduplicated only by their declared component-name set. Project
    tokens and natural-language labels remain aliases/provenance and never cause a merge.
    """

    workspace = workspace.resolve()
    semantic_root = (semantic_root or workspace / "demo" / "semantic_ports").resolve()
    definitions_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    alias_to_definition: dict[tuple[str, str], str] = {}
    project_status: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for project_id in project_ids:
        normalized_project = str(project_id).strip().lower()
        try:
            profile = load_project_assembly_profile(normalized_project)
        except Exception as exc:  # A missing project profile is evidence, not a fatal build error.
            project_status.append(
                {"projectId": normalized_project, "status": "profile_missing", "detail": str(exc)}
            )
            blockers.append(
                {
                    "code": "PROJECT_PROFILE_MISSING",
                    "projectId": normalized_project,
                    "detail": str(exc),
                }
            )
            continue
        project_status.append(
            {
                "projectId": normalized_project,
                "status": "loaded",
                "profilePath": _relative(Path(profile["profilePath"]), workspace),
                "profileDigest": profile["profileDigest"],
            }
        )
        for token, row in profile["modules"].items():
            key = _definition_key(normalized_project, token, row)
            definition = definitions_by_key.get(key)
            if definition is None:
                definition_id = _definition_id(key, row)
                definition = {
                    "moduleDefinitionId": definition_id,
                    "displayName": row["label"],
                    "category": infer_module_category(row["label"], row.get("aliases") or []),
                    "componentNames": _component_names(row),
                    "cadSources": [],
                    "aliases": [],
                    "projectAliases": [],
                    "sourceConfidence": [],
                    "portIds": [],
                    "portCoverage": "none",
                }
                definitions_by_key[key] = definition
            alias_values = [token, row["label"], *(row.get("aliases") or [])]
            for alias in alias_values:
                value = str(alias).strip()
                if value and value.casefold() not in {item.casefold() for item in definition["aliases"]}:
                    definition["aliases"].append(value)
            definition["projectAliases"].append(
                {
                    "projectId": normalized_project,
                    "moduleToken": token,
                    "instanceCount": row.get("instanceCount", 1),
                    "isBaseModule": token == profile["baseModule"],
                    "profileVersion": profile["profileVersion"],
                }
            )
            confidence = str(row.get("sourceConfidence") or "")
            if confidence and confidence not in definition["sourceConfidence"]:
                definition["sourceConfidence"].append(confidence)
            for alias_key in _module_alias_keys(token, row):
                existing = alias_to_definition.get((normalized_project, alias_key))
                if existing is not None and existing != definition["moduleDefinitionId"]:
                    blockers.append(
                        {
                            "code": "AMBIGUOUS_LEGACY_MODULE_IDENTIFIER",
                            "projectId": normalized_project,
                            "identifier": alias_key,
                            "moduleDefinitionIds": sorted({existing, definition["moduleDefinitionId"]}),
                        }
                    )
                    continue
                alias_to_definition[(normalized_project, alias_key)] = definition["moduleDefinitionId"]

    definitions = {row["moduleDefinitionId"]: row for row in definitions_by_key.values()}
    loaded_projects = {
        str(item["projectId"])
        for item in project_status
        if item.get("status") == "loaded"
    }
    global_ports: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    templates: list[dict[str, Any]] = []
    combination_declarations: list[dict[str, Any]] = []
    compatibility: list[dict[str, Any]] = []
    semantic_catalog_status: list[dict[str, Any]] = []

    semantic_paths = {path.resolve() for path in semantic_root.rglob("semantic_port_catalog.json")}
    semantic_paths.update(path.resolve() for path in additional_semantic_catalog_paths)
    for semantic_path in sorted(semantic_paths):
        try:
            semantic = _read_json(semantic_path)
        except GlobalModuleCatalogError as exc:
            semantic_catalog_status.append(
                {"path": _relative(semantic_path, workspace), "status": "invalid", "detail": str(exc)}
            )
            continue
        project_id = str(semantic.get("projectId") or "").strip().lower()
        if project_id not in loaded_projects:
            continue
        endpoint_path = _declared_endpoint_catalog_path(
            semantic_path, semantic, workspace
        )
        endpoint_catalog = _read_json(endpoint_path) if endpoint_path.is_file() else {"Endpoints": []}
        endpoint_by_id = _endpoint_index(endpoint_catalog)
        source_ref = {
            "projectId": project_id,
            "semanticCatalogPath": _relative(semantic_path, workspace),
            "endpointCatalogPath": _relative(endpoint_path, workspace) if endpoint_path.is_file() else None,
            "effectiveMateGraphPath": (
                _relative(
                    (
                        workspace / str(semantic.get("effectiveMateGraphPath"))
                    ).resolve(),
                    workspace,
                )
                if semantic.get("effectiveMateGraphPath")
                else None
            ),
            "semanticCatalogDigest": _digest(semantic),
        }
        local_port_map: dict[str, str] = {}
        local_interface_map: dict[str, list[str]] = defaultdict(list)
        parsed_count = 0
        for category_key, default_category in (("ports", "mechanical"), ("functionalPorts", "functional")):
            for raw_port in semantic.get(category_key) or []:
                # A cross-project connection package can intentionally expose
                # one port from each participating project.  Historical
                # packages inherit the catalog-level projectId, while new
                # packages may declare the owning project per port.  This is a
                # thin provenance override; CAD identity still comes from the
                # project profile and cannot be invented by the package.
                port_project_id = str(
                    raw_port.get("projectId") or project_id
                ).strip().lower()
                if port_project_id not in loaded_projects:
                    blockers.append(
                        {
                            "code": "PORT_PROJECT_NOT_LOADED",
                            "projectId": port_project_id,
                            "moduleToken": raw_port.get("moduleToken"),
                            "source": source_ref["semanticCatalogPath"],
                        }
                    )
                    continue
                token = str(raw_port.get("moduleToken") or "").strip()
                definition_id = alias_to_definition.get(
                    (port_project_id, token.casefold())
                )
                if not definition_id:
                    blockers.append(
                        {
                            "code": "PORT_MODULE_NOT_IN_PROFILE",
                            "projectId": port_project_id,
                            "moduleToken": token,
                            "source": source_ref["semanticCatalogPath"],
                        }
                    )
                    continue
                legacy_port_id = str(raw_port.get("portId") or "").strip()
                category = str(raw_port.get("category") or default_category)
                interface_type = str(raw_port.get("interfaceType") or raw_port.get("geometryType") or "")
                key = (definition_id, legacy_port_id.casefold(), category.casefold(), interface_type.casefold())
                if category_key == "ports":
                    portable, reasons, endpoint_evidence, module_paths = _portable_mechanical_port(
                        raw_port, endpoint_by_id
                    )
                else:
                    portable, reasons = _portable_functional_port(raw_port)
                    endpoint_evidence, module_paths = [], []
                global_port = global_ports.get(key)
                if global_port is None:
                    global_port_id = f"{definition_id}::port/{_slug(legacy_port_id)}/{_digest(key)[:10]}"
                    global_port = {
                        "globalPortId": global_port_id,
                        "moduleDefinitionId": definition_id,
                        "displayName": raw_port.get("displayName") or legacy_port_id,
                        "description": raw_port.get("description"),
                        "category": category,
                        "interfaceType": interface_type,
                        "capabilities": sorted(set(raw_port.get("capabilities") or [])),
                        "aliases": sorted(set([legacy_port_id, *(raw_port.get("aliases") or [])])),
                        "portable": portable,
                        "portabilityReasons": reasons,
                        "endpointEvidence": endpoint_evidence,
                        "functionalGeometry": deepcopy(raw_port) if category_key == "functionalPorts" else None,
                        "provenance": [],
                    }
                    global_ports[key] = global_port
                else:
                    global_port["portable"] = bool(global_port["portable"] and portable)
                    global_port["portabilityReasons"] = sorted(
                        set([*global_port["portabilityReasons"], *reasons])
                    )
                    for evidence in endpoint_evidence:
                        if evidence not in global_port["endpointEvidence"]:
                            global_port["endpointEvidence"].append(evidence)
                global_port["provenance"].append(
                    {
                        **source_ref,
                        "portProjectId": port_project_id,
                        "legacyPortId": legacy_port_id,
                        "moduleToken": token,
                        "moduleHierarchyPath": raw_port.get("moduleHierarchyPath"),
                        "status": raw_port.get("status"),
                    }
                )
                definition = definitions[definition_id]
                for module_path in module_paths:
                    if module_path.casefold() not in {item["path"].casefold() for item in definition["cadSources"]}:
                        definition["cadSources"].append(
                            {"path": module_path, "source": source_ref["endpointCatalogPath"]}
                        )
                if global_port["globalPortId"] not in definition["portIds"]:
                    definition["portIds"].append(global_port["globalPortId"])
                local_port_map[legacy_port_id] = global_port["globalPortId"]
                if interface_type:
                    local_interface_map[interface_type].append(global_port["globalPortId"])
                parsed_count += 1

        for template in semantic.get("connectionTemplates") or []:
            type_a = str(template.get("interfaceTypeA") or "")
            type_b = str(template.get("interfaceTypeB") or "")
            ports_a = sorted(set(local_interface_map.get(type_a) or []))
            ports_b = sorted(set(local_interface_map.get(type_b) or []))
            template_key = (
                source_ref["semanticCatalogPath"],
                str(template.get("templateId") or ""),
            )
            global_template_id = f"template/{_slug(project_id)}/{_slug(template_key[1])}/{_digest(template_key)[:10]}"
            templates.append(
                {
                    "globalTemplateId": global_template_id,
                    "legacyTemplateId": template.get("templateId"),
                    "purposes": template.get("purposes") or [],
                    "interfaceTypeA": type_a,
                    "interfaceTypeB": type_b,
                    "candidatePortIdsA": ports_a,
                    "candidatePortIdsB": ports_b,
                    "constraintEffect": template.get("constraintEffect"),
                    "mateSteps": template.get("mateSteps") or [],
                    "provenance": source_ref,
                }
            )
            required_roles_a: set[str] = set()
            required_roles_b: set[str] = set()
            for step in template.get("mateSteps") or []:
                endpoint_roles = step.get("endpointRoles")
                if endpoint_roles is None:
                    endpoint_roles = [
                        {"side": "A", "role": step.get("endpointRoleA")},
                        {"side": "B", "role": step.get("endpointRoleB")},
                    ]
                for endpoint_role in endpoint_roles:
                    side = str(endpoint_role.get("side") or "").upper()
                    role = str(endpoint_role.get("role") or "").strip()
                    if side == "A" and role:
                        required_roles_a.add(role)
                    elif side == "B" and role:
                        required_roles_b.add(role)

            port_by_id = {
                str(item["globalPortId"]): item for item in global_ports.values()
            }

            def template_side_portable(port_id: str, required_roles: set[str]) -> bool:
                port = port_by_id.get(port_id) or {}
                if str(port.get("category")) != "mechanical":
                    return bool(port.get("portable"))
                evidence_by_role = {
                    str(item.get("role") or ""): item
                    for item in port.get("endpointEvidence") or []
                }
                return bool(required_roles) and all(
                    bool((evidence_by_role.get(role) or {}).get("rolePortable"))
                    for role in required_roles
                )

            for port_a in ports_a:
                for port_b in ports_b:
                    if port_a == port_b:
                        continue
                    compatibility.append(
                        {
                            "portAId": port_a,
                            "portBId": port_b,
                            "globalTemplateId": global_template_id,
                            "purpose": (template.get("purposes") or ["installation"])[0],
                            "directional": True,
                            "portableForTemplate": bool(
                                template_side_portable(port_a, required_roles_a)
                                and template_side_portable(port_b, required_roles_b)
                            ),
                        }
                    )
        for combination in semantic.get("templateCombinations") or []:
            combination_declarations.append(
                {
                    "declaration": deepcopy(combination),
                    "provenance": source_ref,
                }
            )
        semantic_catalog_status.append(
            {
                "path": source_ref["semanticCatalogPath"],
                "status": "loaded",
                "projectId": project_id,
                "parsedPortCount": parsed_count,
                "endpointCatalogPresent": endpoint_path.is_file(),
            }
        )

    templates_by_legacy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for template in templates:
        legacy_id = str(template.get("legacyTemplateId") or "")
        if legacy_id:
            templates_by_legacy[legacy_id].append(template)
    template_combinations: list[dict[str, Any]] = []
    for row in combination_declarations:
        declaration = row["declaration"]
        legacy_ids = [
            str(value).strip()
            for value in declaration.get("memberLegacyTemplateIds") or []
            if str(value).strip()
        ]
        resolved: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for legacy_id in legacy_ids:
            matches = templates_by_legacy.get(legacy_id) or []
            if len(matches) == 1:
                resolved.append(matches[0])
            else:
                unresolved.append(legacy_id)
        if len(legacy_ids) < 2 or unresolved:
            blockers.append(
                {
                    "code": "TEMPLATE_COMBINATION_MEMBER_NOT_UNIQUE",
                    "combinationId": declaration.get("combinationId"),
                    "memberLegacyTemplateIds": legacy_ids,
                    "unresolvedLegacyTemplateIds": unresolved,
                    "source": row["provenance"]["semanticCatalogPath"],
                }
            )
            continue
        primary_legacy_id = str(
            declaration.get("primaryLegacyTemplateId") or legacy_ids[0]
        )
        if primary_legacy_id not in legacy_ids:
            blockers.append(
                {
                    "code": "TEMPLATE_COMBINATION_PRIMARY_NOT_MEMBER",
                    "combinationId": declaration.get("combinationId"),
                    "primaryLegacyTemplateId": primary_legacy_id,
                }
            )
            continue
        identity = (
            row["provenance"]["semanticCatalogPath"],
            str(declaration.get("combinationId") or ""),
            *sorted(template["globalTemplateId"] for template in resolved),
        )
        template_combinations.append(
            {
                "globalCombinationId": (
                    f"combination/{_slug(row['provenance']['projectId'])}/"
                    f"{_slug(str(declaration.get('combinationId') or 'bundle'))}/"
                    f"{_digest(identity)[:10]}"
                ),
                "legacyCombinationId": declaration.get("combinationId"),
                "memberGlobalTemplateIds": sorted(
                    template["globalTemplateId"] for template in resolved
                ),
                "memberLegacyTemplateIds": sorted(legacy_ids),
                "primaryGlobalTemplateId": next(
                    template["globalTemplateId"]
                    for template in resolved
                    if template.get("legacyTemplateId") == primary_legacy_id
                ),
                "primaryLegacyTemplateId": primary_legacy_id,
                "applicationScope": declaration.get("applicationScope")
                or "same_target_insertion",
                "exactMemberSetRequired": bool(
                    declaration.get("exactMemberSetRequired", True)
                ),
                "fullyLocatesAddedComponent": bool(
                    declaration.get("fullyLocatesAddedComponent")
                ),
                "expectedResidualDof": declaration.get("expectedResidualDof"),
                "explanation": declaration.get("explanation"),
                "provenance": row["provenance"],
            }
        )

    ports = sorted(global_ports.values(), key=lambda item: item["globalPortId"])
    compatibility = sorted(
        {(_digest(item), json.dumps(item, ensure_ascii=False, sort_keys=True)): item for item in compatibility}.values(),
        key=lambda item: (item["portAId"], item["portBId"], item["globalTemplateId"]),
    )
    for definition in definitions.values():
        definition["aliases"] = sorted(definition["aliases"], key=str.casefold)
        definition["projectAliases"] = sorted(
            definition["projectAliases"], key=lambda item: (item["projectId"], item["moduleToken"])
        )
        definition["componentNames"] = sorted(definition["componentNames"], key=str.casefold)
        definition["cadSources"] = sorted(definition["cadSources"], key=lambda item: item["path"].casefold())
        definition["portIds"] = sorted(definition["portIds"])
        portable_count = sum(
            1 for port in ports if port["moduleDefinitionId"] == definition["moduleDefinitionId"] and port["portable"]
        )
        total_count = len(definition["portIds"])
        definition["portCoverage"] = (
            "none" if total_count == 0 else "portable_complete" if portable_count == total_count else "partial"
        )
        if total_count == 0:
            blockers.append(
                {
                    "code": "MODULE_HAS_NO_SEMANTIC_PORT",
                    "moduleDefinitionId": definition["moduleDefinitionId"],
                    "displayName": definition["displayName"],
                }
            )

    catalog: dict[str, Any] = {
        "schemaVersion": GLOBAL_MODULE_CATALOG_SCHEMA,
        "portRegistrySchemaVersion": GLOBAL_PORT_REGISTRY_SCHEMA,
        "catalogPurpose": "跨项目CAD模组检索、语义端口选择和增量装配规划",
        "identityPolicy": {
            "deduplicateBy": "declared_component_name_set",
            "neverDeduplicateBy": ["project token", "display label", "functional category"],
            "projectTokensAre": "historical aliases and provenance only",
        },
        "collisionPolicy": {
            "enabled": False,
            "status": "deferred_by_user_scope",
            "statement": "本目录与本轮装配预览不执行碰撞门禁；CAD结果仅为工程草案。",
        },
        "projects": project_status,
        "moduleDefinitions": sorted(definitions.values(), key=lambda item: item["moduleDefinitionId"]),
        "semanticPorts": ports,
        "connectionTemplates": sorted(templates, key=lambda item: item["globalTemplateId"]),
        "templateCombinations": sorted(
            template_combinations, key=lambda item: item["globalCombinationId"]
        ),
        "compatibility": compatibility,
        "sourceCatalogs": semantic_catalog_status,
        "blockers": blockers,
    }
    catalog["summary"] = {
        "loadedProjectCount": sum(1 for item in project_status if item["status"] == "loaded"),
        "missingProjectCount": sum(1 for item in project_status if item["status"] != "loaded"),
        "moduleDefinitionCount": len(catalog["moduleDefinitions"]),
        "semanticPortCount": len(ports),
        "portablePortCount": sum(1 for port in ports if port["portable"]),
        "connectionTemplateCount": len(templates),
        "templateCombinationCount": len(template_combinations),
        "compatibilityCount": len(compatibility),
        "blockerCount": len(blockers),
    }
    catalog["catalogDigest"] = _digest(catalog)
    return catalog


def validate_global_module_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    if catalog.get("schemaVersion") != GLOBAL_MODULE_CATALOG_SCHEMA:
        raise GlobalModuleCatalogError("不支持的全局模组目录版本。")
    definitions = catalog.get("moduleDefinitions")
    ports = catalog.get("semanticPorts")
    if not isinstance(definitions, list) or not isinstance(ports, list):
        raise GlobalModuleCatalogError("全局目录缺少moduleDefinitions或semanticPorts数组。")
    definition_ids = [str(item.get("moduleDefinitionId") or "") for item in definitions]
    port_ids = [str(item.get("globalPortId") or "") for item in ports]
    if any(not item for item in definition_ids) or len(definition_ids) != len(set(definition_ids)):
        raise GlobalModuleCatalogError("moduleDefinitionId必须非空且唯一。")
    if any(not item for item in port_ids) or len(port_ids) != len(set(port_ids)):
        raise GlobalModuleCatalogError("globalPortId必须非空且唯一。")
    known_definitions = set(definition_ids)
    for port in ports:
        if port.get("moduleDefinitionId") not in known_definitions:
            raise GlobalModuleCatalogError("语义端口引用了不存在的模组定义。")
    known_ports = set(port_ids)
    for row in catalog.get("compatibility") or []:
        if row.get("portAId") not in known_ports or row.get("portBId") not in known_ports:
            raise GlobalModuleCatalogError("兼容关系引用了不存在的语义端口。")
    template_ids = {
        str(item.get("globalTemplateId") or "")
        for item in catalog.get("connectionTemplates") or []
    }
    combination_ids: list[str] = []
    for combination in catalog.get("templateCombinations") or []:
        combination_id = str(combination.get("globalCombinationId") or "")
        combination_ids.append(combination_id)
        members = {
            str(value)
            for value in combination.get("memberGlobalTemplateIds") or []
            if str(value)
        }
        if not combination_id or len(members) < 2 or not members <= template_ids:
            raise GlobalModuleCatalogError("模板组合身份或成员模板无效。")
        if combination.get("primaryGlobalTemplateId") not in members:
            raise GlobalModuleCatalogError("模板组合的主定位模板不属于成员集合。")
        if not isinstance(combination.get("expectedResidualDof"), (int, float)):
            raise GlobalModuleCatalogError("模板组合缺少可计算的剩余自由度。")
    if len(combination_ids) != len(set(combination_ids)):
        raise GlobalModuleCatalogError("globalCombinationId必须非空且唯一。")
    expected = _digest({key: value for key, value in catalog.items() if key != "catalogDigest"})
    if catalog.get("catalogDigest") != expected:
        raise GlobalModuleCatalogError("全局模组目录摘要不匹配。")
    return {
        "success": True,
        "schemaVersion": GLOBAL_MODULE_CATALOG_SCHEMA,
        "moduleDefinitionCount": len(definitions),
        "semanticPortCount": len(ports),
        "catalogDigest": expected,
    }
