"""Compile the first Project 01 JJ00/HL00 -> SS00 incremental CAD packet."""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from .semantic_port_catalog import build_semantic_assembly_plan


JJ00 = "JJ00"
HL00 = "HL00"
SS00 = "SS00"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    rows = [
        row
        for row in graph.get("Modules", [])
        if str(row.get("ModuleToken", "")).casefold() == token.casefold()
    ]
    if len(rows) != 1:
        raise ValueError(f"Module {token} resolved to {len(rows)} rows")
    return rows[0]


def _pair_mates(graph: dict[str, Any], first: str, second: str) -> list[dict[str, Any]]:
    wanted = {first.casefold(), second.casefold()}
    return [
        row
        for row in graph.get("Mates", [])
        if {str(value).casefold() for value in row.get("ModuleTokens", [])} == wanted
    ]


def _endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    rows = [
        row
        for row in mate.get("Endpoints", [])
        if str(row.get("ModuleToken", "")).casefold() == token.casefold()
    ]
    if len(rows) != 1:
        raise ValueError(f"Mate {mate.get('MateName')} has {len(rows)} endpoints for {token}")
    return rows[0]


def _file_index(root: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.is_file():
            result.setdefault(path.name.casefold(), []).append(path.resolve())
    return result


def _relocate(raw_path: str, index: dict[str, list[Path]], field: str) -> tuple[str, dict[str, Any]]:
    name = Path(str(raw_path)).name
    rows = index.get(name.casefold(), [])
    if len(rows) != 1:
        raise ValueError(f"{field} {name!r} resolved to {len(rows)} files")
    path = rows[0]
    return str(path), {
        "field": field,
        "capturedPath": raw_path,
        "filename": name,
        "resolvedPath": str(path),
        "sha256": _sha256(path),
    }


def _catalog_endpoint_id(catalog: dict[str, Any], endpoint: dict[str, Any]) -> str:
    reference = endpoint.get("SourceAssemblyPersistentReferenceBase64")
    rows = [
        row
        for row in catalog.get("Endpoints", [])
        if (row.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64")
        == reference
    ]
    if len(rows) != 1:
        raise ValueError(f"Endpoint reference resolved to {len(rows)} catalog rows")
    return str(rows[0]["EndpointId"])


def build_project01_ss00_work_packet(
    source_graph: dict[str, Any], prototype_assembly: Path
) -> dict[str, Any]:
    prototype = prototype_assembly.resolve()
    if not prototype.is_file():
        raise FileNotFoundError(prototype)
    graph = copy.deepcopy(source_graph)
    graph["SourceAssemblyPath"] = str(prototype)
    selected = {JJ00, HL00, SS00}
    index = _file_index(prototype.parent)
    audit_rows = []
    for module in graph.get("Modules", []):
        if str(module.get("ModuleToken")) in selected:
            module["Path"], audit = _relocate(
                str(module.get("Path") or ""),
                index,
                f"module:{module.get('ModuleToken')}",
            )
            audit_rows.append(audit)
    for mate in graph.get("Mates", []):
        tokens = {str(value) for value in mate.get("ModuleTokens", [])}
        if not tokens <= selected:
            continue
        for endpoint in mate.get("Endpoints", []):
            endpoint["LeafComponentPath"], audit = _relocate(
                str(endpoint.get("LeafComponentPath") or ""),
                index,
                f"mate:{mate.get('MateName')}:{endpoint.get('ModuleToken')}:{endpoint.get('Index')}",
            )
            audit_rows.append(audit)

    mates = _pair_mates(graph, JJ00, SS00)
    coincident = [row for row in mates if row.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [row for row in mates if row.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError("JJ00/SS00 requires one coincident and two concentric mates")
    if not all(row.get("IsBasicTwoFaceRebuildable") is True for row in mates):
        raise ValueError("JJ00/SS00 contains an unsupported mate")
    captured_names = [str(row["MateName"]) for row in mates]
    coincident[0]["MateName"] = "重合4"
    concentric.sort(key=lambda row: float(_endpoint(row, JJ00)["FaceCenterWorld"][2]))
    for name, row in zip(("同心6", "同心7"), concentric, strict=True):
        row["MateName"] = name
    mate_names = [str(row["MateName"]) for row in mates]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    jj00 = copy.deepcopy(_module(graph, JJ00))
    hl00 = copy.deepcopy(_module(graph, HL00))
    ss00 = copy.deepcopy(_module(graph, SS00))
    centers = [_endpoint(row, JJ00)["FaceCenterWorld"] for row in concentric]
    spacing = math.sqrt(
        sum((float(a) - float(b)) ** 2 for a, b in zip(centers[0], centers[1], strict=True))
    )
    if abs(spacing - 0.058) > 1e-6:
        raise ValueError(f"JJ00/SS00 locating-hole spacing is {spacing} m")
    roles = [
        ("support_plane", _endpoint(coincident[0], SS00), _endpoint(coincident[0], JJ00)),
        ("locating_hole_1", _endpoint(concentric[0], SS00), _endpoint(concentric[0], JJ00)),
        ("locating_hole_2", _endpoint(concentric[1], SS00), _endpoint(concentric[1], JJ00)),
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": "Install SS00 on JJ00 through one support plane and two locating holes.",
        "ports": [
            {
                "portId": "SS00.frame_installation",
                "displayName": "SS00传输安装端口",
                "moduleToken": SS00,
                "moduleHierarchyPath": ss00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project01_transport_frame_installation",
                "capabilities": ["installation", "transport_alignment"],
                "aliases": ["SS00安装接口", "项目01传输安装端口"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, target)}
                    for role, target, _ in roles
                ],
                "evidence": ["项目01原型：1个重合支承面、2个同心定位孔"],
            },
            {
                "portId": "JJ00.transport_installation",
                "displayName": "JJ00传输承载端口",
                "moduleToken": JJ00,
                "moduleHierarchyPath": jj00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project01_transport_frame_installation",
                "capabilities": ["installation", "transport_support"],
                "aliases": ["JJ00传输安装位", "项目01箱体传输承载端口"],
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
                "templateId": "SS00_to_JJ00_three_datum_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project01_transport_frame_installation",
                "interfaceTypeB": "project01_transport_frame_installation",
                "constraintEffect": {
                    "purpose": "Recover the complete rigid SS00 installation pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": [
                    {
                        "mateName": "重合4",
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
    base_graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": str(prototype),
        "ModuleCount": 2,
        "InterModuleMateCount": 0,
        "Modules": [jj00, hl00],
        "Mates": [],
        "EditPolicy": {
            "baseModuleToken": JJ00,
            "initialPlacementMode": "source_pose",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [JJ00, HL00],
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project01-add-SS00-three-datum-v1",
        "baseModuleToken": JJ00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": [JJ00, HL00],
        "componentToAdd": ss00,
        "connections": [
            {
                "connectionId": "SS00-installed-on-JJ00",
                "portAId": "SS00.frame_installation",
                "portBId": "JJ00.transport_installation",
                "templateId": "SS00_to_JJ00_three_datum_installation",
            }
        ],
    }
    plan = build_semantic_assembly_plan(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    effective = plan["effectiveGraph"]
    effective.setdefault("SemanticAssemblyPlanAudit", {})["collisionPolicy"] = {
        "pair": [JJ00, SS00],
        "classification": "intended-installation-contact",
        "broadPhasePolicy": "AABB overlap allowed",
        "exactGate": "conditional exact B-rep after insertion; reject new penetration beyond the source interface",
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
        "schemaVersion": "project01-first-increment-work-packet/v1",
        "projectId": "project01",
        "stepId": "step-01-add-SS00",
        "baseModules": [JJ00, HL00],
        "targetModule": SS00,
        "sourceMateNames": mate_names,
        "capturedMateNamesBeforeUnicodeRecovery": captured_names,
        "mateNameUnicodeRecoveryApplied": captured_names != mate_names,
        "locatingHoleSpacingMeters": spacing,
        "pathRecoveryPassed": True,
        "endpointCount": len(endpoint_catalog.get("Endpoints", [])),
        "allEndpointsHavePersistentReferences": all(
            bool((row.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64"))
            for row in endpoint_catalog.get("Endpoints", [])
        ),
        "expectedResidualDof": 0,
        "safeToStartCad": len(endpoint_catalog.get("Endpoints", [])) == 6,
        "knownLimits": [
            "The 58 mm interface is prototype-derived, not vendor-confirmed.",
            "This checkpoint validates static installation only.",
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
