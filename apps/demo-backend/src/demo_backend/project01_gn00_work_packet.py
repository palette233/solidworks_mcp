"""Compile the multi-base Project01 GN00 incremental work packet."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from .project01_incremental_work_packet import (
    _catalog_endpoint_id,
    _endpoint,
    _file_index,
    _module,
    _pair_mates,
    _relocate,
    _sha256,
)
from .semantic_port_catalog import build_semantic_assembly_plan


CONTEXT = ["JJ00", "HL00", "SS00", "FF00", "SM00"]
TARGET = "GN00"


def build_project01_gn00_work_packet(
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
) -> dict[str, Any]:
    prototype = prototype_assembly.resolve()
    graph = copy.deepcopy(source_graph)
    graph["SourceAssemblyPath"] = str(prototype)
    selected = set(CONTEXT) | {TARGET}
    index = _file_index(prototype.parent)
    audits = []
    for module in graph.get("Modules", []):
        if str(module.get("ModuleToken")) in selected:
            module["Path"], audit = _relocate(
                str(module.get("Path") or ""), index, f"module:{module.get('ModuleToken')}"
            )
            audits.append(audit)
    roots = {
        str(module["ModuleToken"]): Path(str(module["Path"])).resolve().parent
        for module in graph.get("Modules", [])
        if str(module.get("ModuleToken")) in selected
    }
    primary = _pair_mates(graph, "JJ00", TARGET)
    anti_rotation = _pair_mates(graph, "SS00", TARGET)
    coincident = [row for row in primary if row.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [row for row in primary if row.get("MateTypeName") == "swMateCONCENTRIC"]
    parallel = [row for row in anti_rotation if row.get("MateTypeName") == "swMatePARALLEL"]
    if (len(coincident), len(concentric), len(parallel)) != (1, 1, 1):
        raise ValueError("GN00 requires JJ00 plane+hole and SS00 anti-rotation parallel mates")
    mates = [coincident[0], concentric[0], parallel[0]]
    if not all(row.get("IsBasicTwoFaceRebuildable") is True for row in mates):
        raise ValueError("GN00 contains an unsupported mate")
    for mate in mates:
        for endpoint in mate.get("Endpoints", []):
            raw = str(endpoint.get("LeafComponentPath") or "")
            name = Path(raw).name
            token = str(endpoint.get("ModuleToken"))
            rows = [path for path in index.get(name.casefold(), []) if path.is_relative_to(roots[token])]
            if len(rows) != 1:
                raise ValueError(f"{token}:{name} resolved to {len(rows)} files in module tree")
            endpoint["LeafComponentPath"] = str(rows[0])
            audits.append({
                "field": f"mate:{mate.get('MateName')}:{token}:{endpoint.get('Index')}",
                "capturedPath": raw, "filename": name, "resolvedPath": str(rows[0]),
                "resolutionScope": f"module-tree:{token}", "sha256": _sha256(rows[0]),
            })
    captured = [str(row["MateName"]) for row in mates]
    for row, name in zip(mates, ["重合6", "同心11", "平行1"], strict=True):
        row["MateName"] = name
    names = ["重合6", "同心11", "平行1"]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, names)
    gn = copy.deepcopy(_module(graph, TARGET))
    jj = copy.deepcopy(_module(graph, "JJ00"))
    ss = copy.deepcopy(_module(graph, "SS00"))

    def eid(mate: dict[str, Any], token: str) -> str:
        return _catalog_endpoint_id(catalog, _endpoint(mate, token))

    ports = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": "Install GN00 using JJ00 primary location and SS00 anti-rotation datum.",
        "ports": [
            {
                "portId": "GN00.primary_installation", "displayName": "GN00主安装端口",
                "moduleToken": TARGET, "moduleHierarchyPath": gn["HierarchyPath"],
                "category": "mechanical", "interfaceType": "project01_gn00_primary",
                "capabilities": ["installation", "multifunction_service"], "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": "support_plane", "endpointId": eid(coincident[0], TARGET)},
                    {"role": "locating_hole", "endpointId": eid(concentric[0], TARGET)},
                ],
            },
            {
                "portId": "JJ00.gn00_primary", "displayName": "JJ00-GN00主安装位",
                "moduleToken": "JJ00", "moduleHierarchyPath": jj["HierarchyPath"],
                "category": "mechanical", "interfaceType": "project01_gn00_primary",
                "capabilities": ["installation", "frame_support"], "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": "support_plane", "endpointId": eid(coincident[0], "JJ00")},
                    {"role": "locating_hole", "endpointId": eid(concentric[0], "JJ00")},
                ],
            },
            {
                "portId": "GN00.anti_rotation", "displayName": "GN00防转端口",
                "moduleToken": TARGET, "moduleHierarchyPath": gn["HierarchyPath"],
                "category": "mechanical", "interfaceType": "project01_gn00_anti_rotation",
                "capabilities": ["anti_rotation"], "status": "prototype-confirmed",
                "endpointBindings": [{"role": "anti_rotation_plane", "endpointId": eid(parallel[0], TARGET)}],
            },
            {
                "portId": "SS00.gn00_anti_rotation", "displayName": "SS00-GN00防转基准",
                "moduleToken": "SS00", "moduleHierarchyPath": ss["HierarchyPath"],
                "category": "mechanical", "interfaceType": "project01_gn00_anti_rotation",
                "capabilities": ["anti_rotation_reference"], "status": "prototype-confirmed",
                "endpointBindings": [{"role": "anti_rotation_plane", "endpointId": eid(parallel[0], "SS00")}],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "GN00_to_JJ00_primary", "purposes": ["installation"],
                "interfaceTypeA": "project01_gn00_primary", "interfaceTypeB": "project01_gn00_primary",
                "constraintEffect": {"fullyLocatesAddedComponent": False, "expectedResidualDof": 1},
                "mateSteps": [
                    {"mateName": "重合6", "mateType": int(coincident[0]["MateType"]), "mateTypeName": "swMateCOINCIDENT", "alignment": int(coincident[0]["Alignment"]), "alignmentName": coincident[0]["AlignmentName"], "endpointRoleA": "support_plane", "endpointRoleB": "support_plane"},
                    {"mateName": "同心11", "mateType": int(concentric[0]["MateType"]), "mateTypeName": "swMateCONCENTRIC", "alignment": int(concentric[0]["Alignment"]), "alignmentName": concentric[0]["AlignmentName"], "endpointRoleA": "locating_hole", "endpointRoleB": "locating_hole"},
                ],
            },
            {
                "templateId": "GN00_to_SS00_anti_rotation", "purposes": ["installation"],
                "interfaceTypeA": "project01_gn00_anti_rotation", "interfaceTypeB": "project01_gn00_anti_rotation",
                "constraintEffect": {"fullyLocatesAddedComponent": True, "expectedResidualDof": 0},
                "mateSteps": [
                    {"mateName": "平行1", "mateType": int(parallel[0]["MateType"]), "mateTypeName": "swMatePARALLEL", "alignment": int(parallel[0]["Alignment"]), "alignmentName": parallel[0]["AlignmentName"], "endpointRoleA": "anti_rotation_plane", "endpointRoleB": "anti_rotation_plane"}
                ],
            },
        ],
    }
    base = copy.deepcopy(prior_effective_graph)
    if {str(row["ModuleToken"]) for row in base.get("Modules") or []} != set(CONTEXT):
        raise ValueError("Unexpected prior context modules for GN00")
    base["Mates"] = []
    base["InterModuleMateCount"] = 0
    base.setdefault("EditPolicy", {})["fixedModuleTokens"] = CONTEXT
    request = {
        "schemaVersion": "semantic-assembly-plan/v1", "planId": "project01-add-GN00-multibase-v1",
        "baseModuleToken": "JJ00", "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": CONTEXT, "componentToAdd": gn,
        "connections": [
            {"connectionId": "GN00-primary-on-JJ00", "portAId": "GN00.primary_installation", "portBId": "JJ00.gn00_primary", "templateId": "GN00_to_JJ00_primary"},
            {"connectionId": "GN00-anti-rotation-to-SS00", "portAId": "GN00.anti_rotation", "portBId": "SS00.gn00_anti_rotation", "templateId": "GN00_to_SS00_anti_rotation"},
        ],
    }
    plan = build_semantic_assembly_plan(base, ports, catalog, request)
    summary = {
        "schemaVersion": "project01-gn00-work-packet/v1", "projectId": "project01",
        "stepId": "step-04-add-GN00", "baseModules": CONTEXT, "targetModule": TARGET,
        "sourceMateNames": names, "capturedMateNamesBeforeUnicodeRecovery": captured,
        "endpointCount": len(catalog.get("Endpoints", [])), "expectedResidualDof": 0,
        "connectionCount": 2, "safeToStartStaticCad": len(catalog.get("Endpoints", [])) == 6,
        "serviceTargetGateReady": False,
        "knownLimits": ["GN00 service targets and maintenance envelope are not validated by this mechanical packet."],
    }
    return {
        "pathAudit": {"schemaVersion": "project01-path-recovery-audit/v1", "prototypeAssemblyPath": str(prototype), "prototypeAssemblySha256": _sha256(prototype), "recordCount": len(audits), "allResolved": True, "records": audits},
        "endpointCatalog": catalog, "semanticCatalog": ports, "baseGraph": base,
        "request": request, "patch": plan["patch"], "effectiveGraph": plan["effectiveGraph"], "summary": summary,
    }
