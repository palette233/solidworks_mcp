from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


class FaceEndpointCatalogError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise FaceEndpointCatalogError(
            f"Unsupported endpoint catalog schema '{catalog.get('SchemaVersion')}'."
        )
    entries = catalog.get("Endpoints")
    if not isinstance(entries, list):
        raise FaceEndpointCatalogError("Endpoint catalog must contain an Endpoints array.")
    ids = [str(item.get("EndpointId") or "") for item in entries]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise FaceEndpointCatalogError("EndpointId values must be unique and non-empty.")
    return entries


def select_face_endpoint(catalog: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
    matches = [item for item in _entries(catalog) if item["EndpointId"] == endpoint_id]
    if len(matches) != 1:
        raise FaceEndpointCatalogError(
            f"EndpointId '{endpoint_id}' resolved to {len(matches)} entries; expected exactly one."
        )
    return matches[0]


def list_face_candidates(
    catalog: dict[str, Any],
    *,
    module_token: str | None = None,
    geometry_class: str | None = "Plane",
    minimum_area: float = 0.0,
    leaf_contains: str | None = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in _entries(catalog):
        endpoint = entry.get("Endpoint") or {}
        if module_token and str(endpoint.get("ModuleToken") or "").casefold() != module_token.casefold():
            continue
        if geometry_class and str(entry.get("GeometryClass") or "").casefold() != geometry_class.casefold():
            continue
        if float(endpoint.get("FaceArea") or 0.0) < minimum_area:
            continue
        if leaf_contains and leaf_contains.casefold() not in str(endpoint.get("RelativeLeafHierarchyPath") or "").casefold():
            continue
        result.append(entry)
    return sorted(
        result,
        key=lambda item: (
            str((item.get("Endpoint") or {}).get("ModuleToken") or ""),
            -float((item.get("Endpoint") or {}).get("FaceArea") or 0.0),
            str(item.get("EndpointId") or ""),
        ),
    )


def validate_mate_endpoint_pair(
    catalog: dict[str, Any], endpoint_ids: list[str], mate_type: int
) -> list[dict[str, Any]]:
    if len(endpoint_ids) != 2:
        raise FaceEndpointCatalogError("Exactly two EndpointIds are required.")
    selected = [select_face_endpoint(catalog, value) for value in endpoint_ids]
    endpoints = [item["Endpoint"] for item in selected]
    module_paths = {str(item.get("ModuleHierarchyPath") or "") for item in endpoints}
    if len(module_paths) != 2:
        raise FaceEndpointCatalogError("A mate must connect endpoints from two different modules.")
    if mate_type in {0, 2, 3, 5, 6} and any(
        str(item.get("GeometryClass") or "").casefold() != "plane" for item in selected
    ):
        raise FaceEndpointCatalogError("This mate type requires two planar catalog endpoints.")
    # Slot mates are reconstructed from two ordered face endpoints.  One side is
    # commonly a cylindrical/slot wall and therefore has no single planar normal.
    if mate_type not in {0, 1, 2, 3, 4, 5, 6, 21}:
        raise FaceEndpointCatalogError(f"Unsupported basic mate type {mate_type}.")
    return selected


def match_exported_face_endpoint(
    catalog: dict[str, Any], exported_endpoint: dict[str, Any]
) -> dict[str, Any]:
    exact = []
    for entry in _entries(catalog):
        endpoint = entry.get("Endpoint") or {}
        if all(
            endpoint.get(field) == exported_endpoint.get(field)
            for field in (
                "ModuleHierarchyPath",
                "RelativeLeafHierarchyPath",
                "BodyIndex",
                "FaceIndexInBody",
            )
        ):
            exact.append(entry)
    if len(exact) == 1:
        return exact[0]

    fingerprint = []
    for entry in _entries(catalog):
        endpoint = entry.get("Endpoint") or {}
        if endpoint.get("ModuleHierarchyPath") != exported_endpoint.get("ModuleHierarchyPath"):
            continue
        area_delta = abs(float(endpoint.get("FaceArea") or 0.0) - float(exported_endpoint.get("FaceArea") or 0.0))
        if area_delta <= max(1e-10, abs(float(exported_endpoint.get("FaceArea") or 0.0)) * 1e-6):
            fingerprint.append(entry)
    if len(fingerprint) != 1:
        raise FaceEndpointCatalogError(
            f"Exported endpoint resolved to {len(fingerprint)} catalog candidates; expected exactly one."
        )
    return fingerprint[0]


def append_face_endpoint(
    catalog: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    current = _entries(catalog)
    endpoint_id = str(entry.get("EndpointId") or "").strip()
    if not endpoint_id or not isinstance(entry.get("Endpoint"), dict):
        raise FaceEndpointCatalogError("Captured entry requires EndpointId and Endpoint.")
    if any(item["EndpointId"] == endpoint_id for item in current):
        raise FaceEndpointCatalogError(f"EndpointId already exists: {endpoint_id}")
    result = copy.deepcopy(catalog)
    result["Endpoints"].append(copy.deepcopy(entry))
    result["EndpointCount"] = len(result["Endpoints"])
    result["CatalogMode"] = "seed_plus_selected_faces"
    return result


def merge_face_endpoint_catalogs(
    base_catalog: dict[str, Any], extension_catalog: dict[str, Any]
) -> dict[str, Any]:
    """Merge a bounded leaf scan into a new catalog without mutating either input."""

    base_entries = _entries(base_catalog)
    extension_entries = _entries(extension_catalog)
    base_source = str(base_catalog.get("SourceAssemblyPath") or "")
    extension_source = str(extension_catalog.get("SourceAssemblyPath") or "")
    if base_source and extension_source and base_source.casefold() != extension_source.casefold():
        raise FaceEndpointCatalogError("Catalogs must reference the same source assembly.")

    def identity_payload(entry: dict[str, Any]) -> tuple[Any, ...]:
        endpoint = entry.get("Endpoint") or {}
        return (
            str(entry.get("ModulePath") or "").casefold(),
            entry.get("ModuleReferencedConfiguration"),
            entry.get("LeafReferencedConfiguration"),
            entry.get("GeometryClass"),
            endpoint.get("ModuleHierarchyPath"),
            endpoint.get("RelativeLeafHierarchyPath"),
            str(endpoint.get("LeafComponentPath") or "").casefold(),
            endpoint.get("BodyIndex"),
            endpoint.get("FaceIndexInBody"),
            endpoint.get("FaceArea"),
            tuple(endpoint.get("FaceCenterLocal") or []),
            tuple(endpoint.get("FaceNormalLocal") or []),
        )

    result = copy.deepcopy(base_catalog)
    by_id = {str(item["EndpointId"]): item for item in result["Endpoints"]}
    added_ids: list[str] = []
    duplicate_ids: list[str] = []
    for entry in extension_entries:
        endpoint_id = str(entry["EndpointId"])
        existing = by_id.get(endpoint_id)
        if existing is not None:
            if identity_payload(existing) != identity_payload(entry):
                raise FaceEndpointCatalogError(
                    f"EndpointId collision has different payloads: {endpoint_id}"
                )
            duplicate_ids.append(endpoint_id)
            continue
        copied = copy.deepcopy(entry)
        result["Endpoints"].append(copied)
        by_id[endpoint_id] = copied
        added_ids.append(endpoint_id)

    result["EndpointCount"] = len(result["Endpoints"])
    result["CatalogMode"] = "seed_plus_leaf_scans"
    result["MergedLeafSelectors"] = list(
        dict.fromkeys(
            [
                *list(base_catalog.get("MergedLeafSelectors") or []),
                *list(extension_catalog.get("RequestedLeafSelectors") or []),
            ]
        )
    )
    result["LastMerge"] = {
        "extensionCatalogMode": extension_catalog.get("CatalogMode"),
        "addedEndpointIds": added_ids,
        "duplicateEndpointIds": duplicate_ids,
        "duplicateRecoveryEvidence": {
            endpoint_id: list(
                dict.fromkeys(
                    [
                        str(by_id[endpoint_id].get("RecoveryConfidence") or ""),
                        str(
                            next(
                                item
                                for item in extension_entries
                                if str(item["EndpointId"]) == endpoint_id
                            ).get("RecoveryConfidence")
                            or ""
                        ),
                    ]
                )
            )
            for endpoint_id in duplicate_ids
        },
    }
    return result


def build_face_endpoint_catalog_from_source_mates(
    source_graph: dict[str, Any],
    mate_names: list[str],
    existing_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bounded face catalog from already exported, named source mates.

    This deliberately avoids a full leaf scan.  The exported mate already contains
    the persistent reference and geometric fingerprint needed by the SolidWorks
    recovery pipeline.  Existing stable EndpointIds are reused when the same
    persistent reference has previously been registered.
    """

    modules = source_graph.get("Modules")
    mates = source_graph.get("Mates")
    if not isinstance(modules, list) or not isinstance(mates, list):
        raise FaceEndpointCatalogError("Source graph must contain Modules and Mates arrays.")
    requested = [str(value).strip() for value in mate_names]
    if any(not value for value in requested) or len(requested) != len(set(requested)):
        raise FaceEndpointCatalogError("mate_names must be unique and non-empty.")
    by_name = {str(item.get("MateName") or ""): item for item in mates}
    missing = [value for value in requested if value not in by_name]
    if missing:
        raise FaceEndpointCatalogError("Unknown source mate names: " + ", ".join(missing))
    module_by_path = {
        str(item.get("HierarchyPath") or "").casefold(): item for item in modules
    }

    existing_entries = _entries(existing_catalog) if existing_catalog is not None else []
    existing_by_reference = {
        str((entry.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64") or ""):
        entry
        for entry in existing_entries
        if str((entry.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64") or "")
    }

    def endpoint_identity(endpoint: dict[str, Any]) -> dict[str, Any]:
        return {
            "ModuleToken": endpoint.get("ModuleToken"),
            "ModuleHierarchyPath": endpoint.get("ModuleHierarchyPath"),
            "RelativeLeafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
            "LeafComponentPath": endpoint.get("LeafComponentPath"),
            "BodyIndex": endpoint.get("BodyIndex"),
            "FaceIndexInBody": endpoint.get("FaceIndexInBody"),
            "FaceArea": endpoint.get("FaceArea"),
            "FaceCenterLocal": endpoint.get("FaceCenterLocal"),
            "FaceNormalLocal": endpoint.get("FaceNormalLocal"),
        }

    result_entries: list[dict[str, Any]] = []
    seen_references: set[str] = set()
    seen_identities: set[str] = set()
    reused_ids: list[str] = []
    generated_ids: list[str] = []
    source_mate_usage: dict[str, list[str]] = {}
    for mate_name in requested:
        mate = by_name[mate_name]
        endpoints = mate.get("Endpoints")
        if not isinstance(endpoints, list) or len(endpoints) < 2:
            raise FaceEndpointCatalogError(
                f"Source mate '{mate_name}' does not contain enough endpoints."
            )
        for endpoint in endpoints:
            if str(endpoint.get("GeometryType") or "").casefold() != "face":
                raise FaceEndpointCatalogError(
                    f"Source mate '{mate_name}' contains a non-face endpoint."
                )
            reference = str(
                endpoint.get("SourceAssemblyPersistentReferenceBase64") or ""
            )
            identity_digest = _digest(endpoint_identity(endpoint))
            dedupe_key = reference or identity_digest
            if dedupe_key in seen_references or identity_digest in seen_identities:
                continue
            seen_references.add(dedupe_key)
            seen_identities.add(identity_digest)

            existing = existing_by_reference.get(reference) if reference else None
            if existing is not None:
                entry = copy.deepcopy(existing)
                endpoint_id = str(entry["EndpointId"])
                reused_ids.append(endpoint_id)
            else:
                token = str(endpoint.get("ModuleToken") or "module").strip().lower()
                endpoint_id = f"face:{token}:{identity_digest[:16]}"
                module_path = str(endpoint.get("ModuleHierarchyPath") or "")
                module = module_by_path.get(module_path.casefold())
                if module is None:
                    raise FaceEndpointCatalogError(
                        f"Source mate '{mate_name}' references unknown module '{module_path}'."
                    )
                entry = {
                    "EndpointId": endpoint_id,
                    "ModulePath": module.get("Path"),
                    "ModuleReferencedConfiguration": module.get("ReferencedConfiguration"),
                    "LeafReferencedConfiguration": None,
                    "GeometryClass": (
                        "Plane" if endpoint.get("FaceNormalLocal") is not None else "Face"
                    ),
                    "RecoveryConfidence": "SOURCE_MATE_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
                    "Endpoint": copy.deepcopy(endpoint),
                }
                generated_ids.append(endpoint_id)
            result_entries.append(entry)
            source_mate_usage.setdefault(endpoint_id, []).append(mate_name)

    return {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "SourceAssemblyPath": source_graph.get("SourceAssemblyPath"),
        "CatalogMode": "bounded_source_mate_endpoints",
        "SelectedMateNames": requested,
        "EndpointCount": len(result_entries),
        "Endpoints": result_entries,
        "SourceMateEndpointAudit": {
            "reusedEndpointIds": reused_ids,
            "generatedEndpointIds": generated_ids,
            "endpointMateUsage": source_mate_usage,
            "sourceGraphSha256": _digest(source_graph),
        },
    }
