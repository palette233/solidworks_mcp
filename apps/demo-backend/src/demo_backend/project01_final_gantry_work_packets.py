"""Compile Project01 final LM00 and ZZ00 incremental CAD work packets."""

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
from .project01_three_datum_work_packet import build_project01_three_datum_work_packet
from .semantic_port_catalog import build_semantic_assembly_plan


JJ00 = "JJ00"
LM00 = "LM00"
ZZ00 = "ZZ00"
LM_CONTEXT = ["JJ00", "HL00", "SS00", "FF00", "SM00", "GN00", "BD00", "GJ00"]
ZZ_CONTEXT = [*LM_CONTEXT, LM00]


def build_project01_lm00_work_packet(
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
    prototype_lm00_subtree_poses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Install the gantry frame on JJ00 using the source plane and two holes."""
    result = build_project01_three_datum_work_packet(
        source_graph=source_graph,
        prior_effective_graph=prior_effective_graph,
        prototype_assembly=prototype_assembly,
        target_token=LM00,
        prior_context_tokens=LM_CONTEXT,
        canonical_coincident_name="重合2",
        canonical_concentric_names_by_sorted_axis=["同心3", "同心2"],
        sort_axis=2,
        expected_hole_spacing_meters=0.0355536566333197,
        interface_type="project01_gantry_frame_installation",
        target_port_id="LM00.frame_installation",
        base_port_id="JJ00.gantry_installation",
        template_id="LM00_to_JJ00_three_datum_installation",
        target_display_name="LM00龙门安装端口",
        base_display_name="JJ00龙门承载端口",
        capabilities=["installation", "gantry_motion", "dual_valve_support"],
        step_id="step-07a-add-LM00",
        extra_limits=[
            "The locating-hole center distance is measured in the prototype coordinate system.",
            "Static installation does not prove valve travel, Z stroke, hose sweep or dynamic collision clearance.",
        ],
    )
    result["summary"]["requiredReachValidation"] = "project01_dual_valve_reach.json"
    result["summary"]["finalStageActionIndex"] = 1
    lm_effective_rows = [
        row
        for row in result["effectiveGraph"].get("Modules") or []
        if str(row.get("ModuleToken") or "") == LM00
    ]
    if len(lm_effective_rows) != 1:
        raise ValueError(f"LM00 effective graph resolved to {len(lm_effective_rows)} rows")
    lm_effective_rows[0]["SolvingState"] = 1
    lm_effective_rows[0]["SolvingStateName"] = "swComponentFlexibleSolving"
    result["summary"]["targetSolvingState"] = "swComponentFlexibleSolving"
    if prototype_lm00_subtree_poses is not None:
        anchor_paths = [
            "FL9C24N074LM10.001-1",
            "FL9C24N074LM10.001-1/FL205AE-00097-1",
        ]
        anchors = []
        for relative_path in anchor_paths:
            suffix = f"/{relative_path}"
            matches = [
                row
                for row in prototype_lm00_subtree_poses.get("components") or []
                if str(row.get("Name") or "").endswith(suffix)
            ]
            if len(matches) != 1 or len(matches[0].get("Transform") or []) < 13:
                raise ValueError(
                    f"LM00 static-state anchor {relative_path!r} resolved to {len(matches)} pose rows"
                )
            anchors.append(
                {
                    "relativeLeafHierarchyPath": relative_path,
                    "transform": [float(value) for value in matches[0]["Transform"]],
                    "evidence": "Project01 prototype parent-context static carriage state.",
                    "fixAfterApply": False,
                    "solvingState": 1,
                }
            )
        result["effectiveGraph"].setdefault("EditPolicy", {})["targetLeafPoseAnchors"] = anchors
        result["summary"]["targetInternalStateAnchorCount"] = len(anchors)
        result["summary"]["targetInternalStateAnchorPaths"] = anchor_paths
        result["summary"]["knownLimits"].append(
            "LM10 and FL205AE-00097 internal transforms are prototype static-state anchors, not motion limits."
        )
    else:
        result["summary"]["targetInternalStateAnchorCount"] = 0
    return result


def _normalise_selected_paths(
    graph: dict[str, Any], prototype: Path, selected: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    graph = copy.deepcopy(graph)
    graph["SourceAssemblyPath"] = str(prototype)
    index = _file_index(prototype.parent)
    audit: list[dict[str, Any]] = []
    for module in graph.get("Modules", []):
        token = str(module.get("ModuleToken") or "")
        if token in selected:
            module["Path"], row = _relocate(str(module.get("Path") or ""), index, f"module:{token}")
            audit.append(row)
    roots = {
        token: Path(str(_module(graph, token)["Path"])).resolve().parent for token in selected
    }
    for mate in _pair_mates(graph, LM00, ZZ00):
        for endpoint in mate.get("Endpoints", []):
            token = str(endpoint.get("ModuleToken") or "")
            raw = str(endpoint.get("LeafComponentPath") or "")
            filename = Path(raw).name
            candidates = [
                path
                for path in index.get(filename.casefold(), [])
                if path.is_relative_to(roots[token])
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f"LM00/ZZ00 endpoint {mate.get('MateName')}:{token} resolved to {len(candidates)} files"
                )
            resolved = candidates[0]
            endpoint["LeafComponentPath"] = str(resolved)
            audit.append(
                {
                    "field": f"mate:{mate.get('MateName')}:{token}:{endpoint.get('Index')}",
                    "capturedPath": raw,
                    "filename": filename,
                    "resolvedPath": str(resolved),
                    "resolutionScope": f"module-tree:{token}",
                    "sha256": _sha256(resolved),
                }
            )
    return graph, audit


def build_project01_zz00_work_packet(
    source_graph: dict[str, Any],
    prior_effective_graph: dict[str, Any],
    prototype_assembly: Path,
) -> dict[str, Any]:
    """Install the dual-valve moving head on LM00 through three source relations."""
    prototype = prototype_assembly.resolve()
    if not prototype.is_file():
        raise FileNotFoundError(prototype)
    selected = set(ZZ_CONTEXT) | {ZZ00}
    graph, audit_rows = _normalise_selected_paths(source_graph, prototype, selected)
    mates = _pair_mates(graph, LM00, ZZ00)
    if len(mates) != 3:
        raise ValueError(f"LM00/ZZ00 expected three source mates, got {len(mates)}")
    by_type = {str(row.get("MateTypeName")): row for row in mates}
    expected = {"swMateCONCENTRIC", "swMatePARALLEL", "swMateCOINCIDENT"}
    if set(by_type) != expected or not all(
        row.get("IsBasicTwoFaceRebuildable") is True for row in mates
    ):
        raise ValueError("LM00/ZZ00 source relation set is not the expected rebuildable trio")
    canonical = {
        "swMateCONCENTRIC": "同心21",
        "swMatePARALLEL": "平行2",
        "swMateCOINCIDENT": "重合11",
    }
    for mate_type, name in canonical.items():
        by_type[mate_type]["MateName"] = name
    ordered = [
        by_type["swMateCONCENTRIC"],
        by_type["swMatePARALLEL"],
        by_type["swMateCOINCIDENT"],
    ]
    roles = ["rotation_axis", "anti_rotation_plane", "axial_stop_plane"]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(
        graph, [str(row["MateName"]) for row in ordered]
    )
    lm00 = copy.deepcopy(_module(graph, LM00))
    zz00 = copy.deepcopy(_module(graph, ZZ00))

    def port(token: str, port_id: str, target: bool) -> dict[str, Any]:
        module = zz00 if target else lm00
        return {
            "portId": port_id,
            "displayName": "ZZ00双阀执行头安装端口" if target else "LM00双阀承载端口",
            "moduleToken": token,
            "moduleHierarchyPath": module["HierarchyPath"],
            "category": "mechanical",
            "interfaceType": "project01_dual_valve_gantry_installation",
            "capabilities": ["installation", "dual_valve_motion", "process_reach"],
            "aliases": ["双阀安装接口" if target else "龙门双阀承载接口"],
            "status": "prototype-confirmed",
            "endpointBindings": [
                {
                    "role": role,
                    "endpointId": _catalog_endpoint_id(
                        endpoint_catalog, _endpoint(mate, ZZ00 if target else LM00)
                    ),
                }
                for role, mate in zip(roles, ordered, strict=True)
            ],
            "evidence": ["项目01原型：同心21、平行2、重合11"],
        }

    mate_steps = [
        {
            "mateName": str(mate["MateName"]),
            "mateType": int(mate["MateType"]),
            "mateTypeName": str(mate["MateTypeName"]),
            "alignment": int(mate["Alignment"]),
            "alignmentName": str(mate["AlignmentName"]),
            "endpointRoleA": role,
            "endpointRoleB": role,
        }
        for role, mate in zip(roles, ordered, strict=True)
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project01",
        "catalogPurpose": "Install ZZ00 on LM00 with axis, anti-rotation and axial-stop datums.",
        "ports": [
            port(ZZ00, "ZZ00.gantry_installation", True),
            port(LM00, "LM00.dual_valve_installation", False),
        ],
        "connectionTemplates": [
            {
                "templateId": "ZZ00_to_LM00_axis_plane_stop_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "project01_dual_valve_gantry_installation",
                "interfaceTypeB": "project01_dual_valve_gantry_installation",
                "constraintEffect": {
                    "purpose": "Close translation and rotation of the ZZ00 moving-head assembly.",
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                },
                "mateSteps": mate_steps,
            }
        ],
    }
    base_graph = copy.deepcopy(prior_effective_graph)
    base_tokens = {str(row.get("ModuleToken")) for row in base_graph.get("Modules") or []}
    if base_tokens != set(ZZ_CONTEXT):
        raise ValueError(
            f"Prior LM00 context contains {sorted(base_tokens)}, expected {sorted(ZZ_CONTEXT)}"
        )
    base_graph["Mates"] = []
    base_graph["InterModuleMateCount"] = 0
    base_graph.setdefault("EditPolicy", {})["fixedModuleTokens"] = ZZ_CONTEXT
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project01-add-ZZ00-axis-plane-stop-v1",
        "baseModuleToken": LM00,
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": ZZ_CONTEXT,
        "caseAnchoredModuleTokens": [ZZ00],
        "componentToAdd": zz00,
        "connections": [
            {
                "connectionId": "ZZ00-installed-on-LM00",
                "portAId": "ZZ00.gantry_installation",
                "portBId": "LM00.dual_valve_installation",
                "templateId": "ZZ00_to_LM00_axis_plane_stop_installation",
            }
        ],
    }
    plan = build_semantic_assembly_plan(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    effective = plan["effectiveGraph"]
    # LM00 contains the travelling carriage that ZZ00 attaches to.  The three
    # external relations correctly identify the faces but do not select one
    # position along the internal travel.  Start ZZ00 at the prototype static
    # checkpoint, solve the real mates, verify that the root stayed on that
    # branch, and only then fix the saved checkpoint.  Fixing it before mate
    # creation over-defines two of the three otherwise valid source relations.
    effective.setdefault("EditPolicy", {})["fixCaseAnchorBeforeMates"] = True
    effective.setdefault("SemanticAssemblyPlanAudit", {})["reachValidation"] = {
        "applicationMode": "validate_only",
        "evidenceArtifact": "project01_dual_valve_reach.json",
        "engineeringConfirmed": False,
    }
    summary = {
        "schemaVersion": "project01-final-zz00-work-packet/v1",
        "projectId": "project01",
        "stepId": "step-07b-add-ZZ00",
        "finalStageActionIndex": 2,
        "baseModules": ZZ_CONTEXT,
        "targetModule": ZZ00,
        "sourceMateNames": [str(row["MateName"]) for row in ordered],
        "sourceMateTypes": [str(row["MateTypeName"]) for row in ordered],
        "endpointCount": len(endpoint_catalog.get("Endpoints") or []),
        "allEndpointsHavePersistentReferences": all(
            bool((row.get("Endpoint") or {}).get("SourceAssemblyPersistentReferenceBase64"))
            for row in endpoint_catalog.get("Endpoints") or []
        ),
        "expectedResidualDof": 0,
        "caseAnchoredStaticState": True,
        "fixCaseAnchorBeforeMates": True,
        "safeToStartStaticCad": len(endpoint_catalog.get("Endpoints") or []) == 6,
        "knownLimits": [
            "Three source relations are treated as the minimal rigid installation contract.",
            "The source relation set leaves the LM00 internal travel state selectable; ZZ00 is fixed at the prototype static checkpoint so its real mates drive the restored-flexible LM00 motion stages.",
            "Static mates do not validate valve travel, Z stroke, hoses or motion sweep.",
            "Process reach remains a validation-only prototype estimate.",
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
