from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.semantic_port_catalog import build_semantic_connection_patch  # noqa: E402


DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
DEFAULT_ENDPOINTS = ROOT / "demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_plus_A720009_leaf_v1.json"
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project02_incremental_A500_A700_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Project02 semantic-port graph-increment demo without starting SolidWorks."
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--endpoint-catalog", type=Path, default=DEFAULT_ENDPOINTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    graph_path = args.graph.resolve()
    endpoint_path = args.endpoint_catalog.resolve()
    output_dir = args.output_dir.resolve()
    full_graph = read_json(graph_path)
    endpoint_catalog = read_json(endpoint_path)

    modules = full_graph.get("Modules") or []
    a500 = next(item for item in modules if item.get("ModuleToken") == "A500")
    a700 = next(item for item in modules if item.get("ModuleToken") == "A700")
    base_graph = {
        "SchemaVersion": full_graph.get("SchemaVersion"),
        "SourceAssemblyPath": full_graph.get("SourceAssemblyPath"),
        "RequestedModuleTokens": ["A700"],
        "ModuleCount": 1,
        "InterModuleMateCount": 0,
        "MateBundleCount": 0,
        "IgnoredIntraModuleMateCount": 0,
        "IgnoredUnresolvedMateCount": 0,
        "Modules": [a700],
        "Mates": [],
        "MateBundles": [],
        "SavedJsonPath": None,
        "Diagnostics": [
            "Derived read-only from the Project02 full graph for a graph-level incremental-add demo."
        ],
    }
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": "Graph-level incremental component and connection demo.",
        "endpointCatalogPath": str(endpoint_path),
        "ports": [
            {
                "portId": "A500.prototype_spacing_reference",
                "displayName": "A500原型间距参考端口",
                "description": "由原型距离8配合的A500端点注册；不宣称是通用安装底面。",
                "moduleToken": "A500",
                "moduleHierarchyPath": a500["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "planar_spacing_reference",
                "status": "confirmed",
                "evidence": "project02 source mate 距离8",
                "endpointBindings": [
                    {"role": "primary", "endpointId": "face:a500:7d587bfd92815e6f"}
                ],
            },
            {
                "portId": "A700.prototype_spacing_reference",
                "displayName": "A700原型间距参考端口",
                "description": "由原型距离8配合的A700端点注册；不宣称是通用安装底面。",
                "moduleToken": "A700",
                "moduleHierarchyPath": a700["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "planar_spacing_reference",
                "status": "confirmed",
                "evidence": "project02 source mate 距离8",
                "endpointBindings": [
                    {"role": "primary", "endpointId": "face:a700:22da287d7186a8d3"}
                ],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "project02_planar_spacing_distance",
                "displayName": "项目02平面间距关系",
                "interfaceTypeA": "planar_spacing_reference",
                "interfaceTypeB": "planar_spacing_reference",
                "constraintEffect": {
                    "estimatedRemovedScalarDof": 1,
                    "fullyLocatesAddedComponent": False,
                    "assessment": "DEMO_PARTIAL_RELATION_ONLY",
                },
                "mateSteps": [
                    {
                        "mateName": "距离8_语义端口重建",
                        "mateType": 5,
                        "mateTypeName": "swMateDISTANCE",
                        "alignment": 1,
                        "alignmentName": "swMateAlignANTI_ALIGNED",
                        "endpointRoleA": "primary",
                        "endpointRoleB": "primary",
                        "distanceMeters": 0.05,
                    }
                ],
            }
        ],
    }
    request = {
        "schemaVersion": "semantic-connection-request/v1",
        "connectionId": "project02-add-A500-to-A700",
        "intent": "在仅含A700的现有图上增加A500，并恢复原型中距离8对应的50 mm平面间距关系。",
        "portAId": "A500.prototype_spacing_reference",
        "portBId": "A700.prototype_spacing_reference",
        "templateId": "project02_planar_spacing_distance",
        "baseModuleToken": "A700",
        "initialPlacementMode": "source_pose",
        "componentToAdd": a500,
        "parameters": {"distanceMeters": 0.05},
    }
    result = build_semantic_connection_patch(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    report = {
        "schemaVersion": "project02-semantic-port-demo-report/v1",
        "success": result["success"],
        "scope": "graph_level_increment_with_isolated_cad_rebuild",
        "sourceFullGraphPath": str(graph_path),
        "sourceEndpointCatalogPath": str(endpoint_path),
        "artifacts": {
            "baseGraph": str(output_dir / "base_A700_graph.json"),
            "semanticPortCatalog": str(output_dir / "semantic_port_catalog.json"),
            "connectionRequest": str(output_dir / "connection_request.json"),
            "mateGraphPatch": str(output_dir / "mate_graph_patch.json"),
            "effectiveGraph": str(output_dir / "effective_graph.json"),
        },
        "summary": result["summary"],
        "acceptance": {
            "componentNodeAdded": result["summary"]["addedComponent"] == a500["HierarchyPath"],
            "semanticPortsResolved": result["summary"]["portAId"].startswith("A500.")
            and result["summary"]["portBId"].startswith("A700."),
            "mateGenerated": result["summary"]["generatedMateCount"] == 1,
            "sourceGraphUnmodified": len(base_graph["Modules"]) == 1 and not base_graph["Mates"],
            "fullLocationNotClaimed": result["summary"]["constraintEffect"].get(
                "fullyLocatesAddedComponent"
            )
            is False,
        },
        "nextGate": "Register two additional independent A500/A700 interface references before claiming fully constrained placement.",
    }
    report["success"] = report["success"] and all(report["acceptance"].values())

    write_json(output_dir / "base_A700_graph.json", base_graph)
    write_json(output_dir / "semantic_port_catalog.json", semantic_catalog)
    write_json(output_dir / "connection_request.json", request)
    write_json(output_dir / "mate_graph_patch.json", result["patch"])
    write_json(output_dir / "effective_graph.json", result["effectiveGraph"])
    write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
