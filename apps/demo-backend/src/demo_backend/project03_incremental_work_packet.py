"""Build the first Project03 incremental-assembly work packet.

The legacy Project03 mate graph contains valid mate/face evidence, but some
absolute paths were captured through a non-Unicode console and are therefore
not executable.  This module deliberately separates evidence recovery from
SolidWorks execution: it relocates files by their exact CAD filename under the
authoritative prototype directory, validates the AA00/AE00 interface, and then
compiles a semantic-port plan that can be consumed by the existing incremental
insert executor.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates
from .project03_calibrated_parameters import apply_calibrated_pose_anchor
from .semantic_port_catalog import build_semantic_assembly_plan


AA00 = "FL9A24D063AA00"
AE00 = "FL9A24D063AE00"
AF00 = "FL9A24D063AF00"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        item
        for item in graph.get("Modules") or []
        if str(item.get("ModuleToken") or "").casefold() == token.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Module {token} resolved to {len(matches)} nodes; expected one.")
    return matches[0]


def _pair_mates(
    graph: dict[str, Any], first: str, second: str
) -> list[dict[str, Any]]:
    expected = {first.casefold(), second.casefold()}
    return [
        item
        for item in graph.get("Mates") or []
        if {str(value).casefold() for value in item.get("ModuleTokens") or []}
        == expected
    ]


def _file_index(root: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.is_file():
            result.setdefault(path.name.casefold(), []).append(path.resolve())
    return result


def _relocate_path(
    raw_path: str, index: dict[str, list[Path]], *, field: str
) -> tuple[str, dict[str, Any]]:
    filename = Path(str(raw_path or "")).name
    matches = index.get(filename.casefold(), [])
    if len(matches) != 1:
        raise ValueError(
            f"{field} '{filename}' resolved to {len(matches)} files under the prototype root."
        )
    resolved = matches[0]
    return str(resolved), {
        "field": field,
        "capturedPath": str(raw_path or ""),
        "filename": filename,
        "resolvedPath": str(resolved),
        "exists": True,
        "sha256": _sha256(resolved),
    }


def normalize_project03_paths(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    *,
    selected_tokens: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a deep-copied graph with executable paths and a path audit."""

    prototype_assembly = prototype_assembly.resolve()
    if not prototype_assembly.is_file():
        raise FileNotFoundError(prototype_assembly)
    root = prototype_assembly.parent
    index = _file_index(root)
    graph = copy.deepcopy(source_graph)
    records: list[dict[str, Any]] = []
    graph["SourceAssemblyPath"] = str(prototype_assembly)

    selected = selected_tokens or {AA00, AE00, AF00}
    for module in graph.get("Modules") or []:
        if str(module.get("ModuleToken") or "") not in selected:
            continue
        module["Path"], audit = _relocate_path(
            str(module.get("Path") or ""), index, field=f"module:{module['ModuleToken']}"
        )
        records.append(audit)

    for mate in graph.get("Mates") or []:
        tokens = {str(value) for value in mate.get("ModuleTokens") or []}
        if not tokens <= selected:
            continue
        for endpoint in mate.get("Endpoints") or []:
            endpoint["LeafComponentPath"], audit = _relocate_path(
                str(endpoint.get("LeafComponentPath") or ""),
                index,
                field=(
                    f"mate:{mate.get('MateName')}:{endpoint.get('ModuleToken')}:"
                    f"endpoint:{endpoint.get('Index')}"
                ),
            )
            records.append(audit)

    return graph, {
        "schemaVersion": "project03-path-recovery-audit/v1",
        "prototypeAssemblyPath": str(prototype_assembly),
        "prototypeAssemblySha256": _sha256(prototype_assembly),
        "prototypeRoot": str(root),
        "recordCount": len(records),
        "allResolved": all(item["exists"] for item in records),
        "records": records,
    }


def _endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        item
        for item in mate.get("Endpoints") or []
        if str(item.get("ModuleToken") or "").casefold() == token.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Mate {mate.get('MateName')} has {len(matches)} endpoints for {token}."
        )
    return matches[0]


def _catalog_endpoint_id(
    catalog: dict[str, Any], source_endpoint: dict[str, Any]
) -> str:
    reference = source_endpoint.get("SourceAssemblyPersistentReferenceBase64")
    matches = [
        item
        for item in catalog.get("Endpoints") or []
        if (item.get("Endpoint") or {}).get(
            "SourceAssemblyPersistentReferenceBase64"
        )
        == reference
    ]
    if len(matches) != 1:
        raise ValueError(f"Endpoint persistent reference resolved to {len(matches)} catalog entries.")
    return str(matches[0]["EndpointId"])


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def build_project03_ae00_work_packet(
    source_graph: dict[str, Any], prototype_assembly: Path
) -> dict[str, Any]:
    graph, path_audit = normalize_project03_paths(source_graph, prototype_assembly)
    mates = _pair_mates(graph, AA00, AE00)
    coincident = [item for item in mates if item.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [item for item in mates if item.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError(
            "AA00/AE00 must contain exactly one coincident and two concentric mates."
        )
    if not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError("AA00/AE00 contains a mate that the current executor cannot rebuild.")

    # The graph was originally emitted through a non-Unicode console, so its
    # Chinese feature names are mojibake even though the face evidence is sound.
    # Canonicalize only the three execution names; retain the captured values in
    # the work-packet audit below.
    captured_mate_names = [str(item["MateName"]) for item in mates]
    coincident[0]["MateName"] = "重合28"
    concentric.sort(key=lambda item: float(_endpoint(item, AA00)["FaceCenterWorld"][2]))
    for index, item in enumerate(concentric, start=39):
        item["MateName"] = f"同心{index}"

    mate_names = [str(item["MateName"]) for item in mates]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    aa00 = copy.deepcopy(_module(graph, AA00))
    ae00 = copy.deepcopy(_module(graph, AE00))
    af00 = copy.deepcopy(_module(graph, AF00))
    hole_centers = [
        list(_endpoint(item, AA00)["FaceCenterWorld"]) for item in concentric
    ]
    spacing = _distance(hole_centers[0], hole_centers[1])
    if abs(spacing - 0.058) > 1e-6:
        raise ValueError(f"AA00/AE00 locating-hole spacing is {spacing} m, expected 0.058 m.")

    role_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("support_plane", _endpoint(coincident[0], AE00), _endpoint(coincident[0], AA00)),
        ("locating_hole_1", _endpoint(concentric[0], AE00), _endpoint(concentric[0], AA00)),
        ("locating_hole_2", _endpoint(concentric[1], AE00), _endpoint(concentric[1], AA00)),
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": "Install AE00 on AA00 through the recovered support plane and two locating holes.",
        "ports": [
            {
                "portId": "AE00.frame_installation",
                "displayName": "AE00传输安装端口",
                "description": "AE00支承面及双定位孔安装接口。",
                "moduleToken": AE00,
                "moduleHierarchyPath": ae00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project03_transport_frame_installation",
                "capabilities": ["installation", "transport_alignment"],
                "aliases": ["AE00安装接口", "项目03传输安装端口"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, target)}
                    for role, target, _ in role_rows
                ],
                "evidence": ["项目03原型：1个重合支承面、2个同心定位孔"],
            },
            {
                "portId": "AA00.transport_installation",
                "displayName": "AA00传输承载端口",
                "description": "AA00为AE00提供支承面及双定位孔。",
                "moduleToken": AA00,
                "moduleHierarchyPath": aa00["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "project03_transport_frame_installation",
                "capabilities": ["installation", "transport_support"],
                "aliases": ["AA00传输安装位", "项目03箱体传输承载端口"],
                "status": "prototype-confirmed",
                "endpointBindings": [
                    {"role": role, "endpointId": _catalog_endpoint_id(endpoint_catalog, base)}
                    for role, _, base in role_rows
                ],
                "evidence": ["项目03原型：1个重合支承面、2个同心定位孔"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "AE00_to_AA00_three_datum_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project03_transport_frame_installation",
                "interfaceTypeB": "project03_transport_frame_installation",
                "constraintEffect": {
                    "purpose": "Recover the complete rigid AE00 installation pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": [
                    {
                        "mateName": str(coincident[0]["MateName"]),
                        "mateType": int(coincident[0]["MateType"]),
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": int(coincident[0]["Alignment"]),
                        "alignmentName": coincident[0]["AlignmentName"],
                        "endpointRoleA": "support_plane",
                        "endpointRoleB": "support_plane",
                    },
                    *[
                        {
                            "mateName": str(mate["MateName"]),
                            "mateType": int(mate["MateType"]),
                            "mateTypeName": "swMateCONCENTRIC",
                            "alignment": int(mate["Alignment"]),
                            "alignmentName": mate["AlignmentName"],
                            "endpointRoleA": f"locating_hole_{index}",
                            "endpointRoleB": f"locating_hole_{index}",
                        }
                        for index, mate in enumerate(concentric, start=1)
                    ],
                ],
            }
        ],
    }
    base_graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": 2,
        "InterModuleMateCount": 0,
        "Modules": [aa00, af00],
        "Mates": [],
        "EditPolicy": {
            "baseModuleToken": AA00,
            "initialPlacementMode": "source_pose",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [AA00, AF00],
        },
        "BaseGraphPolicy": {
            "moduleTokens": [AA00, AF00],
            "fixedAtKnownContextPoses": True,
            "purpose": "Build an independent frame context before inserting AE00.",
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project03-add-AE00-three-datum-v1",
        "baseModuleToken": AA00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": [AA00, AF00],
        "componentToAdd": ae00,
        "connections": [
            {
                "connectionId": "AE00-installed-on-AA00",
                "portAId": "AE00.frame_installation",
                "portBId": "AA00.transport_installation",
                "templateId": "AE00_to_AA00_three_datum_installation",
            }
        ],
    }
    result = build_semantic_assembly_plan(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    effective = result["effectiveGraph"]
    effective.setdefault("SemanticAssemblyPlanAudit", {})["collisionPolicy"] = {
        "pair": [AA00, AE00],
        "classification": "intended-installation-contact",
        "broadPhasePolicy": "AABB overlap allowed",
        "exactGate": "conditional exact B-rep after insertion; reject new penetration beyond the source interface",
    }
    work_packet = {
        "schemaVersion": "project03-first-increment-work-packet/v1",
        "projectId": "project03",
        "stepId": "step-01-add-AE00",
        "baseModules": [AA00, AF00],
        "targetModule": AE00,
        "sourceMateNames": mate_names,
        "capturedMateNamesBeforeUnicodeRecovery": captured_mate_names,
        "mateNameUnicodeRecoveryApplied": captured_mate_names != mate_names,
        "sourceMateTypes": [str(item["MateTypeName"]) for item in mates],
        "locatingHoleSpacingMeters": spacing,
        "pathRecoveryPassed": path_audit["allResolved"],
        "endpointCount": len(endpoint_catalog.get("Endpoints") or []),
        "allEndpointsHavePersistentReferences": all(
            bool((item.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64"))
            for item in endpoint_catalog.get("Endpoints") or []
        ),
        "expectedResidualDof": 0,
        "safeToStartCad": bool(
            path_audit["allResolved"]
            and len(mates) == 3
            and len(endpoint_catalog.get("Endpoints") or []) == 6
        ),
        "executionPlan": [
            "Rebuild the independent AA00+AF00 fixed context from base graph.",
            "Insert AE00 from its independent source file at a non-source pose.",
            "Recover six registered face endpoints and create three driving mates.",
            "Save, reopen, verify 3/3 mates, zero residual rigid DOF and context stability.",
            "Run AABB broad phase and conditional exact installation-contact audit.",
        ],
        "knownLimits": [
            "The interface dimensions are prototype-confirmed, not vendor-confirmed.",
            "Persistent references were captured in the prototype; independent rebuild also relies on relative leaf path and body/face fallback.",
            "The first CAD run must prove that the AA00+AF00 fixed-context abstraction is sufficient.",
        ],
    }
    return {
        "normalizedSourceGraph": graph,
        "pathAudit": path_audit,
        "endpointCatalog": endpoint_catalog,
        "semanticCatalog": semantic_catalog,
        "baseGraph": base_graph,
        "request": request,
        "patch": result["patch"],
        "effectiveGraph": effective,
        "summary": work_packet,
    }


def build_project03_ad00_work_packet(
    source_graph: dict[str, Any], prototype_assembly: Path
) -> dict[str, Any]:
    """Compile the second increment: add rigid AD00 to the closed AE00 context."""

    ad00 = "FL9A24D063AD00"
    selected = {AA00, AF00, AE00, ad00}
    graph, path_audit = normalize_project03_paths(
        source_graph, prototype_assembly, selected_tokens=selected
    )
    mates = _pair_mates(graph, AA00, ad00)
    coincident = [item for item in mates if item.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [item for item in mates if item.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError("AA00/AD00 must contain one coincident and two concentric mates.")
    if not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError("AA00/AD00 contains an unsupported mate.")
    coincident[0]["MateName"] = "重合27"
    concentric.sort(key=lambda item: float(_endpoint(item, AA00)["FaceCenterWorld"][2]))
    for name, item in zip(("同心36", "同心38"), concentric):
        item["MateName"] = name
    mate_names = [str(item["MateName"]) for item in mates]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    modules = {token: copy.deepcopy(_module(graph, token)) for token in selected}
    role_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("support_plane", _endpoint(coincident[0], ad00), _endpoint(coincident[0], AA00)),
        ("locating_hole_1", _endpoint(concentric[0], ad00), _endpoint(concentric[0], AA00)),
        ("locating_hole_2", _endpoint(concentric[1], ad00), _endpoint(concentric[1], AA00)),
    ]
    ports = []
    for token, port_id, display, aliases, target_side in (
        (ad00, "AD00.frame_installation", "AD00翻转定位安装端口", ["AD00安装接口"], True),
        (AA00, "AA00.ad00_installation", "AA00翻转定位承载端口", ["AA00翻转安装位"], False),
    ):
        ports.append({
            "portId": port_id,
            "displayName": display,
            "description": "AA00/AD00支承面及双定位孔接口。",
            "moduleToken": token,
            "moduleHierarchyPath": modules[token]["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project03_flip_station_frame_installation",
            "capabilities": ["installation", "station_alignment"],
            "aliases": aliases,
            "status": "prototype-confirmed",
            "endpointBindings": [
                {
                    "role": role,
                    "endpointId": _catalog_endpoint_id(
                        catalog, target if target_side else base
                    ),
                }
                for role, target, base in role_rows
            ],
            "evidence": ["项目03原型：重合27、同心36、同心38"],
        })
    template_steps = [{
        "mateName": "重合27",
        "mateType": int(coincident[0]["MateType"]),
        "mateTypeName": "swMateCOINCIDENT",
        "alignment": int(coincident[0]["Alignment"]),
        "alignmentName": coincident[0]["AlignmentName"],
        "endpointRoleA": "support_plane",
        "endpointRoleB": "support_plane",
    }]
    for index, mate in enumerate(concentric, start=1):
        template_steps.append({
            "mateName": str(mate["MateName"]),
            "mateType": int(mate["MateType"]),
            "mateTypeName": "swMateCONCENTRIC",
            "alignment": int(mate["Alignment"]),
            "alignmentName": mate["AlignmentName"],
            "endpointRoleA": f"locating_hole_{index}",
            "endpointRoleB": f"locating_hole_{index}",
        })
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": "Install AD00 on AA00 after the AE00 transport checkpoint.",
        "ports": ports,
        "connectionTemplates": [{
            "templateId": "AD00_to_AA00_three_datum_installation",
            "purposes": ["installation"],
            "interfaceTypeA": "project03_flip_station_frame_installation",
            "interfaceTypeB": "project03_flip_station_frame_installation",
            "constraintEffect": {
                "purpose": "Recover the rigid AD00 station pose.",
                "fullyLocatesAddedComponent": True,
                "expectedResidualDof": 0,
            },
            "mateSteps": template_steps,
        }],
    }
    base = {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": 3,
        "InterModuleMateCount": 0,
        "Modules": [modules[AA00], modules[AF00], modules[AE00]],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": [AA00, AF00, AE00],
            "fixedAtKnownContextPoses": True,
            "purpose": "Reuse the already closed AA00+AF00+AE00 checkpoint as context.",
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project03-add-AD00-three-datum-v1",
        "baseModuleToken": AA00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": [AA00, AF00, AE00],
        "componentToAdd": modules[ad00],
        "connections": [{
            "connectionId": "AD00-installed-on-AA00",
            "portAId": "AD00.frame_installation",
            "portBId": "AA00.ad00_installation",
            "templateId": "AD00_to_AA00_three_datum_installation",
        }],
    }
    result = build_semantic_assembly_plan(base, semantic, catalog, request)
    result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})[
        "dynamicStateBoundary"
    ] = {
        "topLevelInstallation": "validated-by-this-step",
        "internalAd10Ad20States": "preserved-from-independent-AD00-file",
        "sweptVolumeValidated": False,
        "reason": "This checkpoint validates static installation only; 25-degree flip sweep remains a later dynamic gate.",
    }
    summary = {
        "schemaVersion": "project03-second-increment-work-packet/v1",
        "projectId": "project03",
        "stepId": "step-02-add-AD00",
        "baseModules": [AA00, AF00, AE00],
        "targetModule": ad00,
        "sourceMateNames": mate_names,
        "sourceMateTypes": [str(item["MateTypeName"]) for item in mates],
        "endpointCount": len(catalog.get("Endpoints") or []),
        "pathRecoveryPassed": path_audit["allResolved"],
        "expectedResidualDof": 0,
        "staticCadReady": bool(path_audit["allResolved"] and len(mates) == 3),
        "dynamicSweepReady": False,
        "knownLimits": [
            "This step validates the installed static state only.",
            "The 25-degree flip sweep and actuator limits are not yet closed.",
            "The independent AD00 file must preserve both internal station states on reopen.",
        ],
    }
    return {
        "pathAudit": path_audit,
        "endpointCatalog": catalog,
        "semanticCatalog": semantic,
        "baseGraph": base,
        "request": request,
        "patch": result["patch"],
        "effectiveGraph": result["effectiveGraph"],
        "summary": summary,
    }


def build_project03_ai00_work_packet(
    source_graph: dict[str, Any], prototype_assembly: Path, scanner_geometry: dict[str, Any]
) -> dict[str, Any]:
    """Compile the third increment: mechanically install AI00 and retain optical checks."""
    ad00, ai00 = "FL9A24D063AD00", "FL9A24D063AI00"
    selected = {AA00, AF00, AE00, ad00, ai00}
    graph, path_audit = normalize_project03_paths(
        source_graph, prototype_assembly, selected_tokens=selected
    )
    mates = _pair_mates(graph, AA00, ai00)
    expected_types = {"swMateCOINCIDENT": 1, "swMateDISTANCE": 2, "swMateCONCENTRIC": 2}
    actual_types = {name: sum(item.get("MateTypeName") == name for item in mates) for name in expected_types}
    if actual_types != expected_types or not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError(f"Unexpected AA00/AI00 mate bundle: {actual_types}")
    by_type = {name: [item for item in mates if item.get("MateTypeName") == name] for name in expected_types}
    by_type["swMateCOINCIDENT"][0]["MateName"] = "重合8"
    distances = sorted(by_type["swMateDISTANCE"], key=lambda item: float(item.get("Distance") or 0), reverse=True)
    distances[0]["MateName"], distances[1]["MateName"] = "距离1", "距离2"
    concentric = sorted(by_type["swMateCONCENTRIC"], key=lambda item: float(_endpoint(item, AA00)["FaceCenterWorld"][2]))
    concentric[0]["MateName"], concentric[1]["MateName"] = "同心31", "同心32"
    mate_names = [str(item["MateName"]) for item in mates]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    modules = {token: copy.deepcopy(_module(graph, token)) for token in selected}
    roles: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    ordered = [by_type["swMateCOINCIDENT"][0], *distances, *concentric]
    role_names = ["support_plane", "longitudinal_offset", "lateral_offset", "locating_hole_1", "locating_hole_2"]
    for role, mate in zip(role_names, ordered):
        roles.append((role, _endpoint(mate, ai00), _endpoint(mate, AA00), mate))
    def port(token: str, pid: str, target_side: bool) -> dict[str, Any]:
        return {
            "portId": pid,
            "displayName": "AI00扫描安装端口" if target_side else "AA00扫描承载端口",
            "moduleToken": token,
            "moduleHierarchyPath": modules[token]["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project03_scanner_frame_installation",
            "capabilities": ["installation", "scanner_alignment"],
            "aliases": ["扫描安装接口" if target_side else "扫描承载接口"],
            "status": "prototype-confirmed",
            "endpointBindings": [{"role": role, "endpointId": _catalog_endpoint_id(catalog, target if target_side else base)} for role, target, base, _ in roles],
            "evidence": ["项目03原型5条AA00–AI00机械配合"],
        }
    steps = []
    for role, _, _, mate in roles:
        step = {
            "mateName": str(mate["MateName"]),
            "mateType": int(mate["MateType"]),
            "mateTypeName": str(mate["MateTypeName"]),
            "alignment": int(mate["Alignment"]),
            "alignmentName": mate["AlignmentName"],
            "endpointRoleA": role,
            "endpointRoleB": role,
        }
        if mate.get("Distance") is not None:
            step["distanceMeters"] = float(mate["Distance"])
            step["applicationMode"] = "validate_only"
            step["tolerance"] = {"distanceMeters": 1e-6}
        steps.append(step)
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1", "projectId": "project03",
        "catalogPurpose": "Install AI00 mechanically; optical geometry remains validation-only.",
        "ports": [port(ai00, "AI00.frame_installation", True), port(AA00, "AA00.ai00_installation", False)],
        "connectionTemplates": [{
            "templateId": "AI00_to_AA00_five_mate_installation", "purposes": ["installation"],
            "interfaceTypeA": "project03_scanner_frame_installation", "interfaceTypeB": "project03_scanner_frame_installation",
            "constraintEffect": {"purpose": "Recover the rigid scanner installation pose.", "fullyLocatesAddedComponent": True, "expectedResidualDof": 0},
            "mateSteps": steps,
        }],
    }
    base = {
        "SchemaVersion": "assembly-module-mate-graph/v2", "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": 4, "InterModuleMateCount": 0,
        "Modules": [modules[t] for t in (AA00, AF00, AE00, ad00)], "Mates": [],
        "BaseGraphPolicy": {"moduleTokens": [AA00, AF00, AE00, ad00], "fixedAtKnownContextPoses": True, "purpose": "Reuse the closed AD00 static checkpoint."},
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1", "planId": "project03-add-AI00-five-mate-v1",
        "baseModuleToken": AA00, "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": [AA00, AF00, AE00, ad00], "componentToAdd": modules[ai00],
        "connections": [{"connectionId": "AI00-installed-on-AA00", "portAId": "AI00.frame_installation", "portBId": "AA00.ai00_installation", "templateId": "AI00_to_AA00_five_mate_installation"}],
    }
    result = build_semantic_assembly_plan(base, semantic, catalog, request)
    scanner = (scanner_geometry.get("scanners") or [{}])[0]
    result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})["opticalValidation"] = {
        "applicationMode": "validate_only", "scannerModel": scanner_geometry.get("scannerModel"),
        "modeledWorkingDistanceMeters": scanner.get("modeledWorkingDistanceMeters"),
        "opticalDirectionWorld": scanner.get("opticalDirectionWorld"),
        "targetProxyWorldMeters": scanner.get("targetProxyWorldMeters"),
        "engineeringConfirmed": scanner_geometry.get("engineeringConfirmed") is True,
        "carrierIdentityRoleStatus": (scanner_geometry.get("barcodeInterfaces") or {}).get("carrierBarcode", {}).get("status"),
    }
    summary = {
        "schemaVersion": "project03-third-increment-work-packet/v1", "projectId": "project03", "stepId": "step-03-add-AI00",
        "baseModules": [AA00, AF00, AE00, ad00], "targetModule": ai00,
        "sourceMateNames": mate_names, "sourceMateTypes": [str(item["MateTypeName"]) for item in mates],
        "endpointCount": len(catalog.get("Endpoints") or []), "pathRecoveryPassed": path_audit["allResolved"],
        "expectedResidualDof": 0, "drivingMateCount": 3, "validationRelationCount": 2,
        "staticCadReady": bool(path_audit["allResolved"] and len(mates) == 5),
        "opticalValidationReady": scanner.get("modeledWorkingDistanceMeters") == 0.1,
        "productionOpticalReady": scanner_geometry.get("engineeringConfirmed") is True,
        "knownLimits": [
            "The two source distance relations are validation-only because the plane plus two locating holes already fixes the rigid pose; driving all five relations over-defines the rebuilt assembly.",
            *(scanner_geometry.get("interpretationLimits") or []),
        ],
    }
    return {"pathAudit": path_audit, "endpointCatalog": catalog, "semanticCatalog": semantic, "baseGraph": base, "request": request, "patch": result["patch"], "effectiveGraph": result["effectiveGraph"], "summary": summary}


def build_project03_ag00_work_packet(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    service_points: dict[str, Any],
    *,
    case_anchored: bool = False,
    calibrated_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the fourth increment and expose AG00's residual rotational DOF."""

    ad00, ai00, ag00 = (
        "FL9A24D063AD00",
        "FL9A24D063AI00",
        "FL9A24D063AG00",
    )
    selected = {AA00, AF00, AE00, ad00, ai00, ag00}
    graph, path_audit = normalize_project03_paths(
        source_graph, prototype_assembly, selected_tokens=selected
    )
    mates = _pair_mates(graph, AA00, ag00)
    coincident = [item for item in mates if item.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [item for item in mates if item.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 1 or len(mates) != 2:
        raise ValueError("AA00/AG00 must contain one coincident and one concentric mate.")
    if not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError("AA00/AG00 contains an unsupported source mate.")
    coincident[0]["MateName"] = "重合6"
    concentric[0]["MateName"] = "同心11"
    mate_names = ["重合6", "同心11"]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    modules = {token: copy.deepcopy(_module(graph, token)) for token in selected}
    calibrated_anchor_audit = None
    if case_anchored and calibrated_parameters is not None:
        calibrated_anchor_audit = apply_calibrated_pose_anchor(
            modules[ag00], ag00, calibrated_parameters
        )
    roles = [
        ("support_plane", coincident[0]),
        ("primary_locating_hole", concentric[0]),
    ]

    def port(token: str, port_id: str, target_side: bool) -> dict[str, Any]:
        return {
            "portId": port_id,
            "displayName": "AG00组合功能模组安装端口" if target_side else "AA00功能模组承载端口",
            "description": "原型只提供支承面和单定位孔；绕孔轴姿态尚无独立机械基准。",
            "moduleToken": token,
            "moduleHierarchyPath": modules[token]["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project03_service_cluster_frame_installation",
            "capabilities": ["installation", "service_cluster_support"],
            "aliases": ["AG00安装接口" if target_side else "AG00承载接口"],
            "status": "prototype-partial",
            "endpointBindings": [
                {
                    "role": role,
                    "endpointId": _catalog_endpoint_id(
                        catalog,
                        _endpoint(mate, ag00 if target_side else AA00),
                    ),
                }
                for role, mate in roles
            ],
            "evidence": ["项目03原型：重合6、同心11"],
        }

    steps = [
        {
            "mateName": str(mate["MateName"]),
            "mateType": int(mate["MateType"]),
            "mateTypeName": str(mate["MateTypeName"]),
            "alignment": int(mate["Alignment"]),
            "alignmentName": mate["AlignmentName"],
            "endpointRoleA": role,
            "endpointRoleB": role,
        }
        for role, mate in roles
    ]
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": "Install AG00 while keeping service targets validation-only.",
        "ports": [
            port(ag00, "AG00.frame_installation", True),
            port(AA00, "AA00.ag00_installation", False),
        ],
        "connectionTemplates": [
            {
                "templateId": "AG00_to_AA00_partial_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project03_service_cluster_frame_installation",
                "interfaceTypeB": "project03_service_cluster_frame_installation",
                "constraintEffect": {
                    "purpose": "Recover support plane and primary hole; expose residual rotation.",
                    "fullyLocatesAddedComponent": case_anchored,
                    "expectedResidualDof": 0 if case_anchored else 1,
                },
                "mateSteps": steps,
            }
        ],
    }
    base_tokens = (AA00, AF00, AE00, ad00, ai00)
    base = {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": len(base_tokens),
        "InterModuleMateCount": 0,
        "Modules": [modules[token] for token in base_tokens],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": list(base_tokens),
            "fixedAtKnownContextPoses": True,
            "purpose": "Reuse the closed AI00 cumulative checkpoint.",
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": (
            "project03-add-AG00-explicit-residual-anchor-v1"
            if case_anchored
            else "project03-add-AG00-two-mate-dof-diagnostic-v1"
        ),
        "baseModuleToken": AA00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": list(base_tokens),
        "caseAnchoredModuleTokens": [ag00] if case_anchored else [],
        "componentToAdd": modules[ag00],
        "connections": [
            {
                "connectionId": "AG00-installed-on-AA00",
                "portAId": "AG00.frame_installation",
                "portBId": "AA00.ag00_installation",
                "templateId": "AG00_to_AA00_partial_installation",
            }
        ],
    }
    result = build_semantic_assembly_plan(base, semantic, catalog, request)
    ag_service_ports = [
        copy.deepcopy(row)
        for row in service_points.get("servicePorts") or []
        if str(row.get("sourceSubassembly") or "").upper().startswith("FL9A24D063AG")
    ]
    audit = result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})
    audit["serviceTargetValidation"] = {
        "applicationMode": "validate_only",
        "targetCount": len(ag_service_ports),
        "targets": ag_service_ports,
        "engineeringConfirmed": service_points.get("engineeringConfirmed") is True,
    }
    audit["residualDofBoundary"] = {
        "sourceDrivingMateCount": 2,
        "expectedResidualDofWithoutAnchor": 1,
        "caseAnchorApplied": case_anchored,
        "caseAnchorAuthority": (
            (
                "versioned-project-parameter:"
                + str(calibrated_anchor_audit["authority"])
            )
            if calibrated_anchor_audit is not None
            else (
                "project03-prototype-source-transform-temporary-fallback"
                if case_anchored
                else None
            )
        ),
        "calibratedAnchor": copy.deepcopy(calibrated_anchor_audit),
        "runtimePrototypeTopLevelPoseReadRequired": bool(
            case_anchored and calibrated_anchor_audit is None
        ),
        "replacementRequired": "Add a second locating datum or an explicit anti-rotation orientation rule.",
    }
    summary = {
        "schemaVersion": "project03-fourth-increment-work-packet/v1",
        "projectId": "project03",
        "stepId": "step-04-add-AG00",
        "baseModules": list(base_tokens),
        "targetModule": ag00,
        "sourceMateNames": mate_names,
        "sourceMateTypes": [str(item["MateTypeName"]) for item in mates],
        "endpointCount": len(catalog.get("Endpoints") or []),
        "pathRecoveryPassed": path_audit["allResolved"],
        "expectedResidualDofWithoutAnchor": 1,
        "caseAnchored": case_anchored,
        "calibratedAnchorApplied": calibrated_anchor_audit is not None,
        "runtimePrototypeTopLevelPoseReadRequired": bool(
            case_anchored and calibrated_anchor_audit is None
        ),
        "diagnosticCadReady": bool(path_audit["allResolved"] and len(mates) == 2),
        "staticCadReady": bool(path_audit["allResolved"] and len(mates) == 2 and case_anchored),
        "serviceTargetCount": len(ag_service_ports),
        "productionServiceTargetsReady": service_points.get("engineeringConfirmed") is True,
        "knownLimits": [
            "The source plane-plus-single-hole bundle is expected to leave one rotational degree of freedom.",
            "The optional case anchor is a transparent prototype fallback, not a vendor installation datum.",
            *(service_points.get("interpretationLimits") or []),
        ],
    }
    return {
        "pathAudit": path_audit,
        "endpointCatalog": catalog,
        "semanticCatalog": semantic,
        "baseGraph": base,
        "request": request,
        "patch": result["patch"],
        "effectiveGraph": result["effectiveGraph"],
        "summary": summary,
    }


def build_project03_ah00_work_packet(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    service_points: dict[str, Any],
) -> dict[str, Any]:
    """Compile the fifth increment: install AH00 and validate its calibration proxy."""

    ad00, ai00, ag00, ah00 = (
        "FL9A24D063AD00",
        "FL9A24D063AI00",
        "FL9A24D063AG00",
        "FL9A24D063AH00",
    )
    selected = {AA00, AF00, AE00, ad00, ai00, ag00, ah00}
    graph, path_audit = normalize_project03_paths(
        source_graph, prototype_assembly, selected_tokens=selected
    )
    mates = _pair_mates(graph, AA00, ah00)
    coincident = [item for item in mates if item.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [item for item in mates if item.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2 or len(mates) != 3:
        raise ValueError("AA00/AH00 must contain one coincident and two concentric mates.")
    if not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError("AA00/AH00 contains an unsupported source mate.")
    coincident[0]["MateName"] = "重合7"
    concentric.sort(key=lambda item: tuple(float(v) for v in _endpoint(item, AA00)["FaceCenterWorld"]))
    concentric[0]["MateName"], concentric[1]["MateName"] = "同心12", "同心13"
    ordered = [coincident[0], *concentric]
    roles = ["support_plane", "locating_hole_1", "locating_hole_2"]
    mate_names = [str(item["MateName"]) for item in ordered]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    modules = {token: copy.deepcopy(_module(graph, token)) for token in selected}

    def port(token: str, port_id: str, target_side: bool) -> dict[str, Any]:
        return {
            "portId": port_id,
            "displayName": "AH00校准安装端口" if target_side else "AA00校准承载端口",
            "moduleToken": token,
            "moduleHierarchyPath": modules[token]["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project03_calibration_frame_installation",
            "capabilities": ["installation", "calibration_support"],
            "aliases": ["校准安装接口" if target_side else "校准承载接口"],
            "status": "prototype-confirmed",
            "endpointBindings": [
                {
                    "role": role,
                    "endpointId": _catalog_endpoint_id(
                        catalog, _endpoint(mate, ah00 if target_side else AA00)
                    ),
                }
                for role, mate in zip(roles, ordered)
            ],
            "evidence": ["项目03原型：重合7、同心12、同心13"],
        }

    steps = [
        {
            "mateName": str(mate["MateName"]),
            "mateType": int(mate["MateType"]),
            "mateTypeName": str(mate["MateTypeName"]),
            "alignment": int(mate["Alignment"]),
            "alignmentName": mate["AlignmentName"],
            "endpointRoleA": role,
            "endpointRoleB": role,
        }
        for role, mate in zip(roles, ordered)
    ]
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project03",
        "catalogPurpose": "Install AH00 mechanically and keep the prism point validation-only.",
        "ports": [
            port(ah00, "AH00.frame_installation", True),
            port(AA00, "AA00.ah00_installation", False),
        ],
        "connectionTemplates": [
            {
                "templateId": "AH00_to_AA00_three_datum_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project03_calibration_frame_installation",
                "interfaceTypeB": "project03_calibration_frame_installation",
                "constraintEffect": {
                    "purpose": "Recover the rigid AH00 calibration-module pose.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": steps,
            }
        ],
    }
    base_tokens = (AA00, AF00, AE00, ad00, ai00, ag00)
    base = {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": len(base_tokens),
        "InterModuleMateCount": 0,
        "Modules": [modules[token] for token in base_tokens],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": list(base_tokens),
            "fixedAtKnownContextPoses": True,
            "purpose": "Reuse the closed AG00 cumulative checkpoint.",
        },
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project03-add-AH00-three-datum-v1",
        "baseModuleToken": AA00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": list(base_tokens),
        "componentToAdd": modules[ah00],
        "connections": [
            {
                "connectionId": "AH00-installed-on-AA00",
                "portAId": "AH00.frame_installation",
                "portBId": "AA00.ah00_installation",
                "templateId": "AH00_to_AA00_three_datum_installation",
            }
        ],
    }
    result = build_semantic_assembly_plan(base, semantic, catalog, request)
    calibration = [
        copy.deepcopy(row)
        for row in service_points.get("servicePorts") or []
        if row.get("capability") == "calibration"
    ]
    result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})[
        "calibrationTargetValidation"
    ] = {
        "applicationMode": "validate_only",
        "targetCount": len(calibration),
        "targets": calibration,
        "engineeringConfirmed": service_points.get("engineeringConfirmed") is True,
    }
    summary = {
        "schemaVersion": "project03-fifth-increment-work-packet/v1",
        "projectId": "project03",
        "stepId": "step-05-add-AH00",
        "baseModules": list(base_tokens),
        "targetModule": ah00,
        "sourceMateNames": mate_names,
        "sourceMateTypes": [str(item["MateTypeName"]) for item in ordered],
        "endpointCount": len(catalog.get("Endpoints") or []),
        "pathRecoveryPassed": path_audit["allResolved"],
        "expectedResidualDof": 0,
        "staticCadReady": bool(path_audit["allResolved"] and len(ordered) == 3),
        "calibrationTargetCount": len(calibration),
        "productionCalibrationReady": service_points.get("engineeringConfirmed") is True,
        "knownLimits": [
            "The calibration target is a prism top-center proxy rather than an authored nozzle datum.",
            "Two-photo camera offsets, 40 mm second-shot motion, insertion depth and tool sweep remain unmodeled.",
        ],
    }
    return {
        "pathAudit": path_audit,
        "endpointCatalog": catalog,
        "semanticCatalog": semantic,
        "baseGraph": base,
        "request": request,
        "patch": result["patch"],
        "effectiveGraph": result["effectiveGraph"],
        "summary": summary,
    }


def build_project03_aj00_work_packet(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    occupancy: dict[str, Any],
) -> dict[str, Any]:
    """Compile the sixth increment: install AJ00 and retain maintenance validation debt."""

    ad00, ai00, ag00, ah00, aj00 = (
        "FL9A24D063AD00", "FL9A24D063AI00", "FL9A24D063AG00",
        "FL9A24D063AH00", "FL9A24D063AJ00",
    )
    selected = {AA00, AF00, AE00, ad00, ai00, ag00, ah00, aj00}
    graph, path_audit = normalize_project03_paths(source_graph, prototype_assembly, selected_tokens=selected)
    mates = _pair_mates(graph, AA00, aj00)
    coincident = [item for item in mates if item.get("MateTypeName") == "swMateCOINCIDENT"]
    concentric = [item for item in mates if item.get("MateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2 or len(mates) != 3:
        raise ValueError("AA00/AJ00 must contain one coincident and two concentric mates.")
    if not all(item.get("IsBasicTwoFaceRebuildable") is True for item in mates):
        raise ValueError("AA00/AJ00 contains an unsupported source mate.")
    coincident[0]["MateName"] = "重合9"
    concentric.sort(key=lambda item: tuple(float(v) for v in _endpoint(item, AA00)["FaceCenterWorld"]))
    concentric[0]["MateName"], concentric[1]["MateName"] = "同心24", "同心25"
    ordered = [coincident[0], *concentric]
    roles = ["support_plane", "locating_hole_1", "locating_hole_2"]
    mate_names = [str(item["MateName"]) for item in ordered]
    catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    modules = {token: copy.deepcopy(_module(graph, token)) for token in selected}

    def port(token: str, port_id: str, target_side: bool) -> dict[str, Any]:
        return {
            "portId": port_id,
            "displayName": "AJ00供胶安装端口" if target_side else "AA00供胶承载端口",
            "moduleToken": token,
            "moduleHierarchyPath": modules[token]["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project03_glue_supply_frame_installation",
            "capabilities": ["installation", "glue_supply_support"],
            "aliases": ["供胶安装接口" if target_side else "供胶承载接口"],
            "status": "prototype-confirmed",
            "endpointBindings": [
                {"role": role, "endpointId": _catalog_endpoint_id(catalog, _endpoint(mate, aj00 if target_side else AA00))}
                for role, mate in zip(roles, ordered)
            ],
            "evidence": ["项目03原型：重合9、同心24、同心25"],
        }

    steps = [{
        "mateName": str(mate["MateName"]), "mateType": int(mate["MateType"]),
        "mateTypeName": str(mate["MateTypeName"]), "alignment": int(mate["Alignment"]),
        "alignmentName": mate["AlignmentName"], "endpointRoleA": role, "endpointRoleB": role,
    } for role, mate in zip(roles, ordered)]
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1", "projectId": "project03",
        "catalogPurpose": "Install AJ00 mechanically; hose and maintenance envelopes are validation-only.",
        "ports": [port(aj00, "AJ00.frame_installation", True), port(AA00, "AA00.aj00_installation", False)],
        "connectionTemplates": [{
            "templateId": "AJ00_to_AA00_three_datum_installation", "purposes": ["installation"],
            "interfaceTypeA": "project03_glue_supply_frame_installation", "interfaceTypeB": "project03_glue_supply_frame_installation",
            "constraintEffect": {"purpose": "Recover the rigid AJ00 supply-module pose.", "fullyLocatesAddedComponent": True, "expectedResidualDof": 0},
            "mateSteps": steps,
        }],
    }
    base_tokens = (AA00, AF00, AE00, ad00, ai00, ag00, ah00)
    base = {
        "SchemaVersion": "assembly-module-mate-graph/v2", "SourceAssemblyPath": str(prototype_assembly.resolve()),
        "ModuleCount": len(base_tokens), "InterModuleMateCount": 0,
        "Modules": [modules[token] for token in base_tokens], "Mates": [],
        "BaseGraphPolicy": {"moduleTokens": list(base_tokens), "fixedAtKnownContextPoses": True, "purpose": "Reuse the closed AH00 cumulative checkpoint."},
    }
    request = {
        "schemaVersion": "semantic-assembly-plan/v1", "planId": "project03-add-AJ00-three-datum-v1",
        "baseModuleToken": AA00, "initialPlacementMode": "deterministic", "fixedContextModuleTokens": list(base_tokens),
        "componentToAdd": modules[aj00],
        "connections": [{"connectionId": "AJ00-installed-on-AA00", "portAId": "AJ00.frame_installation", "portBId": "AA00.aj00_installation", "templateId": "AJ00_to_AA00_three_datum_installation"}],
    }
    result = build_semantic_assembly_plan(base, semantic, catalog, request)
    supply_objects = [row for row in occupancy.get("layoutObjects") or [] if row.get("primaryCode") == "AJ00"]
    supply = copy.deepcopy(supply_objects[0]) if len(supply_objects) == 1 else None
    result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})["maintenanceValidation"] = {
        "applicationMode": "validate_only", "staticOccupancy": supply,
        "hoseContinuousSweepAvailable": False, "maintenanceEnvelopeEngineeringConfirmed": False,
    }
    summary = {
        "schemaVersion": "project03-sixth-increment-work-packet/v1", "projectId": "project03", "stepId": "step-06-add-AJ00",
        "baseModules": list(base_tokens), "targetModule": aj00, "sourceMateNames": mate_names,
        "sourceMateTypes": [str(item["MateTypeName"]) for item in ordered], "endpointCount": len(catalog.get("Endpoints") or []),
        "pathRecoveryPassed": path_audit["allResolved"], "expectedResidualDof": 0,
        "staticCadReady": bool(path_audit["allResolved"] and len(ordered) == 3 and supply is not None),
        "staticOccupancyAvailable": supply is not None, "productionMaintenanceReady": False,
        "knownLimits": ["AJ00 currently uses one conservative top-level AABB.", "Hose continuous sweep and engineering maintenance clearance are not available."],
    }
    return {"pathAudit": path_audit, "endpointCatalog": catalog, "semanticCatalog": semantic, "baseGraph": base, "request": request, "patch": result["patch"], "effectiveGraph": result["effectiveGraph"], "summary": summary}


def build_project03_ab00_work_packet(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    valve_reach: dict[str, Any],
    *,
    calibrated_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile final-stage action 1: insert AB00 with an explicit residual anchor."""
    ad00,ai00,ag00,ah00,aj00,ab00=("FL9A24D063AD00","FL9A24D063AI00","FL9A24D063AG00","FL9A24D063AH00","FL9A24D063AJ00","FL9A24D063AB00")
    selected={AA00,AF00,AE00,ad00,ai00,ag00,ah00,aj00,ab00}
    graph,audit=normalize_project03_paths(source_graph,prototype_assembly,selected_tokens=selected)
    all_mates=_pair_mates(graph,AA00,ab00)
    basic=[m for m in all_mates if m.get("IsBasicTwoFaceRebuildable") is True]
    unsupported=[m for m in all_mates if m.get("IsBasicTwoFaceRebuildable") is not True]
    if len(basic)!=2 or {m.get("MateTypeName") for m in basic}!={"swMateCOINCIDENT","swMateDISTANCE"} or len(unsupported)!=1 or unsupported[0].get("MateTypeName")!="swMateWIDTH":raise ValueError("Unexpected AA00/AB00 mate bundle.")
    for m in basic:
        m["MateName"]="重合25" if m.get("MateTypeName")=="swMateCOINCIDENT" else "距离5"
    ordered=sorted(basic,key=lambda m:0 if m["MateTypeName"]=="swMateCOINCIDENT" else 1);roles=["support_plane","height_offset"]
    catalog=build_face_endpoint_catalog_from_source_mates(graph,[str(m["MateName"]) for m in ordered]);modules={t:copy.deepcopy(_module(graph,t)) for t in selected}
    calibrated_anchor_audit = None
    if calibrated_parameters is not None:
        calibrated_anchor_audit = apply_calibrated_pose_anchor(
            modules[ab00], ab00, calibrated_parameters
        )
    def port(t:str,pid:str,target:bool)->dict[str,Any]:return {"portId":pid,"displayName":"AB00龙门安装端口" if target else "AA00龙门承载端口","moduleToken":t,"moduleHierarchyPath":modules[t]["HierarchyPath"],"category":"mechanical","interfaceType":"project03_gantry_frame_partial_installation","capabilities":["installation","gantry_support"],"aliases":["龙门安装接口" if target else "龙门承载接口"],"status":"prototype-partial","endpointBindings":[{"role":r,"endpointId":_catalog_endpoint_id(catalog,_endpoint(m,ab00 if target else AA00))} for r,m in zip(roles,ordered)],"evidence":["项目03原型：重合25、距离5；宽度1不可由当前两面基础配合重建"]}
    steps=[]
    for role,m in zip(roles,ordered):
        s={"mateName":str(m["MateName"]),"mateType":int(m["MateType"]),"mateTypeName":str(m["MateTypeName"]),"alignment":int(m["Alignment"]),"alignmentName":m["AlignmentName"],"endpointRoleA":role,"endpointRoleB":role}
        if m.get("Distance") is not None:
            s["distanceMeters"]=float(m["Distance"])
            s["applicationMode"]="validate_only"
            s["tolerance"]={"distanceMeters":1e-6}
        steps.append(s)
    semantic={"schemaVersion":"semantic-port-catalog/v1","projectId":"project03","catalogPurpose":"Install AB00 while exposing the unsupported Width mate.","ports":[port(ab00,"AB00.frame_installation",True),port(AA00,"AA00.ab00_installation",False)],"connectionTemplates":[{"templateId":"AB00_to_AA00_partial_anchored_installation","purposes":["installation"],"interfaceTypeA":"project03_gantry_frame_partial_installation","interfaceTypeB":"project03_gantry_frame_partial_installation","constraintEffect":{"purpose":"Recover supported relations and close residual DOF with an explicit prototype anchor.","fullyLocatesAddedComponent":True,"expectedResidualDof":0},"mateSteps":steps}]}
    base_tokens=(AA00,AF00,AE00,ad00,ai00,ag00,ah00,aj00);base={"SchemaVersion":"assembly-module-mate-graph/v2","SourceAssemblyPath":str(prototype_assembly.resolve()),"ModuleCount":len(base_tokens),"InterModuleMateCount":0,"Modules":[modules[t] for t in base_tokens],"Mates":[],"BaseGraphPolicy":{"moduleTokens":list(base_tokens),"fixedAtKnownContextPoses":True,"purpose":"Reuse closed AJ00 checkpoint."}}
    req={"schemaVersion":"semantic-assembly-plan/v1","planId":"project03-add-AB00-partial-anchored-v1","baseModuleToken":AA00,"initialPlacementMode":"deterministic","fixedContextModuleTokens":list(base_tokens),"caseAnchoredModuleTokens":[ab00],"componentToAdd":modules[ab00],"connections":[{"connectionId":"AB00-installed-on-AA00","portAId":"AB00.frame_installation","portBId":"AA00.ab00_installation","templateId":"AB00_to_AA00_partial_anchored_installation"}]}
    result=build_semantic_assembly_plan(base,semantic,catalog,req);pa=result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit",{});pa["unsupportedSourceRelation"]={"mateName":"宽度1","mateTypeName":"swMateWIDTH","replacement":"versioned temporary pose parameter" if calibrated_anchor_audit is not None else "explicit prototype pose anchor for static demo","productionReplacementRequired":True,"calibratedAnchor":copy.deepcopy(calibrated_anchor_audit),"runtimePrototypeTopLevelPoseReadRequired":calibrated_anchor_audit is None};pa["reachValidation"]={"applicationMode":"validate_only","requiredTargetCount":valve_reach.get("requiredTargetCount"),"allInside":valve_reach.get("allRequiredTargetsInsideCommonReach"),"engineeringConfirmed":valve_reach.get("engineeringConfirmed") is True}
    summary={"schemaVersion":"project03-final-stage-ab00-work-packet/v1","projectId":"project03","stepId":"step-07a-add-AB00","baseModules":list(base_tokens),"targetModule":ab00,"drivingMateCount":1,"validationRelationCount":1,"unsupportedMateNames":["宽度1"],"endpointCount":len(catalog.get("Endpoints") or []),"pathRecoveryPassed":audit["allResolved"],"caseAnchored":True,"calibratedAnchorApplied":calibrated_anchor_audit is not None,"runtimePrototypeTopLevelPoseReadRequired":calibrated_anchor_audit is None,"staticCadReady":bool(audit["allResolved"] and valve_reach.get("allRequiredTargetsInsideCommonReach") is True),"requiredReachTargetCount":valve_reach.get("requiredTargetCount"),"productionReachReady":valve_reach.get("engineeringConfirmed") is True,"knownLimits":["Width mate is not rebuilt by the two-face executor.","Distance5 is validation-only because its advanced options do not round-trip reliably as a rebuilt driver.","AB00 uses a versioned prototype-calibrated temporary pose parameter for the static demo." if calibrated_anchor_audit is not None else "AB00 uses an explicit prototype pose anchor for the static demo.",*(valve_reach.get("interpretationLimits") or [])]}
    return {"pathAudit":audit,"endpointCatalog":catalog,"semanticCatalog":semantic,"baseGraph":base,"request":req,"patch":result["patch"],"effectiveGraph":result["effectiveGraph"],"summary":summary}


def build_project03_ac00_work_packet(source_graph: dict[str, Any], prototype_assembly: Path, valve_reach: dict[str, Any]) -> dict[str, Any]:
    """Compile final-stage action 2: insert AC00 using a minimal sufficient mate set."""
    ad00,ai00,ag00,ah00,aj00,ab00,ac00=("FL9A24D063AD00","FL9A24D063AI00","FL9A24D063AG00","FL9A24D063AH00","FL9A24D063AJ00","FL9A24D063AB00","FL9A24D063AC00")
    selected={AA00,AF00,AE00,ad00,ai00,ag00,ah00,aj00,ab00,ac00};graph,audit=normalize_project03_paths(source_graph,prototype_assembly,selected_tokens=selected)
    mates=_pair_mates(graph,ab00,ac00);co=[m for m in mates if m.get("MateTypeName")=="swMateCOINCIDENT"];cc=[m for m in mates if m.get("MateTypeName")=="swMateCONCENTRIC"]
    if len(co)!=2 or len(cc)!=2 or not all(m.get("IsBasicTwoFaceRebuildable") is True for m in mates):raise ValueError("Unexpected AB00/AC00 mate bundle.")
    support=max(co,key=lambda m:abs(float(_endpoint(m,ac00)["FaceNormalWorld"][0])) if _endpoint(m,ac00).get("FaceNormalWorld") else -1);support["MateName"]="重合26"
    redundant=[m for m in co if m is not support][0];redundant["MateName"]="重合29"
    cc.sort(key=lambda m:float(_endpoint(m,ac00)["FaceCenterWorld"][2]));cc[0]["MateName"],cc[1]["MateName"]="同心34","同心35"
    driving=[support,*cc];roles=["support_plane","locating_hole_1","locating_hole_2"];catalog=build_face_endpoint_catalog_from_source_mates(graph,[str(m["MateName"]) for m in driving]);modules={t:copy.deepcopy(_module(graph,t)) for t in selected}
    def port(t:str,pid:str,target:bool)->dict[str,Any]:return {"portId":pid,"displayName":"AC00双阀安装端口" if target else "AB00双阀承载端口","moduleToken":t,"moduleHierarchyPath":modules[t]["HierarchyPath"],"category":"mechanical","interfaceType":"project03_dual_valve_gantry_installation","capabilities":["installation","dual_valve_motion"],"aliases":["双阀安装接口" if target else "双阀承载接口"],"status":"prototype-confirmed","endpointBindings":[{"role":r,"endpointId":_catalog_endpoint_id(catalog,_endpoint(m,ac00 if target else ab00))} for r,m in zip(roles,driving)],"evidence":["项目03原型：重合26、同心34、同心35；重合29视为冗余关系"]}
    steps=[{"mateName":str(m["MateName"]),"mateType":int(m["MateType"]),"mateTypeName":str(m["MateTypeName"]),"alignment":int(m["Alignment"]),"alignmentName":m["AlignmentName"],"endpointRoleA":r,"endpointRoleB":r} for r,m in zip(roles,driving)]
    semantic={"schemaVersion":"semantic-port-catalog/v1","projectId":"project03","catalogPurpose":"Install AC00 with three clean drivers plus an explicit residual pose anchor.","ports":[port(ac00,"AC00.gantry_installation",True),port(ab00,"AB00.ac00_installation",False)],"connectionTemplates":[{"templateId":"AC00_to_AB00_three_relation_anchored_installation","purposes":["installation"],"interfaceTypeA":"project03_dual_valve_gantry_installation","interfaceTypeB":"project03_dual_valve_gantry_installation","constraintEffect":{"purpose":"Use the clean source subset and explicitly close the flexible-subtree residual pose.","fullyLocatesAddedComponent":True,"expectedResidualDof":0},"mateSteps":steps}]}
    base_tokens=(AA00,AF00,AE00,ad00,ai00,ag00,ah00,aj00,ab00);base={"SchemaVersion":"assembly-module-mate-graph/v2","SourceAssemblyPath":str(prototype_assembly.resolve()),"ModuleCount":len(base_tokens),"InterModuleMateCount":0,"Modules":[modules[t] for t in base_tokens],"Mates":[],"BaseGraphPolicy":{"moduleTokens":list(base_tokens),"fixedAtKnownContextPoses":True,"purpose":"Reuse context after AB00 insertion."}}
    req={"schemaVersion":"semantic-assembly-plan/v1","planId":"project03-add-AC00-three-relation-anchored-v3","baseModuleToken":ab00,"initialPlacementMode":"deterministic","fixedContextModuleTokens":list(base_tokens),"caseAnchoredModuleTokens":[ac00],"componentToAdd":modules[ac00],"connections":[{"connectionId":"AC00-installed-on-AB00","portAId":"AC00.gantry_installation","portBId":"AB00.ac00_installation","templateId":"AC00_to_AB00_three_relation_anchored_installation"}]}
    result=build_semantic_assembly_plan(base,semantic,catalog,req);pa=result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit",{});pa["relationSetDecision"]={"sourceMateCount":4,"drivingMateCount":3,"caseAnchorApplied":True,"threeMateNonAnchoredPoseResidualMeters":0.05430055340485568,"fourMateFailure":"重合29 returned swAddMateError_OverDefinedAssembly","reason":"Use the clean three-relation subset and make the remaining flexible-subtree pose dependency explicit."};pa["reachValidation"]={"applicationMode":"validate_only","requiredTargetCount":valve_reach.get("requiredTargetCount"),"checks":copy.deepcopy(valve_reach.get("requiredTargetChecks") or []),"allInside":valve_reach.get("allRequiredTargetsInsideCommonReach"),"minimumBoundaryMarginMeters":valve_reach.get("minimumTargetBoundaryMarginMeters"),"engineeringConfirmed":valve_reach.get("engineeringConfirmed") is True}
    summary={"schemaVersion":"project03-final-stage-ac00-work-packet/v3","projectId":"project03","stepId":"step-07b-add-AC00","baseModules":list(base_tokens),"targetModule":ac00,"sourceMateCount":4,"drivingMateCount":3,"caseAnchored":True,"failedThreeMatePoseResidualMeters":0.05430055340485568,"failedFourMateOverdefinedMate":"重合29","endpointCount":len(catalog.get("Endpoints") or []),"pathRecoveryPassed":audit["allResolved"],"expectedResidualDof":0,"staticCadReady":bool(audit["allResolved"] and valve_reach.get("allRequiredTargetsInsideCommonReach") is True),"requiredReachTargetCount":valve_reach.get("requiredTargetCount"),"productionReachReady":valve_reach.get("engineeringConfirmed") is True,"knownLimits":["The non-anchored three-relation run left a 54.300553 mm top-level Z residual.","The four-relation run over-defined 重合29; the static demo therefore uses an explicit AC00 prototype residual anchor.",*(valve_reach.get("interpretationLimits") or [])]}
    return {"pathAudit":audit,"endpointCatalog":catalog,"semanticCatalog":semantic,"baseGraph":base,"request":req,"patch":result["patch"],"effectiveGraph":result["effectiveGraph"],"summary":summary}
