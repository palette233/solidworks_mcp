"""Discover and confirm plane/plane/axis datum slots for Project05 F000.

F000 already has a released native support + orientation + concentric-axis
installation bundle on Project05 A000.  Other bases expose many cylindrical
faces, so this module turns them into reviewable *axis-line* candidates.  It
never silently treats the nearest hole as an approved installation slot.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
    SCANNER_PLANE_AXIS_FAMILY,
    SCANNER_PLANE_AXIS_RECIPE_ID,
    SCANNER_PLANE_AXIS_ROLES,
    build_exact_three_relation_contract,
    instantiate_connection_template,
    match_interface_contracts,
)


CATALOG_SCHEMA = "hybrid-plane-axis-slot-candidate-catalog/v1"
SELECTION_SCHEMA = "hybrid-plane-axis-slot-selection/v1"
GENERIC_VARIANT = "f000_reviewed_plane_axis_datum/v1"
MODULE_DEFINITION_ID = "project05::F000"
MODULE_TOKEN = "F000"
MODULE_CATALOG = (
    "demo/semantic_ports/project05_global_installation_ports_v1/"
    "F000/face_endpoint_catalog.json"
)
MODULE_ENDPOINTS = {
    "support_plane": "face:f000:4274c58f81f1aaa0",
    "orientation_datum": "face:f000:0197dabe25218b84",
    "locating_axis": "face:f000:410cebded6126f80",
}
MODULE_RELEASE = "relation-v20-project05-d000-f000-portable-driving-20261011"

BASE_SPECS = {
    "project01::JJ00": {
        "token": "JJ00",
        "catalog": (
            "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project01_JJ00_project03_AI00/"
            "jj00-scanner-support-leaf-face-catalog.json"
        ),
        "support": "face:jj00:046bf2789cf6c785",
        "orientation": "face:jj00:692db7bed55b33c9",
        "longitudinal": "face:jj00:e44c72a6880619cd",
        "release": (
            "relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014"
        ),
    },
    "project03::AA00": {
        "token": "AA00",
        "catalog": (
            "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project03_AA00_project01_SM00/"
            "aa00-scanner-support-leaf-face-catalog.json"
        ),
        "support": "face:aa00:640ce034eb768594",
        "orientation": "face:aa00:929f91708da17e03",
        "longitudinal": "face:aa00:ae9c22cef02ef7bd",
        "release": (
            "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
        ),
    },
    "project02::A600": {
        "token": "A600",
        # The three semantic datum planes were recovered from a compact
        # Project02 service-port catalog.  Axis candidates come from the
        # independently captured full A600 leaf-face inventory.  Keeping the
        # sources separate avoids copying an arbitrary hole into the semantic
        # port merely because it happened to be present in a small source-mate
        # catalog.
        "catalog": (
            "demo/semantic_ports/project02_service_installations_v1/"
            "A300/face_endpoint_catalog.json"
        ),
        "axisCatalog": (
            "demo/cross_project_substitution/alternate-slot-discovery-v1/"
            "project02_A600_calibration_slot_acquisition/"
            "a600-native-service-leaf-face-catalog-v1.json"
        ),
        "support": "face:a600:f3e3801b99066522",
        "orientation": "face:a600:17cd6e89a8e64c1e",
        "longitudinal": "face:a600:614f7ba702b31193",
        # These three planes come from different leaves.  Their world-space
        # geometry is expressed in the same source-assembly frame, whereas
        # each leaf-local frame is different.  Axis ranking therefore uses
        # world geometry only for this review catalog; the persistent endpoint
        # references remain the CAD authority.
        "coordinateSpace": "world",
        "release": "relation-v34-project02-six-addon-portable-driving-20261011",
    },
    "project05::A000": {
        "token": "A000",
        "catalog": MODULE_CATALOG,
        "support": "face:a000:6fa65c2382da2d47",
        "orientation": "face:a000:dd9b3d0af3790a28",
        "longitudinal": None,
        "release": MODULE_RELEASE,
        "releasedAxis": "face:a000:0fe1c632c1c9959a",
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


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId")
    }


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


def _subtract(first: list[float], second: list[float]) -> list[float]:
    return [first[index] - second[index] for index in range(3)]


def _unit(raw: Any, label: str) -> list[float]:
    value = _vector(raw, label)
    length = math.sqrt(_dot(value, value))
    if length <= 1e-12:
        raise MechanicalInterfaceContractError(f"{label} is degenerate")
    return [item / length for item in value]


def _surface_type(row: dict[str, Any]) -> str:
    return str(
        (row.get("Endpoint") or {}).get("SurfaceType")
        or row.get("GeometryClass")
        or ""
    )


def _plane_frame(
    index: dict[str, dict[str, Any]],
    *,
    support_id: str,
    orientation_id: str,
    longitudinal_id: str | None,
    coordinate_space: str = "local",
) -> dict[str, Any]:
    if coordinate_space not in {"local", "world"}:
        raise MechanicalInterfaceContractError(
            "plane-axis coordinate space must be local or world"
        )
    suffix = "World" if coordinate_space == "world" else "Local"
    try:
        support = index[support_id]
        orientation = index[orientation_id]
    except KeyError as exc:
        raise MechanicalInterfaceContractError(
            "plane-axis base frame endpoint is missing"
        ) from exc
    if _surface_type(support) != "Plane" or _surface_type(orientation) != "Plane":
        raise MechanicalInterfaceContractError(
            "support and orientation endpoints must be planar"
        )
    support_normal = _unit(
        (support.get("Endpoint") or {}).get(f"FaceNormal{suffix}"),
        "support normal",
    )
    orientation_normal = _unit(
        (orientation.get("Endpoint") or {}).get(f"FaceNormal{suffix}"),
        "orientation normal",
    )
    if abs(_dot(support_normal, orientation_normal)) > 1e-5:
        raise MechanicalInterfaceContractError(
            "support and orientation planes must be orthogonal"
        )
    result: dict[str, Any] = {
        "supportEndpointId": support_id,
        "orientationEndpointId": orientation_id,
        "supportNormalLocal": support_normal,
        "orientationNormalLocal": orientation_normal,
        "coordinateSpace": coordinate_space,
    }
    if longitudinal_id:
        longitudinal = index.get(longitudinal_id)
        if not longitudinal or _surface_type(longitudinal) != "Plane":
            raise MechanicalInterfaceContractError(
                "longitudinal semantic datum must be planar"
            )
        longitudinal_normal = _unit(
            (longitudinal.get("Endpoint") or {}).get(f"FaceNormal{suffix}"),
            "longitudinal normal",
        )
        if max(
            abs(_dot(longitudinal_normal, support_normal)),
            abs(_dot(longitudinal_normal, orientation_normal)),
        ) > 1e-5:
            raise MechanicalInterfaceContractError(
                "longitudinal datum must complete an orthogonal base frame"
            )
        result.update(
            {
                "longitudinalEndpointId": longitudinal_id,
                "longitudinalNormalLocal": longitudinal_normal,
                "longitudinalOriginLocal": _vector(
                    (longitudinal.get("Endpoint") or {}).get(
                        f"FaceCenter{suffix}"
                    ),
                    "longitudinal origin",
                ),
                "lateralOriginLocal": _vector(
                    (orientation.get("Endpoint") or {}).get(
                        f"FaceCenter{suffix}"
                    ),
                    "lateral origin",
                ),
            }
        )
    return result


def _axis_candidates(
    index: dict[str, dict[str, Any]],
    frame: dict[str, Any],
    *,
    coordinate_space: str = "local",
    reference_radius_meters: float = 0.00275,
) -> list[dict[str, Any]]:
    if coordinate_space not in {"local", "world"}:
        raise MechanicalInterfaceContractError(
            "axis-candidate coordinate space must be local or world"
        )
    suffix = "World" if coordinate_space == "world" else "Local"
    support_normal = frame["supportNormalLocal"]
    orientation_normal = frame["orientationNormalLocal"]
    grouped: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for endpoint_id, row in index.items():
        endpoint = row.get("Endpoint") or {}
        if endpoint.get("SurfaceType") != "Cylinder":
            continue
        try:
            axis = _unit(endpoint.get(f"CylinderAxis{suffix}"), "cylinder axis")
            origin = _vector(
                endpoint.get(f"CylinderOrigin{suffix}"), "cylinder origin"
            )
            radius = float(endpoint.get("CylinderRadius"))
        except (MechanicalInterfaceContractError, TypeError, ValueError):
            continue
        if not math.isfinite(radius) or radius <= 0:
            continue
        signed_support_alignment = _dot(axis, support_normal)
        support_alignment = abs(signed_support_alignment)
        orientation_residual = abs(_dot(axis, orientation_normal))
        if support_alignment < 1.0 - 1e-5 or orientation_residual > 1e-5:
            continue
        longitudinal = _dot(
            _subtract(origin, frame["longitudinalOriginLocal"]),
            frame["longitudinalNormalLocal"],
        )
        lateral = _dot(
            _subtract(origin, frame["lateralOriginLocal"]),
            frame["orientationNormalLocal"],
        )
        key = (round(longitudinal, 6), round(lateral, 6))
        grouped.setdefault(key, []).append(
            {
                "endpointId": endpoint_id,
                f"axisOrigin{suffix}": origin,
                f"axisDirection{suffix}": axis,
                "coordinateSpace": coordinate_space,
                "cylinderRadiusMeters": radius,
                "longitudinalMeters": longitudinal,
                "lateralMeters": lateral,
                "supportAxisAlignment": support_alignment,
                "signedSupportAxisAlignment": signed_support_alignment,
                # Both the support mate and concentric mate are anti-aligned.
                # Since F000's locating axis points opposite its support-plane
                # normal, the selected base cylinder must also point opposite
                # the base support normal.  Ignoring this sign can make the
                # third mate over-define an otherwise valid-looking bundle.
                "axisMateAlignmentCompatible": (
                    signed_support_alignment <= -1.0 + 1e-5
                ),
                "orientationAxisResidual": orientation_residual,
            }
        )
    if (
        isinstance(reference_radius_meters, bool)
        or not isinstance(reference_radius_meters, (int, float))
        or not math.isfinite(float(reference_radius_meters))
        or float(reference_radius_meters) <= 0
    ):
        raise MechanicalInterfaceContractError(
            "reference cylinder radius must be finite and positive"
        )
    module_radius = float(reference_radius_meters)
    candidates: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        rows.sort(
            key=lambda row: (
                abs(float(row["cylinderRadiusMeters"]) - module_radius),
                str(row["endpointId"]),
            )
        )
        selected = copy.deepcopy(rows[0])
        selected["coaxialEndpointCount"] = len(rows)
        selected["coaxialAlternativeEndpointIds"] = sorted(
            str(row["endpointId"]) for row in rows[1:]
        )
        selected["axisLineKey"] = {
            "longitudinalMeters": key[0],
            "lateralMeters": key[1],
        }
        selected["diameterCompatibility"] = "not_evaluated"
        candidates.append(selected)
    candidates.sort(
        key=lambda row: (
            float(row["longitudinalMeters"]),
            float(row["lateralMeters"]),
            str(row["endpointId"]),
        )
    )
    return candidates


def build_f000_hybrid_axis_slot_catalog(workspace: Path) -> dict[str, Any]:
    """Return reviewable axis-line choices without approving any new pair."""

    workspace = workspace.resolve()
    module_catalog = _read(workspace / MODULE_CATALOG)
    module_index = _endpoint_index(module_catalog)
    module_frame = _plane_frame(
        module_index,
        support_id=MODULE_ENDPOINTS["support_plane"],
        orientation_id=MODULE_ENDPOINTS["orientation_datum"],
        longitudinal_id=None,
    )
    module_axis_row = module_index.get(MODULE_ENDPOINTS["locating_axis"])
    if not module_axis_row or _surface_type(module_axis_row) != "Cylinder":
        raise MechanicalInterfaceContractError("F000 locating axis is missing")
    module_axis = _unit(
        (module_axis_row.get("Endpoint") or {}).get("CylinderAxisLocal"),
        "F000 locating axis",
    )
    if (
        abs(_dot(module_axis, module_frame["supportNormalLocal"])) < 1.0 - 1e-5
        or abs(_dot(module_axis, module_frame["orientationNormalLocal"])) > 1e-5
    ):
        raise MechanicalInterfaceContractError(
            "F000 plane/axis endpoint bundle is geometrically inconsistent"
        )
    bases = []
    for definition_id, spec in BASE_SPECS.items():
        catalog = _read(workspace / str(spec["catalog"]))
        index = _endpoint_index(catalog)
        coordinate_space = str(spec.get("coordinateSpace") or "local")
        frame = _plane_frame(
            index,
            support_id=str(spec["support"]),
            orientation_id=str(spec["orientation"]),
            longitudinal_id=(
                str(spec["longitudinal"]) if spec.get("longitudinal") else None
            ),
            coordinate_space=coordinate_space,
        )
        if spec.get("releasedAxis"):
            axis_id = str(spec["releasedAxis"])
            row = index.get(axis_id)
            if not row or _surface_type(row) != "Cylinder":
                raise MechanicalInterfaceContractError(
                    "released F000 base axis is missing"
                )
            bases.append(
                {
                    "slotDefinitionId": definition_id,
                    "baseToken": spec["token"],
                    "state": "released_native_pair",
                    "sourceCatalogPath": spec["catalog"],
                    "supportEndpointId": spec["support"],
                    "orientationEndpointId": spec["orientation"],
                    "releasedAxisEndpointId": axis_id,
                    "candidateAxisLineCount": 1,
                    "axisCandidates": [],
                    "requiresExplicitAxisSelection": False,
                    "readyForReleasedCadExecution": True,
                }
            )
            continue
        axis_catalog_path = str(spec.get("axisCatalog") or spec["catalog"])
        axis_catalog = (
            catalog
            if axis_catalog_path == str(spec["catalog"])
            else _read(workspace / axis_catalog_path)
        )
        candidates = _axis_candidates(
            _endpoint_index(axis_catalog),
            frame,
            coordinate_space=coordinate_space,
        )
        if not candidates:
            raise MechanicalInterfaceContractError(
                f"no plane-axis candidate exists on {definition_id}"
            )
        bases.append(
            {
                "slotDefinitionId": definition_id,
                "baseToken": spec["token"],
                "state": "explicit_axis_selection_required",
                "sourceCatalogPath": spec["catalog"],
                "axisCandidateCatalogPath": axis_catalog_path,
                "candidateCoordinateSpace": coordinate_space,
                "supportEndpointId": spec["support"],
                "orientationEndpointId": spec["orientation"],
                "longitudinalEndpointId": spec["longitudinal"],
                "candidateAxisLineCount": len(candidates),
                "axisCandidates": candidates,
                "requiresExplicitAxisSelection": True,
                "readyForReleasedCadExecution": False,
                "selectionBoundary": (
                    "Axis candidates are geometric locations only. A reviewed "
                    "selection and non-prototype CAD validation are still required."
                ),
            }
        )
    core = {
        "schemaVersion": CATALOG_SCHEMA,
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "moduleToken": MODULE_TOKEN,
        "moduleRole": "Scanner",
        "interfaceFamily": SCANNER_PLANE_AXIS_FAMILY,
        "recipeId": SCANNER_PLANE_AXIS_RECIPE_ID,
        "moduleEndpointCatalogPath": MODULE_CATALOG,
        "moduleEndpointBindings": copy.deepcopy(MODULE_ENDPOINTS),
        "baseSlots": bases,
        "summary": {
            "baseSlotCount": len(bases),
            "releasedNativePairCount": sum(
                row["state"] == "released_native_pair" for row in bases
            ),
            "explicitAxisSelectionRequiredCount": sum(
                row["state"] == "explicit_axis_selection_required"
                for row in bases
            ),
            "candidateAxisLineCount": sum(
                int(row["candidateAxisLineCount"]) for row in bases
                if row["state"] == "explicit_axis_selection_required"
            ),
        },
        "claimBoundary": (
            "The catalog inventories stable axis-line candidates. It does not "
            "approve a hole, prove diameter/fastener compatibility, or authorize CAD."
        ),
    }
    return {**core, "catalogDigest": _digest(core)}


def rank_f000_hybrid_axis_candidates(
    catalog: dict[str, Any],
    slot_definition_id: str,
    *,
    longitudinal_meters: float,
    lateral_meters: float,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank geometric candidates; ranking is not an engineering confirmation."""

    for value, label in (
        (longitudinal_meters, "longitudinal"),
        (lateral_meters, "lateral"),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise MechanicalInterfaceContractError(
                f"{label} target must be finite numeric metres"
            )
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise MechanicalInterfaceContractError("candidate limit must be positive")
    slots = [
        row
        for row in catalog.get("baseSlots") or []
        if row.get("slotDefinitionId") == slot_definition_id
    ]
    if len(slots) != 1 or slots[0].get("requiresExplicitAxisSelection") is not True:
        raise MechanicalInterfaceContractError(
            "slot does not expose reviewable axis candidates"
        )
    ranked = []
    for row in slots[0].get("axisCandidates") or []:
        item = copy.deepcopy(row)
        delta_longitudinal = float(row["longitudinalMeters"]) - float(
            longitudinal_meters
        )
        delta_lateral = float(row["lateralMeters"]) - float(lateral_meters)
        item["distanceFromRequestedPositionMeters"] = math.sqrt(
            delta_longitudinal**2 + delta_lateral**2
        )
        item["selectionStatus"] = "recommended_for_review_not_confirmed"
        ranked.append(item)
    ranked.sort(
        key=lambda row: (
            not bool(row.get("axisMateAlignmentCompatible")),
            float(row["distanceFromRequestedPositionMeters"]),
            str(row["endpointId"]),
        )
    )
    return ranked[:limit]


def compile_f000_hybrid_axis_selection(
    workspace: Path,
    *,
    slot_definition_id: str,
    selected_axis_endpoint_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Compile one confirmed axis into a pending three-mate CAD candidate."""

    if evidence.get("confirmed") is not True or not str(
        evidence.get("source") or ""
    ).strip():
        raise MechanicalInterfaceContractError(
            "hybrid axis selection requires confirmed evidence with a source"
        )
    catalog = build_f000_hybrid_axis_slot_catalog(workspace)
    slots = [
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == slot_definition_id
    ]
    if len(slots) != 1 or slots[0]["state"] != "explicit_axis_selection_required":
        raise MechanicalInterfaceContractError(
            "hybrid axis candidate requires an unreleased reviewable base slot"
        )
    slot_row = slots[0]
    candidates = {
        row["endpointId"]: row for row in slot_row.get("axisCandidates") or []
    }
    if selected_axis_endpoint_id not in candidates:
        raise MechanicalInterfaceContractError(
            "selected axis is not a candidate axis line for the requested base"
        )
    if (
        candidates[selected_axis_endpoint_id].get("axisMateAlignmentCompatible")
        is not True
    ):
        raise MechanicalInterfaceContractError(
            "selected axis direction conflicts with the support/axis mate alignments"
        )
    module_release = _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / MODULE_RELEASE
        / "release-manifest.json"
    )
    base_spec = BASE_SPECS[slot_definition_id]
    base_release = _read(
        workspace
        / "demo/global_assembly_catalog/releases"
        / str(base_spec["release"])
        / "release-manifest.json"
    )
    module_port = {
        "portId": "F000.reviewed_plane_axis_datum.v1",
        "moduleToken": MODULE_TOKEN,
        "endpointBindings": [
            {"role": role, "endpointId": endpoint_id}
            for role, endpoint_id in MODULE_ENDPOINTS.items()
        ],
    }
    slot_port = {
        "portId": f"{base_spec['token']}.reviewed_f000_axis_slot.v1",
        "moduleToken": base_spec["token"],
        "endpointBindings": [
            {"role": "support_plane", "endpointId": base_spec["support"]},
            {
                "role": "orientation_datum",
                "endpointId": base_spec["orientation"],
            },
            {"role": "locating_axis", "endpointId": selected_axis_endpoint_id},
        ],
    }
    module_contract = build_exact_three_relation_contract(
        port=module_port,
        release_manifest=module_release,
        side="moving_module",
        module_role="Scanner",
        module_definition_id=MODULE_DEFINITION_ID,
        interface_family=SCANNER_PLANE_AXIS_FAMILY,
        recipe_id=SCANNER_PLANE_AXIS_RECIPE_ID,
        topology_roles=SCANNER_PLANE_AXIS_ROLES,
        interface_variant_key=GENERIC_VARIANT,
        role_aliases={},
    )
    slot_contract = build_exact_three_relation_contract(
        port=slot_port,
        release_manifest=base_release,
        side="base_slot",
        module_role="Base",
        module_definition_id=slot_definition_id,
        accepted_module_roles=["Scanner"],
        interface_family=SCANNER_PLANE_AXIS_FAMILY,
        recipe_id=SCANNER_PLANE_AXIS_RECIPE_ID,
        topology_roles=SCANNER_PLANE_AXIS_ROLES,
        interface_variant_key=GENERIC_VARIANT,
        role_aliases={},
    )
    for contract in (module_contract, slot_contract):
        contract["mechanicalBoundary"].update(
            {
                "requiresExplicitPairRelease": True,
                "placementMode": "reviewed_hybrid_plane_axis_datum",
                "actualFasteningMethod": "not_verified",
                "diameterCompatibility": "not_evaluated",
                "productionReady": False,
            }
        )
        contract["contractId"] = "interface-contract/" + _digest(
            {key: value for key, value in contract.items() if key != "contractId"}
        )[:16]
    match = match_interface_contracts(module_contract, slot_contract)
    if match.get("compatible") is not True:
        raise MechanicalInterfaceContractError(
            "confirmed hybrid axis did not produce a compatible contract"
        )
    template = instantiate_connection_template(
        match, module_contract, slot_contract
    )
    core = {
        "schemaVersion": SELECTION_SCHEMA,
        "status": "ready_for_nonprototype_cad_validation",
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "slotDefinitionId": slot_definition_id,
        "selectedAxisEndpointId": selected_axis_endpoint_id,
        "selectedAxisCandidate": copy.deepcopy(candidates[selected_axis_endpoint_id]),
        "selectionEvidence": copy.deepcopy(evidence),
        "moduleEndpointCatalogPath": MODULE_CATALOG,
        "slotEndpointCatalogPath": base_spec["catalog"],
        "slotFrameEndpointCatalogPath": base_spec["catalog"],
        "slotAxisEndpointCatalogPath": base_spec.get(
            "axisCatalog", base_spec["catalog"]
        ),
        "moduleContract": module_contract,
        "slotContract": slot_contract,
        "match": match,
        "instantiatedTemplate": template,
        "readyForReleasedCadExecution": False,
        "validationRequiredBeforeRelease": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "claimBoundary": (
            "The selected axis is approved only as a CAD validation candidate. "
            "Diameter fit, fastening, collision and production readiness are unverified."
        ),
    }
    return {**core, "selectionDigest": _digest(core)}


def compile_f000_hybrid_axis_validation_package(
    workspace: Path,
    *,
    slot_definition_id: str,
    selected_axis_endpoint_id: str,
    evidence: dict[str, Any],
    initial_placement_variant: int = 1,
) -> dict[str, Any]:
    """Compile a confirmed axis selection into the common CAD evidence package."""

    if (
        isinstance(initial_placement_variant, bool)
        or not isinstance(initial_placement_variant, int)
        or initial_placement_variant < 0
    ):
        raise MechanicalInterfaceContractError(
            "initial placement variant must be a non-negative integer"
        )
    selection = compile_f000_hybrid_axis_selection(
        workspace,
        slot_definition_id=slot_definition_id,
        selected_axis_endpoint_id=selected_axis_endpoint_id,
        evidence=evidence,
    )
    # Reuse the common graph record builders so this candidate exercises the
    # same CAD adapter and publication gates as the three-plane candidates.
    from .parameterized_datum_placement import (  # local import avoids a cycle
        IDENTITY_TRANSFORM,
        VALIDATION_PACKAGE_SCHEMA,
        _base_wrapper_source,
        _mate_row,
        _module_record,
        _sha256_file,
    )

    workspace = workspace.resolve()
    module_contract = selection["moduleContract"]
    slot_contract = selection["slotContract"]
    template = selection["instantiatedTemplate"]
    module_catalog_path = workspace / str(selection["moduleEndpointCatalogPath"])
    slot_catalog_path = workspace / str(selection["slotEndpointCatalogPath"])
    slot_axis_catalog_path = workspace / str(
        selection.get("slotAxisEndpointCatalogPath")
        or selection["slotEndpointCatalogPath"]
    )
    module_catalog = _read(module_catalog_path)
    slot_catalog = _read(slot_catalog_path)
    slot_axis_catalog = (
        slot_catalog
        if slot_axis_catalog_path == slot_catalog_path
        else _read(slot_axis_catalog_path)
    )

    def selected_rows(
        catalog_value: dict[str, Any], contract: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        index = _endpoint_index(catalog_value)
        result: dict[str, dict[str, Any]] = {}
        for binding in contract.get("endpointBindings") or []:
            role = str(binding.get("role") or "")
            endpoint_id = str(binding.get("endpointId") or "")
            if role in result or endpoint_id not in index:
                raise MechanicalInterfaceContractError(
                    f"hybrid endpoint binding cannot be resolved: {role}/{endpoint_id}"
                )
            result[role] = copy.deepcopy(index[endpoint_id])
        if set(result) != set(SCANNER_PLANE_AXIS_ROLES):
            raise MechanicalInterfaceContractError(
                "hybrid validation requires support, orientation and axis endpoints"
            )
        return result

    module_endpoints = selected_rows(module_catalog, module_contract)
    if slot_axis_catalog is slot_catalog:
        slot_endpoints = selected_rows(slot_catalog, slot_contract)
        slot_record_catalog = slot_catalog
    else:
        # A base frame and its complete hole inventory may come from separate
        # immutable captures.  Merge only for endpoint resolution; every row
        # retains its own persistent reference and source model path.
        slot_record_catalog = copy.deepcopy(slot_catalog)
        merged = _endpoint_index(slot_catalog)
        merged.update(_endpoint_index(slot_axis_catalog))
        slot_record_catalog["Endpoints"] = [
            copy.deepcopy(merged[key]) for key in sorted(merged)
        ]
        slot_record_catalog["EndpointCount"] = len(
            slot_record_catalog["Endpoints"]
        )
        slot_endpoints = selected_rows(slot_record_catalog, slot_contract)
    target_token = str(module_contract.get("moduleToken") or "")
    base_token = str(slot_contract.get("moduleToken") or "")
    target_module = _module_record(
        module_catalog, module_endpoints, target_token, nonprototype_target=True
    )
    base_module = _module_record(
        slot_record_catalog,
        slot_endpoints,
        base_token,
        nonprototype_target=False,
    )
    if target_module.get("SourceTransform") != IDENTITY_TRANSFORM:
        raise MechanicalInterfaceContractError(
            "hybrid target must start from identity before deterministic placement"
        )
    if not Path(str(target_module.get("Path") or "")).is_file():
        raise MechanicalInterfaceContractError("target module source assembly is missing")
    cache_entry_path, source_assembly_path = _base_wrapper_source(
        workspace, base_token
    )
    mates = [
        _mate_row(
            step=step,
            target_token=target_token,
            base_token=base_token,
            target_endpoint=module_endpoints[str(step["endpointRoleA"])],
            base_endpoint=slot_endpoints[str(step["endpointRoleB"])],
        )
        for step in template.get("mateSteps") or []
    ]
    if [row["MateTypeName"] for row in mates] != [
        "swMateCOINCIDENT",
        "swMatePARALLEL",
        "swMateCONCENTRIC",
    ]:
        raise MechanicalInterfaceContractError(
            "hybrid validation graph must preserve the exact three-mate topology"
        )
    policy = {
        "mode": "reviewed_hybrid_plane_axis_datum",
        "selectedAxisEndpointId": selected_axis_endpoint_id,
        "selectionDigest": selection["selectionDigest"],
        "actualFixationMethod": "not_verified",
        "diameterCompatibility": "not_evaluated",
        "directMechanicalCompatibilityClaim": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "templateId": template["templateId"],
    }
    effective_graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": None,
        "ModuleCount": 2,
        "InterModuleMateCount": 3,
        "Modules": [base_module, target_module],
        "Mates": mates,
        "BaseGraphPolicy": {
            "status": "reviewed_hybrid_plane_axis_validation_candidate",
            "caseAnchorAllowed": False,
            "prototypeTopLevelTargetPoseAllowed": False,
            "targetLeafPoseAnchorsAllowed": False,
        },
        "CaseAnchor": None,
        "TargetLeafPoseAnchors": [],
        "EditPolicy": {
            "baseModuleToken": base_token,
            "initialPlacementMode": "deterministic",
            "initialPlacementVariant": initial_placement_variant,
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [base_token],
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
            "fixCaseAnchorBeforeMates": False,
        },
        "HybridPlaneAxisPlacementPolicy": policy,
    }
    role_order = ("support_plane", "orientation_datum", "locating_axis")
    selected_endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "CatalogMode": "hybrid-plane-axis-validation-selected-endpoints",
        "SourceMateFacesOnly": False,
        "ModuleCount": 2,
        "Modules": copy.deepcopy(effective_graph["Modules"]),
        "EndpointCount": 6,
        "Endpoints": [
            *[copy.deepcopy(module_endpoints[role]) for role in role_order],
            *[copy.deepcopy(slot_endpoints[role]) for role in role_order],
        ],
    }
    package = {
        "schemaVersion": VALIDATION_PACKAGE_SCHEMA,
        "status": "ready_for_explicit_nonprototype_cad_validation",
        "placementMode": "reviewed_hybrid_plane_axis_datum",
        "moduleDefinitionId": MODULE_DEFINITION_ID,
        "slotDefinitionId": slot_definition_id,
        "targetModuleToken": target_token,
        "baseModuleToken": base_token,
        "sourceAssemblyPath": str(source_assembly_path.resolve()),
        "sourceAssemblySha256": _sha256_file(source_assembly_path),
        "baseWrapperCacheEntryPath": str(cache_entry_path.resolve()),
        "baseWrapperCacheEntrySha256": _sha256_file(cache_entry_path),
        "moduleEndpointCatalogPath": str(module_catalog_path.resolve()),
        "slotEndpointCatalogPath": str(slot_catalog_path.resolve()),
        "slotFrameEndpointCatalogPath": str(slot_catalog_path.resolve()),
        "slotAxisEndpointCatalogPath": str(slot_axis_catalog_path.resolve()),
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": initial_placement_variant,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "readyForReleasedCadExecution": False,
        "validationRequiredBeforeRelease": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "instantiatedTemplate": template,
        "positionParametersOverride": None,
        "hybridAxisSelection": copy.deepcopy(selection),
        "effectiveGraph": effective_graph,
        "selectedEndpointCatalog": selected_endpoint_catalog,
        "claimBoundary": (
            "This package validates only a reviewed support/orientation/axis CAD "
            "pose. It does not prove diameter fit, fastening, collision or production use."
        ),
    }
    package["packageDigest"] = _digest(package)
    return package
