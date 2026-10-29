"""Acquire reviewable three-plane fallback ports for transport modules.

SS00 and AE00 have authoritative native ports made from one support plane and
two 58 mm locating axes.  Project02 A600 does not expose a matching 58 mm axis
pair, so those native ports must not be stretched or relabelled to claim
compatibility.  This module defines the bounded alternative path:

1. scan only the already identified static mounting leaf;
2. keep only real planar faces with persistent references;
3. enumerate mutually orthogonal three-plane datum candidates; and
4. require an explicit engineering confirmation before a parameterized datum
   port can be registered.

The scan and review stages never authorize CAD execution and never copy a
prototype top-level or leaf pose into an execution package.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


PLAN_SCHEMA = "transport-datum-port-acquisition-plan/v1"
REVIEW_SCHEMA = "transport-datum-port-candidate-review/v1"
CONFIRMED_PORT_SCHEMA = "confirmed-transport-datum-port/v1"
SEED_AUDIT_SCHEMA = "transport-datum-seed-evidence-audit/v1"

ACQUISITION_ROOT = (
    "demo/cross_project_substitution/"
    "transport-three-plane-port-acquisition-v1"
)

TRANSPORT_SPECS: tuple[dict[str, str], ...] = (
    {
        "moduleDefinitionId": "project01::SS00",
        "moduleToken": "SS00",
        "sourceReleaseId": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
        "seedCatalog": (
            "demo/semantic_ports/project01_SS00_first_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        "supportEndpointId": "face:ss00:5f78c60819f7f66c",
        "scanFileName": "project01-ss00-static-mount-leaf-face-catalog.json",
    },
    {
        "moduleDefinitionId": "project03::AE00",
        "moduleToken": "AE00",
        "sourceReleaseId": "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
        "seedCatalog": (
            "demo/semantic_ports/project03_AE00_first_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        "supportEndpointId": "face:fl9a24d063ae00:d3f2555c5bc3f5d2",
        "scanFileName": "project03-ae00-static-mount-leaf-face-catalog.json",
    },
)


class TransportDatumPortAcquisitionError(ValueError):
    """Raised when source evidence cannot support a transport datum port."""


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _vector(raw: Any, label: str) -> list[float]:
    if (
        not isinstance(raw, list)
        or len(raw) != 3
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in raw
        )
    ):
        raise TransportDatumPortAcquisitionError(f"{label} must be a finite 3-vector")
    return [float(value) for value in raw]


def _unit(raw: Any, label: str) -> list[float]:
    vector = _vector(raw, label)
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise TransportDatumPortAcquisitionError(f"{label} is degenerate")
    return [value / length for value in vector]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _endpoint_rows(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise TransportDatumPortAcquisitionError("unsupported face endpoint catalog")
    rows = catalog.get("Endpoints")
    if not isinstance(rows, list):
        raise TransportDatumPortAcquisitionError("face endpoint catalog has no Endpoints")
    return rows


def _endpoint_id(row: dict[str, Any]) -> str:
    endpoint_id = str(row.get("EndpointId") or "")
    if not endpoint_id:
        raise TransportDatumPortAcquisitionError("face endpoint has no EndpointId")
    return endpoint_id


def _endpoint(row: dict[str, Any]) -> dict[str, Any]:
    endpoint = row.get("Endpoint")
    if not isinstance(endpoint, dict):
        raise TransportDatumPortAcquisitionError(
            f"endpoint {_endpoint_id(row)} has no geometry payload"
        )
    return endpoint


def _is_plane(row: dict[str, Any]) -> bool:
    endpoint = _endpoint(row)
    return (
        str(row.get("GeometryClass") or "").lower() == "plane"
        or str(endpoint.get("SurfaceType") or "").lower() == "plane"
    ) and endpoint.get("FaceNormalLocal") is not None


def _persistent_reference(row: dict[str, Any]) -> str:
    return str(_endpoint(row).get("SourceAssemblyPersistentReferenceBase64") or "")


def _normalized_path(value: Any) -> str:
    return os.path.normcase(os.path.normpath(str(value or "")))


def _row_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _endpoint_rows(catalog)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        endpoint_id = _endpoint_id(row)
        if endpoint_id in result:
            raise TransportDatumPortAcquisitionError(
                f"duplicate endpoint id: {endpoint_id}"
            )
        result[endpoint_id] = row
    return result


def audit_existing_transport_seed_evidence(workspace: Path) -> dict[str, Any]:
    """Prove whether mate-only seed catalogs can replace a bounded leaf scan.

    The historical catalogs contain only endpoints referenced by native source
    mates.  They are useful evidence, but they are not assumed to inventory all
    faces on a leaf.  This audit checks the exact static leaf and only reports a
    reusable three-plane basis when three persistent, mutually orthogonal
    planar faces are already present.
    """

    workspace = workspace.resolve()
    items: list[dict[str, Any]] = []
    for spec in TRANSPORT_SPECS:
        seed_path = workspace / spec["seedCatalog"]
        seed = _read(seed_path)
        rows = _endpoint_rows(seed)
        support = _row_index(seed).get(spec["supportEndpointId"])
        if support is None or not _is_plane(support):
            raise TransportDatumPortAcquisitionError(
                f"seed support plane is unavailable for {spec['moduleDefinitionId']}"
            )
        support_endpoint = _endpoint(support)
        leaf = str(support_endpoint.get("LeafHierarchyPath") or "")
        support_normal = _unit(
            support_endpoint.get("FaceNormalLocal"), "seed support normal"
        )
        same_leaf = [
            row
            for row in rows
            if str(_endpoint(row).get("LeafHierarchyPath") or "").lower()
            == leaf.lower()
        ]
        planes = [
            row
            for row in same_leaf
            if _is_plane(row) and bool(_persistent_reference(row))
        ]
        directions = []
        for row in planes:
            endpoint_id = _endpoint_id(row)
            if endpoint_id == spec["supportEndpointId"]:
                continue
            normal = _unit(
                _endpoint(row).get("FaceNormalLocal"),
                f"seed plane {endpoint_id} normal",
            )
            if abs(_dot(normal, support_normal)) <= 1e-5:
                directions.append((endpoint_id, normal))
        direction_pair: list[str] | None = None
        for index, first in enumerate(directions):
            for second in directions[index + 1 :]:
                if abs(_dot(first[1], second[1])) <= 1e-5:
                    direction_pair = [first[0], second[0]]
                    break
            if direction_pair is not None:
                break
        reusable = direction_pair is not None
        item_core = {
            "moduleDefinitionId": spec["moduleDefinitionId"],
            "moduleToken": spec["moduleToken"],
            "seedCatalogPath": spec["seedCatalog"],
            "seedCatalogDigest": _digest(seed),
            "staticMountLeafSelector": leaf,
            "seedEndpointCount": len(rows),
            "sameLeafEndpointCount": len(same_leaf),
            "sameLeafPersistentPlaneCount": len(planes),
            "sameLeafNonPlaneEndpointCount": len(same_leaf) - len(planes),
            "existingSupportEndpointId": spec["supportEndpointId"],
            "orthogonalDirectionEndpointIds": direction_pair,
            "supportsThreePlaneFallbackWithoutRescan": reusable,
            "boundedLeafScanStillRequired": not reusable,
            "blocker": (
                None
                if reusable
                else {
                    "code": "SEED_CATALOG_DOES_NOT_INVENTORY_THREE_ORTHOGONAL_PLANES",
                    "detail": (
                        "The historical catalog contains source-mate endpoints, "
                        "not a complete planar inventory of the static mounting leaf."
                    ),
                }
            ),
        }
        items.append(item_core)
    core = {
        "schemaVersion": SEED_AUDIT_SCHEMA,
        "items": items,
        "summary": {
            "itemCount": len(items),
            "reusableWithoutRescanCount": sum(
                row["supportsThreePlaneFallbackWithoutRescan"] for row in items
            ),
            "boundedLeafScanRequiredCount": sum(
                row["boundedLeafScanStillRequired"] for row in items
            ),
        },
        "executionBoundary": {
            "cadExecutionAuthorized": False,
            "normalAssemblyExecutionAuthorized": False,
            "native58mmCompatibilityClaimed": False,
        },
        "claimBoundary": (
            "This audit only determines whether historical mate endpoints already "
            "contain a complete three-plane basis. It never selects faces, registers "
            "a port, starts CAD or authorizes a relation release."
        ),
    }
    return {**core, "auditDigest": _digest(core)}


def build_transport_datum_port_acquisition_plan(workspace: Path) -> dict[str, Any]:
    """Build the deterministic two-item bounded scan plan from existing evidence."""

    workspace = workspace.resolve()
    items: list[dict[str, Any]] = []
    for spec in TRANSPORT_SPECS:
        seed_path = workspace / spec["seedCatalog"]
        seed = _read(seed_path)
        support = _row_index(seed).get(spec["supportEndpointId"])
        if support is None:
            raise TransportDatumPortAcquisitionError(
                f"support endpoint is absent for {spec['moduleDefinitionId']}"
            )
        if not _is_plane(support):
            raise TransportDatumPortAcquisitionError(
                f"support endpoint is not planar for {spec['moduleDefinitionId']}"
            )
        if not _persistent_reference(support):
            raise TransportDatumPortAcquisitionError(
                f"support endpoint has no persistent reference for {spec['moduleDefinitionId']}"
            )
        endpoint = _endpoint(support)
        leaf = str(endpoint.get("LeafHierarchyPath") or "")
        if not leaf:
            raise TransportDatumPortAcquisitionError(
                f"support endpoint has no leaf hierarchy for {spec['moduleDefinitionId']}"
            )
        source = Path(str(seed.get("SourceAssemblyPath") or ""))
        if not source.is_file():
            raise TransportDatumPortAcquisitionError(
                f"source assembly is unavailable for {spec['moduleDefinitionId']}: {source}"
            )
        output_relative = f"{ACQUISITION_ROOT}/{spec['scanFileName']}"
        item_core = {
            "moduleDefinitionId": spec["moduleDefinitionId"],
            "moduleToken": spec["moduleToken"],
            "sourceReleaseId": spec["sourceReleaseId"],
            "sourceAssemblyPath": str(source.resolve()),
            "seedCatalogPath": spec["seedCatalog"],
            "seedCatalogDigest": _digest(seed),
            "existingSupportEndpointId": spec["supportEndpointId"],
            "staticMountLeafSelector": leaf,
            "scanOutputPath": output_relative,
            "scanPolicy": {
                "planarOnly": True,
                "minimumFaceArea": 1e-8,
                "maximumFaceCount": 500,
                "siblingLeafTraversalAllowed": False,
            },
        }
        items.append(
            {
                **item_core,
                "itemId": "transport-datum-scan/" + _digest(item_core)[:16],
                "status": "bounded_leaf_scan_required",
                "cadExecutionAuthorized": False,
                "command": [
                    "python",
                    "scripts/build_leaf_face_endpoint_catalog.py",
                    "--source",
                    item_core["sourceAssemblyPath"],
                    "--module",
                    spec["moduleToken"],
                    "--leaf",
                    leaf,
                    "--output",
                    output_relative,
                    "--minimum-face-area",
                    "1e-8",
                    "--maximum-face-count",
                    "500",
                ],
            }
        )
    core = {
        "schemaVersion": PLAN_SCHEMA,
        "purpose": (
            "Acquire real planar endpoints for an explicitly positioned transport "
            "fallback; do not emulate a missing 58 mm native axis pair."
        ),
        "items": items,
        "safetyBoundary": {
            "prototypeTopLevelPoseAllowed": False,
            "leafPoseAnchorAllowed": False,
            "automaticFaceSelectionAllowed": False,
            "normalCadExecutionAllowedBeforeConfirmationAndRelease": False,
            "native58mmCompatibilityClaimed": False,
        },
        "summary": {
            "itemCount": len(items),
            "scanRequiredCount": len(items),
            "confirmedPortCount": 0,
        },
    }
    return {**core, "planDigest": _digest(core)}


def _find_support_in_scan(
    support: dict[str, Any], scan_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    support_id = _endpoint_id(support)
    exact = [row for row in scan_rows if _endpoint_id(row) == support_id]
    if len(exact) == 1:
        return exact[0]
    persistent = _persistent_reference(support)
    by_persistent = [
        row for row in scan_rows if persistent and _persistent_reference(row) == persistent
    ]
    if len(by_persistent) == 1:
        return by_persistent[0]
    endpoint = _endpoint(support)
    fingerprint = (
        str(endpoint.get("LeafHierarchyPath") or "").lower(),
        endpoint.get("BodyIndex"),
        endpoint.get("FaceIndexInBody"),
        tuple(endpoint.get("FaceCenterLocal") or []),
        tuple(endpoint.get("FaceNormalLocal") or []),
    )
    by_fingerprint = []
    for row in scan_rows:
        candidate = _endpoint(row)
        candidate_fingerprint = (
            str(candidate.get("LeafHierarchyPath") or "").lower(),
            candidate.get("BodyIndex"),
            candidate.get("FaceIndexInBody"),
            tuple(candidate.get("FaceCenterLocal") or []),
            tuple(candidate.get("FaceNormalLocal") or []),
        )
        if candidate_fingerprint == fingerprint:
            by_fingerprint.append(row)
    if len(by_fingerprint) == 1:
        return by_fingerprint[0]
    raise TransportDatumPortAcquisitionError(
        "bounded scan does not uniquely recover the existing support face"
    )


def review_transport_datum_leaf_scan(
    acquisition_item: dict[str, Any],
    seed_catalog: dict[str, Any],
    scan_catalog: dict[str, Any],
    *,
    orthogonality_tolerance: float = 1e-5,
    minimum_face_area: float = 1e-7,
    maximum_candidate_count: int = 100,
) -> dict[str, Any]:
    """Enumerate real three-plane candidates without selecting or publishing one."""

    if maximum_candidate_count <= 0:
        raise TransportDatumPortAcquisitionError(
            "maximum_candidate_count must be positive"
        )
    if not 0 < orthogonality_tolerance < 0.1:
        raise TransportDatumPortAcquisitionError(
            "orthogonality_tolerance must be in (0, 0.1)"
        )
    if minimum_face_area < 0 or not math.isfinite(minimum_face_area):
        raise TransportDatumPortAcquisitionError(
            "minimum_face_area must be finite and non-negative"
        )
    source = str(acquisition_item.get("sourceAssemblyPath") or "")
    if _normalized_path(seed_catalog.get("SourceAssemblyPath")) != _normalized_path(source):
        raise TransportDatumPortAcquisitionError("seed catalog source does not match scan plan")
    if _normalized_path(scan_catalog.get("SourceAssemblyPath")) != _normalized_path(source):
        raise TransportDatumPortAcquisitionError("scan catalog source does not match scan plan")
    if scan_catalog.get("CatalogMode") != "leaf_scoped":
        raise TransportDatumPortAcquisitionError("scan catalog is not leaf_scoped")
    if scan_catalog.get("PlanarOnly") is not True:
        raise TransportDatumPortAcquisitionError("scan catalog is not planar-only")
    selector = str(acquisition_item.get("staticMountLeafSelector") or "")
    selectors = [str(value) for value in scan_catalog.get("RequestedLeafSelectors") or []]
    if selector not in selectors:
        raise TransportDatumPortAcquisitionError(
            "scan catalog was not built for the planned static mounting leaf"
        )
    seed_support_id = str(acquisition_item.get("existingSupportEndpointId") or "")
    seed_support = _row_index(seed_catalog).get(seed_support_id)
    if seed_support is None or not _is_plane(seed_support):
        raise TransportDatumPortAcquisitionError("seed support plane is absent")

    scan_rows = _endpoint_rows(scan_catalog)
    support = _find_support_in_scan(seed_support, scan_rows)
    support_endpoint = _endpoint(support)
    support_normal = _unit(
        support_endpoint.get("FaceNormalLocal"), "support FaceNormalLocal"
    )
    support_leaf = str(support_endpoint.get("LeafHierarchyPath") or "")
    if support_leaf.lower() != selector.lower():
        raise TransportDatumPortAcquisitionError(
            "recovered support face is not on the planned leaf"
        )

    eligible: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in scan_rows:
        endpoint_id = _endpoint_id(row)
        if endpoint_id in seen_ids:
            raise TransportDatumPortAcquisitionError(
                f"duplicate endpoint id in scan catalog: {endpoint_id}"
            )
        seen_ids.add(endpoint_id)
        endpoint = _endpoint(row)
        if not _is_plane(row):
            continue
        if str(endpoint.get("LeafHierarchyPath") or "").lower() != selector.lower():
            continue
        if not _persistent_reference(row):
            continue
        try:
            area = float(endpoint.get("FaceArea"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(area) or area < minimum_face_area:
            continue
        normal = _unit(endpoint.get("FaceNormalLocal"), f"{endpoint_id} normal")
        if abs(_dot(normal, support_normal)) > orthogonality_tolerance:
            continue
        eligible.append(
            {
                "row": row,
                "endpointId": endpoint_id,
                "normal": normal,
                "area": area,
            }
        )

    candidates: list[dict[str, Any]] = []
    for first_index, first in enumerate(eligible):
        for second in eligible[first_index + 1 :]:
            residual = abs(_dot(first["normal"], second["normal"]))
            if residual > orthogonality_tolerance:
                continue
            ordered = sorted((first, second), key=lambda item: item["endpointId"])
            endpoint_ids = [item["endpointId"] for item in ordered]
            core = {
                "supportEndpointId": _endpoint_id(support),
                "directionEndpointIds": endpoint_ids,
                "sourceSupportEndpointId": seed_support_id,
                "leafHierarchyPath": selector,
            }
            candidates.append(
                {
                    **core,
                    "candidateId": "transport-three-plane/" + _digest(core)[:16],
                    "minimumFaceArea": min(first["area"], second["area"]),
                    "totalDirectionFaceArea": first["area"] + second["area"],
                    "orthogonalityResiduals": {
                        "supportLongitudinal": abs(
                            _dot(support_normal, ordered[0]["normal"])
                        ),
                        "supportLateral": abs(
                            _dot(support_normal, ordered[1]["normal"])
                        ),
                        "longitudinalLateral": residual,
                    },
                    "persistentReferenceComplete": True,
                    "engineeringMeaning": "not_confirmed",
                    "actualFasteningMethod": "not_verified",
                }
            )
    candidates.sort(
        key=lambda row: (
            -float(row["minimumFaceArea"]),
            -float(row["totalDirectionFaceArea"]),
            str(row["candidateId"]),
        )
    )
    total_candidate_count = len(candidates)
    candidates = candidates[:maximum_candidate_count]
    status = (
        "candidate_triplets_require_engineering_confirmation"
        if candidates
        else "no_mutually_orthogonal_plane_triplet_found"
    )
    core = {
        "schemaVersion": REVIEW_SCHEMA,
        "moduleDefinitionId": acquisition_item.get("moduleDefinitionId"),
        "moduleToken": acquisition_item.get("moduleToken"),
        "status": status,
        "sourceAssemblyPath": source,
        "sourceReleaseId": acquisition_item.get("sourceReleaseId"),
        "seedCatalogPath": acquisition_item.get("seedCatalogPath"),
        "scanCatalogPath": acquisition_item.get("scanOutputPath"),
        "seedCatalogDigest": _digest(seed_catalog),
        "scanCatalogDigest": _digest(scan_catalog),
        "plannedLeafSelector": selector,
        "existingSupportEndpointId": seed_support_id,
        "recoveredSupportEndpointId": _endpoint_id(support),
        "candidateCountBeforeLimit": total_candidate_count,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "engineeringDecision": {
            "confirmed": False,
            "selectedCandidateId": None,
            "longitudinalEndpointId": None,
            "lateralEndpointId": None,
            "confirmationSource": None,
        },
        "executionBoundary": {
            "cadExecutionAuthorized": False,
            "normalRelationReleaseAuthorized": False,
            "prototypeTopLevelPoseAllowed": False,
            "leafPoseAnchorAllowed": False,
            "native58mmMechanicalCompatibilityClaimed": False,
            "parameterizedPositionStillRequired": True,
        },
    }
    return {**core, "reviewDigest": _digest(core)}


def confirm_transport_datum_port_candidate(
    review: dict[str, Any],
    *,
    selected_candidate_id: str,
    longitudinal_endpoint_id: str,
    lateral_endpoint_id: str,
    confirmation_source: str,
) -> dict[str, Any]:
    """Bind one reviewed triplet; this still does not publish a CAD relation."""

    if review.get("schemaVersion") != REVIEW_SCHEMA:
        raise TransportDatumPortAcquisitionError("unsupported review schema")
    source = confirmation_source.strip()
    if not source:
        raise TransportDatumPortAcquisitionError("confirmation_source is required")
    matches = [
        row
        for row in review.get("candidates") or []
        if row.get("candidateId") == selected_candidate_id
    ]
    if len(matches) != 1:
        raise TransportDatumPortAcquisitionError(
            "selected candidate is absent or ambiguous"
        )
    candidate = matches[0]
    directions = set(candidate.get("directionEndpointIds") or [])
    if (
        not longitudinal_endpoint_id
        or not lateral_endpoint_id
        or longitudinal_endpoint_id == lateral_endpoint_id
        or {longitudinal_endpoint_id, lateral_endpoint_id} != directions
    ):
        raise TransportDatumPortAcquisitionError(
            "longitudinal/lateral role assignment must use both candidate direction faces"
        )
    core = {
        "schemaVersion": CONFIRMED_PORT_SCHEMA,
        "moduleDefinitionId": review.get("moduleDefinitionId"),
        "moduleToken": review.get("moduleToken"),
        "selectedCandidateId": selected_candidate_id,
        "longitudinalEndpointId": longitudinal_endpoint_id,
        "lateralEndpointId": lateral_endpoint_id,
        "confirmationSource": source,
        "reviewDigest": review.get("reviewDigest"),
        "sourceReleaseId": review.get("sourceReleaseId"),
        "scanCatalogPath": review.get("scanCatalogPath"),
        "scanCatalogDigest": review.get("scanCatalogDigest"),
        "port": {
            "portId": f"{review.get('moduleToken')}.parameterized_datum_installation.v1",
            "moduleToken": review.get("moduleToken"),
            "endpointBindings": [
                {
                    "role": "support_datum",
                    "endpointId": candidate["supportEndpointId"],
                },
                {
                    "role": "longitudinal_datum",
                    "endpointId": longitudinal_endpoint_id,
                },
                {
                    "role": "lateral_datum",
                    "endpointId": lateral_endpoint_id,
                },
            ],
        },
        "authorization": {
            "readyForParameterizedCatalogRegistration": True,
            "readyForReleasedCadExecution": False,
            "requiresExplicitPositionParameters": True,
            "requiresNonPrototypeCadValidation": True,
            "requiresSaveReopenVerification": True,
            "requiresImmutableExactPairRelease": True,
        },
        "mechanicalBoundary": {
            "actualFasteningMethod": "not_verified",
            "native58mmMechanicalCompatibilityClaimed": False,
            "collisionAndBrepVerified": False,
            "productionReady": False,
        },
    }
    return {**core, "confirmationDigest": _digest(core)}


def load_confirmed_transport_datum_source_specs(
    workspace: Path,
) -> dict[str, dict[str, Any]]:
    """Load explicitly confirmed ports for parameterized catalog registration.

    Absence is valid and leaves SS00/AE00 on their native two-axis route.  A
    malformed, stale or path-escaping confirmation fails closed.
    """

    workspace = workspace.resolve()
    directory = workspace / ACQUISITION_ROOT / "confirmed-ports"
    if not directory.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        document = _read(path)
        if document.get("schemaVersion") != CONFIRMED_PORT_SCHEMA:
            raise TransportDatumPortAcquisitionError(
                f"unsupported confirmed port schema: {path}"
            )
        confirmation_digest = str(document.get("confirmationDigest") or "")
        core = {
            key: value
            for key, value in document.items()
            if key != "confirmationDigest"
        }
        if not confirmation_digest or _digest(core) != confirmation_digest:
            raise TransportDatumPortAcquisitionError(
                f"confirmed port digest mismatch: {path}"
            )
        module_definition_id = str(document.get("moduleDefinitionId") or "")
        module_token = str(document.get("moduleToken") or "")
        release_id = str(document.get("sourceReleaseId") or "")
        scan_relative = str(document.get("scanCatalogPath") or "")
        if not all((module_definition_id, module_token, release_id, scan_relative)):
            raise TransportDatumPortAcquisitionError(
                f"confirmed port identity is incomplete: {path}"
            )
        scan_path = (workspace / scan_relative).resolve()
        if not scan_path.is_relative_to(workspace):
            raise TransportDatumPortAcquisitionError(
                f"confirmed scan catalog escapes workspace: {path}"
            )
        scan = _read(scan_path)
        if _digest(scan) != document.get("scanCatalogDigest"):
            raise TransportDatumPortAcquisitionError(
                f"confirmed scan catalog digest mismatch: {path}"
            )
        index = _row_index(scan)
        port = document.get("port") or {}
        bindings = port.get("endpointBindings") or []
        if [row.get("role") for row in bindings] != [
            "support_datum",
            "longitudinal_datum",
            "lateral_datum",
        ]:
            raise TransportDatumPortAcquisitionError(
                f"confirmed port bindings are incomplete: {path}"
            )
        endpoint_ids = tuple(str(row.get("endpointId") or "") for row in bindings)
        if len(set(endpoint_ids)) != 3 or any(not value for value in endpoint_ids):
            raise TransportDatumPortAcquisitionError(
                f"confirmed port endpoint ids are invalid: {path}"
            )
        normals = []
        for endpoint_id in endpoint_ids:
            row = index.get(endpoint_id)
            if row is None or not _is_plane(row) or not _persistent_reference(row):
                raise TransportDatumPortAcquisitionError(
                    f"confirmed endpoint is absent or unstable: {endpoint_id}"
                )
            normals.append(_unit(_endpoint(row).get("FaceNormalLocal"), endpoint_id))
        if max(
            abs(_dot(normals[0], normals[1])),
            abs(_dot(normals[0], normals[2])),
            abs(_dot(normals[1], normals[2])),
        ) > 1e-5:
            raise TransportDatumPortAcquisitionError(
                f"confirmed port planes are not mutually orthogonal: {path}"
            )
        if module_definition_id in result:
            raise TransportDatumPortAcquisitionError(
                f"duplicate confirmed transport port: {module_definition_id}"
            )
        result[module_definition_id] = {
            "role": "Transport",
            "token": module_token,
            "release": release_id,
            "catalog": scan_relative.replace("\\", "/"),
            "endpoints": endpoint_ids,
            "confirmationDigest": confirmation_digest,
            "confirmationSource": document.get("confirmationSource"),
        }
    return result
