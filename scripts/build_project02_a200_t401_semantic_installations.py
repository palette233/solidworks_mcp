from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
if str(WORKSPACE / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE / "scripts"))

from demo_backend.face_endpoint_catalog import (  # noqa: E402
    build_face_endpoint_catalog_from_source_mates,
)
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan  # noqa: E402
from build_project02_a800_semantic_installation import (  # noqa: E402
    endpoint_id_for,
    endpoints_for,
    find_mate,
    read_json,
    write_json,
)


SOURCE_GRAPH = WORKSPACE / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
DEFAULT_OUTPUT_ROOT = WORKSPACE / "demo/semantic_ports/project02_a200_t401_installations_v1"


def find_occurrence(graph: dict[str, Any], hierarchy_path: str) -> dict[str, Any]:
    matches = [
        item
        for item in graph.get("Modules") or []
        if str(item.get("HierarchyPath") or "").casefold() == hierarchy_path.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Hierarchy path {hierarchy_path} resolved to {len(matches)} modules."
        )
    return matches[0]


def build_base_graph(
    graph: dict[str, Any], *, base_hierarchy_path: str, purpose: str
) -> dict[str, Any]:
    base = copy.deepcopy(find_occurrence(graph, base_hierarchy_path))
    return {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "ModuleCount": 1,
        "InterModuleMateCount": 0,
        "Modules": [base],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": [base["ModuleToken"]],
            "moduleHierarchyPaths": [base["HierarchyPath"]],
            "fixedAtKnownContextPoses": True,
            "purpose": purpose,
        },
    }


def _binding(
    endpoint_catalog: dict[str, Any], endpoint: dict[str, Any], role: str
) -> dict[str, str]:
    return {"role": role, "endpointId": endpoint_id_for(endpoint_catalog, endpoint)}


def _mate_step(
    mate: dict[str, Any],
    *,
    side_a_role: str,
    side_b_role: str,
    source_order: tuple[str, str] = ("A", "B"),
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "mateName": mate["MateName"],
        "mateType": mate["MateType"],
        "mateTypeName": mate["MateTypeName"],
        "alignment": mate["Alignment"],
        "alignmentName": mate["AlignmentName"],
        "endpointRoles": [
            {
                "side": source_order[0],
                "role": side_a_role if source_order[0] == "A" else side_b_role,
            },
            {
                "side": source_order[1],
                "role": side_a_role if source_order[1] == "A" else side_b_role,
            },
        ],
    }
    if mate.get("Distance") is not None:
        step["distanceMeters"] = mate["Distance"]
    if mate.get("Angle") is not None:
        step["angleRadians"] = mate["Angle"]
    if mate.get("AdvancedOptions") is not None:
        step["advancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
    return step


def build_a200(graph: dict[str, Any], output_root: Path) -> dict[str, Any]:
    mate_names = ["重合26", "槽口1", "槽口2"]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    a200 = find_occurrence(graph, "FL9A24D062A200.001-1")
    a600 = find_occurrence(graph, "FL9A24D062A600.001-1")
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    mate_steps: list[dict[str, Any]] = []
    role_names = [
        ("support_plane", "support_plane"),
        ("slot_face_a", "slot_guide_a"),
        ("slot_face_b", "slot_guide_b"),
    ]
    for mate_name, (target_role, context_role) in zip(mate_names, role_names, strict=True):
        mate = find_mate(graph, mate_name)
        target = endpoints_for(mate, "A200")
        context = endpoints_for(mate, "A600")
        if len(target) != 1 or len(context) != 1:
            raise ValueError(f"Unexpected endpoint cardinality for {mate_name}.")
        target_bindings.append(_binding(endpoint_catalog, target[0], target_role))
        context_bindings.append(_binding(endpoint_catalog, context[0], context_role))
        source_tokens = tuple(str(item.get("ModuleToken")) for item in mate["Endpoints"])
        source_order = ("A", "B") if source_tokens == ("A200", "A600") else ("B", "A")
        mate_steps.append(
            _mate_step(
                mate,
                side_a_role=target_role,
                side_b_role=context_role,
                source_order=source_order,
            )
        )

    catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": "用原型重合面与两个槽口面恢复A200 CCD相对A600的安装接口。",
        "ports": [
            {
                "portId": "A200.frame_installation",
                "displayName": "A200 CCD安装端口",
                "description": "CCD支承面及两处槽口导向安装接口。",
                "moduleToken": "A200",
                "moduleHierarchyPath": a200["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a200_frame_installation",
                "capabilities": ["installation", "vision_alignment"],
                "aliases": ["CCD安装接口", "视觉模组安装端口"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": target_bindings,
                "evidence": ["原型配合：重合26、槽口1、槽口2"],
            },
            {
                "portId": "A600.a200_installation",
                "displayName": "A600-A200安装端口",
                "description": "箱体为CCD提供支承面和两处槽口导向。",
                "moduleToken": "A600",
                "moduleHierarchyPath": a600["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a600_a200_installation",
                "capabilities": ["installation", "vision_support"],
                "aliases": ["箱体CCD安装位"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": context_bindings,
                "evidence": ["原型配合：重合26、槽口1、槽口2"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "A200_to_A600_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "a200_frame_installation",
                "interfaceTypeB": "a600_a200_installation",
                "constraintEffect": {
                    "purpose": "恢复A200支承面与双槽口安装语义。",
                    "fullyLocatesAddedComponent": "cad-verified-in-existing-full-chain",
                    "requiredSolvingState": "flexible",
                    "residualDofPolicy": "project02_source_pose_case_anchor",
                },
                "mateSteps": mate_steps,
            }
        ],
    }
    base_graph = build_base_graph(
        graph,
        base_hierarchy_path=a600["HierarchyPath"],
        purpose="以A600为固定上下文，插入A200 CCD。",
    )
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project02-add-A200-source-installation-v1",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": ["A200"],
        "componentToAdd": copy.deepcopy(a200),
        "connections": [
            {
                "connectionId": "A200-installed-on-A600",
                "portAId": "A200.frame_installation",
                "portBId": "A600.a200_installation",
                "templateId": "A200_to_A600_source_installation",
            }
        ],
        "caseAnchorEvidence": {
            "scope": "project02_only",
            "source": "prototype A200 SourceTransform",
            "reason": "沿用已完成保存重开的项目02全链实证分支。",
            "notVendorDatum": True,
        },
    }
    result = build_semantic_assembly_plan(base_graph, catalog, endpoint_catalog, request)
    result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["caseAnchorEvidence"] = copy.deepcopy(
        request["caseAnchorEvidence"]
    )
    output_dir = output_root / "A200"
    artifacts = {
        "base_A600_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project02-a200-semantic-installation-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "drivingMates": mate_names,
            "existingCadEvidence": "demo/semantic_ports/project02_full_machine_increment_v1/step07_A200_V1.context-insert.result.json",
            "summary": result["summary"],
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    return artifacts["assembly_plan_summary.json"]


def build_t401_occurrence(
    graph: dict[str, Any],
    output_root: Path,
    *,
    occurrence: int,
    base_token: str,
    base_hierarchy_path: str,
    mate_names: list[str],
) -> dict[str, Any]:
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    target_path = f"T401AA-07388-0-{occurrence}"
    target = find_occurrence(graph, target_path)
    base = find_occurrence(graph, base_hierarchy_path)
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    mate_steps: list[dict[str, Any]] = []
    for index, mate_name in enumerate(mate_names, start=1):
        mate = find_mate(graph, mate_name)
        target_endpoints = [
            item
            for item in mate.get("Endpoints") or []
            if str(item.get("ModuleHierarchyPath") or "").casefold() == target_path.casefold()
        ]
        context_endpoints = [
            item
            for item in mate.get("Endpoints") or []
            if str(item.get("ModuleHierarchyPath") or "").casefold()
            == base_hierarchy_path.casefold()
        ]
        if len(target_endpoints) != 1 or len(context_endpoints) != 1:
            raise ValueError(f"Unexpected endpoint cardinality for {mate_name}.")
        target_role = f"relation_{index}_target_face"
        context_role = f"relation_{index}_context_face"
        target_bindings.append(_binding(endpoint_catalog, target_endpoints[0], target_role))
        context_bindings.append(_binding(endpoint_catalog, context_endpoints[0], context_role))
        first_path = str(mate["Endpoints"][0].get("ModuleHierarchyPath") or "")
        source_order = ("A", "B") if first_path.casefold() == target_path.casefold() else ("B", "A")
        mate_steps.append(
            _mate_step(
                mate,
                side_a_role=target_role,
                side_b_role=context_role,
                source_order=source_order,
            )
        )

    suffix = f"t401_{occurrence}"
    target_interface = f"t401_{occurrence}_installation"
    context_interface = f"{base_token.lower()}_t401_{occurrence}_installation"
    catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": f"恢复第{occurrence}套T401相对{base_token}的原型安装关系。",
        "ports": [
            {
                "portId": f"T401.{suffix}_installation",
                "displayName": f"T401第{occurrence}套安装端口",
                "moduleToken": "T401",
                "moduleHierarchyPath": target["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": target_interface,
                "capabilities": ["installation", "glue_supply"],
                "aliases": [f"第{occurrence}套供胶安装接口"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": target_bindings,
                "evidence": [f"原型配合：{'、'.join(mate_names)}"],
            },
            {
                "portId": f"{base_token}.t401_{occurrence}_installation",
                "displayName": f"{base_token}-T401第{occurrence}套安装端口",
                "moduleToken": base_token,
                "moduleHierarchyPath": base["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": context_interface,
                "capabilities": ["installation", "glue_supply_support"],
                "aliases": [f"{base_token}供胶安装位"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": context_bindings,
                "evidence": [f"原型配合：{'、'.join(mate_names)}"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": f"T401_{occurrence}_to_{base_token}_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": target_interface,
                "interfaceTypeB": context_interface,
                "constraintEffect": {
                    "purpose": f"恢复第{occurrence}套T401相对{base_token}的源配合。",
                    "fullyLocatesAddedComponent": "cad-verified-in-existing-full-chain",
                    "residualDofPolicy": "project02_source_pose_case_anchor",
                },
                "mateSteps": mate_steps,
            }
        ],
    }
    base_graph = build_base_graph(
        graph,
        base_hierarchy_path=base_hierarchy_path,
        purpose=f"以{base_token}为固定上下文，插入第{occurrence}套T401。",
    )
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": f"project02-add-T401-{occurrence}-source-installation-v1",
        "baseModuleToken": base_token,
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": [base_token],
        "caseAnchoredModuleTokens": ["T401"],
        "componentToAdd": copy.deepcopy(target),
        "connections": [
            {
                "connectionId": f"T401-{occurrence}-installed-on-{base_token}",
                "portAId": f"T401.{suffix}_installation",
                "portBId": f"{base_token}.t401_{occurrence}_installation",
                "templateId": f"T401_{occurrence}_to_{base_token}_source_installation",
            }
        ],
        "caseAnchorEvidence": {
            "scope": "project02_only",
            "source": f"prototype T401 occurrence {occurrence} SourceTransform",
            "reason": "供胶零件的源配合不足以独立消除全部刚体自由度，保留案例锚点。",
            "notVendorDatum": True,
        },
    }
    result = build_semantic_assembly_plan(base_graph, catalog, endpoint_catalog, request)
    result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["caseAnchorEvidence"] = copy.deepcopy(
        request["caseAnchorEvidence"]
    )
    output_dir = output_root / f"T401-{occurrence}"
    artifacts = {
        f"base_{base_token}_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project02-t401-semantic-installation-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "occurrence": occurrence,
            "baseModuleToken": base_token,
            "drivingMates": mate_names,
            "existingCadEvidence": (
                "demo/semantic_ports/project02_full_machine_increment_v1/"
                f"step0{7 + occurrence}_T401_{occurrence}_V{2 if occurrence == 2 else 1}.context-insert.result.json"
            ),
            "summary": result["summary"],
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    return artifacts["assembly_plan_summary.json"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Project02 A200 and two T401 semantic installation ports."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    graph = read_json(SOURCE_GRAPH)
    summaries = [
        build_a200(graph, output_root),
        build_t401_occurrence(
            graph,
            output_root,
            occurrence=1,
            base_token="A600",
            base_hierarchy_path="FL9A24D062A600.001-1",
            mate_names=["重合14", "距离10"],
        ),
        build_t401_occurrence(
            graph,
            output_root,
            occurrence=2,
            base_token="A200",
            base_hierarchy_path="FL9A24D062A200.001-1",
            mate_names=["距离28"],
        ),
    ]
    report = {
        "schemaVersion": "project02-a200-t401-semantic-port-build/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "outputRoot": str(output_root),
        "artifactGroups": summaries,
        "solidWorksExecuted": False,
        "collisionGateExecuted": False,
    }
    write_json(output_root / "build_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
