"""Build a fail-closed Project05 P000 -> Project02 A600 datum-placement candidate.

The candidate deliberately does not claim fastener or adapter compatibility.  It
only reuses three mutually orthogonal, persistent planar endpoints on P000 and
the already CAD-validated A600/A300 datum slot to create a portable placement
bundle for a cross-project assembly demo.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any


SCHEMA = "cross-project-wastecup-datum-candidate/v1"


class CrossProjectWasteCupDatumError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _single(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    matches = [row for row in rows if str(row.get(key) or "") == value]
    if len(matches) != 1:
        raise CrossProjectWasteCupDatumError(
            f"Expected one row with {key}={value!r}, found {len(matches)}."
        )
    return copy.deepcopy(matches[0])


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectWasteCupDatumError("Unsupported endpoint catalog schema.")
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if str(row.get("EndpointId") or "")
    }


def _port(catalog: dict[str, Any], port_id: str) -> dict[str, Any]:
    return _single(catalog.get("ports") or [], "portId", port_id)


def _bound_endpoints(
    port: dict[str, Any], endpoint_catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    index = _endpoint_index(endpoint_catalog)
    rows = []
    for binding in port.get("endpointBindings") or []:
        endpoint_id = str(binding.get("endpointId") or "")
        if endpoint_id not in index:
            raise CrossProjectWasteCupDatumError(
                f"Port endpoint is missing from the endpoint catalog: {endpoint_id}."
            )
        row = copy.deepcopy(index[endpoint_id])
        row["BindingRole"] = binding.get("role")
        rows.append(row)
    return rows


def _normal(row: dict[str, Any]) -> tuple[float, float, float]:
    endpoint = row.get("Endpoint") or {}
    values = endpoint.get("FaceNormalLocal")
    if endpoint.get("GeometryType") != "Face" or not isinstance(values, list):
        raise CrossProjectWasteCupDatumError(
            f"Endpoint {row.get('EndpointId')} is not a planar face datum."
        )
    if len(values) != 3:
        raise CrossProjectWasteCupDatumError("A planar datum normal must have 3 values.")
    norm = math.sqrt(sum(float(value) ** 2 for value in values))
    if norm < 0.999:
        raise CrossProjectWasteCupDatumError("A planar datum normal is degenerate.")
    return tuple(float(value) / norm for value in values)


def _axis_match(
    rows: list[dict[str, Any]], expected: tuple[float, float, float]
) -> dict[str, Any]:
    matches = []
    for row in rows:
        try:
            normal = _normal(row)
        except CrossProjectWasteCupDatumError:
            continue
        dot = sum(a * b for a, b in zip(normal, expected))
        if dot > 0.999:
            matches.append(row)
    if len(matches) != 1:
        raise CrossProjectWasteCupDatumError(
            f"Expected one planar datum with local normal {expected}, found {len(matches)}."
        )
    return copy.deepcopy(matches[0])


def _endpoint(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    endpoint = copy.deepcopy(row["Endpoint"])
    endpoint["Index"] = index
    return endpoint


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    return _single(graph.get("Modules") or [], "ModuleToken", token)


def _mate(
    name: str,
    mate_type: int,
    mate_type_name: str,
    alignment: int,
    alignment_name: str,
    target_endpoint: dict[str, Any],
    context_endpoint: dict[str, Any],
    *,
    distance: float | None = None,
) -> dict[str, Any]:
    row = {
        "MateName": name,
        "MateType": mate_type,
        "MateTypeName": mate_type_name,
        "Alignment": alignment,
        "AlignmentName": alignment_name,
        "Distance": distance,
        "Angle": None,
        "IsSuppressed": False,
        "Endpoints": [
            _endpoint(target_endpoint, index=0),
            _endpoint(context_endpoint, index=1),
        ],
        "ModuleTokens": ["P000", "A600"],
        "ModuleHierarchyPaths": [
            str((target_endpoint.get("Endpoint") or {}).get("ModuleHierarchyPath") or ""),
            str((context_endpoint.get("Endpoint") or {}).get("ModuleHierarchyPath") or ""),
        ],
        "IsBasicTwoFaceRebuildable": True,
        "RebuildRejectionReason": None,
    }
    if distance is not None:
        row["AdvancedOptions"] = {"DistanceFlipDimension": False}
    row["MateId"] = "mate:cross-project-wastecup:" + _digest(row)[:16]
    return row


def build_project05_p000_to_project02_a600_datum_candidate(
    *,
    a300_graph: dict[str, Any],
    a300_semantic_catalog: dict[str, Any],
    a300_endpoint_catalog: dict[str, Any],
    p000_graph: dict[str, Any],
    p000_semantic_catalog: dict[str, Any],
    p000_endpoint_catalog: dict[str, Any],
    longitudinal_distance_meters: float = 0.08,
    lateral_distance_meters: float = 0.39,
) -> dict[str, Any]:
    """Return an effective graph and audit report for a three-plane candidate."""

    for value in (longitudinal_distance_meters, lateral_distance_meters):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise CrossProjectWasteCupDatumError("Position distances must be finite non-negative metres.")

    a600_port = _port(a300_semantic_catalog, "A600.a300_installation")
    p000_port = _port(p000_semantic_catalog, "P000.frame_installation")
    a600_rows = _bound_endpoints(a600_port, a300_endpoint_catalog)
    p000_rows = _bound_endpoints(p000_port, p000_endpoint_catalog)

    a600_by_role = {
        str(row.get("BindingRole") or ""): row for row in a600_rows
    }
    required_a600_roles = {
        "mate_1_context_1",
        "mate_2_context_1",
        "mate_3_context_1",
    }
    if set(a600_by_role) != required_a600_roles:
        raise CrossProjectWasteCupDatumError(
            "A600 waste-cup slot is not the verified three-plane datum bundle."
        )

    # These are semantic installation datums, not inferred fastener geometry.
    p000_longitudinal = _axis_match(p000_rows, (0.0, -1.0, 0.0))
    p000_lateral = _axis_match(p000_rows, (1.0, 0.0, 0.0))
    p000_support = _axis_match(p000_rows, (0.0, 0.0, 1.0))

    mates = [
        _mate(
            "P000_A600_DATUM_DISTANCE_1",
            5,
            "swMateDISTANCE",
            0,
            "swMateAlignALIGNED",
            p000_longitudinal,
            a600_by_role["mate_1_context_1"],
            distance=longitudinal_distance_meters,
        ),
        _mate(
            "P000_A600_DATUM_DISTANCE_2",
            5,
            "swMateDISTANCE",
            0,
            "swMateAlignALIGNED",
            p000_lateral,
            a600_by_role["mate_2_context_1"],
            distance=lateral_distance_meters,
        ),
        _mate(
            "P000_A600_DATUM_SUPPORT",
            0,
            "swMateCOINCIDENT",
            1,
            "swMateAlignANTI_ALIGNED",
            p000_support,
            a600_by_role["mate_3_context_1"],
        ),
    ]

    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": None,
        "ModuleCount": 2,
        "InterModuleMateCount": 3,
        "Modules": [_module(a300_graph, "A600"), _module(p000_graph, "P000")],
        "Mates": mates,
        "BaseGraphPolicy": {
            "status": "cross_project_datum_placement_demo",
            "caseAnchorAllowed": False,
            "prototypeTopLevelTargetPoseAllowed": False,
            "targetLeafPoseAnchorsAllowed": False,
        },
        "CaseAnchor": None,
        "TargetLeafPoseAnchors": [],
        "CrossProjectWasteCupDatumAudit": {
            "schemaVersion": SCHEMA,
            "sourceProjectId": "project05",
            "sourceModuleToken": "P000",
            "targetProjectId": "project02",
            "targetBaseToken": "A600",
            "targetSlotRole": "WasteCup",
            "placementMode": "three_orthogonal_planar_datums",
            "expectedResidualExternalDof": 0,
            "prototypeTopLevelTargetPoseUsed": False,
            "caseAnchorUsed": False,
            "targetLeafPoseAnchorsUsed": False,
            "physicalFastenerCompatibility": "not_evaluated",
            "adapterCompatibility": "not_evaluated",
            "collisionOrBrep": "not_evaluated",
            "productionReady": False,
        },
    }
    audit = copy.deepcopy(graph["CrossProjectWasteCupDatumAudit"])
    audit.update(
        {
            "status": "ready_for_nonprototype_cad_validation",
            "cadLaunchAllowed": True,
            "mateCount": len(mates),
            "targetEndpointIds": [
                p000_longitudinal["EndpointId"],
                p000_lateral["EndpointId"],
                p000_support["EndpointId"],
            ],
            "contextEndpointIds": [
                a600_by_role["mate_1_context_1"]["EndpointId"],
                a600_by_role["mate_2_context_1"]["EndpointId"],
                a600_by_role["mate_3_context_1"]["EndpointId"],
            ],
            "effectiveGraphDigest": _digest(graph),
            "limitations": [
                "This candidate proves datum placement only, not bolt-pattern compatibility.",
                "Collision, B-rep, maintenance access and process reach are not evaluated.",
                "A real CAD run from a displaced initial pose is required before publication.",
            ],
        }
    )
    return {"effectiveGraph": graph, "audit": audit}

