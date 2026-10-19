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

from demo_backend.face_endpoint_catalog import (  # noqa: E402
    build_face_endpoint_catalog_from_source_mates,
)
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan  # noqa: E402
from demo_backend.project02_positioning_standard import (  # noqa: E402
    load_project02_positioning_standard,
    positioning_standard_binding,
)


SOURCE_GRAPH = (
    WORKSPACE / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
)
DEFAULT_OUTPUT_DIR = (
    WORKSPACE / "demo/semantic_ports/project02_A800_case_anchored_installation_v1"
)
SOURCE_MATE_NAMES = ["重合35", "宽度9"]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def find_mate(graph: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in graph.get("Mates") or [] if item.get("MateName") == name]
    if len(matches) != 1:
        raise ValueError(f"Mate {name} resolved to {len(matches)} mates.")
    return matches[0]


def endpoint_id_for(
    endpoint_catalog: dict[str, Any], source_endpoint: dict[str, Any]
) -> str:
    reference = source_endpoint.get("SourceAssemblyPersistentReferenceBase64")
    matches = [
        entry
        for entry in endpoint_catalog.get("Endpoints") or []
        if (entry.get("Endpoint") or {}).get(
            "SourceAssemblyPersistentReferenceBase64"
        )
        == reference
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Source endpoint {source_endpoint.get('ModuleToken')} / "
            f"{source_endpoint.get('LeafComponentName')} / Face "
            f"{source_endpoint.get('FaceIndexInBody')} resolved to {len(matches)} entries."
        )
    return str(matches[0]["EndpointId"])


def endpoints_for(mate: dict[str, Any], token: str) -> list[dict[str, Any]]:
    return [
        item
        for item in mate.get("Endpoints") or []
        if str(item.get("ModuleToken") or "").casefold() == token.casefold()
    ]


def build_base_graph(graph: dict[str, Any]) -> dict[str, Any]:
    a600 = copy.deepcopy(find_module(graph, "A600"))
    return {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "ModuleCount": 1,
        "InterModuleMateCount": 0,
        "Modules": [a600],
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": ["A600"],
            "fixedAtKnownContextPoses": True,
            "purpose": "Use the installed cabinet as the fixed context for an independent A800 insertion.",
        },
    }


def build_semantic_catalog(
    graph: dict[str, Any], endpoint_catalog: dict[str, Any]
) -> dict[str, Any]:
    positioning_standard = load_project02_positioning_standard()
    coincident = find_mate(graph, "重合35")
    width = find_mate(graph, "宽度9")
    coincident_a600 = endpoints_for(coincident, "A600")
    coincident_a800 = endpoints_for(coincident, "A800")
    width_a600 = endpoints_for(width, "A600")
    width_a800 = endpoints_for(width, "A800")
    if not (
        len(coincident_a600) == len(coincident_a800) == 1
        and len(width_a600) == len(width_a800) == 2
    ):
        raise ValueError("Unexpected A600/A800 source-mate endpoint cardinality.")

    a600 = find_module(graph, "A600")
    a800 = find_module(graph, "A800")
    return {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": (
            "Insert A800 through its source support/centering interface and explicitly close "
            "the remaining longitudinal DOF with a Project02-only source-pose case anchor."
        ),
        "positioningStandardBinding": positioning_standard_binding(
            positioning_standard, "A800"
        ),
        "ports": [
            {
                "portId": "A800.frame_installation",
                "displayName": "A800传输安装端口",
                "description": "A800相对A600的支承接触面和宽度居中安装接口。",
                "moduleToken": "A800",
                "moduleHierarchyPath": a800["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a800_frame_installation",
                "capabilities": ["installation", "transport_alignment"],
                "aliases": ["A800安装接口", "传输模组安装端口"],
                "status": "confirmed",
                "endpointBindings": [
                    {
                        "role": "support_plane",
                        "endpointId": endpoint_id_for(
                            endpoint_catalog, coincident_a800[0]
                        ),
                    },
                    {
                        "role": "tab_side_a",
                        "endpointId": endpoint_id_for(endpoint_catalog, width_a800[0]),
                    },
                    {
                        "role": "tab_side_b",
                        "endpointId": endpoint_id_for(endpoint_catalog, width_a800[1]),
                    },
                ],
                "evidence": ["原型配合：重合35、宽度9"],
            },
            {
                "portId": "A600.a800_installation",
                "displayName": "A600-A800承载安装端口",
                "description": "A600为传输模组提供上部支承面和横向居中槽。",
                "moduleToken": "A600",
                "moduleHierarchyPath": a600["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a600_a800_installation",
                "capabilities": ["installation", "transport_support"],
                "aliases": ["A600传输安装位", "箱体传输承载端口"],
                "status": "confirmed",
                "endpointBindings": [
                    {
                        "role": "support_plane",
                        "endpointId": endpoint_id_for(
                            endpoint_catalog, coincident_a600[0]
                        ),
                    },
                    {
                        "role": "width_side_a",
                        "endpointId": endpoint_id_for(endpoint_catalog, width_a600[0]),
                    },
                    {
                        "role": "width_side_b",
                        "endpointId": endpoint_id_for(endpoint_catalog, width_a600[1]),
                    },
                ],
                "evidence": ["原型配合：重合35、宽度9"],
            },
        ],
        "connectionTemplates": [
            {
                "templateId": "A800_to_A600_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "a800_frame_installation",
                "interfaceTypeB": "a600_a800_installation",
                "constraintEffect": {
                    "purpose": "Reproduce A800 support and width-centering source mates.",
                    "fullyLocatesAddedComponent": False,
                    "remainingDof": "translation along A600 X / transport longitudinal axis",
                    "residualDofPolicy": "project02_source_pose_case_anchor",
                },
                "mateSteps": [
                    {
                        "mateName": "重合35",
                        "mateType": 0,
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": coincident["Alignment"],
                        "alignmentName": coincident["AlignmentName"],
                        "endpointRoleA": "support_plane",
                        "endpointRoleB": "support_plane",
                    },
                    {
                        "mateName": "宽度9",
                        "mateType": 11,
                        "mateTypeName": "swMateWIDTH",
                        "alignment": width["Alignment"],
                        "alignmentName": width["AlignmentName"],
                        "endpointRoles": [
                            {"side": "B", "role": "width_side_a"},
                            {"side": "B", "role": "width_side_b"},
                            {"side": "A", "role": "tab_side_a"},
                            {"side": "A", "role": "tab_side_b"},
                        ],
                        "advancedOptions": copy.deepcopy(width["AdvancedOptions"]),
                    },
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Project02 A600-A800 case-anchored semantic installation."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = read_json(SOURCE_GRAPH)
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(
        graph, SOURCE_MATE_NAMES
    )
    semantic_catalog = build_semantic_catalog(graph, endpoint_catalog)
    base_graph = build_base_graph(graph)
    a800 = copy.deepcopy(find_module(graph, "A800"))
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project02-add-A800-source-interface-case-anchor-v1",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": ["A800"],
        "componentToAdd": a800,
        "connections": [
            {
                "connectionId": "A800-installed-on-A600",
                "portAId": "A800.frame_installation",
                "portBId": "A600.a800_installation",
                "templateId": "A800_to_A600_source_installation",
            }
        ],
        "caseAnchorEvidence": {
            "scope": "project02_only",
            "source": "prototype A800 SourceTransform",
            "reason": (
                "重合35＋宽度9锁定Y/Z及姿态，但不锁定传输长轴X；需求方允许项目02短期复用原型参数。"
            ),
            "notVendorDatum": True,
        },
    }
    result = build_semantic_assembly_plan(
        base_graph, semantic_catalog, endpoint_catalog, request
    )
    result["effectiveGraph"]["SemanticAssemblyPlanAudit"][
        "caseAnchorEvidence"
    ] = copy.deepcopy(request["caseAnchorEvidence"])

    artifacts = {
        "base_A600_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": semantic_catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project02-a800-semantic-installation-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "sourceGraphPath": str(SOURCE_GRAPH),
            "outputDirectory": str(output_dir),
            "summary": result["summary"],
            "caseAnchorEvidence": request["caseAnchorEvidence"],
            "nextGate": "Run context incremental insert, reopen, verify two source mates and the explicit case-anchor pose.",
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    print(json.dumps(artifacts["assembly_plan_summary.json"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
