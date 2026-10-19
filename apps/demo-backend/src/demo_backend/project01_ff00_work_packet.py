"""Compile the Project01 FF00 static incremental CAD packet."""

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


SS00 = "SS00"
FF00 = "FF00"


def build_project01_ff00_work_packet(
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
) -> dict[str, Any]:
    prototype = prototype_assembly.resolve()
    if not prototype.is_file():
        raise FileNotFoundError(prototype)
    graph = copy.deepcopy(source_graph)
    graph["SourceAssemblyPath"] = str(prototype)
    selected = {JJ00, HL00, SS00, FF00}
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
    for mate in graph.get("Mates", []):
        tokens = {str(value) for value in mate.get("ModuleTokens", [])}
        if not tokens <= selected:
            continue
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
            audit = {
                "field": field,
                "capturedPath": raw_path,
                "filename": filename,
                "resolvedPath": str(resolved),
                "resolutionScope": f"module-tree:{token}",
                "sha256": _sha256(resolved),
            }
            audit_rows.append(audit)

    mates = _pair_mates(graph, JJ00, FF00)
    coincident = [row for row in mates if row.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [row for row in mates if row.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError("JJ00/FF00 requires one coincident and two concentric mates")
    if not all(row.get("IsBasicTwoFaceRebuildable") is True for row in mates):
        raise ValueError("JJ00/FF00 contains an unsupported mate")
    captured_names = [str(row["MateName"]) for row in mates]
    coincident[0]["MateName"] = "重合10"
    concentric.sort(key=lambda row: float(_endpoint(row, JJ00)["FaceCenterWorld"][0]))
    for name, row in zip(("同心20", "同心19"), concentric, strict=True):
        row["MateName"] = name
    mate_names = [
        str(coincident[0]["MateName"]),
        *(str(row["MateName"]) for row in concentric),
    ]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    jj00 = copy.deepcopy(_module(graph, JJ00))
    ff00 = copy.deepcopy(_module(graph, FF00))
    centers = [_endpoint(row, JJ00)["FaceCenterWorld"] for row in concentric]
    spacing = math.sqrt(
        sum((float(a) - float(b)) ** 2 for a, b in zip(centers[0], centers[1], strict=True))
    )
    if abs(spacing - 0.035) > 1e-6:
        raise ValueError(f"JJ00/FF00 locating-hole spacing is {spacing} m")
    roles = [
        ("support_plane", _endpoint(coincident[0], FF00), _endpoint(coincident[0], JJ00)),
        ("locating_hole_1", _endpoint(concentric[0], FF00), _endpoint(concentric[0], JJ00)),
        ("locating_hole_2", _endpoint(concentric[1], FF00), _endpoint(concentric[1], JJ00)),
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": "Install FF00 on JJ00 through one support plane and two locating holes.",
        "ports": [
            {
                "portId": "FF00.frame_installation",
                "displayName": "FF00举升翻转安装端口",
                "moduleToken": FF00,
                "moduleHierarchyPath": ff00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project01_flip_lift_frame_installation",
                "capabilities": ["installation", "lift_flip_positioning"],
                "aliases": ["FF00安装接口", "项目01翻转模组安装端口"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, target)}
                    for role, target, _ in roles
                ],
                "evidence": ["项目01原型：1个重合支承面、2个同心定位孔"],
            },
            {
                "portId": "JJ00.flip_lift_installation",
                "displayName": "JJ00举升翻转载荷端口",
                "moduleToken": JJ00,
                "moduleHierarchyPath": jj00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project01_flip_lift_frame_installation",
                "capabilities": ["installation", "flip_lift_support"],
                "aliases": ["JJ00翻转安装位"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, base)}
                    for role, _, base in roles
                ],
                "evidence": ["项目01原型：1个重合支承面、2个同心定位孔"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "FF00_to_JJ00_three_datum_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project01_flip_lift_frame_installation",
                "interfaceTypeB": "project01_flip_lift_frame_installation",
                "constraintEffect": {
                    "purpose": "Recover the rigid static FF00 installation pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": [
                    {
                        "mateName": "重合10",
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
                            "endpointRoleA": f"locating_hole_{number}",
                            "endpointRoleB": f"locating_hole_{number}",
                        }
                        for number, row in enumerate(concentric, start=1)
                    ],
                ],
            }
        ],
    }
    base_graph = copy.deepcopy(prior_effective_graph)
    base_tokens = {str(row.get("ModuleToken")) for row in base_graph.get("Modules") or []}
    if base_tokens != {JJ00, HL00, SS00}:
        raise ValueError(f"Prior effective graph contains unexpected modules: {sorted(base_tokens)}")
    # The source assembly already owns the accepted SS00 mates.  The context-insert
    # operation must receive only driving mates that reference the newly inserted
    # target; existing context mates remain in the copied assembly and are audited
    # after save/reopen.
    base_graph["Mates"] = []
    base_graph["InterModuleMateCount"] = 0
    base_graph.setdefault("EditPolicy", {})["fixedModuleTokens"] = [JJ00, HL00, SS00]
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project01-add-FF00-three-datum-v1",
        "baseModuleToken": JJ00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": [JJ00, HL00, SS00],
        "componentToAdd": ff00,
        "connections": [
            {
                "connectionId": "FF00-installed-on-JJ00",
                "portAId": "FF00.frame_installation",
                "portBId": "JJ00.flip_lift_installation",
                "templateId": "FF00_to_JJ00_three_datum_installation",
            }
        ],
    }
    plan = build_semantic_assembly_plan(base_graph, semantic_catalog, endpoint_catalog, request)
    effective = plan["effectiveGraph"]
    effective.setdefault("SemanticAssemblyPlanAudit", {})["collisionPolicy"] = {
        "pair": [JJ00, FF00],
        "classification": "intended-installation-contact",
        "broadPhasePolicy": "AABB overlap allowed",
        "exactGate": "conditional exact B-rep or source-pose equivalence after insertion",
    }
    path_audit = {
        "schemaVersion": "project01-path-recovery-audit/v1",
        "prototypeAssemblyPath": str(prototype),
        "prototypeAssemblySha256": _sha256(prototype),
        "recordCount": len(audit_rows),
        "allResolved": True,
        "records": audit_rows,
    }
    summary = {
        "schemaVersion": "project01-ff00-work-packet/v1",
        "projectId": "project01",
        "stepId": "step-02-add-FF00",
        "baseModules": [JJ00, HL00, SS00],
        "targetModule": FF00,
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
        "dynamicGateReady": False,
        "knownLimits": [
            "The 35 mm interface is prototype-derived, not vendor-confirmed.",
            "The 25 degree flip sweep is not validated by this static packet.",
        ],
    }
    return {
        "pathAudit": path_audit,
        "endpointCatalog": endpoint_catalog,
        "semanticCatalog": semantic_catalog,
        "baseGraph": base_graph,
        "request": request,
        "patch": plan["patch"],
        "effectiveGraph": effective,
        "summary": summary,
    }
