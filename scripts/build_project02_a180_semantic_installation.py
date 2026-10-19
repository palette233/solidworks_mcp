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

from demo_backend.face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates  # noqa: E402
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan  # noqa: E402
from demo_backend.project02_positioning_standard import (  # noqa: E402
    load_project02_positioning_standard,
    positioning_standard_binding,
)
from build_project02_a800_semantic_installation import (  # noqa: E402
    endpoint_id_for,
    endpoints_for,
    find_mate,
    find_module,
    read_json,
    write_json,
)


SOURCE_GRAPH = WORKSPACE / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
OPTICAL_REVIEW = WORKSPACE / "demo/layout_previews/project02_scanner_optical_face_review.json"
BARCODE_POINTS = WORKSPACE / "demo/layout_previews/project02_scanner_barcode_points.json"
DEFAULT_OUTPUT_DIR = WORKSPACE / "demo/semantic_ports/project02_A180_scanner_installation_v1"
SOURCE_MATE_NAMES = ["重合34", "距离24", "槽口3"]


def build_base_graph(graph: dict[str, Any]) -> dict[str, Any]:
    modules = [copy.deepcopy(find_module(graph, token)) for token in ("A600", "A800")]
    return {
        "SchemaVersion": "assembly-module-mate-graph/v2",
        "SourceAssemblyPath": graph.get("SourceAssemblyPath"),
        "ModuleCount": len(modules),
        "InterModuleMateCount": 0,
        "Modules": modules,
        "Mates": [],
        "BaseGraphPolicy": {
            "moduleTokens": ["A600", "A800"],
            "fixedAtKnownContextPoses": True,
            "purpose": "Install the scanner after the cabinet and transport positions are established.",
        },
    }


def build_catalog(graph: dict[str, Any], endpoint_catalog: dict[str, Any]) -> dict[str, Any]:
    positioning_standard = load_project02_positioning_standard()
    optical_rule = positioning_standard["modules"]["A180"]["functional"]
    coincident = find_mate(graph, "重合34")
    distance = find_mate(graph, "距离24")
    slot = find_mate(graph, "槽口3")
    a180 = find_module(graph, "A180")
    a600 = find_module(graph, "A600")

    def endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
        values = endpoints_for(mate, token)
        if len(values) != 1:
            raise ValueError(f"Expected one {token} endpoint for {mate['MateName']}.")
        return values[0]

    optical = read_json(OPTICAL_REVIEW)
    points = read_json(BARCODE_POINTS)["entries"]
    return {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": "Install A180 mechanically, then validate its optical service relation to the A800 barcode target.",
        "positioningStandardBinding": positioning_standard_binding(
            positioning_standard, "A180"
        ),
        "ports": [
            {
                "portId": "A180.frame_installation",
                "displayName": "A180扫描模组安装端口",
                "description": "扫描模组安装平面、纵向距离基准和槽口定位证据。",
                "moduleToken": "A180",
                "moduleHierarchyPath": a180["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a180_frame_installation",
                "capabilities": ["installation", "scanner_alignment"],
                "aliases": ["扫描安装端口", "A180安装位"],
                "status": "confirmed_with_read_only_slot_evidence",
                "endpointBindings": [
                    {"role": "support_plane", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(coincident, "A180"))},
                    {"role": "longitudinal_datum", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(distance, "A180"))},
                    {"role": "slot_pin_face", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(slot, "A180"))},
                ],
                "evidence": ["原型配合：重合34、距离24、槽口3"],
            },
            {
                "portId": "A600.a180_installation",
                "displayName": "A600扫描安装端口",
                "description": "箱体提供扫描模组支承、纵向基准和槽口定位接口。",
                "moduleToken": "A600",
                "moduleHierarchyPath": a600["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": "a600_a180_installation",
                "capabilities": ["installation", "scanner_support"],
                "aliases": ["箱体扫描安装位"],
                "status": "confirmed_with_read_only_slot_evidence",
                "endpointBindings": [
                    {"role": "support_plane", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(coincident, "A600"))},
                    {"role": "longitudinal_datum", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(distance, "A600"))},
                    {"role": "slot_hole_face", "endpointId": endpoint_id_for(endpoint_catalog, endpoint(slot, "A600"))},
                ],
                "evidence": ["原型配合：重合34、距离24、槽口3"],
            },
        ],
        "functionalPorts": [
            {
                "portId": "A180.scan_optical",
                "moduleToken": "A180",
                "geometryType": "point_axis",
                "originInModuleBottomFrame": optical["moduleCoordinateConversion"]["moduleLocalPointMeters"]
                | {"height": optical["moduleCoordinateConversion"]["heightAboveModuleBottomMeters"]},
                "axisInLayoutFrame": optical["moduleCoordinateConversion"]["normalInLayoutFrame"],
                "axisSignConfirmed": optical_rule["opticalAxisSignConfirmed"],
                "status": "cad_inferred_for_coarse_layout",
            },
            {
                "portId": "A800.barcode_target",
                "moduleToken": "A800",
                "geometryType": "point_plane",
                "pointInModuleBottomFrame": points["barcode"]["moduleLocalPointMeters"]
                | {"height": points["barcode"]["heightAboveModuleBottomMeters"]},
                "status": points["barcode"]["measurementStatus"],
            },
        ],
        "functionalConstraintProfiles": [
            {
                "profileId": "A180_to_A800_barcode_visibility",
                "sourcePortId": "A180.scan_optical",
                "targetPortId": "A800.barcode_target",
                "workingDistanceMeters": copy.deepcopy(
                    optical_rule["workingDistanceMeters"]
                ),
                "requiresLineOfSight": optical_rule["requiresLineOfSight"],
                "requiresBarcodeSide": optical_rule["requiresBarcodeSide"],
                "status": "provisional_until_vendor_working_distance_and_axis_sign_confirmed",
            }
        ],
        "connectionTemplates": [
            {
                "templateId": "A180_to_A600_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": "a180_frame_installation",
                "interfaceTypeB": "a600_a180_installation",
                "constraintEffect": {
                    "purpose": "Rebuild supported source mates and retain the slot relation as read-only evidence.",
                    "fullyLocatesAddedComponent": False,
                    "residualDofPolicy": "project02_source_pose_case_anchor_until_slot_rebuild_is_enabled",
                },
                "mateSteps": [
                    {
                        "mateName": "重合34",
                        "mateType": 0,
                        "mateTypeName": "swMateCOINCIDENT",
                        "alignment": coincident["Alignment"],
                        "alignmentName": coincident["AlignmentName"],
                        "endpointRoleA": "support_plane",
                        "endpointRoleB": "support_plane",
                    },
                    {
                        "mateName": "距离24",
                        "mateType": 5,
                        "mateTypeName": "swMateDISTANCE",
                        "alignment": distance["Alignment"],
                        "alignmentName": distance["AlignmentName"],
                        "distanceMeters": distance["Distance"],
                        "endpointRoleA": "longitudinal_datum",
                        "endpointRoleB": "longitudinal_datum",
                        "advancedOptions": copy.deepcopy(distance["AdvancedOptions"]),
                    },
                ],
            }
        ],
        "readOnlySourceRelations": [
            {
                "mateName": "槽口3",
                "mateTypeName": slot["MateTypeName"],
                "reason": "Slot mate is exported but not yet enabled as a driving semantic-graph operation.",
                "endpointIds": [endpoint_id_for(endpoint_catalog, item) for item in slot["Endpoints"]],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Project02 A180 mechanical and optical semantic installation artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    graph = read_json(SOURCE_GRAPH)
    endpoints = build_face_endpoint_catalog_from_source_mates(graph, SOURCE_MATE_NAMES)
    catalog = build_catalog(graph, endpoints)
    base_graph = build_base_graph(graph)
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": "project02-add-A180-scanner-case-anchor-v1",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600", "A800"],
        "caseAnchoredModuleTokens": ["A180"],
        "componentToAdd": copy.deepcopy(find_module(graph, "A180")),
        "connections": [
            {
                "connectionId": "A180-installed-on-A600",
                "portAId": "A180.frame_installation",
                "portBId": "A600.a180_installation",
                "templateId": "A180_to_A600_source_installation",
            }
        ],
        "caseAnchorEvidence": {
            "scope": "project02_only",
            "source": "prototype A180 SourceTransform",
            "reason": "槽口3尚未作为驱动配合重建，且扫描光轴符号与厂商工作距离尚待确认。",
            "notVendorDatum": True,
        },
    }
    result = build_semantic_assembly_plan(base_graph, catalog, endpoints, request)
    audit = result["effectiveGraph"]["SemanticAssemblyPlanAudit"]
    audit["caseAnchorEvidence"] = copy.deepcopy(request["caseAnchorEvidence"])
    audit["readOnlySourceRelations"] = copy.deepcopy(catalog["readOnlySourceRelations"])
    audit["functionalPorts"] = copy.deepcopy(catalog["functionalPorts"])
    audit["functionalConstraintProfiles"] = copy.deepcopy(catalog["functionalConstraintProfiles"])
    artifacts = {
        "base_A600_A800_graph.json": base_graph,
        "face_endpoint_catalog.json": endpoints,
        "semantic_port_catalog.json": catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project02-a180-semantic-installation-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "summary": result["summary"],
            "drivingMates": ["重合34", "距离24"],
            "readOnlyRelations": ["槽口3"],
            "functionalGate": "provisional",
            "nextGate": "CAD context insertion, reopen verification, then scanner-to-barcode distance/side/LOS evaluation.",
        },
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    print(json.dumps(artifacts["assembly_plan_summary.json"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
