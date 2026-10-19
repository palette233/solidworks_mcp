"""Complete the Project03 AB00 external installation port from prototype mates.

The historical AB00 packet predated four-face Width-mate reconstruction.  It
therefore exported only the coincident and distance relations and closed the
remaining pose with a prototype anchor.  The current editable graph executor
supports Width mates, so this module upgrades the original three-relation
bundle into a non-anchored semantic-port candidate without re-guessing faces.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from .project03_incremental_work_packet import (
    AA00,
    AE00,
    AF00,
    _catalog_endpoint_id,
    _module,
    _pair_mates,
    normalize_project03_paths,
)
from .semantic_port_catalog import build_semantic_assembly_plan


AB00 = "FL9A24D063AB00"
BASE_TOKENS = (
    AA00,
    AF00,
    AE00,
    "FL9A24D063AD00",
    "FL9A24D063AI00",
    "FL9A24D063AG00",
    "FL9A24D063AH00",
    "FL9A24D063AJ00",
)


class Project03Ab00PortCompletionError(ValueError):
    pass


def _single_by_type(mates: list[dict[str, Any]], mate_type: str) -> dict[str, Any]:
    matches = [row for row in mates if row.get("MateTypeName") == mate_type]
    if len(matches) != 1:
        raise Project03Ab00PortCompletionError(
            f"AA00/AB00 expected one {mate_type} relation, found {len(matches)}."
        )
    return matches[0]


def _endpoints_for_token(mate: dict[str, Any], token: str) -> list[dict[str, Any]]:
    return [
        row
        for row in mate.get("Endpoints") or []
        if str(row.get("ModuleToken") or "").casefold() == token.casefold()
    ]


def _endpoint_id(
    catalog: dict[str, Any], mate: dict[str, Any], token: str, ordinal: int = 0
) -> str:
    matches = _endpoints_for_token(mate, token)
    if ordinal < 0 or ordinal >= len(matches):
        raise Project03Ab00PortCompletionError(
            f"Mate {mate.get('MateName')} has no endpoint {ordinal} for {token}."
        )
    return _catalog_endpoint_id(catalog, matches[ordinal])


def _distance_advanced_options() -> dict[str, Any]:
    return {
        "WidthConstraintType": None,
        "WidthPercentDistanceFromEnd": None,
        "WidthDistanceFromEnd": None,
        "WidthFlipDimension": None,
        "WidthEndpointIndices": [],
        "TabEndpointIndices": [],
        "SlotConstraint": None,
        "SlotDistance": None,
        "SlotPercent": None,
        "SlotFlipDirection": None,
        "DistanceFlipDimension": False,
        "SourceFeatureErrorCode": 0,
        "SourceFeatureIsWarning": False,
    }


def _width_advanced_options() -> dict[str, Any]:
    return {
        "WidthConstraintType": 0,
        "WidthPercentDistanceFromEnd": -1.0,
        "WidthDistanceFromEnd": -1.0,
        "WidthFlipDimension": False,
        "WidthEndpointIndices": [0, 1],
        "TabEndpointIndices": [2, 3],
        "SlotConstraint": None,
        "SlotDistance": None,
        "SlotPercent": None,
        "SlotFlipDirection": None,
        "DistanceFlipDimension": None,
        "SourceFeatureErrorCode": 0,
        "SourceFeatureIsWarning": False,
    }


def build_project03_ab00_complete_port_candidate(
    source_graph: dict[str, Any], prototype_assembly: Path
) -> dict[str, Any]:
    """Compile a complete, non-anchored AB00 semantic installation packet."""

    selected = {*BASE_TOKENS, AB00}
    graph, path_audit = normalize_project03_paths(
        source_graph, prototype_assembly, selected_tokens=selected
    )
    pair_mates = _pair_mates(graph, AA00, AB00)
    coincident = _single_by_type(pair_mates, "swMateCOINCIDENT")
    width = _single_by_type(pair_mates, "swMateWIDTH")
    distance = _single_by_type(pair_mates, "swMateDISTANCE")
    if len(coincident.get("Endpoints") or []) != 2:
        raise Project03Ab00PortCompletionError("AB00 coincident relation is not two-face.")
    if len(width.get("Endpoints") or []) != 4:
        raise Project03Ab00PortCompletionError("AB00 width relation is not four-face.")
    if len(distance.get("Endpoints") or []) != 2:
        raise Project03Ab00PortCompletionError("AB00 distance relation is not two-face.")
    if len(_endpoints_for_token(width, AA00)) != 2 or len(
        _endpoints_for_token(width, AB00)
    ) != 2:
        raise Project03Ab00PortCompletionError(
            "AB00 width relation does not contain two context and two tab faces."
        )

    coincident["MateName"] = "AB00_SUPPORT_COINCIDENT"
    width["MateName"] = "AB00_WIDTH_CENTER"
    distance["MateName"] = "AB00_X_OFFSET"
    catalog = build_face_endpoint_catalog_from_source_mates(
        graph,
        [coincident["MateName"], width["MateName"], distance["MateName"]],
    )
    modules = {token: deepcopy(_module(graph, token)) for token in selected}

    ab00_port = {
        "portId": "AB00.frame_installation_complete",
        "displayName": "AB00龙门完整安装端口",
        "moduleToken": AB00,
        "moduleHierarchyPath": modules[AB00]["HierarchyPath"],
        "category": "mechanical",
        "interfaceType": "project03_gantry_frame_complete_installation",
        "capabilities": ["installation", "gantry_support", "width_centering"],
        "aliases": ["AB00.frame_installation", "龙门完整安装接口"],
        "status": "prototype-derived-candidate",
        "endpointBindings": [
            {
                "role": "support_plane",
                "endpointId": _endpoint_id(catalog, coincident, AB00),
            },
            {
                "role": "height_offset",
                "endpointId": _endpoint_id(catalog, distance, AB00),
            },
            {
                "role": "width_tab_1",
                "endpointId": _endpoint_id(catalog, width, AB00, 0),
            },
            {
                "role": "width_tab_2",
                "endpointId": _endpoint_id(catalog, width, AB00, 1),
            },
        ],
        "evidence": [
            "项目03原型AA00/AB00三关系：重合25、宽度1、距离5；所有端点直接复用原型导出持久引用。"
        ],
    }
    aa00_port = {
        "portId": "AA00.ab00_installation_complete",
        "displayName": "AA00龙门完整承载端口",
        "moduleToken": AA00,
        "moduleHierarchyPath": modules[AA00]["HierarchyPath"],
        "category": "mechanical",
        "interfaceType": "project03_gantry_frame_complete_installation",
        "capabilities": ["installation", "gantry_support", "width_centering"],
        "aliases": ["AA00.ab00_installation", "龙门完整承载接口"],
        "status": "prototype-derived-candidate",
        "endpointBindings": [
            {
                "role": "support_plane",
                "endpointId": _endpoint_id(catalog, coincident, AA00),
            },
            {
                "role": "height_offset",
                "endpointId": _endpoint_id(catalog, distance, AA00),
            },
            {
                "role": "width_reference_1",
                "endpointId": _endpoint_id(catalog, width, AA00, 0),
            },
            {
                "role": "width_reference_2",
                "endpointId": _endpoint_id(catalog, width, AA00, 1),
            },
        ],
        "evidence": [
            "项目03原型AA00/AB00三关系：重合25、宽度1、距离5；所有端点直接复用原型导出持久引用。"
        ],
    }
    template_id = "AB00_to_AA00_complete_three_relation_installation"
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": (
            "Complete the historical AB00 partial port with the original four-face "
            "Width relation; candidate pending real-CAD non-anchor validation."
        ),
        "ports": [ab00_port, aa00_port],
        "connectionTemplates": [
            {
                "templateId": template_id,
                "purposes": ["installation"],
                "interfaceTypeA": "project03_gantry_frame_complete_installation",
                "interfaceTypeB": "project03_gantry_frame_complete_installation",
                "constraintEffect": {
                    "purpose": "Drive the complete prototype-derived AB00 installation bundle.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                    "residualDofPolicy": "closed_by_coincident_width_distance_bundle",
                    "drivingAuthorization": "candidate_pending_real_cad_validation",
                    "exactMateBundleRequired": True,
                },
                "mateSteps": [
                    {
                        "mateName": "AB00_SUPPORT_COINCIDENT",
                        "mateType": 0,
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": int(coincident.get("Alignment", 1)),
                        "alignmentName": coincident.get("AlignmentName"),
                        "endpointRoleA": "support_plane",
                        "endpointRoleB": "support_plane",
                    },
                    {
                        "mateName": "AB00_WIDTH_CENTER",
                        "mateType": 11,
                        "mateTypeName": "swMateWIDTH",
                        "alignment": int(width.get("Alignment", 1)),
                        "alignmentName": width.get("AlignmentName"),
                        "endpointRoles": [
                            {"side": "B", "role": "width_reference_1"},
                            {"side": "B", "role": "width_reference_2"},
                            {"side": "A", "role": "width_tab_1"},
                            {"side": "A", "role": "width_tab_2"},
                        ],
                        "advancedOptions": _width_advanced_options(),
                    },
                    {
                        "mateName": "AB00_X_OFFSET",
                        "mateType": 5,
                        "mateTypeName": "swMateDISTANCE",
                        "alignment": int(distance.get("Alignment", 0)),
                        "alignmentName": distance.get("AlignmentName"),
                        "endpointRoleA": "height_offset",
                        "endpointRoleB": "height_offset",
                        "distanceMeters": float(distance.get("Distance", 0.04)),
                        "advancedOptions": _distance_advanced_options(),
                    },
                ],
            }
        ],
    }
    base_graph = {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": len(BASE_TOKENS),
        "InterModuleMateCount": 0,
        "Modules": [modules[token] for token in BASE_TOKENS],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": list(BASE_TOKENS),
            "fixedAtKnownContextPoses": True,
            "purpose": "Reuse the closed Project03 AJ00 checkpoint as AB00 context.",
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project03-add-AB00-complete-nonanchor-v1",
        "baseModuleToken": AA00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": list(BASE_TOKENS),
        "caseAnchoredModuleTokens": [],
        "componentToAdd": modules[AB00],
        "connections": [
            {
                "connectionId": "AB00-installed-on-AA00-complete",
                "portAId": ab00_port["portId"],
                "portBId": aa00_port["portId"],
                "templateId": template_id,
            }
        ],
    }
    result = build_semantic_assembly_plan(base_graph, semantic, catalog, request)
    summary = {
        "schemaVersion": "project03-ab00-port-completion/v1",
        "success": True,
        "projectId": "project03",
        "moduleToken": AB00,
        "sourceMateTypes": [
            "swMateCOINCIDENT",
            "swMateWIDTH",
            "swMateDISTANCE",
        ],
        "endpointCount": catalog["EndpointCount"],
        "drivingMateCount": len(result["effectiveGraph"].get("Mates") or []),
        "caseAnchorUsed": bool(
            (result["effectiveGraph"].get("EditPolicy") or {}).get(
                "caseAnchoredModuleTokens"
            )
        ),
        "expectedResidualDof": 0,
        "pathRecoveryPassed": path_audit["allResolved"],
        "offlineCandidateReady": True,
        "realCadValidated": False,
        "knownLimits": [
            "WidthConstraintType=0 is inferred from the prototype centered Width geometry and must be confirmed by the real-CAD run.",
            "The candidate must pass deterministic non-source initial pose, save, close, reopen and pose comparison before release.",
        ],
    }
    return {
        "pathAudit": path_audit,
        "endpointCatalog": catalog,
        "semanticCatalog": semantic,
        "baseGraph": base_graph,
        "request": request,
        "patch": result["patch"],
        "effectiveGraph": result["effectiveGraph"],
        "summary": summary,
    }


def validate_project03_ab00_live_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate the bounded real-CAD gate before the port is catalog-visible."""

    tool = result.get("toolResult") or {}
    checks = {
        "runSucceeded": result.get("success") is True and tool.get("Success") is True,
        "independentComponentInserted": tool.get("IndependentComponentInserted") is True,
        "nonPrototypeInitialPose": tool.get("TargetCaseAnchored") is False,
        "threeMatesCreated": int(tool.get("RequestedMateCount") or 0) == 3
        and int(tool.get("CreatedMateCount") or 0) == 3,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "reopened": tool.get("Reopened") is True,
        "parametersMatchAfterReopen": tool.get("ReopenedMateParametersMatch") is True,
        "targetFullyConstrained": tool.get("TargetFullyConstrained") is True,
        "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True,
        "allMateVerificationsPassed": len(tool.get("MateVerifications") or []) == 3
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in tool.get("MateVerifications") or []
        ),
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise Project03Ab00PortCompletionError(
            "AB00 real-CAD validation failed: " + ", ".join(failed)
        )
    return {
        "schemaVersion": "project03-ab00-live-validation/v1",
        "success": True,
        "checks": checks,
        "durationSeconds": result.get("durationSeconds"),
        "phaseDurationsSeconds": tool.get("PhaseDurationsSeconds") or {},
        "outputAssemblyPath": result.get("outputAssemblyPath"),
    }


def finalize_project03_ab00_complete_port(
    semantic_catalog: dict[str, Any],
    summary: dict[str, Any],
    live_result: dict[str, Any],
    *,
    effective_graph_path: str,
    validation_evidence_path: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validation = validate_project03_ab00_live_result(live_result)
    semantic = deepcopy(semantic_catalog)
    for port in semantic.get("ports") or []:
        port["status"] = "real-cad-confirmed"
    template = (semantic.get("connectionTemplates") or [])[0]
    effect = template.setdefault("constraintEffect", {})
    effect["drivingAuthorization"] = "real_cad_validated_nonprototype_initial_pose"
    semantic["effectiveMateGraphPath"] = effective_graph_path
    semantic["validationEvidence"] = {
        "schemaVersion": validation["schemaVersion"],
        "path": validation_evidence_path,
        "checks": deepcopy(validation["checks"]),
    }
    finalized_summary = deepcopy(summary)
    finalized_summary["realCadValidated"] = True
    finalized_summary["offlineCandidateReady"] = True
    finalized_summary["liveValidation"] = validation
    finalized_summary["knownLimits"] = [
        "原型导出的三关系已通过非原型初始位姿、完全约束、保存关闭重开和参数复核。",
        "本轮未执行碰撞或B-rep；按当前主线它们不是端口发布前置条件。",
    ]
    return semantic, finalized_summary, validation
