"""Build an isolated global-catalog candidate for the WasteCup datum demo."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from .global_module_catalog import validate_global_module_catalog
from .semantic_port_catalog import validate_semantic_port_catalog


SCHEMA = "cross-project-wastecup-datum-catalog-package/v1"
LEGACY_TEMPLATE_ID = "P000_to_A600_cross_project_datum_placement_demo_v1"
INTERFACE_TYPE = "cross_project_wastecup_three_plane_datum"


class CrossProjectWasteCupDatumCatalogError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _definition(
    catalog: dict[str, Any], project_id: str, module_token: str
) -> dict[str, Any]:
    rows = [
        row
        for row in catalog.get("moduleDefinitions") or []
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == module_token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(rows) != 1:
        raise CrossProjectWasteCupDatumCatalogError(
            f"无法唯一定位{project_id}/{module_token}全局模组定义。"
        )
    return rows[0]


def _endpoint_rows(
    catalog: dict[str, Any], endpoint_ids: list[str]
) -> list[dict[str, Any]]:
    index = {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
    }
    missing = [value for value in endpoint_ids if value not in index]
    if missing:
        raise CrossProjectWasteCupDatumCatalogError(
            "面端点目录缺少：" + ", ".join(missing)
        )
    return [copy.deepcopy(index[value]) for value in endpoint_ids]


def _endpoint_evidence(role: str, row: dict[str, Any]) -> dict[str, Any]:
    endpoint = row.get("Endpoint") or {}
    return {
        "role": role,
        "endpointId": row.get("EndpointId"),
        "geometryClass": row.get("GeometryClass") or endpoint.get("SurfaceType"),
        "recoveryConfidence": row.get("RecoveryConfidence"),
        "relativeLeafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
        "bodyIndex": endpoint.get("BodyIndex"),
        "faceIndexInBody": endpoint.get("FaceIndexInBody"),
        "faceArea": endpoint.get("FaceArea"),
        "faceCenterLocal": endpoint.get("FaceCenterLocal"),
        "faceNormalLocal": endpoint.get("FaceNormalLocal"),
        "hasPersistentReference": bool(
            endpoint.get("SourceAssemblyPersistentReferenceBase64")
        ),
        "rolePortable": True,
        "portabilityReasons": [],
    }


def _global_port_id(definition_id: str, suffix: str) -> str:
    return f"{definition_id}::port/{suffix}/{_digest((definition_id, suffix))[:10]}"


def build_wastecup_datum_catalog_package(
    *,
    base_global_catalog: dict[str, Any],
    candidate_graph: dict[str, Any],
    candidate_audit: dict[str, Any],
    a600_endpoint_catalog: dict[str, Any] | None = None,
    context_endpoint_catalog: dict[str, Any] | None = None,
    p000_endpoint_catalog: dict[str, Any],
    semantic_catalog_path: str,
    endpoint_catalog_path: str,
    base_graph_path: str,
) -> dict[str, Any]:
    validate_global_module_catalog(base_global_catalog)
    if candidate_audit.get("schemaVersion") != (
        "cross-project-wastecup-datum-candidate/v1"
    ):
        raise CrossProjectWasteCupDatumCatalogError("候选审计版本不受支持。")
    if candidate_audit.get("status") != "ready_for_nonprototype_cad_validation":
        raise CrossProjectWasteCupDatumCatalogError("候选基准图未进入CAD验证状态。")
    target_project = str(candidate_audit.get("targetProjectId") or "").strip()
    base_token = str(candidate_audit.get("targetBaseToken") or "").strip()
    if not target_project or not base_token or not base_token.isalnum():
        raise CrossProjectWasteCupDatumCatalogError("候选审计缺少有效的目标项目或基座编号。")
    if context_endpoint_catalog is None:
        context_endpoint_catalog = a600_endpoint_catalog
    elif a600_endpoint_catalog is not None and context_endpoint_catalog != a600_endpoint_catalog:
        raise CrossProjectWasteCupDatumCatalogError("新旧基座端点目录参数不能指向不同内容。")
    if context_endpoint_catalog is None:
        raise CrossProjectWasteCupDatumCatalogError("缺少基座端点目录。")
    legacy_a600 = (target_project, base_token) == ("project02", "A600")
    mate_prefix = f"P000_{base_token}_DATUM"
    mate_names = [f"{mate_prefix}_{suffix}" for suffix in ("DISTANCE_1", "DISTANCE_2", "SUPPORT")]

    # Preserve legacy identities, but give the opt-in support-position recipe
    # its own template identity. Distances must come from the validated graph,
    # never from hard-coded defaults that silently discard an edited parameter.
    support_policy = candidate_graph.get("SupportPositionDemoPolicy") or {}
    support_demo = candidate_audit.get("mode") == "support_position_demo"
    graph_mates = {row.get("MateName"): row for row in candidate_graph.get("Mates") or []}
    alignments = []
    alignment_names = {0: "swMateAlignALIGNED", 1: "swMateAlignANTI_ALIGNED", 2: "swMateAlignCLOSEST"}
    for name, mate_type in zip(mate_names, (5, 5, 0)):
        mate = graph_mates.get(name) or {}
        alignment = mate.get("Alignment")
        if (
            mate.get("MateType") != mate_type
            or isinstance(alignment, bool)
            or not isinstance(alignment, int)
            or alignment not in alignment_names
            or mate.get("AlignmentName") not in (None, "", alignment_names[alignment])
        ):
            raise CrossProjectWasteCupDatumCatalogError("基准配合类型或对齐方向无效/不一致。")
        alignments.append(alignment)
    distances = []
    for name in mate_names[:2]:
        value = (graph_mates.get(name) or {}).get("Distance")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise CrossProjectWasteCupDatumCatalogError("距离配合必须包含有限非负的位置参数。")
        distances.append(value)
    legacy_template_id = (
        LEGACY_TEMPLATE_ID if legacy_a600
        else f"P000_to_{base_token}_cross_project_datum_placement_demo_v1"
    )
    if support_demo:
        parameters = support_policy.get("positionParametersMeters") or {}
        if not (
            support_policy.get("mode") == "support_position_demo"
            and support_policy.get("holePatternMatchRequired") is False
            and support_policy.get("actualFixationMethod") == "not_verified"
            and support_policy.get("directMechanicalCompatibilityClaim") is False
            and parameters == candidate_audit.get("positionParametersMeters")
            and parameters.get("longitudinal") == distances[0]
            and parameters.get("lateral") == distances[1]
            and parameters.get("supportGap") == 0
        ):
            raise CrossProjectWasteCupDatumCatalogError("支承定位Demo的参数或能力边界与执行图不一致。")
        legacy_template_id = f"P000_to_{base_token}_support_position_demo_v2_" + _digest(parameters)[:10]
    # Preserve published A600 identities for their original directions. A
    # changed direction must never silently reuse the same executable recipe.
    if alignments != [0, 0, 1]:
        legacy_template_id += "_alignment_" + _digest(alignments)[:10]

    roles = ["longitudinal_datum", "lateral_datum", "support_datum"]
    target_ids = list(candidate_audit.get("targetEndpointIds") or [])
    context_ids = list(candidate_audit.get("contextEndpointIds") or [])
    if len(target_ids) != 3 or len(context_ids) != 3:
        raise CrossProjectWasteCupDatumCatalogError("候选必须恰好包含两侧各三个基准端点。")
    p000_rows = _endpoint_rows(p000_endpoint_catalog, target_ids)
    context_rows = _endpoint_rows(context_endpoint_catalog, context_ids)
    endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "SourceAssemblyPath": candidate_graph.get("SourceAssemblyPath"),
        "CatalogMode": "cross-project-wastecup-datum-demo-endpoints-only",
        "EndpointCount": 6,
        "Endpoints": [*p000_rows, *context_rows],
    }

    p000_hierarchy = str((p000_rows[0].get("Endpoint") or {}).get("ModuleHierarchyPath") or "")
    context_hierarchy = str((context_rows[0].get("Endpoint") or {}).get("ModuleHierarchyPath") or "")
    p000_port_suffix = "" if legacy_a600 else f".{base_token.lower()}"
    ports = [
        {
            "portId": f"P000.cross_project_wastecup_datum{p000_port_suffix}",
            "displayName": "P000跨项目排胶杯三平面基准端口",
            "moduleToken": "P000",
            "moduleHierarchyPath": p000_hierarchy,
            "category": "mechanical",
            "interfaceType": INTERFACE_TYPE,
            "capabilities": ["installation", "datum_placement_demo"],
            "aliases": ["排胶杯基准定位端口"],
            "status": "confirmed",
            "portable": True,
            "endpointBindings": [
                {"role": role, "endpointId": endpoint_id}
                for role, endpoint_id in zip(roles, target_ids)
            ],
            "endpointEvidence": [
                _endpoint_evidence(role, row)
                for role, row in zip(roles, p000_rows)
            ],
            "projectId": "project05",
            "validationStatus": "candidate-awaiting-nonprototype-cad-validation",
        },
        {
            "portId": f"{base_token}.cross_project_wastecup_datum_slot",
            "displayName": f"{base_token}排胶杯三平面基准槽位",
            "moduleToken": base_token,
            "moduleHierarchyPath": context_hierarchy,
            "category": "mechanical",
            "interfaceType": INTERFACE_TYPE,
            "capabilities": ["installation", "datum_placement_demo"],
            "aliases": [f"{base_token}排胶杯基准定位槽位"],
            "status": "confirmed",
            "portable": True,
            "endpointBindings": [
                {"role": role, "endpointId": endpoint_id}
                for role, endpoint_id in zip(roles, context_ids)
            ],
            "endpointEvidence": [
                _endpoint_evidence(role, row)
                for role, row in zip(roles, context_rows)
            ],
            "projectId": target_project,
            "validationStatus": "candidate-awaiting-nonprototype-cad-validation",
        },
    ]
    steps = [
        {
            "mateName": mate_names[0],
            "mateType": 5,
            "mateTypeName": "swMateDISTANCE",
            "alignment": alignments[0],
            "alignmentName": alignment_names[alignments[0]],
            "distanceMeters": distances[0],
            "endpointRoleA": roles[0],
            "endpointRoleB": roles[0],
        },
        {
            "mateName": mate_names[1],
            "mateType": 5,
            "mateTypeName": "swMateDISTANCE",
            "alignment": alignments[1],
            "alignmentName": alignment_names[alignments[1]],
            "distanceMeters": distances[1],
            "endpointRoleA": roles[1],
            "endpointRoleB": roles[1],
        },
        {
            "mateName": mate_names[2],
            "mateType": 0,
            "mateTypeName": "swMateCOINCIDENT",
            "alignment": alignments[2],
            "alignmentName": alignment_names[alignments[2]],
            "endpointRoleA": roles[2],
            "endpointRoleB": roles[2],
        },
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project-global",
        "catalogPurpose": f"Project05 P000 to {target_project} {base_token} datum-placement demo candidate only.",
        "endpointCatalogPath": endpoint_catalog_path,
        "effectiveMateGraphPath": str(candidate_audit.get("effectiveGraphPath") or ""),
        "ports": ports,
        "connectionTemplates": [
            {
                "templateId": legacy_template_id,
                "purposes": ["installation", "datum_placement_demo"],
                "interfaceTypeA": INTERFACE_TYPE,
                "interfaceTypeB": INTERFACE_TYPE,
                "constraintEffect": {
                    "purpose": f"Locate P000 on {base_token} by three orthogonal planar datums.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                    "drivingAuthorization": "explicit_datum_placement_demo_candidate",
                    "cadValidationStatus": "not_yet_validated",
                    "directMechanicalInterfaceCompatible": False,
                },
                "mateSteps": steps,
            }
        ],
    }
    if support_demo:
        semantic_catalog["supportPositionDemoPolicy"] = copy.deepcopy(support_policy)
        semantic_catalog["connectionTemplates"][0]["constraintEffect"]["supportPositionDemoPolicy"] = copy.deepcopy(support_policy)
    validate_semantic_port_catalog(semantic_catalog, endpoint_catalog)

    # The generic packet executor needs both the fixed context module and the
    # independently inserted target module plus the requested mate bundle.
    # Removing P000 here made language compilation appear ready while the CAD
    # execution planner could not resolve its target token.  Keep the complete
    # two-module semantic graph, but continue to strip every pose anchor.
    base_graph = copy.deepcopy(candidate_graph)
    base_graph["CaseAnchor"] = None
    base_graph["TargetLeafPoseAnchors"] = []
    base_graph["BaseGraphPolicy"] = {
        **copy.deepcopy(candidate_graph.get("BaseGraphPolicy") or {}),
        "moduleTokens": [base_token],
        "caseAnchorAllowed": False,
        "prototypeTopLevelTargetPoseAllowed": False,
        "targetLeafPoseAnchorsAllowed": False,
        "executionGraphComplete": True,
    }

    result = copy.deepcopy(base_global_catalog)
    p000_definition = _definition(result, "project05", "P000")
    context_definition = _definition(result, target_project, base_token)
    global_p000_id = _global_port_id(
        p000_definition["moduleDefinitionId"],
        "p000-cross-project-wastecup-datum" + ("" if legacy_a600 else f"-{base_token.lower()}"),
    )
    global_context_id = _global_port_id(
        context_definition["moduleDefinitionId"], f"{base_token.lower()}-cross-project-wastecup-datum-slot"
    )
    provenance_common = {
        "projectId": "project-global",
        "semanticCatalogPath": semantic_catalog_path,
        "endpointCatalogPath": endpoint_catalog_path,
        "effectiveMateGraphPath": base_graph_path,
        "semanticCatalogDigest": _digest(semantic_catalog),
    }

    def global_port(
        local: dict[str, Any], definition: dict[str, Any], global_id: str
    ) -> dict[str, Any]:
        return {
            "globalPortId": global_id,
            "moduleDefinitionId": definition["moduleDefinitionId"],
            "displayName": local["displayName"],
            "description": "仅用于跨项目基准定位Demo，不证明直接机械接口兼容。",
            "category": "mechanical",
            "interfaceType": INTERFACE_TYPE,
            "capabilities": list(local["capabilities"]),
            "aliases": list(local["aliases"]),
            "portable": True,
            "portabilityReasons": [],
            "endpointEvidence": copy.deepcopy(local["endpointEvidence"]),
            "functionalGeometry": None,
            "provenance": [
                {
                    **provenance_common,
                    "portProjectId": local["projectId"],
                    "legacyPortId": local["portId"],
                    "moduleToken": local["moduleToken"],
                    "moduleHierarchyPath": local["moduleHierarchyPath"],
                    "status": local["validationStatus"],
                }
            ],
        }

    result.setdefault("semanticPorts", []).extend(
        [
            global_port(ports[0], p000_definition, global_p000_id),
            global_port(ports[1], context_definition, global_context_id),
        ]
    )
    for definition, port_id in (
        (p000_definition, global_p000_id),
        (context_definition, global_context_id),
    ):
        definition.setdefault("portIds", []).append(port_id)
        definition["portIds"] = sorted(set(definition["portIds"]))

    global_template_id = (
        f"template/project-global/p000-{base_token.lower()}-wastecup-datum-demo/"
        + _digest((global_p000_id, global_context_id, legacy_template_id))[:10]
    )
    result.setdefault("connectionTemplates", []).append(
        {
            "globalTemplateId": global_template_id,
            "legacyTemplateId": legacy_template_id,
            "purposes": ["installation", "datum_placement_demo"],
            "interfaceTypeA": INTERFACE_TYPE,
            "interfaceTypeB": INTERFACE_TYPE,
            "candidatePortIdsA": [global_p000_id],
            "candidatePortIdsB": [global_context_id],
            "constraintEffect": copy.deepcopy(
                semantic_catalog["connectionTemplates"][0]["constraintEffect"]
            ),
            "mateSteps": copy.deepcopy(steps),
            "provenance": provenance_common,
        }
    )
    result.setdefault("compatibility", []).append(
        {
            "portAId": global_p000_id,
            "portBId": global_context_id,
            "globalTemplateId": global_template_id,
            "purpose": "installation",
            "directional": True,
            "portableForTemplate": True,
        }
    )
    if not any(row.get("path") == semantic_catalog_path for row in result.get("sourceCatalogs") or []):
        result.setdefault("sourceCatalogs", []).append(
            {
                "path": semantic_catalog_path,
                "projectId": "project-global",
                "status": "datum-placement-demo-candidate",
            }
        )
    result["semanticPorts"] = sorted(
        result["semanticPorts"], key=lambda row: str(row.get("globalPortId") or "")
    )
    result["connectionTemplates"] = sorted(
        result["connectionTemplates"], key=lambda row: str(row.get("globalTemplateId") or "")
    )
    result["compatibility"] = sorted(
        result["compatibility"],
        key=lambda row: (
            str(row.get("portAId") or ""),
            str(row.get("portBId") or ""),
            str(row.get("globalTemplateId") or ""),
        ),
    )
    result["summary"] = {
        **(result.get("summary") or {}),
        "moduleDefinitionCount": len(result.get("moduleDefinitions") or []),
        "semanticPortCount": len(result.get("semanticPorts") or []),
        "portablePortCount": sum(
            row.get("portable") is True for row in result.get("semanticPorts") or []
        ),
        "connectionTemplateCount": len(result.get("connectionTemplates") or []),
        "templateCombinationCount": len(result.get("templateCombinations") or []),
        "compatibilityCount": len(result.get("compatibility") or []),
        "blockerCount": len(result.get("blockers") or []),
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return {
        "schemaVersion": SCHEMA,
        "semanticCatalog": semantic_catalog,
        "endpointCatalog": endpoint_catalog,
        "baseGraph": base_graph,
        "candidateGlobalCatalog": result,
        "globalTemplateId": global_template_id,
        "globalPortIds": [global_p000_id, global_context_id],
    }

