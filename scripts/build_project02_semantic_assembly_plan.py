from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.face_endpoint_catalog import (  # noqa: E402
    build_face_endpoint_catalog_from_source_mates,
)
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan  # noqa: E402


SOURCE_GRAPH = (
    WORKSPACE
    / "demo"
    / "layout_previews"
    / "project02_module_mate_graph_v6_all_bodies.json"
)
EXISTING_ENDPOINT_CATALOG = (
    WORKSPACE
    / "demo"
    / "mate_graph_edit"
    / "face_catalog"
    / "project02_A500_A700_seed_plus_A720009_leaf_v1.json"
)
DEFAULT_OUTPUT_DIR = (
    WORKSPACE / "demo" / "semantic_ports" / "project02_A500_full_installation_v2"
)
A500_MATE_NAMES = ["重合13", "宽度4", "距离27", "距离8"]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def find_module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        item
        for item in graph.get("Modules") or []
        if str(item.get("ModuleToken") or "").casefold() == token.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Module token {token} resolved to {len(matches)} modules.")
    return matches[0]


def find_mate(graph: dict[str, Any], mate_name: str) -> dict[str, Any]:
    matches = [
        item
        for item in graph.get("Mates") or []
        if str(item.get("MateName") or "") == mate_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Mate {mate_name} resolved to {len(matches)} mates.")
    return matches[0]


def endpoint_id_for(
    endpoint_catalog: dict[str, Any], source_mate: dict[str, Any], endpoint_index: int
) -> str:
    source_endpoint = source_mate["Endpoints"][endpoint_index]
    persistent = source_endpoint.get("SourceAssemblyPersistentReferenceBase64")
    matches = [
        entry
        for entry in endpoint_catalog.get("Endpoints") or []
        if (entry.get("Endpoint") or {}).get(
            "SourceAssemblyPersistentReferenceBase64"
        )
        == persistent
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Source endpoint {source_mate['MateName']}[{endpoint_index}] resolved to "
            f"{len(matches)} catalog entries."
        )
    return str(matches[0]["EndpointId"])


def build_base_graph(graph: dict[str, Any]) -> dict[str, Any]:
    tokens = {"A600", "A700"}
    modules = [
        copy.deepcopy(item)
        for item in graph.get("Modules") or []
        if str(item.get("ModuleToken") or "").upper() in tokens
    ]
    paths = {str(item["HierarchyPath"]) for item in modules}
    source_context_mates = [
        copy.deepcopy(item)
        for item in graph.get("Mates") or []
        if set(str(value) for value in item.get("ModuleHierarchyPaths") or []) <= paths
        and len(set(str(value) for value in item.get("ModuleHierarchyPaths") or [])) == 2
    ]
    return {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "ModuleCount": len(modules),
        "InterModuleMateCount": 0,
        "Modules": modules,
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": sorted(tokens),
            "fixedAtKnownContextPoses": True,
            "sourceMateNamesRepresentedByFixedContext": [
                item["MateName"] for item in source_context_mates
            ],
            "purpose": (
                "Provide the already installed A600/A700 context without re-solving its "
                "expensive internal mate chain during an incremental A500 addition."
            ),
        },
    }


def build_catalogs(
    graph: dict[str, Any], endpoint_catalog: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    coincident = find_mate(graph, "重合13")
    width = find_mate(graph, "宽度4")
    offset = find_mate(graph, "距离27")
    spacing = find_mate(graph, "距离8")
    ids = {
        "a600_mount": endpoint_id_for(endpoint_catalog, coincident, 0),
        "a500_mount": endpoint_id_for(endpoint_catalog, coincident, 1),
        "a600_width_a": endpoint_id_for(endpoint_catalog, width, 0),
        "a600_width_b": endpoint_id_for(endpoint_catalog, width, 1),
        "a500_tab_a": endpoint_id_for(endpoint_catalog, width, 2),
        "a500_tab_b": endpoint_id_for(endpoint_catalog, width, 3),
        "a500_offset": endpoint_id_for(endpoint_catalog, offset, 0),
        "a600_offset": endpoint_id_for(endpoint_catalog, offset, 1),
        "a500_spacing": endpoint_id_for(endpoint_catalog, spacing, 0),
        "a700_spacing": endpoint_id_for(endpoint_catalog, spacing, 1),
    }
    module_a500 = find_module(graph, "A500")
    module_a600 = find_module(graph, "A600")
    module_a700 = find_module(graph, "A700")
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": (
            "Rebuild the complete source A500 installation semantics from stable face endpoints."
        ),
        "ports": [
            {
                "portId": "A500.frame_installation",
                "displayName": "A500箱体安装端口",
                "description": "A500相对A600的接触、居中及轴向偏置安装接口。",
                "moduleToken": "A500",
                "moduleHierarchyPath": module_a500["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a500_frame_installation",
                "capabilities": ["installation"],
                "aliases": ["A500安装接口", "A500箱体安装端口", "安装到A600"],
                "status": "confirmed",
                "endpointBindings": [
                    {"role": "mount_plane", "endpointId": ids["a500_mount"]},
                    {"role": "tab_side_a", "endpointId": ids["a500_tab_a"]},
                    {"role": "tab_side_b", "endpointId": ids["a500_tab_b"]},
                    {"role": "offset_plane", "endpointId": ids["a500_offset"]},
                ],
                "evidence": ["原型配合：重合13、宽度4、距离27"],
            },
            {
                "portId": "A600.a500_installation",
                "displayName": "A600-A500承载安装端口",
                "description": "A600箱体为A500提供接触面、宽度槽与轴向距离基准。",
                "moduleToken": "A600",
                "moduleHierarchyPath": module_a600["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a600_a500_installation",
                "capabilities": ["installation"],
                "aliases": ["A600承载安装接口", "A600箱体安装端口", "A500安装位"],
                "status": "confirmed",
                "endpointBindings": [
                    {"role": "mount_plane", "endpointId": ids["a600_mount"]},
                    {"role": "width_side_a", "endpointId": ids["a600_width_a"]},
                    {"role": "width_side_b", "endpointId": ids["a600_width_b"]},
                    {"role": "offset_plane", "endpointId": ids["a600_offset"]},
                ],
                "evidence": ["原型配合：重合13、宽度4、距离27"],
            },
            {
                "portId": "A500.a700_spacing",
                "displayName": "A500对A700间距端口",
                "moduleToken": "A500",
                "moduleHierarchyPath": module_a500["HierarchyPath"],
                "category": "spatial",
                "interfaceType": "service_module_spacing",
                "capabilities": ["spacing"],
                "aliases": ["A500间距基准", "A500对A700距离基准"],
                "status": "confirmed",
                "endpointBindings": [
                    {"role": "primary", "endpointId": ids["a500_spacing"]}
                ],
                "evidence": ["原型配合：距离8=50mm"],
            },
            {
                "portId": "A700.a500_spacing",
                "displayName": "A700对A500间距端口",
                "moduleToken": "A700",
                "moduleHierarchyPath": module_a700["HierarchyPath"],
                "category": "spatial",
                "interfaceType": "service_module_spacing",
                "capabilities": ["spacing"],
                "aliases": ["A700间距基准", "A700对A500距离基准"],
                "status": "confirmed",
                "endpointBindings": [
                    {"role": "primary", "endpointId": ids["a700_spacing"]}
                ],
                "evidence": ["原型配合：距离8=50mm"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "A500_to_A600_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "a500_frame_installation",
                "interfaceTypeB": "a600_a500_installation",
                "constraintEffect": {
                    "purpose": "Reproduce A500's three source installation relations to A600.",
                    "fullyLocatesAddedComponent": "requires_cad_verification",
                },
                "mateSteps": [
                    {
                        "mateName": "重合13",
                        "mateType": 0,
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": 1,
                        "alignmentName": "swMateAlignANTI_ALIGNED",
                        "endpointRoleA": "mount_plane",
                        "endpointRoleB": "mount_plane",
                    },
                    {
                        "mateName": "宽度4",
                        "mateType": 11,
                        "mateTypeName": "swMateWIDTH",
                        "alignment": 1,
                        "alignmentName": "swMateAlignANTI_ALIGNED",
                        "endpointRoles": [
                            {"side": "B", "role": "width_side_a"},
                            {"side": "B", "role": "width_side_b"},
                            {"side": "A", "role": "tab_side_a"},
                            {"side": "A", "role": "tab_side_b"},
                        ],
                        "advancedOptions": copy.deepcopy(width["AdvancedOptions"]),
                    },
                    {
                        "mateName": "距离27",
                        "mateType": 5,
                        "mateTypeName": "swMateDISTANCE",
                        "alignment": 0,
                        "alignmentName": "swMateAlignALIGNED",
                        "endpointRoleA": "offset_plane",
                        "endpointRoleB": "offset_plane",
                        "distanceMeters": 0.06,
                        "advancedOptions": copy.deepcopy(offset["AdvancedOptions"]),
                    },
                ],
            },
            {
                "templateId": "A500_to_A700_source_spacing",
                "purposes": ["spacing"],
                "interfaceTypeA": "service_module_spacing",
                "interfaceTypeB": "service_module_spacing",
                "constraintEffect": {
                    "purpose": "Preserve the 50 mm source process spacing between A500 and A700.",
                    "fullyLocatesAddedComponent": False,
                },
                "mateSteps": [
                    {
                        "mateName": "距离8",
                        "mateType": 5,
                        "mateTypeName": "swMateDISTANCE",
                        "alignment": 1,
                        "alignmentName": "swMateAlignANTI_ALIGNED",
                        "endpointRoleA": "primary",
                        "endpointRoleB": "primary",
                        "distanceMeters": 0.05,
                        "applicationMode": "validate_only",
                        "tolerance": {"distanceMeters": 0.0001},
                        "advancedOptions": copy.deepcopy(spacing["AdvancedOptions"]),
                    }
                ],
            },
        ],
    }
    return semantic_catalog, ids


def stage_effective_graph(
    effective: dict[str, Any], module_tokens: set[str], mate_names: set[str], stage: str
) -> dict[str, Any]:
    staged = copy.deepcopy(effective)
    staged["Modules"] = [
        item
        for item in staged["Modules"]
        if str(item.get("ModuleToken") or "").upper() in module_tokens
    ]
    staged["Mates"] = [
        item for item in staged["Mates"] if str(item.get("MateName") or "") in mate_names
    ]
    staged["ModuleCount"] = len(staged["Modules"])
    staged["InterModuleMateCount"] = len(staged["Mates"])
    staged["StagedRebuildGate"] = {
        "stage": stage,
        "purpose": "Bound CAD execution time and isolate the first failing semantic group.",
        "moduleTokens": sorted(module_tokens),
        "mateNames": [item["MateName"] for item in staged["Mates"]],
    }
    return staged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build project02 A500 complete semantic installation plan."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = read_json(SOURCE_GRAPH)
    existing = read_json(EXISTING_ENDPOINT_CATALOG)
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(
        graph, A500_MATE_NAMES, existing
    )
    semantic_catalog, endpoint_ids = build_catalogs(graph, endpoint_catalog)
    base_graph = build_base_graph(graph)
    a500 = copy.deepcopy(find_module(graph, "A500"))
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project02-add-A500-complete-source-semantics-v2",
        "baseModuleToken": "A600",
        "initialPlacementMode": "deterministic",
        "fixedContextModuleTokens": ["A600", "A700"],
        "componentToAdd": a500,
        "connections": [
            {
                "connectionId": "A500-installed-on-A600",
                "portAId": "A500.frame_installation",
                "portBId": "A600.a500_installation",
                "templateId": "A500_to_A600_source_installation",
            },
            {
                "connectionId": "A500-spaced-from-A700",
                "portAId": "A500.a700_spacing",
                "portBId": "A700.a500_spacing",
                "templateId": "A500_to_A700_source_spacing",
            },
        ],
    }
    stage2_evidence_path = output_dir / "stage2_A500_install.result.json"
    if stage2_evidence_path.is_file():
        stage2_evidence = read_json(stage2_evidence_path)
        tool_result = stage2_evidence.get("toolResult") or {}
        a500_status = next(
            (
                item
                for item in tool_result.get("ComponentStatuses") or []
                if item.get("ModuleToken") == "A500"
            ),
            {},
        )
        request["cadVerificationEvidence"] = {
            "resultPath": str(stage2_evidence_path),
            "fullyConstrained": bool(
                tool_result.get("Success")
                and a500_status.get("ConstrainedStatusName") == "swFullyConstrained"
            ),
            "createdMateCount": tool_result.get("CreatedMateCount"),
            "reopenedMateCount": tool_result.get("ReopenedMateCount"),
            "reopenedMateParametersMatch": tool_result.get(
                "ReopenedMateParametersMatch"
            ),
        }
    result = build_semantic_assembly_plan(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    base_mate_names = {
        item["MateName"] for item in base_graph.get("Mates") or []
    }
    install_mate_names = base_mate_names | {"重合13", "宽度4", "距离27"}
    full_mate_names = install_mate_names | {"距离8"}
    stage1 = stage_effective_graph(
        result["effectiveGraph"], {"A600", "A700"}, base_mate_names, "1-base-A600-A700"
    )
    stage2 = stage_effective_graph(
        result["effectiveGraph"],
        {"A500", "A600", "A700"},
        install_mate_names,
        "2-add-A500-installation",
    )
    stage3 = stage_effective_graph(
        result["effectiveGraph"],
        {"A500", "A600", "A700"},
        full_mate_names,
        "3-add-A500-spacing",
    )
    artifacts = {
        "base_A600_A700_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": semantic_catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "stage1_base_effective.json": stage1,
        "stage2_install_effective.json": stage2,
        "stage3_full_effective.json": stage3,
        "assembly_plan_summary.json": {
            "success": True,
            "sourceGraphPath": str(SOURCE_GRAPH),
            "existingEndpointCatalogPath": str(EXISTING_ENDPOINT_CATALOG),
            "outputDirectory": str(output_dir),
            "endpointIds": endpoint_ids,
            "summary": result["summary"],
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    print(json.dumps(artifacts["assembly_plan_summary.json"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
