"""Review and compile support-plane/two-axis slots on a foreign base.

The transport and calibration module families already expose released moving
ports whose two locating-axis spacings are 58 mm and 50 mm respectively.  A
foreign base may contain cylindrical faces with the same spacing, but spacing
alone is not mechanical compatibility.  This module inventories exact stable
endpoint pairs.  It can rank them against the released native
primary/secondary-axis station of each exact module, but that projection is
review-only.  An explicit engineering selection is still required before an
unpublished non-prototype CAD candidate can be compiled.

No candidate is auto-selected.  Hole purpose, diameter/fastener fit and the
installation side remain explicit engineering-review boundaries.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .direct_interface_validation import compile_direct_interface_validation_package
from .hybrid_plane_axis_slot_selection import build_f000_hybrid_axis_slot_catalog
from .mechanical_interface_contracts import (
    CALIBRATION_CATALOG_SCHEMA,
    TRANSPORT_CATALOG_SCHEMA,
    MechanicalInterfaceContractError,
    build_plane_two_hole_contract,
    instantiate_connection_template,
    match_interface_contracts,
    validate_contract_catalog,
)
from .parameterized_datum_placement import (
    _base_wrapper_source,
    load_parameterized_datum_placement_catalog,
)


CATALOG_SCHEMA = "two-axis-slot-candidate-catalog/v1"
SELECTION_SCHEMA = "two-axis-slot-selection/v1"
NATIVE_STATION_SCHEMA = "two-axis-native-station-review-evidence/v1"
BASE_DEFINITION_ID = "project05::A000"
BASE_TOKEN = "A000"
BASE_CATALOG = (
    "demo/semantic_ports/project05_p000_locator_discovery_v1/"
    "a000-p000-support-leaf-face-catalog.json"
)
BASE_SUPPORT_ENDPOINT_ID = "face:fl9c254098a000.001-1:8237e6a9e0e0e083"
BASE_RELEASE = "relation-v58-project05-g000-static-four-relation-driving-20261014"

FAMILY_SPECS = {
    "Calibration": {
        "spacingMeters": 0.05,
        "interfaceFamily": "calibration_plane_two_hole_mount/v1",
        "recipeId": "recipe/calibration-plane-two-hole-rigid-mount/v1",
        "catalog": (
            "demo/cross_project_substitution/calibration-interface-contract-v1/"
            "interface-contract-catalog.json"
        ),
        "catalogSchema": CALIBRATION_CATALOG_SCHEMA,
        "moduleCatalogs": {
            "project01::BD00": (
                "demo/semantic_ports/project01_BD00_fifth_increment_v1/"
                "face_endpoint_catalog.json"
            ),
            "project03::AH00": (
                "demo/semantic_ports/project03_AH00_fifth_increment_v1/"
                "face_endpoint_catalog.json"
            ),
        },
    },
    "Transport": {
        "spacingMeters": 0.058,
        "interfaceFamily": "transport_plane_two_hole_mount/v1",
        "recipeId": "recipe/transport-plane-two-hole-rigid-mount/v1",
        "catalog": (
            "demo/cross_project_substitution/transport-interface-contract-v1/"
            "interface-contract-catalog.json"
        ),
        "catalogSchema": TRANSPORT_CATALOG_SCHEMA,
        "moduleCatalogs": {
            "project01::SS00": (
                "demo/semantic_ports/project01_SS00_first_increment_v1/"
                "face_endpoint_catalog.json"
            ),
            "project03::AE00": (
                "demo/semantic_ports/project03_AE00_first_increment_v1/"
                "face_endpoint_catalog.json"
            ),
        },
    },
}

NATIVE_PAIR_SPECS = {
    "project01::BD00": {
        "baseDefinitionId": "project01::JJ00",
        "moduleRole": "Calibration",
        "moduleToken": "BD00",
        "baseToken": "JJ00",
        "sourceCatalogPath": FAMILY_SPECS["Calibration"]["moduleCatalogs"][
            "project01::BD00"
        ],
        "relationReleaseId": (
            "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014"
        ),
    },
    "project03::AH00": {
        "baseDefinitionId": "project03::AA00",
        "moduleRole": "Calibration",
        "moduleToken": "FL9A24D063AH00",
        "baseToken": "FL9A24D063AA00",
        "sourceCatalogPath": FAMILY_SPECS["Calibration"]["moduleCatalogs"][
            "project03::AH00"
        ],
        "relationReleaseId": (
            "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
        ),
    },
    "project01::SS00": {
        "baseDefinitionId": "project01::JJ00",
        "moduleRole": "Transport",
        "moduleToken": "SS00",
        "baseToken": "JJ00",
        "sourceCatalogPath": FAMILY_SPECS["Transport"]["moduleCatalogs"][
            "project01::SS00"
        ],
        "relationReleaseId": (
            "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014"
        ),
    },
    "project03::AE00": {
        "baseDefinitionId": "project03::AA00",
        "moduleRole": "Transport",
        "moduleToken": "FL9A24D063AE00",
        "baseToken": "FL9A24D063AA00",
        "sourceCatalogPath": FAMILY_SPECS["Transport"]["moduleCatalogs"][
            "project03::AE00"
        ],
        "relationReleaseId": (
            "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
        ),
    },
}


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
        raise MechanicalInterfaceContractError(f"{label} must be a finite vector")
    return [float(value) for value in raw]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _sub(first: list[float], second: list[float]) -> list[float]:
    return [first[index] - second[index] for index in range(3)]


def _unit(raw: Any, label: str) -> list[float]:
    value = _vector(raw, label)
    length = math.sqrt(_dot(value, value))
    if length <= 1e-12:
        raise MechanicalInterfaceContractError(f"{label} is degenerate")
    return [item / length for item in value]


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId")
    }
    if len(rows) != len(catalog.get("Endpoints") or []):
        raise MechanicalInterfaceContractError(
            "two-axis source catalog has empty or duplicate endpoint ids"
        )
    return rows


def _normalised_source(value: Any) -> str:
    return str(Path(str(value or "")).resolve()).casefold()


def _base_semantic_frame(
    workspace: Path,
    placement_catalog: dict[str, Any],
    *,
    base_definition_id: str,
    module_role: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    contracts = [
        row
        for row in placement_catalog.get("contracts") or []
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == base_definition_id
        and module_role in (row.get("acceptedModuleRoles") or [])
    ]
    audits = [
        row
        for row in placement_catalog.get("datumFrameAudit") or []
        if row.get("owner") == base_definition_id
        and row.get("side") == "base_slot"
        and row.get("acceptedRole") == module_role
    ]
    if len(contracts) != 1 or len(audits) != 1 or not audits[0].get("source"):
        raise MechanicalInterfaceContractError(
            "two-axis native station base frame does not resolve uniquely: "
            f"{base_definition_id}/{module_role}"
        )
    payload = _read(workspace / str(audits[0]["source"]))
    index = _endpoint_index(payload)
    bindings = {
        str(binding.get("role") or ""): index.get(
            str(binding.get("endpointId") or "")
        )
        for binding in contracts[0].get("endpointBindings") or []
    }
    expected = {"support_datum", "longitudinal_datum", "lateral_datum"}
    if set(bindings) != expected or any(value is None for value in bindings.values()):
        raise MechanicalInterfaceContractError(
            "two-axis native station base frame has stale endpoint bindings"
        )
    return payload, bindings  # type: ignore[return-value]


def _semantic_point(
    endpoint: dict[str, Any], frame: dict[str, dict[str, Any]]
) -> list[float]:
    point = _vector(
        (endpoint.get("Endpoint") or {}).get("FaceCenterWorld"),
        "two-axis station point",
    )
    result: list[float] = []
    for role in ("longitudinal_datum", "lateral_datum"):
        plane = frame[role]
        center = _vector(
            (plane.get("Endpoint") or {}).get("FaceCenterWorld"),
            f"two-axis {role} center",
        )
        normal = _unit(
            (plane.get("Endpoint") or {}).get("FaceNormalWorld"),
            f"two-axis {role} normal",
        )
        result.append(_dot(_sub(point, center), normal))
    return result


def _released_native_relation(workspace: Path, release_id: str) -> dict[str, Any]:
    path = (
        workspace
        / "demo/global_assembly_catalog/releases"
        / release_id
        / "release-manifest.json"
    )
    payload = _read(path)
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
            f"two-axis native relation is not authoritative: {release_id}"
        )
    return {
        "releaseId": release_id,
        "releaseDigest": str(payload.get("releaseDigest") or ""),
        "manifestPath": str(path.relative_to(workspace)),
    }


def _project_to_plane(
    point: list[float], origin: list[float], normal: list[float]
) -> list[float]:
    offset = _sub(point, origin)
    distance = _dot(offset, normal)
    return [point[index] - distance * normal[index] for index in range(3)]


def _axis_lines(catalog: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = _endpoint_index(catalog)
    support = index.get(BASE_SUPPORT_ENDPOINT_ID)
    if not support or (support.get("Endpoint") or {}).get("SurfaceType") != "Plane":
        raise MechanicalInterfaceContractError("A000 support endpoint is missing")
    support_endpoint = support["Endpoint"]
    normal = _unit(support_endpoint.get("FaceNormalLocal"), "A000 support normal")
    origin = _vector(support_endpoint.get("FaceCenterLocal"), "A000 support origin")
    grouped: dict[tuple[float, float, float], list[dict[str, Any]]] = {}
    for endpoint_id, row in index.items():
        endpoint = row.get("Endpoint") or {}
        if endpoint.get("SurfaceType") != "Cylinder":
            continue
        try:
            direction = _unit(endpoint.get("CylinderAxisLocal"), "cylinder axis")
            axis_origin = _vector(
                endpoint.get("CylinderOriginLocal"), "cylinder origin"
            )
            radius = float(endpoint.get("CylinderRadius"))
        except (MechanicalInterfaceContractError, TypeError, ValueError):
            continue
        if (
            not math.isfinite(radius)
            or radius <= 0
            or abs(_dot(direction, normal)) < 1.0 - 1e-5
        ):
            continue
        projected = _project_to_plane(axis_origin, origin, normal)
        key = tuple(round(value, 6) for value in projected)
        grouped.setdefault(key, []).append(
            {
                "endpointId": endpoint_id,
                "axisOriginLocal": axis_origin,
                "axisDirectionLocal": direction,
                "axisPointOnSupportPlaneLocal": projected,
                "cylinderRadiusMeters": radius,
            }
        )
    lines: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        rows.sort(key=lambda row: (float(row["cylinderRadiusMeters"]), row["endpointId"]))
        selected = copy.deepcopy(rows[0])
        selected["axisLineKey"] = list(key)
        selected["coaxialEndpointCount"] = len(rows)
        selected["coaxialAlternativeEndpointIds"] = sorted(
            str(row["endpointId"]) for row in rows[1:]
        )
        selected["diameterCompatibility"] = "not_evaluated"
        lines.append(selected)
    lines.sort(key=lambda row: (row["axisLineKey"], row["endpointId"]))
    return support, lines


def _pair_candidates(
    lines: list[dict[str, Any]], spacing_meters: float, *, tolerance_meters: float
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for first_index, first in enumerate(lines):
        for second in lines[first_index + 1 :]:
            delta = _sub(
                second["axisPointOnSupportPlaneLocal"],
                first["axisPointOnSupportPlaneLocal"],
            )
            distance = math.sqrt(_dot(delta, delta))
            residual = abs(distance - spacing_meters)
            if residual > tolerance_meters:
                continue
            ordered = sorted(
                (first, second),
                key=lambda row: (row["axisLineKey"], row["endpointId"]),
            )
            center = [
                (first["axisPointOnSupportPlaneLocal"][index]
                 + second["axisPointOnSupportPlaneLocal"][index])
                / 2.0
                for index in range(3)
            ]
            core = {
                "primaryAxisEndpointId": ordered[0]["endpointId"],
                "secondaryAxisEndpointId": ordered[1]["endpointId"],
                "axisEndpointIds": sorted(
                    [first["endpointId"], second["endpointId"]]
                ),
                "measuredSpacingMeters": distance,
                "requiredSpacingMeters": spacing_meters,
                "spacingResidualMeters": residual,
                "pairCenterLocal": center,
                "primaryAxisRadiusMeters": ordered[0]["cylinderRadiusMeters"],
                "secondaryAxisRadiusMeters": ordered[1]["cylinderRadiusMeters"],
                "diameterAndFastenerFit": "not_evaluated",
                "installationPurpose": "not_confirmed",
            }
            candidates.append(
                {**core, "candidatePairId": "axis-pair/" + _digest(core)[:16]}
            )
    candidates.sort(
        key=lambda row: (
            float(row["spacingResidualMeters"]),
            row["pairCenterLocal"],
            row["candidatePairId"],
        )
    )
    return candidates


def build_two_axis_slot_candidate_catalog(
    workspace: Path, *, tolerance_meters: float = 0.0002
) -> dict[str, Any]:
    """Inventory A000 axis pairs for the two released moving-port families."""

    if (
        isinstance(tolerance_meters, bool)
        or not isinstance(tolerance_meters, (int, float))
        or not math.isfinite(float(tolerance_meters))
        or float(tolerance_meters) <= 0
    ):
        raise MechanicalInterfaceContractError("pair tolerance must be positive")
    workspace = workspace.resolve()
    base_catalog = _read(workspace / BASE_CATALOG)
    support, lines = _axis_lines(base_catalog)
    families: list[dict[str, Any]] = []
    for role, spec in FAMILY_SPECS.items():
        candidates = _pair_candidates(
            lines,
            float(spec["spacingMeters"]),
            tolerance_meters=float(tolerance_meters),
        )
        if not candidates:
            raise MechanicalInterfaceContractError(
                f"A000 has no reviewable {spec['spacingMeters']} m axis pair"
            )
        families.append(
            {
                "moduleRole": role,
                "moduleDefinitionIds": sorted(spec["moduleCatalogs"]),
                "slotDefinitionId": BASE_DEFINITION_ID,
                "interfaceFamily": spec["interfaceFamily"],
                "recipeId": spec["recipeId"],
                "requiredSpacingMeters": spec["spacingMeters"],
                "candidatePairCount": len(candidates),
                "axisPairCandidates": candidates,
                "state": "explicit_axis_pair_selection_required",
                "readyForReleasedCadExecution": False,
            }
        )
    # Audit the same 58 mm transport topology on A600.  The complete A600
    # axis inventory is already normalized by the hybrid-slot catalog.  A
    # zero result is recorded as evidence about the current authoritative
    # capture, not as a universal claim that no adapter or new drilling can
    # ever make the module installable.
    hybrid = build_f000_hybrid_axis_slot_catalog(workspace)
    a600 = next(
        row
        for row in hybrid.get("baseSlots") or []
        if row.get("slotDefinitionId") == "project02::A600"
    )
    a600_lines = [
        {
            "endpointId": row["endpointId"],
            "axisPointOnSupportPlaneLocal": [
                float(row["longitudinalMeters"]),
                float(row["lateralMeters"]),
                0.0,
            ],
            "axisLineKey": [
                float(row["longitudinalMeters"]),
                float(row["lateralMeters"]),
                0.0,
            ],
            "cylinderRadiusMeters": float(row["cylinderRadiusMeters"]),
        }
        for row in a600.get("axisCandidates") or []
    ]
    a600_transport_pairs = _pair_candidates(
        a600_lines, 0.058, tolerance_meters=float(tolerance_meters)
    )
    verified_incompatibilities = []
    if not a600_transport_pairs:
        verified_incompatibilities = [
            {
                "moduleDefinitionId": module_definition_id,
                "slotDefinitionId": "project02::A600",
                "moduleRole": "Transport",
                "requiredSpacingMeters": 0.058,
                "candidateAxisLineCount": len(a600_lines),
                "matchingAxisPairCount": 0,
                "state": "axis_pair_not_found_in_authoritative_catalog",
                "nextAction": (
                    "review_an_alternate_mounting_strategy_or_capture_new_geometry"
                ),
            }
            for module_definition_id in FAMILY_SPECS["Transport"][
                "moduleCatalogs"
            ]
        ]
    core = {
        "schemaVersion": CATALOG_SCHEMA,
        "slotDefinitionId": BASE_DEFINITION_ID,
        "baseToken": BASE_TOKEN,
        "sourceCatalogPath": BASE_CATALOG,
        "supportEndpointId": BASE_SUPPORT_ENDPOINT_ID,
        "supportEndpointRecoveryConfidence": support.get("RecoveryConfidence"),
        "candidateAxisLineCount": len(lines),
        "spacingToleranceMeters": float(tolerance_meters),
        "families": families,
        "verifiedIncompatibilities": verified_incompatibilities,
        "summary": {
            "familyCount": len(families),
            "modulePairDecisionCount": sum(
                len(row["moduleDefinitionIds"]) for row in families
            ),
            "candidatePairCountBySpacing": {
                str(row["requiredSpacingMeters"]): row["candidatePairCount"]
                for row in families
            },
            "verifiedIncompatibilityCount": len(verified_incompatibilities),
        },
        "claimBoundary": (
            "Candidate pairs prove stable endpoint recovery and center spacing only. "
            "No pair is selected automatically; hole purpose, installation side, "
            "diameter/fastener fit and exact-pair CAD release remain required."
        ),
    }
    return {**core, "catalogDigest": _digest(core)}


def build_two_axis_native_station_references(workspace: Path) -> dict[str, Any]:
    """Measure native primary/secondary locating axes in semantic base frames.

    These measurements are review-only.  They may rank A000 candidate pairs,
    but they never authorize CAD and never supply an initial component pose.
    """

    workspace = workspace.resolve()
    placement_catalog = load_parameterized_datum_placement_catalog(workspace)
    rows: list[dict[str, Any]] = []
    for module_definition_id, spec in NATIVE_PAIR_SPECS.items():
        role = str(spec["moduleRole"])
        source_path = str(spec["sourceCatalogPath"])
        source = _read(workspace / source_path)
        frame_payload, frame = _base_semantic_frame(
            workspace,
            placement_catalog,
            base_definition_id=str(spec["baseDefinitionId"]),
            module_role=role,
        )
        if _normalised_source(source.get("SourceAssemblyPath")) != _normalised_source(
            frame_payload.get("SourceAssemblyPath")
        ):
            raise MechanicalInterfaceContractError(
                "two-axis native pair and semantic frame do not share one source assembly: "
                f"{module_definition_id}"
            )
        family_spec = FAMILY_SPECS[role]
        contract_catalog = _read(workspace / str(family_spec["catalog"]))
        moving = [
            row
            for row in contract_catalog.get("contracts") or []
            if row.get("side") == "moving_module"
            and row.get("moduleDefinitionId") == module_definition_id
        ]
        if len(moving) != 1:
            raise MechanicalInterfaceContractError(
                f"two-axis native moving contract is not unique: {module_definition_id}"
            )
        bindings = {
            str(row.get("role") or ""): str(row.get("endpointId") or "")
            for row in moving[0].get("endpointBindings") or []
        }
        source_rows = source.get("Endpoints") or []
        source_index = _endpoint_index(source)
        source_graph_path = workspace / Path(source_path).parent / "assembly_plan_effective.json"
        source_graph = _read(source_graph_path)
        points: list[list[float]] = []
        base_axis_ids: list[str] = []
        native_concentric_alignments: list[int] = []
        for binding_role in ("primary_locating_hole", "secondary_locating_hole"):
            moving_axis_id = bindings.get(binding_role)
            indexes = [
                index
                for index, row in enumerate(source_rows)
                if row.get("EndpointId") == moving_axis_id
            ]
            if len(indexes) != 1 or indexes[0] == 0:
                raise MechanicalInterfaceContractError(
                    f"two-axis native mate ordering is ambiguous: {module_definition_id}"
                )
            base_row = source_rows[indexes[0] - 1]
            base_token = str((base_row.get("Endpoint") or {}).get("ModuleToken") or "")
            if base_token.casefold() != str(spec["baseToken"]).casefold():
                raise MechanicalInterfaceContractError(
                    f"two-axis native axis is not paired with the expected base: {module_definition_id}"
                )
            base_axis_id = str(base_row.get("EndpointId") or "")
            if source_index.get(base_axis_id) is None:
                raise MechanicalInterfaceContractError(
                    f"two-axis native base axis is absent: {module_definition_id}"
                )
            base_axis_ids.append(base_axis_id)
            points.append(_semantic_point(base_row, frame))
            moving_reference = str(
                (source_rows[indexes[0]].get("Endpoint") or {}).get(
                    "SourceAssemblyPersistentReferenceBase64"
                )
                or ""
            )
            native_mates = [
                mate
                for mate in source_graph.get("Mates") or []
                if mate.get("MateTypeName") == "swMateCONCENTRIC"
                and any(
                    str(endpoint.get("SourceAssemblyPersistentReferenceBase64") or "")
                    == moving_reference
                    for endpoint in mate.get("Endpoints") or []
                )
            ]
            if len(native_mates) != 1 or native_mates[0].get("Alignment") not in {0, 1}:
                raise MechanicalInterfaceContractError(
                    "two-axis native concentric alignment is not unique: "
                    f"{module_definition_id}/{binding_role}"
                )
            native_concentric_alignments.append(int(native_mates[0]["Alignment"]))
        spacing = math.sqrt(
            sum((points[1][index] - points[0][index]) ** 2 for index in range(2))
        )
        required_spacing = float(family_spec["spacingMeters"])
        if abs(spacing - required_spacing) > 2e-4:
            raise MechanicalInterfaceContractError(
                f"two-axis native station spacing disagrees with its interface: {module_definition_id}"
            )
        core = {
            "moduleDefinitionId": module_definition_id,
            "baseDefinitionId": spec["baseDefinitionId"],
            "moduleRole": role,
            "primaryBaseAxisEndpointId": base_axis_ids[0],
            "secondaryBaseAxisEndpointId": base_axis_ids[1],
            "semanticAxisPointsMeters": {
                "primary": [round(value, 12) for value in points[0]],
                "secondary": [round(value, 12) for value in points[1]],
            },
            "baseSupportNormalWorld": [
                round(value, 12)
                for value in _unit(
                    (frame["support_datum"].get("Endpoint") or {}).get(
                        "FaceNormalWorld"
                    ),
                    f"two-axis native support normal for {module_definition_id}",
                )
            ],
            "nativeConcentricAlignments": {
                "primary": native_concentric_alignments[0],
                "secondary": native_concentric_alignments[1],
            },
            "measuredSpacingMeters": round(spacing, 12),
            "sourceCatalogPath": source_path,
            "semanticFrameCatalogPath": next(
                str(row["source"])
                for row in placement_catalog.get("datumFrameAudit") or []
                if row.get("owner") == spec["baseDefinitionId"]
                and row.get("side") == "base_slot"
                and row.get("acceptedRole") == role
            ),
            "nativeRelationRelease": _released_native_relation(
                workspace, str(spec["relationReleaseId"])
            ),
            "prototypePoseUsedForMeasurement": True,
            "prototypePoseAllowedAsCadExecutionAuthority": False,
            "reviewOnly": True,
            "targetEnvelopeVerified": False,
            "diameterAndFastenerFit": "not_evaluated",
        }
        rows.append({**core, "referenceDigest": _digest(core)})
    rows.sort(key=lambda row: row["moduleDefinitionId"])
    report = {
        "schemaVersion": NATIVE_STATION_SCHEMA,
        "status": "review_only_two_axis_native_station_evidence",
        "stations": rows,
        "summary": {"stationCount": len(rows)},
        "claimBoundary": (
            "Native primary/secondary axes rank target-base pairs for engineering review only. "
            "They do not authorize CAD, inherit a prototype top-level pose, prove hole purpose, "
            "diameter/fastener fit, target envelope or production use."
        ),
    }
    return {**report, "evidenceCatalogDigest": _digest(report)}


def rank_two_axis_candidates_from_native_station(
    workspace: Path,
    catalog: dict[str, Any],
    module_definition_id: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank A000 candidate pairs by two-point RMS in the semantic base frame."""

    if catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported two-axis candidate catalog")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MechanicalInterfaceContractError("two-axis ranking limit must be positive")
    families = [
        row
        for row in catalog.get("families") or []
        if module_definition_id in (row.get("moduleDefinitionIds") or [])
    ]
    if len(families) != 1:
        raise MechanicalInterfaceContractError(
            "two-axis ranking module does not resolve one family"
        )
    references = build_two_axis_native_station_references(workspace)
    native = [
        row
        for row in references["stations"]
        if row["moduleDefinitionId"] == module_definition_id
    ]
    if len(native) != 1:
        raise MechanicalInterfaceContractError(
            "two-axis native station does not resolve uniquely"
        )
    placement_catalog = load_parameterized_datum_placement_catalog(workspace)
    target_payload, target_frame = _base_semantic_frame(
        workspace,
        placement_catalog,
        base_definition_id=BASE_DEFINITION_ID,
        module_role=str(families[0]["moduleRole"]),
    )
    target_index = _endpoint_index(target_payload)
    reference_points = [
        native[0]["semanticAxisPointsMeters"]["primary"],
        native[0]["semanticAxisPointsMeters"]["secondary"],
    ]
    ranked: list[dict[str, Any]] = []
    for candidate in families[0].get("axisPairCandidates") or []:
        candidate_points = [
            _semantic_point(target_index[candidate[endpoint_role]], target_frame)
            for endpoint_role in (
                "primaryAxisEndpointId",
                "secondaryAxisEndpointId",
            )
        ]

        def rms(order: tuple[int, int]) -> float:
            return math.sqrt(
                sum(
                    sum(
                        (
                            float(reference_points[index][axis])
                            - float(candidate_points[order[index]][axis])
                        )
                        ** 2
                        for axis in range(2)
                    )
                    for index in range(2)
                )
                / 2.0
            )

        direct = rms((0, 1))
        reversed_value = rms((1, 0))
        assignment = "direct" if direct <= reversed_value else "reversed"
        ranked.append(
            {
                **copy.deepcopy(candidate),
                "semanticAxisPointsMeters": {
                    "primary": candidate_points[0],
                    "secondary": candidate_points[1],
                },
                "axisAssignment": assignment,
                "twoPointRmsFromNativeStationMeters": min(direct, reversed_value),
                "nativeStationReferenceDigest": native[0]["referenceDigest"],
            }
        )
    ranked.sort(
        key=lambda row: (
            float(row["twoPointRmsFromNativeStationMeters"]),
            str(row["candidatePairId"]),
        )
    )
    return ranked[:limit]


def _family_and_candidate(
    catalog: dict[str, Any],
    module_definition_id: str,
    candidate_pair_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    families = [
        row
        for row in catalog.get("families") or []
        if module_definition_id in (row.get("moduleDefinitionIds") or [])
    ]
    if len(families) != 1:
        raise MechanicalInterfaceContractError(
            "module does not resolve one two-axis interface family"
        )
    matches = [
        row
        for row in families[0].get("axisPairCandidates") or []
        if row.get("candidatePairId") == candidate_pair_id
    ]
    if len(matches) != 1:
        raise MechanicalInterfaceContractError(
            "selected two-axis pair is not a candidate for the module family"
        )
    return families[0], matches[0]


def compile_two_axis_slot_selection(
    workspace: Path,
    *,
    module_definition_id: str,
    selected_candidate_pair_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Compile a confirmed A000 axis pair into an unpublished contract pair."""

    if evidence.get("confirmed") is not True or not str(
        evidence.get("source") or ""
    ).strip():
        raise MechanicalInterfaceContractError(
            "two-axis selection requires confirmed evidence with a source"
        )
    if str(evidence.get("selectedCandidatePairId") or "") != selected_candidate_pair_id:
        raise MechanicalInterfaceContractError(
            "selection evidence does not identify the requested axis pair"
        )
    workspace = workspace.resolve()
    catalog = build_two_axis_slot_candidate_catalog(workspace)
    family, candidate = _family_and_candidate(
        catalog, module_definition_id, selected_candidate_pair_id
    )
    role = str(family["moduleRole"])
    spec = FAMILY_SPECS[role]
    source_contract_catalog = _read(workspace / str(spec["catalog"]))
    moving = [
        copy.deepcopy(row)
        for row in source_contract_catalog.get("contracts") or []
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == module_definition_id
    ]
    if len(moving) != 1:
        raise MechanicalInterfaceContractError(
            "moving module does not resolve one released two-axis contract"
        )
    base_release = _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / BASE_RELEASE
        / "release-manifest.json"
    )
    references = build_two_axis_native_station_references(workspace)
    native_rows = [
        row
        for row in references["stations"]
        if row["moduleDefinitionId"] == module_definition_id
    ]
    if len(native_rows) != 1:
        raise MechanicalInterfaceContractError(
            "two-axis native orientation reference is not unique"
        )
    ranked = rank_two_axis_candidates_from_native_station(
        workspace,
        catalog,
        module_definition_id,
        limit=len(family.get("axisPairCandidates") or []),
    )
    ranked_selected = [
        row
        for row in ranked
        if row.get("candidatePairId") == selected_candidate_pair_id
    ]
    if len(ranked_selected) != 1:
        raise MechanicalInterfaceContractError(
            "two-axis selected pair has no orientation assignment"
        )
    assignment = str(ranked_selected[0]["axisAssignment"])
    target_axis_ids = [
        str(candidate["primaryAxisEndpointId"]),
        str(candidate["secondaryAxisEndpointId"]),
    ]
    if assignment == "reversed":
        target_axis_ids.reverse()
    elif assignment != "direct":
        raise MechanicalInterfaceContractError(
            "unsupported two-axis primary/secondary assignment"
        )
    target_catalog = _read(workspace / BASE_CATALOG)
    target_index = _endpoint_index(target_catalog)
    native_support_normal = [
        float(value) for value in native_rows[0]["baseSupportNormalWorld"]
    ]
    target_support_normal = _unit(
        (target_index[BASE_SUPPORT_ENDPOINT_ID].get("Endpoint") or {}).get(
            "FaceNormalWorld"
        ),
        "selected two-axis target support normal",
    )
    support_normal_dot = _dot(native_support_normal, target_support_normal)
    if abs(support_normal_dot) < 0.999:
        raise MechanicalInterfaceContractError(
            "native and selected two-axis support normals are not parallel"
        )
    native_concentric_alignments = [
        int(native_rows[0]["nativeConcentricAlignments"]["primary"]),
        int(native_rows[0]["nativeConcentricAlignments"]["secondary"]),
    ]
    # Preserve the source interface's axis directions when the support frame
    # is unchanged.  Reversing the target support normal flips the installed
    # module frame, so each source concentric alignment must also flip.
    concentric_alignments = (
        native_concentric_alignments
        if support_normal_dot > 0
        else [1 - value for value in native_concentric_alignments]
    )
    slot_port = {
        "portId": f"A000.reviewed_{role.lower()}_two_axis_slot.v1",
        "moduleToken": BASE_TOKEN,
        "endpointBindings": [
            {"role": "support_plane", "endpointId": BASE_SUPPORT_ENDPOINT_ID},
            {
                "role": "primary_locating_hole",
                "endpointId": target_axis_ids[0],
            },
            {
                "role": "secondary_locating_hole",
                "endpointId": target_axis_ids[1],
            },
        ],
    }
    slot = build_plane_two_hole_contract(
        port=slot_port,
        summary={
            "projectId": "project05",
            "expectedResidualDof": 0,
            "drivingMateCount": 3,
            "secondaryAxis": {
                "primaryIndependenceMeters": family["requiredSpacingMeters"],
                "axisParallelScore": 1.0,
                "axisRelationToPrimary": 1.0,
            },
        },
        release_manifest=base_release,
        side="base_slot",
        module_role="Base",
        module_definition_id=BASE_DEFINITION_ID,
        accepted_module_roles=[role],
        interface_family=str(family["interfaceFamily"]),
        recipe_id=str(family["recipeId"]),
        locating_axis_spacing_meters=float(family["requiredSpacingMeters"]),
        role_aliases={},
        axis_parallel_score=1.0,
        axis_relation_to_primary=1.0,
    )
    for contract in (moving[0], slot):
        contract.setdefault("mechanicalBoundary", {}).update(
            {
                "requiresExplicitPairRelease": True,
                "candidateAxisPairId": selected_candidate_pair_id,
                "actualFasteningMethod": "not_verified",
                "diameterAndFastenerFit": "not_evaluated",
                "productionReady": False,
            }
        )
    match = match_interface_contracts(moving[0], slot)
    if match.get("compatible") is not True:
        raise MechanicalInterfaceContractError(
            "confirmed two-axis pair did not produce a compatible interface contract"
        )
    template = instantiate_connection_template(match, moving[0], slot)
    concentric_steps = [
        row
        for row in template["mateSteps"]
        if row.get("mateTypeName") == "swMateCONCENTRIC"
    ]
    if len(concentric_steps) != 2:
        raise MechanicalInterfaceContractError(
            "two-axis template does not contain exactly two concentric mates"
        )
    for step, alignment in zip(concentric_steps, concentric_alignments):
        step["alignment"] = alignment
        step["alignmentName"] = (
            "swMateAlignALIGNED"
            if alignment == 0
            else "swMateAlignANTI_ALIGNED"
        )
    template.pop("templateId", None)
    template["templateId"] = "instantiated-template/" + _digest(template)[:16]
    orientation_evidence = {
        "axisAssignment": assignment,
        "selectedTargetAxisEndpointIds": {
            "primary": target_axis_ids[0],
            "secondary": target_axis_ids[1],
        },
        "nativeBaseSupportNormalWorld": [
            round(value, 12) for value in native_support_normal
        ],
        "selectedTargetSupportNormalWorld": [
            round(value, 12) for value in target_support_normal
        ],
        "supportNormalDotProduct": round(support_normal_dot, 12),
        "concentricAlignments": {
            "primary": concentric_alignments[0],
            "secondary": concentric_alignments[1],
        },
        "nativeConcentricAlignments": {
            "primary": native_concentric_alignments[0],
            "secondary": native_concentric_alignments[1],
        },
        "prototypePoseUsedForDirectionSignReview": True,
        "prototypePoseAllowedAsCadExecutionAuthority": False,
    }
    core = {
        "schemaVersion": SELECTION_SCHEMA,
        "status": "ready_for_nonprototype_cad_validation",
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": BASE_DEFINITION_ID,
        "moduleRole": role,
        "selectedCandidatePairId": selected_candidate_pair_id,
        "selectedCandidate": copy.deepcopy(candidate),
        "selectionEvidence": copy.deepcopy(evidence),
        "moduleEndpointCatalogPath": spec["moduleCatalogs"][module_definition_id],
        "slotEndpointCatalogPath": BASE_CATALOG,
        "moduleContract": moving[0],
        "slotContract": slot,
        "match": match,
        "instantiatedTemplate": template,
        "axisOrientationEvidence": orientation_evidence,
        "readyForReleasedCadExecution": False,
        "validationRequiredBeforeRelease": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "claimBoundary": (
            "The confirmed pair is an exact CAD-validation candidate only. "
            "It is not normal execution authority until non-prototype CAD, save/reopen "
            "and an immutable exact-pair release succeed."
        ),
    }
    return {**core, "selectionDigest": _digest(core)}


def compile_two_axis_slot_validation_package(
    workspace: Path,
    *,
    module_definition_id: str,
    selected_candidate_pair_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Compile a confirmed pair into the common direct-interface CAD package."""

    workspace = workspace.resolve()
    selection = compile_two_axis_slot_selection(
        workspace,
        module_definition_id=module_definition_id,
        selected_candidate_pair_id=selected_candidate_pair_id,
        evidence=evidence,
    )
    spec = FAMILY_SPECS[str(selection["moduleRole"])]
    module_catalog = _read(workspace / str(selection["moduleEndpointCatalogPath"]))
    slot_catalog = _read(workspace / BASE_CATALOG)
    moving_endpoint_id = str(
        selection["moduleContract"]["endpointBindings"][0]["endpointId"]
    )
    moving_row = _endpoint_index(module_catalog).get(moving_endpoint_id)
    slot_row = _endpoint_index(slot_catalog).get(BASE_SUPPORT_ENDPOINT_ID)
    if not moving_row or not slot_row:
        raise MechanicalInterfaceContractError("source module records cannot be recovered")
    moving_endpoint = moving_row.get("Endpoint") or {}
    slot_endpoint = slot_row.get("Endpoint") or {}
    module_source = Path(str(moving_row.get("ModulePath") or ""))
    slot_source = Path(str(slot_row.get("ModulePath") or ""))
    _, wrapper = _base_wrapper_source(workspace, BASE_TOKEN)
    contract_catalog_core = {
        "schemaVersion": spec["catalogSchema"],
        "role": selection["moduleRole"],
        "contracts": [
            selection["moduleContract"],
            selection["slotContract"],
        ],
        "releasedPairEvidence": [],
        "compatibilityMatrix": [selection["match"]],
        "instantiatedTemplates": [selection["instantiatedTemplate"]],
        "summary": {
            "modulePortCount": 1,
            "baseSlotCount": 1,
            "compatiblePairCount": 1,
            "incompatiblePairCount": 0,
            "releasedPairCount": 0,
            "genericRecipeCount": 1,
            "projectIdentityUsedForCompatibility": False,
            "crossProjectPairReleaseCount": 0,
        },
        "claimBoundary": selection["claimBoundary"],
    }
    contract_catalog = {
        **contract_catalog_core,
        "catalogDigest": _digest(contract_catalog_core),
    }
    validate_contract_catalog(contract_catalog)
    package = compile_direct_interface_validation_package(
        contract_catalog=contract_catalog,
        module_definition_id=module_definition_id,
        slot_definition_id=BASE_DEFINITION_ID,
        module_face_catalog=module_catalog,
        slot_face_catalog=slot_catalog,
        module_source_path=module_source,
        slot_source_path=slot_source,
        base_wrapper_path=wrapper,
        module_hierarchy_path=str(
            moving_endpoint.get("ModuleHierarchyPath")
            or moving_endpoint.get("ModuleToken")
        ),
        slot_hierarchy_path=str(
            slot_endpoint.get("ModuleHierarchyPath")
            or slot_endpoint.get("ModuleToken")
        ),
    )
    package["twoAxisSelectionDigest"] = selection["selectionDigest"]
    package["selectedCandidatePairId"] = selected_candidate_pair_id
    package["moduleEndpointCatalogPath"] = selection[
        "moduleEndpointCatalogPath"
    ]
    package["slotEndpointCatalogPath"] = selection["slotEndpointCatalogPath"]
    package["physicalFasteningVerified"] = False
    package["productionReady"] = False
    package["packageDigest"] = _digest(
        {key: value for key, value in package.items() if key != "packageDigest"}
    )
    return package
