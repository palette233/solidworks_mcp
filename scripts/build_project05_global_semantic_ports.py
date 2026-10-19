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
    find_mate,
    read_json,
    write_json,
)


SOURCE_GRAPH = WORKSPACE / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"
DEFAULT_OUTPUT_ROOT = WORKSPACE / "demo/semantic_ports/project05_global_installation_ports_v1"
A000_PATH = "FL9C254098A000.001-1"
MODULES = {
    "D000": {
        "path": "FL9C254098D000.001-1",
        "drivingMates": ["重合3", "距离1"],
        "readOnlyMates": ["宽度17"],
        "label": "上层产品输送模组",
    },
    "K000": {
        "path": "FL9C254098K000.001-1",
        "drivingMates": ["重合4", "平行2", "同心5"],
        "readOnlyMates": [],
        "label": "双工位顶升定位模组",
    },
    "F000": {
        "path": "FL9C254098F000.001-1",
        "drivingMates": ["重合12", "平行3", "同心15"],
        "readOnlyMates": [],
        "label": "双读头条码扫描模组",
    },
    "M000": {
        "path": "FL9C254098M000.001-1",
        "drivingMates": ["重合19", "同心6", "平行5"],
        "readOnlyMates": [],
        "label": "产品定位CCD模组",
    },
    "G000": {
        "path": "FL9C254098G000.001-1",
        "drivingMates": ["重合14", "平行4", "距离2"],
        "readOnlyMates": ["槽口1"],
        "label": "校准与称重组合模组",
    },
    "N000": {
        "path": "FL9C251093N000.001-4",
        "drivingMates": ["重合42", "平行13"],
        "readOnlyMates": ["槽口4"],
        "label": "自动针头清洁模组",
    },
    "P000": {
        "path": "FL9C254098P000.001-2",
        "drivingMates": ["重合43", "平行14"],
        "readOnlyMates": ["槽口6"],
        "label": "双杯排胶模组",
    },
    "B000": {
        "path": "FL9C254098B000.001-1",
        "drivingMates": ["重合37", "同心1", "平行1"],
        "readOnlyMates": [],
        "label": "龙门与双阀Z轴运动组",
    },
}


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


def build_base_graph(graph: dict[str, Any]) -> dict[str, Any]:
    base = copy.deepcopy(find_occurrence(graph, A000_PATH))
    return {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "ModuleCount": 1,
        "InterModuleMateCount": 0,
        "Modules": [base],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": ["A000"],
            "moduleHierarchyPaths": [A000_PATH],
            "fixedAtKnownContextPoses": True,
            "purpose": "Use the Project05 A000/E000 fixed environment as the installation context.",
        },
    }


def build_one(graph: dict[str, Any], token: str, output_root: Path) -> dict[str, Any]:
    config = MODULES[token]
    driving_mates = config["drivingMates"]
    read_only_mates = config["readOnlyMates"]
    mate_names = [*driving_mates, *read_only_mates]
    target_path = config["path"]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, mate_names)
    target = find_occurrence(graph, target_path)
    base = find_occurrence(graph, A000_PATH)
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    mate_steps: list[dict[str, Any]] = []
    for mate_name in driving_mates:
        mate = find_mate(graph, mate_name)
        endpoint_roles: list[dict[str, str]] = []
        target_index = 0
        context_index = 0
        for endpoint in mate.get("Endpoints") or []:
            hierarchy_path = str(endpoint.get("ModuleHierarchyPath") or "")
            if hierarchy_path.casefold() == target_path.casefold():
                target_index += 1
                role = f"{mate_name}_target_{target_index}"
                target_bindings.append(
                    {"role": role, "endpointId": endpoint_id_for(endpoint_catalog, endpoint)}
                )
                endpoint_roles.append({"side": "A", "role": role})
            elif hierarchy_path.casefold() == A000_PATH.casefold():
                context_index += 1
                role = f"{mate_name}_context_{context_index}"
                context_bindings.append(
                    {"role": role, "endpointId": endpoint_id_for(endpoint_catalog, endpoint)}
                )
                endpoint_roles.append({"side": "B", "role": role})
            else:
                raise ValueError(
                    f"Mate {mate_name} contains endpoint outside {target_path} and {A000_PATH}."
                )
        expected = 4 if int(mate["MateType"]) == 11 else 2
        if len(endpoint_roles) != expected or not target_index or not context_index:
            raise ValueError(f"Unexpected endpoint cardinality for {mate_name}.")
        step: dict[str, Any] = {
            "mateName": mate_name,
            "mateType": mate["MateType"],
            "mateTypeName": mate["MateTypeName"],
            "alignment": mate["Alignment"],
            "alignmentName": mate["AlignmentName"],
            "endpointRoles": endpoint_roles,
        }
        if mate.get("Distance") is not None:
            step["distanceMeters"] = mate["Distance"]
        if mate.get("Angle") is not None:
            step["angleRadians"] = mate["Angle"]
        if mate.get("AdvancedOptions") is not None:
            step["advancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
        mate_steps.append(step)

    target_interface = f"project05_{token.lower()}_installation"
    context_interface = f"project05_a000_{token.lower()}_installation"
    catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project05",
        "catalogPurpose": (
            f"Migrate the source {token}/A000 installation mates into the global port registry."
        ),
        "ports": [
            {
                "portId": f"{token}.frame_installation",
                "displayName": f"{token}{config['label']}安装端口",
                "moduleToken": token,
                "moduleHierarchyPath": target_path,
                "category": "mechanical",
                "interfaceType": target_interface,
                "capabilities": ["installation"],
                "aliases": [f"{token}安装接口", f"{config['label']}安装端口"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": target_bindings,
                "evidence": [f"项目05原型配合：{'、'.join(mate_names)}"],
            },
            {
                "portId": f"A000.{token.lower()}_installation",
                "displayName": f"A000-{token}安装端口",
                "moduleToken": "A000",
                "moduleHierarchyPath": A000_PATH,
                "category": "mechanical",
                "interfaceType": context_interface,
                "capabilities": ["installation", "frame_support"],
                "aliases": [f"A000的{token}安装位"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": context_bindings,
                "evidence": [f"项目05原型配合：{'、'.join(mate_names)}"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": f"{token}_to_A000_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": target_interface,
                "interfaceTypeB": context_interface,
                "constraintEffect": {
                    "purpose": f"Reproduce the source {token}/A000 installation relation set.",
                    "fullyLocatesAddedComponent": "cad-verified-in-project05-live-chain",
                    "residualDofPolicy": "project05_source_pose_case_anchor",
                    "compositeModuleNote": (
                        "B000 port is on the B000 member of the B000/Z000 group."
                        if token == "B000"
                        else None
                    ),
                },
                "mateSteps": mate_steps,
            }
        ],
        "readOnlySourceRelations": [
            {
                "mateName": mate_name,
                "mateType": find_mate(graph, mate_name)["MateType"],
                "mateTypeName": find_mate(graph, mate_name)["MateTypeName"],
                "reason": (
                    "The exported Project05 v1.2 graph contains the relation faces but omits "
                    "the advanced Width/Slot constraint option required for deterministic creation."
                ),
                "applicationMode": "evidence_only",
            }
            for mate_name in read_only_mates
        ],
    }
    base_graph = build_base_graph(graph)
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": f"project05-add-{token}-source-installation-v1",
        "baseModuleToken": "A000",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A000"],
        "caseAnchoredModuleTokens": [token],
        "componentToAdd": copy.deepcopy(target),
        "connections": [
            {
                "connectionId": f"{token}-installed-on-A000",
                "portAId": f"{token}.frame_installation",
                "portBId": f"A000.{token.lower()}_installation",
                "templateId": f"{token}_to_A000_source_installation",
            }
        ],
        "caseAnchorEvidence": {
            "scope": "project05_only",
            "source": f"prototype {token} SourceTransform and validated live-CAD chain",
            "reason": "Current milestone migrates real source faces while retaining the validated static branch.",
            "notVendorDatum": True,
        },
    }
    result = build_semantic_assembly_plan(base_graph, catalog, endpoint_catalog, request)
    result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["caseAnchorEvidence"] = copy.deepcopy(
        request["caseAnchorEvidence"]
    )
    output_dir = output_root / token
    artifacts = {
        "base_A000_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project05-global-semantic-port-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "moduleToken": token,
            "targetHierarchyPath": target_path,
            "drivingMates": driving_mates,
            "readOnlySourceMates": read_only_mates,
            "sourceMateCount": len(mate_names),
            "existingCadEvidence": "demo/semantic_ports/project05_live_adapter_jobs/project05_live_adapter_closure.json",
            "summary": result["summary"],
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    return artifacts["assembly_plan_summary.json"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Project05 source installation mates into global semantic ports."
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    graph = read_json(SOURCE_GRAPH)
    output_root = args.output_root.resolve()
    summaries = [build_one(graph, token, output_root) for token in MODULES]
    report = {
        "schemaVersion": "project05-global-semantic-port-migration/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "sourceGraph": str(SOURCE_GRAPH),
        "outputRoot": str(output_root),
        "moduleCount": len(summaries),
        "sourceMateCount": sum(item["sourceMateCount"] for item in summaries),
        "modules": summaries,
        "solidWorksExecuted": False,
        "collisionGateExecuted": False,
        "limitations": [
            "All modules retain Project05 source-pose case anchors; these are not vendor datums.",
            "B000 exposes the external port on the B000 member; Z000 remains an internal group member.",
            "N000 and P000 use the source occurrences participating in the exported installation mates.",
        ],
    }
    write_json(output_root / "migration_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
