"""Compile one compatible, unpublished interface pair into a CAD package.

The compiler consumes normalized mechanical-interface contracts rather than a
prototype top-level transform.  It is intentionally narrow: a pair must be
compatible, instantiate exactly one template, and still require its own CAD
release.  The resulting graph fixes only the selected base and places the
moving module from a deterministic non-source pose during execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import validate_contract_catalog


SCHEMA = "direct-interface-cad-validation-package/v1"
IDENTITY_TRANSFORM = [
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
    1.0, 0.0, 0.0, 0.0,
]


class DirectInterfaceValidationError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise DirectInterfaceValidationError("unsupported face endpoint catalog")
    result = {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId")
    }
    if len(result) != len(catalog.get("Endpoints") or []):
        raise DirectInterfaceValidationError("face endpoint ids are empty or duplicated")
    return result


def _graph_endpoint(
    row: dict[str, Any],
    *,
    index: int,
    module_token: str,
    module_hierarchy_path: str,
) -> dict[str, Any]:
    endpoint = copy.deepcopy(row.get("Endpoint") or {})
    relative = str(endpoint.get("RelativeLeafHierarchyPath") or "")
    if not relative:
        raise DirectInterfaceValidationError("endpoint has no relative leaf path")
    endpoint.update(
        {
            "Index": index,
            "ModuleToken": module_token,
            "ModuleHierarchyPath": module_hierarchy_path,
            "LeafHierarchyPath": f"{module_hierarchy_path}/{relative}",
        }
    )
    return endpoint


def compile_direct_interface_validation_package(
    *,
    contract_catalog: dict[str, Any],
    module_definition_id: str,
    slot_definition_id: str,
    module_face_catalog: dict[str, Any],
    slot_face_catalog: dict[str, Any],
    module_source_path: str | Path,
    slot_source_path: str | Path,
    base_wrapper_path: str | Path,
    module_hierarchy_path: str,
    slot_hierarchy_path: str,
) -> dict[str, Any]:
    """Create a non-prototype validation graph for one exact contract pair."""

    validate_contract_catalog(contract_catalog)
    matches = [
        row
        for row in contract_catalog.get("compatibilityMatrix") or []
        if row.get("moduleDefinitionId") == module_definition_id
        and row.get("slotDefinitionId") == slot_definition_id
        and row.get("compatible") is True
    ]
    if len(matches) != 1:
        raise DirectInterfaceValidationError(
            "exact pair does not resolve one compatible interface contract"
        )
    match = matches[0]
    if match.get("requiresNewPairCadValidation") is not True:
        raise DirectInterfaceValidationError(
            "exact pair is not an unpublished CAD-validation candidate"
        )
    if match.get("existingPairReleaseReusable") is True:
        raise DirectInterfaceValidationError("exact pair already has a reusable release")

    contracts = {
        str(row.get("contractId") or ""): row
        for row in contract_catalog.get("contracts") or []
    }
    module_contract = contracts.get(str(match.get("moduleContractId") or ""))
    slot_contract = contracts.get(str(match.get("slotContractId") or ""))
    templates = [
        row
        for row in contract_catalog.get("instantiatedTemplates") or []
        if row.get("matchId") == match.get("matchId")
    ]
    if not module_contract or not slot_contract or len(templates) != 1:
        raise DirectInterfaceValidationError(
            "candidate contracts or instantiated template are missing"
        )
    template = templates[0]

    module_bindings = {
        str(row.get("role") or ""): str(row.get("endpointId") or "")
        for row in module_contract.get("endpointBindings") or []
    }
    slot_bindings = {
        str(row.get("role") or ""): str(row.get("endpointId") or "")
        for row in slot_contract.get("endpointBindings") or []
    }
    required_module_roles = {
        str(step.get("endpointRoleA") or "") for step in template.get("mateSteps") or []
    }
    required_slot_roles = {
        str(step.get("endpointRoleB") or "") for step in template.get("mateSteps") or []
    }
    if (
        not required_module_roles
        or required_module_roles - set(module_bindings)
        or required_slot_roles - set(slot_bindings)
    ):
        raise DirectInterfaceValidationError("template roles do not resolve endpoints")

    module_endpoints = _endpoint_index(module_face_catalog)
    slot_endpoints = _endpoint_index(slot_face_catalog)
    module_token = str(module_contract.get("moduleToken") or "")
    slot_token = str(slot_contract.get("moduleToken") or "")
    if not module_token or not slot_token:
        raise DirectInterfaceValidationError("contract module tokens are missing")

    module_source = Path(module_source_path).resolve()
    slot_source = Path(slot_source_path).resolve()
    wrapper = Path(base_wrapper_path).resolve()
    for path in (module_source, slot_source, wrapper):
        if not path.is_file():
            raise FileNotFoundError(path)

    mates: list[dict[str, Any]] = []
    selected_endpoint_ids: list[str] = []
    selected_endpoint_rows: dict[str, dict[str, Any]] = {}
    for index, step in enumerate(template.get("mateSteps") or []):
        role_a = str(step.get("endpointRoleA") or "")
        role_b = str(step.get("endpointRoleB") or "")
        endpoint_a = module_bindings[role_a]
        endpoint_b = slot_bindings[role_b]
        if endpoint_a not in module_endpoints or endpoint_b not in slot_endpoints:
            raise DirectInterfaceValidationError(
                f"template endpoint cannot be recovered: {role_a}/{role_b}"
            )
        selected_endpoint_ids.extend((endpoint_a, endpoint_b))
        selected_endpoint_rows[endpoint_a] = copy.deepcopy(
            module_endpoints[endpoint_a]
        )
        selected_endpoint_rows[endpoint_b] = copy.deepcopy(
            slot_endpoints[endpoint_b]
        )
        mates.append(
            {
                "MateName": str(step["mateName"]),
                "MateType": int(step["mateType"]),
                "MateTypeName": str(step["mateTypeName"]),
                "Alignment": int(step["alignment"]),
                "AlignmentName": str(step["alignmentName"]),
                "Distance": step.get("distanceMeters"),
                "Angle": step.get("angleRadians"),
                "IsSuppressed": False,
                "Endpoints": [
                    _graph_endpoint(
                        module_endpoints[endpoint_a],
                        index=0,
                        module_token=module_token,
                        module_hierarchy_path=module_hierarchy_path,
                    ),
                    _graph_endpoint(
                        slot_endpoints[endpoint_b],
                        index=1,
                        module_token=slot_token,
                        module_hierarchy_path=slot_hierarchy_path,
                    ),
                ],
                "ModuleTokens": [module_token, slot_token],
                "ModuleHierarchyPaths": [
                    module_hierarchy_path,
                    slot_hierarchy_path,
                ],
                "IsBasicTwoFaceRebuildable": True,
                "RebuildRejectionReason": None,
                "MateId": f"mate:direct-interface:{match['matchId'].split('/')[-1]}:{index}",
            }
        )

    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": str(wrapper),
        "ModuleCount": 2,
        "InterModuleMateCount": len(mates),
        "Modules": [
            {
                "ModuleToken": slot_token,
                "Name": slot_hierarchy_path,
                "Path": str(slot_source),
                "HierarchyPath": slot_hierarchy_path,
                "SourceTransform": list(IDENTITY_TRANSFORM),
                "IsSuppressed": False,
                "SuppressionState": 2,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            },
            {
                "ModuleToken": module_token,
                "Name": module_hierarchy_path,
                "Path": str(module_source),
                "HierarchyPath": module_hierarchy_path,
                "SourceTransform": list(IDENTITY_TRANSFORM),
                "IsSuppressed": False,
                "SuppressionState": 2,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            },
        ],
        "Mates": mates,
        "EditPolicy": {
            "baseModuleToken": slot_token,
            "initialPlacementMode": "deterministic",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [slot_token],
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
            "sourceMateNamesToSuppress": [],
        },
        "SemanticAssemblyPlanAudit": {
            "planId": f"direct-interface-{match['matchId'].split('/')[-1]}",
            "addedComponentHierarchyPath": module_hierarchy_path,
            "generatedMateNames": [row["MateName"] for row in mates],
            "validationRelations": [],
            "executionMode": "candidate_cross_project_validation",
            "constraintAssessment": {
                "authority": "compatible-interface-contract-pending-exact-pair-cad",
                "fullyLocatesAddedComponent": True,
                "expectedResidualDof": 0,
                "caseAnchoredModuleTokens": [],
            },
        },
        "BaseGraphPolicy": {
            "moduleTokens": [slot_token],
            "source": "verified-base-wrapper",
        },
        "CandidateValidationPolicy": {
            "normalExecutionAuthorized": False,
            "collisionOrBrepRequired": False,
            "requiredCadChecks": [
                "moving module inserted from deterministic non-source pose",
                "all contract mates created without solver error",
                "moving module fully constrained",
                "save-close-reopen parameters match",
                "source module and base files unchanged",
            ],
        },
    }
    selected_endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "CatalogMode": "direct-interface-validation-selected-endpoints",
        "SourceMateFacesOnly": False,
        "ModuleCount": 2,
        "Modules": copy.deepcopy(graph["Modules"]),
        "EndpointCount": len(selected_endpoint_rows),
        "Endpoints": list(selected_endpoint_rows.values()),
    }
    graph_digest = _digest(graph)
    core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_nonprototype_cad_validation",
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": slot_definition_id,
        "matchId": match["matchId"],
        "templateId": template["templateId"],
        "interfaceFamily": match["interfaceFamily"],
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "normalExecutionAuthorized": False,
        "baseWrapperPath": str(wrapper),
        "baseWrapperSha256": _sha256(wrapper),
        "sourceModulePaths": {
            module_definition_id: str(module_source),
            slot_definition_id: str(slot_source),
        },
        "sourceModuleSha256": {
            module_definition_id: _sha256(module_source),
            slot_definition_id: _sha256(slot_source),
        },
        "selectedEndpointIds": selected_endpoint_ids,
        "instantiatedTemplate": copy.deepcopy(template),
        "effectiveMateGraph": graph,
        "effectiveMateGraphDigest": graph_digest,
        "selectedEndpointCatalog": selected_endpoint_catalog,
        "claimBoundary": (
            "This package proves only that one normalized interface contract can be "
            "compiled without prototype pose inheritance. Normal execution still requires "
            "a successful exact-pair CAD run and immutable release. Collision, B-rep and "
            "physical fastening remain outside this validation."
        ),
    }
    return {**core, "packageDigest": _digest(core)}
