from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


class MateGraphEditError(ValueError):
    pass


SUPPORTED_BASIC_MATE_TYPES = {
    0,  # coincident
    1,  # concentric
    2,  # perpendicular
    3,  # parallel
    4,  # tangent
    5,  # distance
    6,  # angle
    11,  # width (import/rebuild only; four face endpoints plus AdvancedOptions)
}


def _mate_id(mate: dict[str, Any]) -> str:
    existing = str(mate.get("MateId") or mate.get("mateId") or "").strip()
    if existing:
        return existing
    payload = "|".join(
        [
            str(mate.get("MateName") or ""),
            str(mate.get("MateType") or ""),
            *sorted(str(value) for value in mate.get("ModuleHierarchyPaths") or []),
        ]
    )
    return "mate:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _resolve_mate(mates: list[dict[str, Any]], operation: dict[str, Any]) -> dict[str, Any]:
    mate_id = str(operation.get("mateId") or "").strip()
    mate_name = str(operation.get("mateName") or "").strip()
    matches = [
        item
        for item in mates
        if (mate_id and _mate_id(item) == mate_id)
        or (mate_name and str(item.get("MateName") or "") == mate_name)
    ]
    if len(matches) != 1:
        selector = mate_id or mate_name or "<missing selector>"
        raise MateGraphEditError(
            f"Mate selector '{selector}' resolved to {len(matches)} mates; expected exactly one."
        )
    return matches[0]


def _canonical_endpoint_key(mate: dict[str, Any]) -> tuple[str, ...]:
    endpoints = []
    for endpoint in mate.get("Endpoints") or []:
        endpoints.append(
            "|".join(
                [
                    str(endpoint.get("ModuleHierarchyPath") or ""),
                    str(endpoint.get("RelativeLeafHierarchyPath") or ""),
                    str(endpoint.get("BodyIndex")),
                    str(endpoint.get("FaceIndexInBody")),
                ]
            )
        )
    return tuple(sorted(endpoints))


def _validate_graph(graph: dict[str, Any]) -> list[str]:
    modules = graph.get("Modules")
    mates = graph.get("Mates")
    if not isinstance(modules, list) or not isinstance(mates, list):
        raise MateGraphEditError("Mate graph must contain Modules and Mates arrays.")
    module_paths = [str(item.get("HierarchyPath") or "") for item in modules]
    if any(not value for value in module_paths) or len(module_paths) != len(set(module_paths)):
        raise MateGraphEditError("Every module must have one unique non-empty HierarchyPath.")
    names: set[str] = set()
    ids: set[str] = set()
    warnings: list[str] = []
    for mate in mates:
        name = str(mate.get("MateName") or "").strip()
        normalized_name = name.casefold()
        if not name or normalized_name in names:
            raise MateGraphEditError(f"Mate names must be unique; invalid name '{name}'.")
        names.add(normalized_name)
        mate_id = _mate_id(mate)
        if mate_id in ids:
            raise MateGraphEditError(f"MateId must be unique: {mate_id}")
        ids.add(mate_id)
        mate["MateId"] = mate_id
        mate_type = int(mate.get("MateType", -1))
        endpoints = mate.get("Endpoints") or []
        if mate_type not in SUPPORTED_BASIC_MATE_TYPES:
            raise MateGraphEditError(
                f"Editable graph does not support mate type {mate_type} for '{name}'."
            )
        is_width = mate_type == 11
        expected_endpoint_count = 4 if is_width else 2
        if len(endpoints) != expected_endpoint_count:
            raise MateGraphEditError(
                f"Mate '{name}' must contain exactly {expected_endpoint_count} endpoints."
            )
        endpoint_modules = []
        for endpoint in endpoints:
            if str(endpoint.get("GeometryType") or "").lower() != "face":
                raise MateGraphEditError(f"Mate '{name}' contains a non-face endpoint.")
            module_path = str(endpoint.get("ModuleHierarchyPath") or "")
            if module_path not in module_paths:
                raise MateGraphEditError(
                    f"Mate '{name}' references module '{module_path}' outside Modules."
                )
            endpoint_modules.append(module_path)
        if len(set(endpoint_modules)) != 2:
            raise MateGraphEditError(f"Mate '{name}' must connect two different modules.")
        if is_width:
            advanced = mate.get("AdvancedOptions") or {}
            width_indices = list(advanced.get("WidthEndpointIndices") or [])
            tab_indices = list(advanced.get("TabEndpointIndices") or [])
            endpoint_indices = {int(item.get("Index", -1)) for item in endpoints}
            combined = [int(value) for value in width_indices + tab_indices]
            if (
                len(width_indices) != 2
                or len(tab_indices) != 2
                or len(set(combined)) != 4
                or any(value not in endpoint_indices for value in combined)
                or advanced.get("WidthConstraintType") is None
            ):
                raise MateGraphEditError(
                    f"Width mate '{name}' requires two width faces, two tab faces, and WidthConstraintType."
                )
        if mate_type == 5 and mate.get("Distance") is None:
            raise MateGraphEditError(f"Distance mate '{name}' has no Distance value.")
        if mate_type == 5 and float(mate["Distance"]) < 0:
            raise MateGraphEditError(f"Distance mate '{name}' has a negative Distance value.")
        if mate_type == 6 and mate.get("Angle") is None:
            raise MateGraphEditError(f"Angle mate '{name}' has no Angle value.")

    active_by_signature: dict[tuple[int, tuple[str, ...]], dict[str, Any]] = {}
    for mate in mates:
        if bool(mate.get("IsSuppressed", False)):
            continue
        signature = (int(mate["MateType"]), _canonical_endpoint_key(mate))
        prior = active_by_signature.get(signature)
        if prior is None:
            active_by_signature[signature] = mate
            continue
        if int(mate["MateType"]) == 5 and abs(float(mate["Distance"]) - float(prior["Distance"])) > 1e-12:
            raise MateGraphEditError(
                f"Conflicting distance mates share the same endpoints: "
                f"{prior['MateName']}={prior['Distance']} and {mate['MateName']}={mate['Distance']}."
            )
        warnings.append(
            f"Potential redundant mate '{mate['MateName']}' duplicates '{prior['MateName']}'."
        )
    return warnings


def compile_mate_graph_patch(
    source_graph: dict[str, Any],
    patch: dict[str, Any],
    endpoint_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile an immutable exported graph plus auditable operations into an executable graph."""

    source_digest = hashlib.sha256(
        json.dumps(source_graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    patch_digest = hashlib.sha256(
        json.dumps(patch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    patch_schema = str(patch.get("schemaVersion") or "").strip()
    if patch_schema != "mate-graph-patch/v1":
        raise MateGraphEditError(f"Unsupported patch schema '{patch_schema}'.")
    graph = copy.deepcopy(source_graph)
    if not isinstance(graph.get("Modules"), list) or not isinstance(graph.get("Mates"), list):
        raise MateGraphEditError("Source graph must contain Modules and Mates arrays.")
    selected_tokens = {
        str(value).upper() for value in patch.get("includeModuleTokens") or []
    }
    if selected_tokens:
        available_tokens = {str(item.get("ModuleToken") or "").upper() for item in graph["Modules"]}
        missing_tokens = sorted(selected_tokens - available_tokens)
        if missing_tokens:
            raise MateGraphEditError("Unknown includeModuleTokens: " + ", ".join(missing_tokens))
        graph["Modules"] = [
            item
            for item in graph["Modules"]
            if str(item.get("ModuleToken") or "").upper() in selected_tokens
        ]
        selected_paths = {str(item["HierarchyPath"]) for item in graph["Modules"]}
        graph["Mates"] = [
            item
            for item in graph["Mates"]
            if set(str(value) for value in item.get("ModuleHierarchyPaths") or [])
            <= selected_paths
        ]
    selected_names = {str(value) for value in patch.get("includeMateNames") or []}
    if selected_names:
        available_names = {str(item.get("MateName") or "") for item in graph["Mates"]}
        missing_names = sorted(selected_names - available_names)
        if missing_names:
            raise MateGraphEditError("Unknown includeMateNames: " + ", ".join(missing_names))
        graph["Mates"] = [
            item for item in graph["Mates"] if str(item.get("MateName") or "") in selected_names
        ]

    catalog_by_id: dict[str, dict[str, Any]] = {}
    catalog_digest: str | None = None
    if endpoint_catalog is not None:
        if endpoint_catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
            raise MateGraphEditError(
                f"Unsupported endpoint catalog schema '{endpoint_catalog.get('SchemaVersion')}'."
            )
        catalog_digest = hashlib.sha256(
            json.dumps(endpoint_catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for entry in endpoint_catalog.get("Endpoints") or []:
            endpoint_id = str(entry.get("EndpointId") or "").strip()
            endpoint = entry.get("Endpoint")
            if not endpoint_id or not isinstance(endpoint, dict):
                raise MateGraphEditError("Every endpoint catalog entry requires EndpointId and Endpoint.")
            if endpoint_id in catalog_by_id:
                raise MateGraphEditError(f"Duplicate EndpointId in catalog: {endpoint_id}")
            catalog_by_id[endpoint_id] = entry

    audit: list[dict[str, Any]] = []
    for index, operation in enumerate(patch.get("operations") or []):
        kind = str(operation.get("operation") or "").strip()
        if kind == "removeMate":
            target = _resolve_mate(graph["Mates"], operation)
            graph["Mates"].remove(target)
            audit.append({"index": index, "operation": kind, "mateName": target["MateName"]})
        elif kind == "updateMate":
            target = _resolve_mate(graph["Mates"], operation)
            changes = operation.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise MateGraphEditError("updateMate requires a non-empty changes object.")
            allowed = {"MateName", "MateType", "MateTypeName", "Alignment", "AlignmentName", "Distance", "Angle", "IsSuppressed"}
            unknown = sorted(set(changes) - allowed)
            if unknown:
                raise MateGraphEditError("Unsupported update fields: " + ", ".join(unknown))
            before = {key: target.get(key) for key in changes}
            target.update(copy.deepcopy(changes))
            audit.append(
                {
                    "index": index,
                    "operation": kind,
                    "mateName": target.get("MateName"),
                    "before": before,
                    "after": {key: target.get(key) for key in changes},
                }
            )
        elif kind == "addMate":
            raw_mate = operation.get("mate")
            if not isinstance(raw_mate, dict):
                raise MateGraphEditError("addMate requires a mate object.")
            added = copy.deepcopy(raw_mate)
            endpoint_source = str(operation.get("copyEndpointsFromMate") or "").strip()
            endpoint_ids = [str(value) for value in operation.get("endpointIds") or []]
            if endpoint_source and endpoint_ids:
                raise MateGraphEditError(
                    "addMate cannot use copyEndpointsFromMate and endpointIds together."
                )
            if endpoint_ids:
                if len(endpoint_ids) != 2:
                    raise MateGraphEditError("addMate endpointIds must contain exactly two IDs.")
                if endpoint_catalog is None:
                    raise MateGraphEditError("addMate endpointIds require an endpoint catalog.")
                missing_ids = [value for value in endpoint_ids if value not in catalog_by_id]
                if missing_ids:
                    raise MateGraphEditError("Unknown EndpointIds: " + ", ".join(missing_ids))
                endpoints = []
                for endpoint_index, endpoint_id in enumerate(endpoint_ids):
                    endpoint = copy.deepcopy(catalog_by_id[endpoint_id]["Endpoint"])
                    endpoint["Index"] = endpoint_index
                    endpoints.append(endpoint)
                added["Endpoints"] = endpoints
                added.setdefault(
                    "ModuleTokens",
                    list(dict.fromkeys(str(item.get("ModuleToken") or "") for item in endpoints)),
                )
                added.setdefault(
                    "ModuleHierarchyPaths",
                    list(dict.fromkeys(str(item.get("ModuleHierarchyPath") or "") for item in endpoints)),
                )
            elif endpoint_source:
                source = _resolve_mate(graph["Mates"], {"mateName": endpoint_source})
                added["Endpoints"] = copy.deepcopy(source.get("Endpoints") or [])
                added.setdefault("ModuleTokens", copy.deepcopy(source.get("ModuleTokens") or []))
                added.setdefault(
                    "ModuleHierarchyPaths",
                    copy.deepcopy(source.get("ModuleHierarchyPaths") or []),
                )
            added.setdefault("IsSuppressed", False)
            added.setdefault("IsBasicTwoFaceRebuildable", True)
            added.setdefault("RebuildRejectionReason", None)
            graph["Mates"].append(added)
            audit.append(
                {
                    "index": index,
                    "operation": kind,
                    "mateName": added.get("MateName"),
                    "endpointIds": endpoint_ids,
                    "copyEndpointsFromMate": endpoint_source or None,
                }
            )
        else:
            raise MateGraphEditError(f"Unknown patch operation '{kind}'.")

    warnings = _validate_graph(graph)
    base_module = str(patch.get("baseModuleToken") or "A600").strip()
    available_bases = {
        str(module.get(field) or "").casefold()
        for module in graph["Modules"]
        for field in ("ModuleToken", "HierarchyPath")
    }
    if base_module.casefold() not in available_bases:
        raise MateGraphEditError(f"baseModuleToken '{base_module}' is outside the effective Modules set.")
    placement_mode = str(patch.get("initialPlacementMode") or "deterministic").strip().lower().replace("-", "_")
    if placement_mode not in {"deterministic", "source_pose"}:
        raise MateGraphEditError(
            "initialPlacementMode must be deterministic or source_pose."
        )
    graph["SchemaVersion"] = "editable-module-mate-graph/v1"
    graph["ModuleCount"] = len(graph["Modules"])
    graph["InterModuleMateCount"] = len(graph["Mates"])
    graph["MateBundleCount"] = 0
    graph["MateBundles"] = []
    graph["SavedJsonPath"] = None
    graph["SourceGraphProvenance"] = {
        "schemaVersion": str(source_graph.get("SchemaVersion") or ""),
        "sourceAssemblyPath": str(source_graph.get("SourceAssemblyPath") or ""),
        "sha256": source_digest,
    }
    if endpoint_catalog is not None:
        graph["EndpointCatalogProvenance"] = {
            "schemaVersion": str(endpoint_catalog.get("SchemaVersion") or ""),
            "sourceAssemblyPath": str(endpoint_catalog.get("SourceAssemblyPath") or ""),
            "sha256": catalog_digest,
        }
    graph["EditPolicy"] = {
        "baseModuleToken": base_module,
        "initialPlacementMode": placement_mode,
        "sourceGraphImmutable": True,
    }
    graph["PatchAudit"] = {
        "patchSchemaVersion": patch_schema,
        "patchSha256": patch_digest,
        "operationCount": len(audit),
        "operations": audit,
        "warnings": warnings,
    }
    return graph
