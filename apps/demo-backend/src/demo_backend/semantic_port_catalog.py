"""Resolve semantic assembly ports into concrete CAD endpoints and mate bundles.

A semantic port describes *how* a module can connect: endpoint roles, stable
face/edge/point selectors, and the mate bundle expected to close external
degrees of freedom.  A port proves neither process suitability nor collision
safety; those are separate validation layers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from .face_endpoint_catalog import FaceEndpointCatalogError, select_face_endpoint
from .mate_graph_edit import MateGraphEditError, compile_mate_graph_patch


SEMANTIC_PORT_SCHEMA = "semantic-port-catalog/v1"
SEMANTIC_CONNECTION_SCHEMA = "semantic-connection-request/v1"
SEMANTIC_ASSEMBLY_PLAN_SCHEMA = "semantic-assembly-plan/v1"
PORT_CATEGORIES = {"mechanical", "functional", "spatial"}


class SemanticPortCatalogError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _ports(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("schemaVersion") != SEMANTIC_PORT_SCHEMA:
        raise SemanticPortCatalogError(
            f"Unsupported semantic port catalog schema '{catalog.get('schemaVersion')}'."
        )
    ports = catalog.get("ports")
    if not isinstance(ports, list):
        raise SemanticPortCatalogError("Semantic port catalog must contain a ports array.")
    ids = [str(item.get("portId") or "").strip() for item in ports]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SemanticPortCatalogError("portId values must be unique and non-empty.")
    return ports


def _templates(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    templates = catalog.get("connectionTemplates")
    if not isinstance(templates, list):
        raise SemanticPortCatalogError(
            "Semantic port catalog must contain a connectionTemplates array."
        )
    ids = [str(item.get("templateId") or "").strip() for item in templates]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SemanticPortCatalogError("templateId values must be unique and non-empty.")
    return templates


def select_semantic_port(catalog: dict[str, Any], port_id: str) -> dict[str, Any]:
    matches = [item for item in _ports(catalog) if item.get("portId") == port_id]
    if len(matches) != 1:
        raise SemanticPortCatalogError(
            f"portId '{port_id}' resolved to {len(matches)} ports; expected exactly one."
        )
    return matches[0]


def validate_semantic_port_catalog(
    catalog: dict[str, Any], endpoint_catalog: dict[str, Any]
) -> dict[str, Any]:
    ports = _ports(catalog)
    templates = _templates(catalog)
    warnings: list[str] = []
    endpoint_use: dict[str, list[str]] = {}
    for port in ports:
        category = str(port.get("category") or "")
        if category not in PORT_CATEGORIES:
            raise SemanticPortCatalogError(
                f"Port '{port.get('portId')}' has unsupported category '{category}'."
            )
        module_token = str(port.get("moduleToken") or "").strip()
        module_path = str(port.get("moduleHierarchyPath") or "").strip()
        interface_type = str(port.get("interfaceType") or "").strip()
        if not module_token or not module_path or not interface_type:
            raise SemanticPortCatalogError(
                f"Port '{port.get('portId')}' requires moduleToken, moduleHierarchyPath, and interfaceType."
            )
        bindings = port.get("endpointBindings")
        if not isinstance(bindings, list) or not bindings:
            raise SemanticPortCatalogError(
                f"Port '{port.get('portId')}' requires endpointBindings."
            )
        roles: set[str] = set()
        for binding in bindings:
            role = str(binding.get("role") or "").strip()
            endpoint_id = str(binding.get("endpointId") or "").strip()
            if not role or role in roles or not endpoint_id:
                raise SemanticPortCatalogError(
                    f"Port '{port.get('portId')}' has an invalid or duplicate endpoint role."
                )
            roles.add(role)
            try:
                endpoint_entry = select_face_endpoint(endpoint_catalog, endpoint_id)
            except FaceEndpointCatalogError as exc:
                raise SemanticPortCatalogError(str(exc)) from exc
            endpoint = endpoint_entry.get("Endpoint") or {}
            if str(endpoint.get("ModuleToken") or "").casefold() != module_token.casefold():
                raise SemanticPortCatalogError(
                    f"Port '{port.get('portId')}' endpoint '{endpoint_id}' belongs to a different module."
                )
            if str(endpoint.get("ModuleHierarchyPath") or "").casefold() != module_path.casefold():
                raise SemanticPortCatalogError(
                    f"Port '{port.get('portId')}' endpoint '{endpoint_id}' belongs to a different module occurrence."
                )
            endpoint_use.setdefault(endpoint_id, []).append(str(port["portId"]))
        if str(port.get("status") or "provisional") != "confirmed":
            warnings.append(f"Port '{port['portId']}' is provisional and requires engineering review.")

    known_types = {str(item.get("interfaceType") or "") for item in ports}
    for template in templates:
        type_a = str(template.get("interfaceTypeA") or "")
        type_b = str(template.get("interfaceTypeB") or "")
        if type_a not in known_types or type_b not in known_types:
            raise SemanticPortCatalogError(
                f"Template '{template.get('templateId')}' references an unknown interface type."
            )
        steps = template.get("mateSteps")
        if not isinstance(steps, list) or not steps:
            raise SemanticPortCatalogError(
                f"Template '{template.get('templateId')}' requires mateSteps."
            )
        for step in steps:
            mate_type = int(step.get("mateType", -1))
            if mate_type not in {0, 1, 2, 3, 4, 5, 6, 11, 21}:
                raise SemanticPortCatalogError(
                    f"Template '{template.get('templateId')}' has an unsupported mate type."
                )
            endpoint_roles = step.get("endpointRoles")
            if endpoint_roles is None:
                endpoint_roles = [
                    {"side": "A", "role": step.get("endpointRoleA")},
                    {"side": "B", "role": step.get("endpointRoleB")},
                ]
            expected_count = 4 if mate_type == 11 else 2
            if not isinstance(endpoint_roles, list) or len(endpoint_roles) != expected_count:
                raise SemanticPortCatalogError(
                    f"Template '{template.get('templateId')}' mate type {mate_type} requires "
                    f"{expected_count} ordered endpoint roles."
                )
            for endpoint_role in endpoint_roles:
                if (
                    not isinstance(endpoint_role, dict)
                    or str(endpoint_role.get("side") or "").upper() not in {"A", "B"}
                    or not str(endpoint_role.get("role") or "").strip()
                ):
                    raise SemanticPortCatalogError(
                        f"Template '{template.get('templateId')}' contains an invalid endpoint role."
                    )
            application_mode = str(step.get("applicationMode") or "driving").strip()
            if application_mode not in {"driving", "validate_only"}:
                raise SemanticPortCatalogError(
                    f"Template '{template.get('templateId')}' has unsupported applicationMode "
                    f"'{application_mode}'."
                )
            if application_mode == "validate_only" and mate_type not in {5, 6}:
                raise SemanticPortCatalogError(
                    "validate_only currently supports distance and angle relations only."
                )
            if mate_type == 11:
                advanced = step.get("advancedOptions") or {}
                if (
                    advanced.get("WidthConstraintType") is None
                    or list(advanced.get("WidthEndpointIndices") or []) != [0, 1]
                    or list(advanced.get("TabEndpointIndices") or []) != [2, 3]
                ):
                    raise SemanticPortCatalogError(
                        f"Width step in template '{template.get('templateId')}' requires ordered "
                        "width/tab endpoint indices and WidthConstraintType."
                    )
            if mate_type == 21 and (step.get("advancedOptions") or {}).get(
                "SlotConstraint"
            ) is None:
                raise SemanticPortCatalogError(
                    f"Slot step in template '{template.get('templateId')}' requires "
                    "SlotConstraint in advancedOptions."
                )

    reused = {key: value for key, value in endpoint_use.items() if len(value) > 1}
    if reused:
        warnings.append(
            "Some geometric endpoints are intentionally exposed by more than one semantic port: "
            + ", ".join(sorted(reused))
        )
    return {
        "success": True,
        "schemaVersion": SEMANTIC_PORT_SCHEMA,
        "projectId": catalog.get("projectId"),
        "portCount": len(ports),
        "connectionTemplateCount": len(templates),
        "warnings": warnings,
        "catalogSha256": _digest(catalog),
        "endpointCatalogSha256": _digest(endpoint_catalog),
    }


def _binding_map(port: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["role"]): str(item["endpointId"])
        for item in port.get("endpointBindings") or []
    }


def _ordered_endpoint_ids(
    step: dict[str, Any], bindings_a: dict[str, str], bindings_b: dict[str, str], index: int
) -> list[str]:
    endpoint_roles = step.get("endpointRoles")
    if endpoint_roles is None:
        endpoint_roles = [
            {"side": "A", "role": step.get("endpointRoleA")},
            {"side": "B", "role": step.get("endpointRoleB")},
        ]
    result: list[str] = []
    for endpoint_role in endpoint_roles:
        side = str(endpoint_role.get("side") or "").upper()
        role = str(endpoint_role.get("role") or "")
        bindings = bindings_a if side == "A" else bindings_b
        if role not in bindings:
            raise SemanticPortCatalogError(
                f"Template step {index} cannot resolve endpoint role '{side}.{role}'."
            )
        result.append(bindings[role])
    return result


def _connection_operations(
    semantic_catalog: dict[str, Any], request: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    connection_id = str(request.get("connectionId") or "").strip()
    if not connection_id:
        raise SemanticPortCatalogError("connectionId must not be empty.")
    port_a = select_semantic_port(semantic_catalog, str(request.get("portAId") or ""))
    port_b = select_semantic_port(semantic_catalog, str(request.get("portBId") or ""))
    if str(port_a.get("moduleHierarchyPath")).casefold() == str(
        port_b.get("moduleHierarchyPath")
    ).casefold():
        raise SemanticPortCatalogError("A semantic connection must join two module occurrences.")
    template, reversed_template = _select_template(
        semantic_catalog, str(request.get("templateId") or ""), port_a, port_b
    )
    if reversed_template:
        port_a, port_b = port_b, port_a
    bindings_a = _binding_map(port_a)
    bindings_b = _binding_map(port_b)
    parameters = request.get("parameters") or {}
    operations: list[dict[str, Any]] = []
    mate_names: list[str] = []
    validation_relations: list[dict[str, Any]] = []
    for index, step in enumerate(template.get("mateSteps") or []):
        endpoint_ids = _ordered_endpoint_ids(step, bindings_a, bindings_b, index)
        mate_type = int(step["mateType"])
        distance = step.get("distanceMeters")
        angle = step.get("angleRadians")
        if mate_type == 5 and "distanceMeters" in parameters:
            distance = float(parameters["distanceMeters"])
        if mate_type == 6 and "angleDegrees" in parameters:
            angle = math.radians(float(parameters["angleDegrees"]))
        if mate_type == 5 and (
            distance is None
            or not math.isfinite(float(distance))
            or float(distance) < 0
        ):
            raise SemanticPortCatalogError(
                "Distance mate requires a finite non-negative distanceMeters."
            )
        if mate_type == 6 and (angle is None or not math.isfinite(float(angle))):
            raise SemanticPortCatalogError("Angle mate requires a finite angle.")
        mate_name = str(step.get("mateName") or f"{connection_id}_{index + 1}")
        application_mode = str(step.get("applicationMode") or "driving")
        if application_mode == "validate_only":
            validation_relations.append(
                {
                    "relationName": mate_name,
                    "relationType": mate_type,
                    "relationTypeName": str(step.get("mateTypeName") or ""),
                    "endpointIds": endpoint_ids,
                    "expectedDistanceMeters": distance,
                    "expectedAngleRadians": angle,
                    "tolerance": copy.deepcopy(step.get("tolerance") or {}),
                    "status": "requires_cad_measurement",
                }
            )
            continue
        mate_names.append(mate_name)
        mate = {
            "MateName": mate_name,
            "MateType": mate_type,
            "MateTypeName": str(step.get("mateTypeName") or ""),
            "Alignment": int(step.get("alignment", 0)),
            "AlignmentName": str(
                step.get("alignmentName") or "swMateAlignALIGNED"
            ),
            "Distance": distance,
            "Angle": angle,
            "IsSuppressed": False,
        }
        if step.get("advancedOptions") is not None:
            mate["AdvancedOptions"] = copy.deepcopy(step["advancedOptions"])
        operations.append(
            {"operation": "addMate", "endpointIds": endpoint_ids, "mate": mate}
        )
    return operations, {
        "connectionId": connection_id,
        "portAId": port_a["portId"],
        "portBId": port_b["portId"],
        "interfaceTypeA": port_a["interfaceType"],
        "interfaceTypeB": port_b["interfaceType"],
        "templateId": template["templateId"],
        "generatedMateNames": mate_names,
        "validationRelations": validation_relations,
        "constraintEffect": copy.deepcopy(template.get("constraintEffect") or {}),
    }


def _select_template(
    catalog: dict[str, Any], template_id: str, port_a: dict[str, Any], port_b: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    matches = [item for item in _templates(catalog) if item.get("templateId") == template_id]
    if len(matches) != 1:
        raise SemanticPortCatalogError(
            f"templateId '{template_id}' resolved to {len(matches)} templates; expected exactly one."
        )
    template = matches[0]
    type_a = str(port_a.get("interfaceType") or "")
    type_b = str(port_b.get("interfaceType") or "")
    direct = type_a == template.get("interfaceTypeA") and type_b == template.get("interfaceTypeB")
    reverse = type_a == template.get("interfaceTypeB") and type_b == template.get("interfaceTypeA")
    if not direct and not reverse:
        raise SemanticPortCatalogError(
            f"Template '{template_id}' is incompatible with '{type_a}' and '{type_b}'."
        )
    return template, not direct and reverse


def _expand_validation_relations(
    relations: list[dict[str, Any]], endpoint_catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach recoverable face payloads to non-driving validation relations."""

    expanded: list[dict[str, Any]] = []
    for relation in relations:
        copied = copy.deepcopy(relation)
        endpoints: list[dict[str, Any]] = []
        for index, endpoint_id in enumerate(copied.get("endpointIds") or []):
            try:
                entry = select_face_endpoint(endpoint_catalog, str(endpoint_id))
            except FaceEndpointCatalogError as exc:
                raise SemanticPortCatalogError(str(exc)) from exc
            endpoint = copy.deepcopy(entry.get("Endpoint") or {})
            endpoint["Index"] = index
            endpoints.append(endpoint)
        copied["endpoints"] = endpoints
        expanded.append(copied)
    return expanded


def build_semantic_connection_patch(
    source_graph: dict[str, Any],
    semantic_catalog: dict[str, Any],
    endpoint_catalog: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    """Compile a port-level connection request into an executable editable mate graph."""

    validation = validate_semantic_port_catalog(semantic_catalog, endpoint_catalog)
    if request.get("schemaVersion") != SEMANTIC_CONNECTION_SCHEMA:
        raise SemanticPortCatalogError(
            f"Unsupported semantic connection schema '{request.get('schemaVersion')}'."
        )
    connection_operations, connection_audit = _connection_operations(
        semantic_catalog, request
    )
    operations: list[dict[str, Any]] = []
    component = request.get("componentToAdd")
    existing_paths = {
        str(item.get("HierarchyPath") or "").casefold()
        for item in source_graph.get("Modules") or []
    }
    target_new_path = str((component or {}).get("HierarchyPath") or "").casefold()
    if component is not None:
        if not isinstance(component, dict):
            raise SemanticPortCatalogError("componentToAdd must be an object.")
        if target_new_path in existing_paths:
            raise SemanticPortCatalogError(
                f"componentToAdd already exists in the source graph: {component.get('HierarchyPath')}"
            )
        operations.append({"operation": "addModule", "module": copy.deepcopy(component)})
    operations.extend(connection_operations)

    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "baseModuleToken": str(request.get("baseModuleToken") or "A600"),
        "initialPlacementMode": str(request.get("initialPlacementMode") or "deterministic"),
        "fixedContextModuleTokens": copy.deepcopy(
            request.get("fixedContextModuleTokens") or []
        ),
        "caseAnchoredModuleTokens": copy.deepcopy(
            request.get("caseAnchoredModuleTokens") or []
        ),
        "operations": operations,
        "semanticConnection": copy.deepcopy(connection_audit),
    }
    try:
        effective = compile_mate_graph_patch(source_graph, patch, endpoint_catalog)
    except MateGraphEditError as exc:
        raise SemanticPortCatalogError(str(exc)) from exc
    effective["SemanticPortProvenance"] = {
        "catalogSchemaVersion": semantic_catalog["schemaVersion"],
        "catalogSha256": _digest(semantic_catalog),
        "endpointCatalogSha256": _digest(endpoint_catalog),
    }
    effective["SemanticConnectionAudit"] = {
        "requestSha256": _digest(request),
        **copy.deepcopy(connection_audit),
        "validationRelations": _expand_validation_relations(
            list(connection_audit.get("validationRelations") or []),
            endpoint_catalog,
        ),
        "addedComponentHierarchyPath": (component or {}).get("HierarchyPath"),
        "executionMode": "isolated_rebuild_from_augmented_graph",
        "warnings": validation["warnings"],
    }
    return {
        "success": True,
        "validation": validation,
        "request": copy.deepcopy(request),
        "patch": patch,
        "effectiveGraph": effective,
        "summary": {
            "connectionId": connection_audit["connectionId"],
            "portAId": connection_audit["portAId"],
            "portBId": connection_audit["portBId"],
            "addedComponent": (component or {}).get("HierarchyPath"),
            "generatedMateCount": len(connection_audit["generatedMateNames"]),
            "effectiveModuleCount": effective["ModuleCount"],
            "effectiveMateCount": effective["InterModuleMateCount"],
            "executionMode": "isolated_rebuild_from_augmented_graph",
            "constraintEffect": copy.deepcopy(connection_audit["constraintEffect"]),
        },
    }


def build_semantic_assembly_plan(
    source_graph: dict[str, Any],
    semantic_catalog: dict[str, Any],
    endpoint_catalog: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    """Compile one added module plus all of its semantic connections in one transaction."""

    validation = validate_semantic_port_catalog(semantic_catalog, endpoint_catalog)
    if request.get("schemaVersion") != SEMANTIC_ASSEMBLY_PLAN_SCHEMA:
        raise SemanticPortCatalogError(
            f"Unsupported semantic assembly plan schema '{request.get('schemaVersion')}'."
        )
    plan_id = str(request.get("planId") or "").strip()
    if not plan_id:
        raise SemanticPortCatalogError("planId must not be empty.")
    component = request.get("componentToAdd")
    if not isinstance(component, dict):
        raise SemanticPortCatalogError("componentToAdd must be an object.")
    new_path = str(component.get("HierarchyPath") or "").strip()
    new_token = str(component.get("ModuleToken") or "").strip()
    if not new_path or not new_token:
        raise SemanticPortCatalogError(
            "componentToAdd requires HierarchyPath and ModuleToken."
        )
    existing_paths = {
        str(item.get("HierarchyPath") or "").casefold()
        for item in source_graph.get("Modules") or []
    }
    if new_path.casefold() in existing_paths:
        raise SemanticPortCatalogError(
            f"componentToAdd already exists in the source graph: {new_path}"
        )
    connections = request.get("connections")
    if not isinstance(connections, list) or not connections:
        raise SemanticPortCatalogError("connections must contain at least one connection.")

    operations: list[dict[str, Any]] = [
        {"operation": "addModule", "module": copy.deepcopy(component)}
    ]
    audits: list[dict[str, Any]] = []
    all_mate_names: list[str] = []
    for connection in connections:
        if not isinstance(connection, dict):
            raise SemanticPortCatalogError("Every connection must be an object.")
        connection_operations, audit = _connection_operations(
            semantic_catalog, connection
        )
        connected_ports = [
            select_semantic_port(semantic_catalog, audit["portAId"]),
            select_semantic_port(semantic_catalog, audit["portBId"]),
        ]
        if new_path.casefold() not in {
            str(port.get("moduleHierarchyPath") or "").casefold()
            for port in connected_ports
        }:
            raise SemanticPortCatalogError(
                f"Connection '{audit['connectionId']}' does not reference the added module."
            )
        duplicate_names = set(all_mate_names) & set(audit["generatedMateNames"])
        if duplicate_names:
            raise SemanticPortCatalogError(
                "Generated mate names must be unique across connections: "
                + ", ".join(sorted(duplicate_names))
            )
        all_mate_names.extend(audit["generatedMateNames"])
        operations.extend(connection_operations)
        audits.append(audit)

    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "baseModuleToken": str(request.get("baseModuleToken") or "A600"),
        "initialPlacementMode": str(
            request.get("initialPlacementMode") or "deterministic"
        ),
        "fixedContextModuleTokens": copy.deepcopy(
            request.get("fixedContextModuleTokens") or []
        ),
        "caseAnchoredModuleTokens": copy.deepcopy(
            request.get("caseAnchoredModuleTokens") or []
        ),
        "operations": operations,
        "semanticAssemblyPlan": {
            "planId": plan_id,
            "addedModuleToken": new_token,
            "connectionIds": [item["connectionId"] for item in audits],
        },
    }
    try:
        effective = compile_mate_graph_patch(source_graph, patch, endpoint_catalog)
    except MateGraphEditError as exc:
        raise SemanticPortCatalogError(str(exc)) from exc
    effective["SemanticPortProvenance"] = {
        "catalogSchemaVersion": semantic_catalog["schemaVersion"],
        "catalogSha256": _digest(semantic_catalog),
        "endpointCatalogSha256": _digest(endpoint_catalog),
    }
    case_anchored_tokens = copy.deepcopy(
        effective["EditPolicy"].get("caseAnchoredModuleTokens") or []
    )
    target_is_case_anchored = new_token.casefold() in {
        str(value).casefold() for value in case_anchored_tokens
    }
    effective["SemanticAssemblyPlanAudit"] = {
        "requestSha256": _digest(request),
        "planId": plan_id,
        "addedComponentHierarchyPath": new_path,
        "connections": copy.deepcopy(audits),
        "generatedMateNames": all_mate_names,
        "validationRelations": _expand_validation_relations(
            [
                relation
                for audit in audits
                for relation in audit.get("validationRelations") or []
            ],
            endpoint_catalog,
        ),
        "executionMode": "isolated_rebuild_from_augmented_graph",
        "constraintAssessment": {
            "sourceSemanticMateSetReproduced": True,
            "fullyLocatesAddedComponent": (
                "case_anchor_requires_cad_verification"
                if target_is_case_anchored
                else "requires_cad_verification"
            ),
            "reason": (
                "The source installation mate set is represented. The explicitly declared "
                "project-case pose anchor closes the source mate set's documented residual "
                "degree of freedom and must be checked after CAD reopen."
                if target_is_case_anchored
                else "The source installation mate set is represented, but actual residual "
                "degrees of freedom must be measured after a deterministic CAD rebuild."
            ),
            "caseAnchoredModuleTokens": case_anchored_tokens,
        },
        "warnings": validation["warnings"],
        "cadVerificationEvidence": copy.deepcopy(
            request.get("cadVerificationEvidence") or {}
        ),
    }
    return {
        "success": True,
        "validation": validation,
        "request": copy.deepcopy(request),
        "patch": patch,
        "effectiveGraph": effective,
        "summary": {
            "planId": plan_id,
            "addedComponent": new_path,
            "connectionCount": len(audits),
            "generatedMateCount": len(all_mate_names),
            "generatedMateNames": all_mate_names,
            "validationRelationCount": sum(
                len(item.get("validationRelations") or []) for item in audits
            ),
            "effectiveModuleCount": effective["ModuleCount"],
            "effectiveMateCount": effective["InterModuleMateCount"],
            "initialPlacementMode": effective["EditPolicy"]["initialPlacementMode"],
            "fixedContextModuleTokens": copy.deepcopy(
                effective["EditPolicy"].get("fixedModuleTokens") or []
            ),
            "caseAnchoredModuleTokens": case_anchored_tokens,
            "constraintAssessment": copy.deepcopy(
                effective["SemanticAssemblyPlanAudit"]["constraintAssessment"]
            ),
            "cadVerifiedFullyConstrained": bool(
                (request.get("cadVerificationEvidence") or {}).get(
                    "fullyConstrained"
                )
            ),
        },
    }
