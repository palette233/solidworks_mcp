"""Extract review-only role stations from released native prototype relations.

The parameterized datum fallback needs three distances in a target base datum
frame.  Several bases already contain a native module of the requested role,
but the corresponding station was intentionally not copied into the execution
catalog because doing so would turn a prototype pose into silent authority.

This module keeps that boundary explicit.  It measures the native module's
registered datum planes against the registered base datum planes in their
shared source-assembly coordinate system and emits *recommendation evidence*.
The result is never written back to an interface contract and cannot authorize
CAD execution.  A human confirmation and an exact non-prototype CAD release
remain mandatory.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import load_parameterized_datum_placement_catalog


SCHEMA = "native-role-station-review-evidence/v1"


# These are known native module/base relations backed by an immutable global
# relation release.  The list is deliberately small and explicit: merely being
# in the same project is not sufficient evidence that two objects form one
# native installation relation.
NATIVE_RELATIONS: tuple[dict[str, Any], ...] = (
    {
        "moduleDefinitionId": "project01::SM00",
        "baseDefinitionId": "project01::JJ00",
        "moduleRole": "Scanner",
        "relationReleaseId": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
    },
    {
        "moduleDefinitionId": "project02::A180",
        "baseDefinitionId": "project02::A600",
        "moduleRole": "Scanner",
        "relationReleaseId": "relation-v30-project02-a800-a180-portable-driving-20261011",
    },
    {
        "moduleDefinitionId": "project03::AI00",
        "baseDefinitionId": "project03::AA00",
        "moduleRole": "Scanner",
        "relationReleaseId": "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
    },
    {
        "moduleDefinitionId": "project01::GN00",
        "baseDefinitionId": "project01::JJ00",
        "moduleRole": "CleaningWeighing",
        "relationReleaseId": "relation-v65-project01-gn00-base-only-two-hole-driving-20261022",
    },
    {
        "moduleDefinitionId": "project03::AG00",
        "baseDefinitionId": "project03::AA00",
        "moduleRole": "CleaningWeighing",
        "relationReleaseId": "relation-v54-project03-ag00-three-datum-driving-20261014",
    },
    {
        "moduleDefinitionId": "project05::N000",
        "baseDefinitionId": "project05::A000",
        "moduleRole": "CleaningWeighing",
        "relationReleaseId": "relation-v27-project05-seven-addon-portable-driving-20261011",
    },
    {
        "moduleDefinitionId": "project01::SS00",
        "baseDefinitionId": "project01::JJ00",
        "moduleRole": "Transport",
        "relationReleaseId": "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014",
    },
    {
        "moduleDefinitionId": "project02::A800",
        "baseDefinitionId": "project02::A600",
        "moduleRole": "Transport",
        "relationReleaseId": "relation-v30-project02-a800-a180-portable-driving-20261011",
    },
    {
        "moduleDefinitionId": "project03::AE00",
        "baseDefinitionId": "project03::AA00",
        "moduleRole": "Transport",
        "relationReleaseId": "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
    },
    {
        "moduleDefinitionId": "project05::D000",
        "baseDefinitionId": "project05::A000",
        "moduleRole": "Transport",
        "relationReleaseId": "relation-v60-project05-d000-deterministic-driving-20261014",
    },
    {
        "moduleDefinitionId": "project02::A500",
        "baseDefinitionId": "project02::A600",
        "moduleRole": "Calibration",
        "relationReleaseId": "relation-v31-project02-a800-a180-a500-portable-driving-20261011",
    },
    {
        "moduleDefinitionId": "project02::A300",
        "baseDefinitionId": "project02::A600",
        "moduleRole": "WasteCup",
        "relationReleaseId": "relation-v34-project02-six-addon-portable-driving-20261011",
    },
    {
        "moduleDefinitionId": "project05::P000",
        "baseDefinitionId": "project05::A000",
        "moduleRole": "WasteCup",
        "relationReleaseId": "relation-v27-project05-seven-addon-portable-driving-20261011",
        # The portable P000 three-plane endpoint catalog deliberately has no
        # SourceAssemblyPath because it is reused by several target bases.
        # Two of its three faces are nevertheless original Project05 mate
        # faces whose persistent references and world geometry are preserved
        # verbatim.  The explicit bridge below validates those witnesses
        # against the original Project05 graph before the third, leaf-scanned
        # datum is allowed to share that coordinate system.  This is review
        # evidence only; it never authorizes reuse of the prototype pose.
        "moduleCoordinateBridge": {
            "nativeGraphPath": "demo/layout_previews/project05_module_mate_graph_v2_axes.json",
            "moduleToken": "P000",
            "moduleHierarchyPath": "FL9C254098P000.001-2",
            "requiredMatchedRoles": ["support_datum", "lateral_datum"],
        },
    },
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalised_source(value: Any) -> str:
    return str(Path(str(value or "")).resolve()).casefold()


def _contract(
    catalog: dict[str, Any],
    *,
    definition_id: str,
    side: str,
    module_role: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == side
        and row.get("moduleDefinitionId") == definition_id
        and (
            row.get("moduleRole") == module_role
            if side == "moving_module"
            else module_role in (row.get("acceptedModuleRoles") or [])
        )
    ]
    if len(rows) != 1:
        raise MechanicalInterfaceContractError(
            "native station contract does not resolve uniquely: "
            f"{definition_id}/{side}/{module_role}"
        )
    return rows[0]


def _catalog_source(
    catalog: dict[str, Any], contract: dict[str, Any], *, module_role: str
) -> str:
    side = str(contract.get("side") or "")
    owner = str(contract.get("moduleDefinitionId") or "")
    rows = [
        row
        for row in catalog.get("datumFrameAudit") or []
        if row.get("owner") == owner
        and row.get("side") == side
        and (
            side == "moving_module" or row.get("acceptedRole") == module_role
        )
    ]
    if len(rows) != 1 or not rows[0].get("source"):
        raise MechanicalInterfaceContractError(
            f"native station endpoint source does not resolve uniquely: {owner}/{module_role}"
        )
    return str(rows[0]["source"])


def _endpoint_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("EndpointId") or ""): row
        for row in payload.get("Endpoints") or payload.get("endpoints") or []
        if row.get("EndpointId")
    }


def _bound_endpoints(
    payload: dict[str, Any], contract: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    index = _endpoint_index(payload)
    result: dict[str, dict[str, Any]] = {}
    for binding in contract.get("endpointBindings") or []:
        role = str(binding.get("role") or "")
        endpoint_id = str(binding.get("endpointId") or "")
        endpoint = index.get(endpoint_id)
        if not role or endpoint is None:
            raise MechanicalInterfaceContractError(
                f"native station endpoint binding is stale: {endpoint_id}"
            )
        result[role] = endpoint
    expected = {"support_datum", "longitudinal_datum", "lateral_datum"}
    if set(result) != expected:
        raise MechanicalInterfaceContractError(
            "native station evidence requires a complete three-plane datum frame"
        )
    return result


def _coordinate_bridge_to_native_source(
    workspace: Path,
    *,
    module_payload: dict[str, Any],
    module_endpoints: dict[str, dict[str, Any]],
    bridge: dict[str, Any],
    expected_base_source_assembly: Any,
) -> dict[str, Any]:
    """Validate that a portable endpoint catalog still uses native coordinates.

    A portable catalog may omit ``SourceAssemblyPath``.  It may be treated as
    native-station evidence only when stable persistent references prove that
    its recorded world points and normals are exactly the ones in an explicit
    original mate graph.  Derived faces are accepted only from the same leaf
    as those matched witnesses.  No transform from the original graph is
    copied into a CAD packet.
    """

    graph_path_value = str(bridge.get("nativeGraphPath") or "")
    module_token = str(bridge.get("moduleToken") or "")
    module_hierarchy_path = str(bridge.get("moduleHierarchyPath") or "")
    required_roles = {
        str(value) for value in bridge.get("requiredMatchedRoles") or []
    }
    if not graph_path_value or not module_token or not required_roles:
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge is incomplete"
        )
    graph_path = workspace / graph_path_value
    graph = _read(graph_path)
    portable_source = module_payload.get("SourceAssemblyPath")
    if portable_source not in (None, ""):
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge is reserved for portable catalogs without source authority"
        )
    graph_source = graph.get("SourceAssemblyPath")
    if _normalised_source(graph_source) != _normalised_source(
        expected_base_source_assembly
    ):
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge graph does not share the base source assembly"
        )
    modules = [
        row
        for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper() == module_token.upper()
        and (
            not module_hierarchy_path
            or str(row.get("HierarchyPath") or "") == module_hierarchy_path
        )
    ]
    if len(modules) != 1 or len(modules[0].get("SourceTransform") or []) != 16:
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge module transform does not resolve uniquely"
        )

    graph_endpoints: dict[str, list[dict[str, Any]]] = {}
    for mate in graph.get("Mates") or []:
        for endpoint in mate.get("Endpoints") or []:
            if str(endpoint.get("ModuleToken") or "").upper() != module_token.upper():
                continue
            if module_hierarchy_path and str(
                endpoint.get("ModuleHierarchyPath") or ""
            ) != module_hierarchy_path:
                continue
            reference = str(
                endpoint.get("SourceAssemblyPersistentReferenceBase64") or ""
            )
            if reference:
                graph_endpoints.setdefault(reference, []).append(endpoint)

    matched_roles: list[str] = []
    matched_leaves: set[str] = set()
    derived_roles: list[str] = []
    tolerance = 1e-9
    for role, wrapper in module_endpoints.items():
        endpoint = wrapper.get("Endpoint") or {}
        reference = str(
            endpoint.get("SourceAssemblyPersistentReferenceBase64") or ""
        )
        matches = graph_endpoints.get(reference, [])
        if matches:
            candidate = matches[0]
            for field in ("FaceCenterWorld", "FaceNormalWorld"):
                first = _vector({"Endpoint": endpoint}, field)
                second = _vector({"Endpoint": candidate}, field)
                if max(abs(a - b) for a, b in zip(first, second, strict=True)) > tolerance:
                    raise MechanicalInterfaceContractError(
                        "native station coordinate bridge geometry differs from original graph: "
                        f"{role}/{field}"
                    )
            matched_roles.append(role)
            matched_leaves.add(str(endpoint.get("RelativeLeafHierarchyPath") or ""))
        else:
            derived_roles.append(role)

    if not required_roles.issubset(matched_roles):
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge lacks required persistent witnesses: "
            + ", ".join(sorted(required_roles - set(matched_roles)))
        )
    if len(matched_leaves) != 1 or not next(iter(matched_leaves)):
        raise MechanicalInterfaceContractError(
            "native station coordinate bridge witnesses do not share one leaf"
        )
    witness_leaf = next(iter(matched_leaves))
    if any(
        str((module_endpoints[role].get("Endpoint") or {}).get(
            "RelativeLeafHierarchyPath"
        ) or "")
        != witness_leaf
        for role in derived_roles
    ):
        raise MechanicalInterfaceContractError(
            "native station derived datum is not on the persistently witnessed leaf"
        )

    return {
        "nativeGraphPath": graph_path_value,
        "nativeGraphDigest": _digest(graph),
        "nativeModuleToken": module_token,
        "nativeModuleHierarchyPath": str(modules[0].get("HierarchyPath") or ""),
        "matchedPersistentRoles": sorted(matched_roles),
        "derivedSameLeafRoles": sorted(derived_roles),
        "witnessLeafHierarchyPath": witness_leaf,
        "sourceAssemblyPath": str(graph_source or ""),
        "portableCatalogSourceAssemblyPath": portable_source,
        "worldGeometryToleranceMeters": tolerance,
        "prototypeTransformUsedForCadExecution": False,
        "reviewOnly": True,
    }


def _vector(endpoint: dict[str, Any], field: str) -> list[float]:
    values = (endpoint.get("Endpoint") or {}).get(field) or []
    if len(values) != 3 or not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        for value in values
    ):
        raise MechanicalInterfaceContractError(
            f"native station endpoint has no finite {field}"
        )
    return [float(value) for value in values]


def _released_relation(workspace: Path, release_id: str) -> dict[str, Any]:
    manifest_path = (
        workspace
        / "demo/global_assembly_catalog/releases"
        / release_id
        / "release-manifest.json"
    )
    payload = _read(manifest_path)
    if (
        payload.get("schemaVersion") != "global-relation-catalog-release/v1"
        or payload.get("status") != "released_for_demo_relation_execution"
        or payload.get("releaseId") != release_id
        or not any(
            row.get("passed") is True
            and row.get("drivingInitialPoseIndependent") is True
            for row in payload.get("validationEvidence") or []
        )
    ):
        raise MechanicalInterfaceContractError(
            f"native station relation release is not authoritative: {release_id}"
        )
    return {
        "releaseId": release_id,
        "releaseDigest": str(payload.get("releaseDigest") or ""),
        "manifestPath": str(manifest_path.relative_to(workspace)),
    }


def _plane_distance(
    module_endpoint: dict[str, Any], base_endpoint: dict[str, Any]
) -> tuple[float, float]:
    module_center = _vector(module_endpoint, "FaceCenterWorld")
    base_center = _vector(base_endpoint, "FaceCenterWorld")
    base_normal = _vector(base_endpoint, "FaceNormalWorld")
    module_normal = _vector(module_endpoint, "FaceNormalWorld")
    base_length = math.sqrt(sum(value * value for value in base_normal))
    module_length = math.sqrt(sum(value * value for value in module_normal))
    if min(base_length, module_length) <= 1e-9:
        raise MechanicalInterfaceContractError("native station datum normal is degenerate")
    base_unit = [value / base_length for value in base_normal]
    module_unit = [value / module_length for value in module_normal]
    parallel_score = abs(sum(a * b for a, b in zip(base_unit, module_unit)))
    if parallel_score < 1.0 - 1e-5:
        raise MechanicalInterfaceContractError(
            "native station module/base datum planes are not parallel"
        )
    signed = sum(
        (module_center[index] - base_center[index]) * base_unit[index]
        for index in range(3)
    )
    value = abs(signed)
    if value < 1e-9:
        value = 0.0
    return round(value, 12), parallel_score


def build_native_role_station_evidence(
    workspace: Path, *, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return prototype-derived station recommendations without execution authority."""

    workspace = workspace.resolve()
    catalog = copy.deepcopy(catalog) if catalog is not None else load_parameterized_datum_placement_catalog(workspace)
    rows: list[dict[str, Any]] = []
    for spec in NATIVE_RELATIONS:
        module_definition_id = spec["moduleDefinitionId"]
        base_definition_id = spec["baseDefinitionId"]
        module_role = spec["moduleRole"]
        module_contract = _contract(
            catalog,
            definition_id=module_definition_id,
            side="moving_module",
            module_role=module_role,
        )
        base_contract = _contract(
            catalog,
            definition_id=base_definition_id,
            side="base_slot",
            module_role=module_role,
        )
        module_source = _catalog_source(
            catalog, module_contract, module_role=module_role
        )
        base_source = _catalog_source(catalog, base_contract, module_role=module_role)
        module_payload = _read(workspace / module_source)
        base_payload = _read(workspace / base_source)
        module_source_assembly = module_payload.get("SourceAssemblyPath")
        base_source_assembly = base_payload.get("SourceAssemblyPath")
        module_endpoints = _bound_endpoints(module_payload, module_contract)
        base_endpoints = _bound_endpoints(base_payload, base_contract)
        coordinate_bridge = None
        if _normalised_source(module_source_assembly) != _normalised_source(
            base_source_assembly
        ):
            bridge_spec = spec.get("moduleCoordinateBridge")
            if not isinstance(bridge_spec, dict):
                raise MechanicalInterfaceContractError(
                    "native station endpoints do not share one source-assembly coordinate system: "
                    f"{module_definition_id}/{base_definition_id}"
                )
            coordinate_bridge = _coordinate_bridge_to_native_source(
                workspace,
                module_payload=module_payload,
                module_endpoints=module_endpoints,
                bridge=bridge_spec,
                expected_base_source_assembly=base_source_assembly,
            )
            module_source_assembly = coordinate_bridge["sourceAssemblyPath"]
        parameters: dict[str, float] = {}
        alignments: dict[str, float] = {}
        for role, parameter_name in (
            ("longitudinal_datum", "longitudinal"),
            ("lateral_datum", "lateral"),
            ("support_datum", "supportGap"),
        ):
            parameters[parameter_name], alignments[role] = _plane_distance(
                module_endpoints[role], base_endpoints[role]
            )
        existing = (
            base_contract.get("geometrySignature") or {}
        ).get("positionParametersByModuleDefinitionId", {}).get(module_definition_id)
        if existing is not None:
            expected = {key: round(float(value), 12) for key, value in existing.items()}
            if set(expected) != set(parameters) or any(
                abs(expected[key] - parameters[key]) > 1e-8 for key in expected
            ):
                raise MechanicalInterfaceContractError(
                    "native station measurement disagrees with the registered station: "
                    f"{module_definition_id}/{base_definition_id}"
                )
            # Prefer the already reviewed decimal value when the geometry
            # measurement differs only by floating-point transform noise.
            parameters = expected
        relation = _released_relation(workspace, spec["relationReleaseId"])
        row = {
            "moduleDefinitionId": module_definition_id,
            "baseDefinitionId": base_definition_id,
            "moduleRole": module_role,
            "parametersMeters": parameters,
            "moduleDatumContractId": module_contract["contractId"],
            "baseDatumContractId": base_contract["contractId"],
            "moduleEndpointCatalogPath": module_source,
            "baseEndpointCatalogPath": base_source,
            "sourceAssemblyPath": str(module_source_assembly or ""),
            "endpointParallelScores": alignments,
            "nativeRelationRelease": relation,
            "prototypePoseUsedForMeasurement": True,
            "prototypePoseAllowedAsCadExecutionAuthority": False,
            "reviewOnly": True,
            "targetEnvelopeVerified": False,
            "actualFasteningVerified": False,
            "collisionOrBrep": "not_evaluated",
        }
        if coordinate_bridge is not None:
            row["moduleCoordinateBridge"] = coordinate_bridge
        row["evidenceDigest"] = _digest(row)
        rows.append(row)
    report = {
        "schemaVersion": SCHEMA,
        "status": "review_only_native_role_station_evidence",
        "stations": rows,
        "summary": {
            "stationCount": len(rows),
            "baseCount": len({row["baseDefinitionId"] for row in rows}),
            "roleCount": len({row["moduleRole"] for row in rows}),
        },
        "claimBoundary": (
            "Coordinates are measured from a released native prototype relation only to propose "
            "a role station for review. They are not interface-contract presets, do not authorize "
            "CAD execution, and never permit the target module to inherit a prototype top-level pose."
        ),
    }
    report["evidenceCatalogDigest"] = _digest(report)
    return report


def index_native_role_stations(
    evidence: dict[str, Any],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if evidence.get("schemaVersion") != SCHEMA:
        raise MechanicalInterfaceContractError("unsupported native station evidence schema")
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in evidence.get("stations") or []:
        key = (str(row["baseDefinitionId"]), str(row["moduleRole"]))
        result.setdefault(key, []).append(copy.deepcopy(row))
    return result
