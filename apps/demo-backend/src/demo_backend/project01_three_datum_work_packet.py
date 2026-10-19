"""Reusable three-datum work-packet builder for Project01 rigid modules."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from .project01_incremental_work_packet import (
    HL00,
    JJ00,
    _catalog_endpoint_id,
    _endpoint,
    _file_index,
    _module,
    _pair_mates,
    _relocate,
    _sha256,
)
from .semantic_port_catalog import build_semantic_assembly_plan


def build_project01_three_datum_work_packet(
    *,
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
    target_token: str,
    prior_context_tokens: list[str],
    canonical_coincident_name: str,
    canonical_concentric_names_by_sorted_axis: list[str],
    sort_axis: int,
    expected_hole_spacing_meters: float,
    interface_type: str,
    target_port_id: str,
    base_port_id: str,
    template_id: str,
    target_display_name: str,
    base_display_name: str,
    capabilities: list[str],
    step_id: str,
    extra_limits: list[str] | None = None,
) -> dict[str, Any]:
    prototype = prototype_assembly.resolve()
    if not prototype.is_file():
        raise FileNotFoundError(prototype)
    if JJ00 not in prior_context_tokens or target_token in prior_context_tokens:
        raise ValueError("Prior context must contain JJ00 and must not contain the target")
    graph = copy.deepcopy(source_graph)
    graph["SourceAssemblyPath"] = str(prototype)
    selected = set(prior_context_tokens) | {target_token}
    index = _file_index(prototype.parent)
    audit_rows: list[dict[str, Any]] = []
    for module in graph.get("Modules", []):
        if str(module.get("ModuleToken")) in selected:
            module["Path"], audit = _relocate(
                str(module.get("Path") or ""), index, f"module:{module.get('ModuleToken')}"
            )
            audit_rows.append(audit)
    module_roots = {
        str(module.get("ModuleToken")): Path(str(module["Path"])).resolve().parent
        for module in graph.get("Modules", [])
        if str(module.get("ModuleToken")) in selected
    }
    mates = _pair_mates(graph, JJ00, target_token)
    coincident = [row for row in mates if row.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [row for row in mates if row.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError(f"JJ00/{target_token} requires one coincident and two concentric mates")
    if not all(row.get("IsBasicTwoFaceRebuildable") is True for row in mates):
        raise ValueError(f"JJ00/{target_token} contains an unsupported mate")
    for mate in mates:
        for endpoint in mate.get("Endpoints", []):
            raw_path = str(endpoint.get("LeafComponentPath") or "")
            filename = Path(raw_path).name
            token = str(endpoint.get("ModuleToken") or "")
            root = module_roots[token]
            candidates = [
                path for path in index.get(filename.casefold(), []) if path.is_relative_to(root)
            ]
            field = f"mate:{mate.get('MateName')}:{token}:{endpoint.get('Index')}"
            if len(candidates) != 1:
                raise ValueError(
                    f"{field} {filename!r} resolved to {len(candidates)} files inside {root}"
                )
            resolved = candidates[0]
            endpoint["LeafComponentPath"] = str(resolved)
            audit_rows.append(
                {
                    "field": field,
                    "capturedPath": raw_path,
                    "filename": filename,
                    "resolvedPath": str(resolved),
                    "resolutionScope": f"module-tree:{token}",
                    "sha256": _sha256(resolved),
                }
            )
    captured_names = [str(row["MateName"]) for row in mates]
    coincident[0]["MateName"] = canonical_coincident_name
    concentric.sort(
        key=lambda row: float(_endpoint(row, JJ00)["FaceCenterWorld"][sort_axis])
    )
    if len(canonical_concentric_names_by_sorted_axis) != 2:
        raise ValueError("Two canonical concentric names are required")
    for name, row in zip(canonical_concentric_names_by_sorted_axis, concentric, strict=True):
        row["MateName"] = name
    mate_names = [canonical_coincident_name, *canonical_concentric_names_by_sorted_axis]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    target = copy.deepcopy(_module(graph, target_token))
    base = copy.deepcopy(_module(graph, JJ00))
    centers = [_endpoint(row, JJ00)["FaceCenterWorld"] for row in concentric]
    spacing = math.dist(
        [float(value) for value in centers[0]],
        [float(value) for value in centers[1]],
    )
    if abs(spacing - expected_hole_spacing_meters) > 1e-6:
        raise ValueError(
            f"JJ00/{target_token} locating-hole spacing is {spacing} m, expected {expected_hole_spacing_meters}"
        )
    roles = [
        ("support_plane", _endpoint(coincident[0], target_token), _endpoint(coincident[0], JJ00)),
        ("locating_hole_1", _endpoint(concentric[0], target_token), _endpoint(concentric[0], JJ00)),
        ("locating_hole_2", _endpoint(concentric[1], target_token), _endpoint(concentric[1], JJ00)),
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": f"Install {target_token} on JJ00 through one plane and two holes.",
        "ports": [
            {
                "portId": target_port_id,
                "displayName": target_display_name,
                "moduleToken": target_token,
                "moduleHierarchyPath": target["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": interface_type,
                "capabilities": capabilities,
                "aliases": [f"{target_token}安装接口"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, endpoint)}
                    for role, endpoint, _ in roles
                ],
            },
            {
                "portId": base_port_id,
                "displayName": base_display_name,
                "moduleToken": JJ00,
                "moduleHierarchyPath": base["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": interface_type,
                "capabilities": ["installation", "frame_support"],
                "aliases": [f"JJ00-{target_token}安装位"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, endpoint)}
                    for role, _, endpoint in roles
                ],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": template_id,
                "purposes": ["installation"],
                "interfaceTypeA": interface_type,
                "interfaceTypeB": interface_type,
                "constraintEffect": {
                    "purpose": f"Recover the complete rigid {target_token} installation pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": [
                    {
                        "mateName": canonical_coincident_name,
                        "mateType": int(coincident[0]["MateType"]),
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": int(coincident[0]["Alignment"]),
                        "alignmentName": coincident[0]["AlignmentName"],
                        "endpointRoleA": "support_plane",
                        "endpointRoleB": "support_plane",
                    },
                    *[
                        {
                            "mateName": str(row["MateName"]),
                            "mateType": int(row["MateType"]),
                            "mateTypeName": "swMateCONCENTRIC",
                            "alignment": int(row["Alignment"]),
                            "alignmentName": row["AlignmentName"],
                            "endpointRoleA": f"locating_hole_{index}",
                            "endpointRoleB": f"locating_hole_{index}",
                        }
                        for index, row in enumerate(concentric, start=1)
                    ],
                ],
            }
        ],
    }
    base_graph = copy.deepcopy(prior_effective_graph)
    base_tokens = {str(row.get("ModuleToken")) for row in base_graph.get("Modules") or []}
    if base_tokens != set(prior_context_tokens):
        raise ValueError(
            f"Prior effective graph contains {sorted(base_tokens)}, expected {sorted(prior_context_tokens)}"
        )
    base_graph["Mates"] = []
    base_graph["InterModuleMateCount"] = 0
    base_graph.setdefault("EditPolicy", {})["fixedModuleTokens"] = prior_context_tokens
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": f"project01-add-{target_token}-three-datum-v1",
        "baseModuleToken": JJ00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": prior_context_tokens,
        "componentToAdd": target,
        "connections": [
            {
                "connectionId": f"{target_token}-installed-on-JJ00",
                "portAId": target_port_id,
                "portBId": base_port_id,
                "templateId": template_id,
            }
        ],
    }
    plan = build_semantic_assembly_plan(base_graph, semantic_catalog, endpoint_catalog, request)
    effective = plan["effectiveGraph"]
    effective.setdefault("SemanticAssemblyPlanAudit", {})["collisionPolicy"] = {
        "pair": [JJ00, target_token],
        "classification": "intended-installation-contact",
        "broadPhasePolicy": "AABB overlap allowed",
        "exactGate": "conditional exact B-rep or accepted source-pose equivalence",
    }
    summary = {
        "schemaVersion": "project01-three-datum-work-packet/v1",
        "projectId": "project01",
        "stepId": step_id,
        "baseModules": prior_context_tokens,
        "targetModule": target_token,
        "sourceMateNames": mate_names,
        "capturedMateNamesBeforeUnicodeRecovery": captured_names,
        "mateNameUnicodeRecoveryApplied": captured_names != mate_names,
        "locatingHoleSpacingMeters": spacing,
        "endpointCount": len(endpoint_catalog.get("Endpoints", [])),
        "allEndpointsHavePersistentReferences": all(
            bool((row.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64"))
            for row in endpoint_catalog.get("Endpoints", [])
        ),
        "expectedResidualDof": 0,
        "priorContextMatePolicy": "preserve-in-source-assembly-do-not-resubmit-as-new-driving-mates",
        "safeToStartStaticCad": len(endpoint_catalog.get("Endpoints", [])) == 6,
        "knownLimits": [
            f"The {expected_hole_spacing_meters * 1000:g} mm interface is prototype-derived, not vendor-confirmed.",
            *(extra_limits or []),
        ],
    }
    return {
        "pathAudit": {
            "schemaVersion": "project01-path-recovery-audit/v1",
            "prototypeAssemblyPath": str(prototype),
            "prototypeAssemblySha256": _sha256(prototype),
            "recordCount": len(audit_rows),
            "allResolved": True,
            "records": audit_rows,
        },
        "endpointCatalog": endpoint_catalog,
        "semanticCatalog": semantic_catalog,
        "baseGraph": base_graph,
        "request": request,
        "patch": plan["patch"],
        "effectiveGraph": effective,
        "summary": summary,
    }
