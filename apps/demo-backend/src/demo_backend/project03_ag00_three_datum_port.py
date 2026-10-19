"""Build the Project03 AG00 three-datum non-anchor installation candidate."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .face_endpoint_catalog import merge_face_endpoint_catalogs
from .nonprototype_execution_graph import prepare_nonprototype_execution_graph


SCHEMA = "project03-ag00-three-datum-port-candidate/v1"


class Project03Ag00ThreeDatumError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _endpoint(catalog: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
    matches = [
        row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId") == endpoint_id
    ]
    if len(matches) != 1:
        raise Project03Ag00ThreeDatumError(
            f"cannot uniquely resolve endpoint: {endpoint_id}"
        )
    return copy.deepcopy(matches[0])


def _binding(port: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [
        row for row in port.get("endpointBindings") or [] if row.get("role") == role
    ]
    if len(matches) != 1:
        raise Project03Ag00ThreeDatumError(f"port has no unique role: {role}")
    return matches[0]


def build_project03_ag00_three_datum_candidate(
    diagnostic_graph: dict[str, Any],
    diagnostic_catalog: dict[str, Any],
    diagnostic_semantic_catalog: dict[str, Any],
    moving_primary_leaf_catalog: dict[str, Any],
    moving_support_leaf_catalog: dict[str, Any],
    target_leaf_catalog: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    if discovery.get("schemaVersion") != "installation-datum-discovery/v1":
        raise Project03Ag00ThreeDatumError("unsupported discovery schema")
    if discovery.get("status") != (
        "single_secondary_axis_candidate_pending_cad_validation"
    ):
        raise Project03Ag00ThreeDatumError(
            "AG00 candidate must contain one unambiguous secondary axis"
        )
    candidate = discovery.get("preferredCandidate") or {}
    moving_id = str(candidate.get("movingEndpointId") or "")
    target_id = str(candidate.get("targetEndpointId") or "")
    if not moving_id or not target_id:
        raise Project03Ag00ThreeDatumError("discovery has no endpoint pair")
    if float(candidate.get("primaryIndependenceMeters") or 0.0) < 0.002:
        raise Project03Ag00ThreeDatumError("secondary axis is not independent")

    merged = merge_face_endpoint_catalogs(
        diagnostic_catalog, moving_primary_leaf_catalog
    )
    merged = merge_face_endpoint_catalogs(merged, moving_support_leaf_catalog)
    merged = merge_face_endpoint_catalogs(merged, target_leaf_catalog)

    source_ports = diagnostic_semantic_catalog.get("ports") or []
    moving_ports = [row for row in source_ports if row.get("moduleToken") == "FL9A24D063AG00"]
    target_ports = [row for row in source_ports if row.get("moduleToken") == "FL9A24D063AA00"]
    if len(moving_ports) != 1 or len(target_ports) != 1:
        raise Project03Ag00ThreeDatumError("diagnostic ports are incomplete")

    moving_port = copy.deepcopy(moving_ports[0])
    target_port = copy.deepcopy(target_ports[0])
    moving_port.update(
        {
            "portId": "AG00.frame_three_datum_installation.v1",
            "description": "支承面、主定位孔和独立第二定位孔组成的一面两孔安装端口。",
            "interfaceType": "project03_service_cluster_frame_three_datum_installation",
            "status": "candidate-cad-validation-required",
            "portable": False,
            "evidence": [
                "项目03原型既有重合6、同心11",
                "限定叶面目录发现第二定位孔；仅用于候选筛选，未复制原型位姿",
            ],
        }
    )
    target_port.update(
        {
            "portId": "AA00.ag00_three_datum_installation.v1",
            "description": "与AG00一面两孔安装端口对应的AA00承载端口。",
            "interfaceType": "project03_service_cluster_frame_three_datum_installation",
            "status": "candidate-cad-validation-required",
            "portable": False,
            "evidence": [
                "项目03原型既有重合6、同心11",
                "限定叶面目录发现第二承载孔；仅用于候选筛选，未复制原型位姿",
            ],
        }
    )
    moving_port["endpointBindings"] = [
        copy.deepcopy(_binding(moving_port, "support_plane")),
        copy.deepcopy(_binding(moving_port, "primary_locating_hole")),
        {"role": "secondary_locating_hole", "endpointId": moving_id},
    ]
    target_port["endpointBindings"] = [
        copy.deepcopy(_binding(target_port, "support_plane")),
        copy.deepcopy(_binding(target_port, "primary_locating_hole")),
        {"role": "secondary_locating_hole", "endpointId": target_id},
    ]

    mate_steps = copy.deepcopy(
        (diagnostic_semantic_catalog.get("connectionTemplates") or [])[0].get(
            "mateSteps"
        )
        or []
    )
    mate_steps.append(
        {
            "mateName": "MCP_GRAPH_AG00_SECONDARY_AXIS",
            "mateType": 1,
            "mateTypeName": "swMateCONCENTRIC",
            "alignment": 1,
            "alignmentName": "swMateAlignANTI_ALIGNED",
            "endpointRoleA": "secondary_locating_hole",
            "endpointRoleB": "secondary_locating_hole",
        }
    )
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": "Validate AG00 one-plane/two-hole non-anchor installation.",
        "ports": [moving_port, target_port],
        "connectionTemplates": [
            {
                "templateId": "AG00_to_AA00_three_datum_installation_v1",
                "purposes": ["installation"],
                "interfaceTypeA": moving_port["interfaceType"],
                "interfaceTypeB": target_port["interfaceType"],
                "status": "candidate-cad-validation-required",
                "constraintEffect": {
                    "purpose": "Use one support plane and two independent locating axes to close the rigid pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": mate_steps,
            }
        ],
    }

    graph = copy.deepcopy(diagnostic_graph)
    moving_endpoint = _endpoint(merged, moving_id)["Endpoint"]
    target_endpoint = _endpoint(merged, target_id)["Endpoint"]
    moving_endpoint["Index"] = 0
    target_endpoint["Index"] = 1
    new_mate = {
        "MateName": "MCP_GRAPH_AG00_SECONDARY_AXIS",
        "MateType": 1,
        "MateTypeName": "swMateCONCENTRIC",
        "Alignment": 1,
        "AlignmentName": "swMateAlignANTI_ALIGNED",
        "Distance": None,
        "Angle": None,
        "IsSuppressed": False,
        "Endpoints": [moving_endpoint, target_endpoint],
        "ModuleTokens": ["FL9A24D063AG00", "FL9A24D063AA00"],
        "ModuleHierarchyPaths": [
            moving_endpoint["ModuleHierarchyPath"],
            target_endpoint["ModuleHierarchyPath"],
        ],
        "IsBasicTwoFaceRebuildable": True,
        "RebuildRejectionReason": None,
    }
    new_mate["MateId"] = "mate:" + _digest(new_mate)[:16]
    graph.setdefault("Mates", []).append(new_mate)
    graph["InterModuleMateCount"] = len(graph["Mates"])
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit.update(
        {
            "planId": "project03-add-AG00-three-datum-nonanchor-v1",
            "generatedMateNames": [row["MateName"] for row in graph["Mates"]],
            "constraintAssessment": {
                "sourceSemanticMateSetReproduced": True,
                "fullyLocatesAddedComponent": "requires_cad_verification",
                "expectedResidualDof": 0,
                "caseAnchoredModuleTokens": [],
                "reason": "The third mate uses a unique secondary axis discovered from bounded persistent face catalogs.",
            },
            "threeDatumCandidate": {
                "schemaVersion": SCHEMA,
                "discoveryDigest": discovery.get("discoveryDigest"),
                "prototypeGeometryUse": "candidate-screening-only",
                "runtimePoseAnchorAllowed": False,
                "secondaryAxis": copy.deepcopy(candidate),
            },
        }
    )
    audit["connections"] = [
        {
            "connectionId": "AG00-installed-on-AA00-three-datum",
            "portAId": moving_port["portId"],
            "portBId": target_port["portId"],
            "interfaceTypeA": moving_port["interfaceType"],
            "interfaceTypeB": target_port["interfaceType"],
            "templateId": "AG00_to_AA00_three_datum_installation_v1",
            "generatedMateNames": [row["mateName"] for row in mate_steps],
            "validationRelations": [],
            "constraintEffect": semantic["connectionTemplates"][0][
                "constraintEffect"
            ],
        }
    ]
    audit["residualDofBoundary"] = {
        "sourceDrivingMateCount": 2,
        "candidateDrivingMateCount": 3,
        "expectedResidualDofWithoutAnchor": 0,
        "caseAnchorApplied": False,
        "leafPoseAnchorApplied": False,
        "candidateRequiresCadValidation": True,
    }
    graph = prepare_nonprototype_execution_graph(
        graph, target_module_token="FL9A24D063AG00"
    )

    selected_ids = {
        binding["endpointId"]
        for port in (moving_port, target_port)
        for binding in port["endpointBindings"]
    }
    endpoint_catalog = copy.deepcopy(merged)
    endpoint_catalog["Endpoints"] = [
        row for row in merged.get("Endpoints") or [] if row.get("EndpointId") in selected_ids
    ]
    endpoint_catalog["EndpointCount"] = len(endpoint_catalog["Endpoints"])
    endpoint_catalog["CatalogMode"] = "project03_ag00_three_datum_candidate"

    summary = {
        "schemaVersion": SCHEMA,
        "status": "candidate_ready_for_nonanchor_cad_validation",
        "projectId": "project03",
        "targetModule": "FL9A24D063AG00",
        "drivingMateCount": 3,
        "expectedResidualDof": 0,
        "casePoseAnchorCount": 0,
        "leafPoseAnchorCount": 0,
        "prototypeUse": "bounded-datum-screening-only",
        "secondaryAxis": copy.deepcopy(candidate),
        "semanticPortPublished": False,
        "nextGate": "nonprototype-cad-save-close-reopen",
    }
    summary["candidateDigest"] = _digest(summary)
    return {
        "endpointCatalog": endpoint_catalog,
        "semanticCatalog": semantic,
        "effectiveGraph": graph,
        "summary": summary,
    }

