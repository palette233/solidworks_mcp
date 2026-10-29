"""Build a base-only, one-plane/two-hole GN00 installation candidate.

The source Project01 GN00 installation uses JJ00 for its support plane and
primary hole, but obtains anti-rotation from SS00.  This candidate replaces
that cross-provider direction datum with a second physical axis on JJ00.  The
prototype pose is used only to screen already registered persistent faces; it
is never copied into the execution graph.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .face_endpoint_catalog import merge_face_endpoint_catalogs
from .nonprototype_execution_graph import prepare_nonprototype_execution_graph


SCHEMA = "project01-gn00-two-hole-port-candidate/v1"


class Project01Gn00TwoHoleError(ValueError):
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
        raise Project01Gn00TwoHoleError(
            f"cannot uniquely resolve endpoint: {endpoint_id}"
        )
    return copy.deepcopy(matches[0])


def _binding(port: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [
        row for row in port.get("endpointBindings") or [] if row.get("role") == role
    ]
    if len(matches) != 1:
        raise Project01Gn00TwoHoleError(f"port has no unique role: {role}")
    return copy.deepcopy(matches[0])


def build_project01_gn00_two_hole_candidate(
    source_graph: dict[str, Any],
    source_catalog: dict[str, Any],
    source_semantic_catalog: dict[str, Any],
    moving_primary_leaf_catalog: dict[str, Any],
    moving_support_leaf_catalog: dict[str, Any],
    target_leaf_catalog: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    if discovery.get("schemaVersion") != "installation-datum-discovery/v1":
        raise Project01Gn00TwoHoleError("unsupported discovery schema")
    if discovery.get("status") != (
        "single_secondary_axis_candidate_pending_cad_validation"
    ):
        raise Project01Gn00TwoHoleError(
            "GN00 candidate must contain one unambiguous secondary axis"
        )
    candidate = copy.deepcopy(discovery.get("preferredCandidate") or {})
    moving_id = str(candidate.get("movingEndpointId") or "")
    target_id = str(candidate.get("targetEndpointId") or "")
    if not moving_id or not target_id:
        raise Project01Gn00TwoHoleError("discovery has no endpoint pair")
    if float(candidate.get("primaryIndependenceMeters") or 0.0) < 0.002:
        raise Project01Gn00TwoHoleError("secondary axis is not independent")

    merged = merge_face_endpoint_catalogs(
        source_catalog, moving_primary_leaf_catalog
    )
    merged = merge_face_endpoint_catalogs(merged, moving_support_leaf_catalog)
    merged = merge_face_endpoint_catalogs(merged, target_leaf_catalog)

    ports = source_semantic_catalog.get("ports") or []
    moving_sources = [
        row for row in ports if row.get("portId") == "GN00.primary_installation"
    ]
    target_sources = [
        row for row in ports if row.get("portId") == "JJ00.gn00_primary"
    ]
    if len(moving_sources) != 1 or len(target_sources) != 1:
        raise Project01Gn00TwoHoleError("source primary ports are incomplete")

    moving_port = copy.deepcopy(moving_sources[0])
    target_port = copy.deepcopy(target_sources[0])
    interface_type = "project01_gn00_jj00_plane_two_hole_installation"
    moving_port.update(
        {
            "portId": "GN00.jj00_plane_two_hole_installation.v1",
            "description": "GN00支承面、主定位孔和独立第二定位孔安装端口。",
            "interfaceType": interface_type,
            "status": "candidate-cad-validation-required",
            "portable": False,
            "providerRoles": ["Base"],
            "evidence": [
                "Project01原型既有重合6、同心11",
                "两个限定静止安装叶目录中唯一发现第二定位孔",
                "原型坐标只用于筛选候选，不进入执行图",
            ],
        }
    )
    target_port.update(
        {
            "portId": "JJ00.gn00_plane_two_hole_installation.v1",
            "description": "JJ00上与GN00一面两孔安装端口对应的承载端口。",
            "interfaceType": interface_type,
            "status": "candidate-cad-validation-required",
            "portable": False,
            "providerRoles": ["Base"],
            "evidence": [
                "Project01原型既有重合6、同心11",
                "JJ00限定安装叶目录中唯一发现第二承载孔",
            ],
        }
    )
    moving_port["endpointBindings"] = [
        _binding(moving_port, "support_plane"),
        {
            "role": "primary_locating_hole",
            "endpointId": _binding(moving_port, "locating_hole")["endpointId"],
        },
        {"role": "secondary_locating_hole", "endpointId": moving_id},
    ]
    target_port["endpointBindings"] = [
        _binding(target_port, "support_plane"),
        {
            "role": "primary_locating_hole",
            "endpointId": _binding(target_port, "locating_hole")["endpointId"],
        },
        {"role": "secondary_locating_hole", "endpointId": target_id},
    ]

    source_templates = source_semantic_catalog.get("connectionTemplates") or []
    primary_templates = [
        row for row in source_templates if row.get("templateId") == "GN00_to_JJ00_primary"
    ]
    if len(primary_templates) != 1:
        raise Project01Gn00TwoHoleError("source primary template is missing")
    mate_steps = copy.deepcopy(primary_templates[0].get("mateSteps") or [])
    for step in mate_steps:
        if step.get("endpointRoleA") == "locating_hole":
            step["endpointRoleA"] = "primary_locating_hole"
        if step.get("endpointRoleB") == "locating_hole":
            step["endpointRoleB"] = "primary_locating_hole"
    mate_steps.append(
        {
            "mateName": "MCP_GRAPH_GN00_SECONDARY_AXIS",
            "mateType": 1,
            "mateTypeName": "swMateCONCENTRIC",
            "alignment": 1,
            "alignmentName": "swMateAlignANTI_ALIGNED",
            "endpointRoleA": "secondary_locating_hole",
            "endpointRoleB": "secondary_locating_hole",
        }
    )
    template_id = "GN00_to_JJ00_plane_two_hole_installation_v1"
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": (
            "Validate GN00 base-only one-plane/two-hole non-anchor installation."
        ),
        "ports": [moving_port, target_port],
        "connectionTemplates": [
            {
                "templateId": template_id,
                "purposes": ["installation"],
                "interfaceTypeA": interface_type,
                "interfaceTypeB": interface_type,
                "status": "candidate-cad-validation-required",
                "constraintEffect": {
                    "purpose": (
                        "Use one support plane and two independent axes on JJ00 "
                        "to locate rigid GN00 without SS00."
                    ),
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": mate_steps,
            }
        ],
    }

    graph = copy.deepcopy(source_graph)
    graph["Mates"] = [
        mate
        for mate in graph.get("Mates") or []
        if str(mate.get("MateName") or "") != "平行1"
    ]
    moving_endpoint = _endpoint(merged, moving_id)["Endpoint"]
    target_endpoint = _endpoint(merged, target_id)["Endpoint"]
    moving_endpoint["Index"] = 0
    target_endpoint["Index"] = 1
    new_mate = {
        "MateName": "MCP_GRAPH_GN00_SECONDARY_AXIS",
        "MateType": 1,
        "MateTypeName": "swMateCONCENTRIC",
        "Alignment": 1,
        "AlignmentName": "swMateAlignANTI_ALIGNED",
        "Distance": None,
        "Angle": None,
        "IsSuppressed": False,
        "Endpoints": [moving_endpoint, target_endpoint],
        "ModuleTokens": ["GN00", "JJ00"],
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
            "planId": "project01-add-GN00-base-only-two-hole-nonanchor-v1",
            "generatedMateNames": [mate["MateName"] for mate in graph["Mates"]],
            "constraintAssessment": {
                "sourceSemanticMateSetReproduced": False,
                "sourceAntiRotationProviderRemoved": "SS00",
                "fullyLocatesAddedComponent": "requires_cad_verification",
                "expectedResidualDof": 0,
                "caseAnchoredModuleTokens": [],
                "reason": (
                    "The source SS00 direction relation is replaced by one "
                    "unique physical secondary axis on JJ00."
                ),
            },
            "twoHoleCandidate": {
                "schemaVersion": SCHEMA,
                "discoveryDigest": discovery.get("discoveryDigest"),
                "prototypeGeometryUse": "candidate-screening-only",
                "runtimePoseAnchorAllowed": False,
                "secondaryAxis": candidate,
            },
        }
    )
    audit["connections"] = [
        {
            "connectionId": "GN00-installed-on-JJ00-plane-two-hole",
            "portAId": moving_port["portId"],
            "portBId": target_port["portId"],
            "interfaceTypeA": interface_type,
            "interfaceTypeB": interface_type,
            "templateId": template_id,
            "generatedMateNames": [step["mateName"] for step in mate_steps],
            "validationRelations": [],
            "constraintEffect": semantic["connectionTemplates"][0][
                "constraintEffect"
            ],
        }
    ]
    audit["residualDofBoundary"] = {
        "sourceDrivingMateCount": 3,
        "candidateDrivingMateCount": 3,
        "sourceProviderRoles": ["Base", "Transport"],
        "candidateProviderRoles": ["Base"],
        "expectedResidualDofWithoutAnchor": 0,
        "caseAnchorApplied": False,
        "leafPoseAnchorApplied": False,
        "candidateRequiresCadValidation": True,
    }
    graph = prepare_nonprototype_execution_graph(graph, target_module_token="GN00")

    selected_ids = {
        binding["endpointId"]
        for port in (moving_port, target_port)
        for binding in port["endpointBindings"]
    }
    endpoint_catalog = copy.deepcopy(merged)
    endpoint_catalog["Endpoints"] = [
        row
        for row in merged.get("Endpoints") or []
        if row.get("EndpointId") in selected_ids
    ]
    endpoint_catalog["EndpointCount"] = len(endpoint_catalog["Endpoints"])
    endpoint_catalog["CatalogMode"] = "project01_gn00_base_only_two_hole_candidate"

    summary = {
        "schemaVersion": SCHEMA,
        "status": "candidate_ready_for_nonanchor_cad_validation",
        "projectId": "project01",
        "targetModule": "GN00",
        "providerRolesBefore": ["Base", "Transport"],
        "providerRolesAfter": ["Base"],
        "drivingMateCount": 3,
        "expectedResidualDof": 0,
        "casePoseAnchorCount": 0,
        "leafPoseAnchorCount": 0,
        "prototypeUse": "bounded-datum-screening-only",
        "secondaryAxis": candidate,
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
