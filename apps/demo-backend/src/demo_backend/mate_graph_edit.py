from __future__ import annotations

import copy
import hashlib
import json
import math
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
    21,  # slot (import/rebuild only; two endpoints plus AdvancedOptions)
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
        if mate_type == 21 and (mate.get("AdvancedOptions") or {}).get("SlotConstraint") is None:
            raise MateGraphEditError(f"Slot mate '{name}' requires SlotConstraint in AdvancedOptions.")

    active_by_signature: dict[tuple[int, tuple[str, ...]], dict[str, Any]] = {}
    active_by_endpoints: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for mate in mates:
        if bool(mate.get("IsSuppressed", False)):
            continue
        signature = (int(mate["MateType"]), _canonical_endpoint_key(mate))
        active_by_endpoints.setdefault(signature[1], []).append(mate)
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
    for endpoint_key, endpoint_mates in active_by_endpoints.items():
        types = {int(item["MateType"]) for item in endpoint_mates}
        names = ", ".join(str(item["MateName"]) for item in endpoint_mates)
        if 2 in types and types.intersection({0, 3, 5}):
            raise MateGraphEditError(
                "Contradictory planar orientation mates share the same endpoints: " + names
            )
        coincident = next(
            (item for item in endpoint_mates if int(item["MateType"]) == 0), None
        )
        nonzero_distance = next(
            (
                item
                for item in endpoint_mates
                if int(item["MateType"]) == 5
                and abs(float(item.get("Distance") or 0.0)) > 1e-12
            ),
            None,
        )
        if coincident is not None and nonzero_distance is not None:
            raise MateGraphEditError(
                "Coincident and non-zero distance mates conflict on the same endpoints: "
                f"{coincident['MateName']} and {nonzero_distance['MateName']}."
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
        if kind in {"addModule", "addComponent"}:
            raw_module = operation.get("module") or operation.get("component")
            if not isinstance(raw_module, dict):
                raise MateGraphEditError(f"{kind} requires a module object.")
            added_module = copy.deepcopy(raw_module)
            module_token = str(added_module.get("ModuleToken") or "").strip()
            hierarchy_path = str(added_module.get("HierarchyPath") or "").strip()
            source_path = str(added_module.get("Path") or "").strip()
            if not module_token or not hierarchy_path or not source_path:
                raise MateGraphEditError(
                    f"{kind} module requires ModuleToken, HierarchyPath, and Path."
                )
            if any(
                str(item.get("HierarchyPath") or "").casefold()
                == hierarchy_path.casefold()
                for item in graph["Modules"]
            ):
                raise MateGraphEditError(
                    f"{kind} HierarchyPath already exists: {hierarchy_path}"
                )
            added_module.setdefault("Name", hierarchy_path.split("/")[-1])
            added_module.setdefault("SourceTransform", None)
            added_module.setdefault("IsSuppressed", False)
            added_module.setdefault("SuppressionState", 3)
            added_module.setdefault("SuppressionStateName", "resolved")
            added_module.setdefault("VisibilityState", 1)
            graph["Modules"].append(added_module)
            audit.append(
                {
                    "index": index,
                    "operation": "addModule",
                    "moduleToken": module_token,
                    "hierarchyPath": hierarchy_path,
                    "path": source_path,
                }
            )
        elif kind == "removeMate":
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
                try:
                    added_mate_type = int(added.get("MateType", -1))
                except (TypeError, ValueError) as exc:
                    raise MateGraphEditError("addMate requires an integer MateType.") from exc
                expected_endpoint_count = 4 if added_mate_type == 11 else 2
                if len(endpoint_ids) != expected_endpoint_count:
                    raise MateGraphEditError(
                        "addMate endpointIds must contain exactly "
                        f"{expected_endpoint_count} IDs for mate type {added_mate_type}."
                    )
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
            is_basic_two_face = int(added.get("MateType", -1)) != 11
            added.setdefault("IsBasicTwoFaceRebuildable", is_basic_two_face)
            added.setdefault(
                "RebuildRejectionReason",
                None
                if is_basic_two_face
                else "Width mate is rebuilt through its four ordered semantic endpoints.",
            )
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
    fixed_module_tokens = [
        str(value).strip() for value in patch.get("fixedContextModuleTokens") or []
    ]
    if any(not value for value in fixed_module_tokens) or len(fixed_module_tokens) != len(
        {value.casefold() for value in fixed_module_tokens}
    ):
        raise MateGraphEditError(
            "fixedContextModuleTokens must contain unique non-empty selectors."
        )
    available_fixed_selectors = {
        str(module.get(field) or "").casefold()
        for module in graph["Modules"]
        for field in ("ModuleToken", "HierarchyPath")
    }
    missing_fixed = [
        value
        for value in fixed_module_tokens
        if value.casefold() not in available_fixed_selectors
    ]
    if missing_fixed:
        raise MateGraphEditError(
            "fixedContextModuleTokens reference modules outside the effective graph: "
            + ", ".join(missing_fixed)
        )
    case_anchored_module_tokens = [
        str(value).strip() for value in patch.get("caseAnchoredModuleTokens") or []
    ]
    if any(not value for value in case_anchored_module_tokens) or len(
        case_anchored_module_tokens
    ) != len({value.casefold() for value in case_anchored_module_tokens}):
        raise MateGraphEditError(
            "caseAnchoredModuleTokens must contain unique non-empty selectors."
        )
    missing_case_anchors = [
        value
        for value in case_anchored_module_tokens
        if value.casefold() not in available_fixed_selectors
    ]
    if missing_case_anchors:
        raise MateGraphEditError(
            "caseAnchoredModuleTokens reference modules outside the effective graph: "
            + ", ".join(missing_case_anchors)
        )
    source_mate_names_to_suppress = [
        str(value).strip() for value in patch.get("sourceMateNamesToSuppress") or []
    ]
    if any(not value for value in source_mate_names_to_suppress) or len(
        source_mate_names_to_suppress
    ) != len({value.casefold() for value in source_mate_names_to_suppress}):
        raise MateGraphEditError(
            "sourceMateNamesToSuppress must contain unique non-empty source mate names."
        )
    source_mate_names = {
        str(item.get("MateName") or "").casefold()
        for item in source_graph.get("Mates") or []
    }
    unknown_source_mates = [
        value
        for value in source_mate_names_to_suppress
        if value.casefold() not in source_mate_names
    ]
    if unknown_source_mates:
        raise MateGraphEditError(
            "sourceMateNamesToSuppress references names outside the immutable source graph: "
            + ", ".join(unknown_source_mates)
        )
    target_leaf_pose_anchors = copy.deepcopy(patch.get("targetLeafPoseAnchors") or [])
    if not isinstance(target_leaf_pose_anchors, list):
        raise MateGraphEditError("targetLeafPoseAnchors must be an array.")
    anchor_paths: set[str] = set()
    for anchor in target_leaf_pose_anchors:
        if not isinstance(anchor, dict):
            raise MateGraphEditError("Every targetLeafPoseAnchor must be an object.")
        relative_path = str(anchor.get("relativeLeafHierarchyPath") or "").strip()
        transform = anchor.get("transform")
        if not relative_path or relative_path.casefold() in anchor_paths:
            raise MateGraphEditError(
                "targetLeafPoseAnchors require unique non-empty relativeLeafHierarchyPath values."
            )
        anchor_paths.add(relative_path.casefold())
        if (
            not isinstance(transform, list)
            or len(transform) != 16
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in transform
            )
        ):
            raise MateGraphEditError(
                f"targetLeafPoseAnchor '{relative_path}' requires 16 finite transform values."
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
        "fixedModuleTokens": fixed_module_tokens,
        "caseAnchoredModuleTokens": case_anchored_module_tokens,
        "sourceMateNamesToSuppress": source_mate_names_to_suppress,
        "targetLeafPoseAnchors": target_leaf_pose_anchors,
    }
    graph["PatchAudit"] = {
        "patchSchemaVersion": patch_schema,
        "patchSha256": patch_digest,
        "operationCount": len(audit),
        "operations": audit,
        "warnings": warnings,
    }
    return graph
