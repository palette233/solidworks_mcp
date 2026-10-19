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

from demo_backend.face_endpoint_catalog import build_face_endpoint_catalog_from_source_mates  # noqa: E402
from demo_backend.semantic_port_catalog import build_semantic_assembly_plan  # noqa: E402
from build_project02_a800_semantic_installation import (  # noqa: E402
    endpoint_id_for,
    endpoints_for,
    find_mate,
    find_module,
    read_json,
    write_json,
)


SOURCE_GRAPH = WORKSPACE / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
DEFAULT_OUTPUT_ROOT = WORKSPACE / "demo/semantic_ports/project02_service_installations_v1"
A100_REFERENCE_SNAPSHOT = (
    DEFAULT_OUTPUT_ROOT / "A100" / "a100_prototype_disk_clean_subtree_poses.json"
)
A100_REFERENCE_COMPARISON = (
    DEFAULT_OUTPUT_ROOT / "A100" / "a100_prototype_vs_v19_subtree_pose_comparison.json"
)
MODULE_CONFIG = {
    "A100": {
        "mateNames": ["重合8", "重合9", "距离9"],
        "displayName": "A100龙门模组安装端口",
        "interfaceType": "a100_frame_installation",
        "contextInterfaceType": "a600_a100_installation",
        "solvingState": "flexible",
        "distanceCreationFlipOverrides": {"距离9": False},
        "maintenanceEnvelopeProfiles": [],
    },
    "A700": {
        "mateNames": ["平行1", "平行2", "距离6", "重合38", "宽度10", "距离29"],
        "displayName": "A700清洁称重模组安装端口",
        "interfaceType": "a700_frame_installation",
        "contextInterfaceType": "a600_a700_installation",
        "solvingState": "flexible",
        "staticLeafPoseAnchors": [
            {
                "relativeLeafHierarchyPath": "FL9A24D062A730.001-1",
                "transform": [
                    1.0755285551055713e-16, 7.942931842487584e-16, 1.0,
                    1.0, 5.93791391094496e-15, -1.0755285551056188e-16,
                    -5.93791391094496e-15, 1.0, -7.942931842487579e-16,
                    -0.7674785364039903, 0.5099292352278397, 0.406298948235787,
                    1.0, 0.0, 0.0, 0.0,
                ],
                "evidence": "clean-disk prototype parent-context Transform2, A730",
            },
            {
                "relativeLeafHierarchyPath": "FL9A24D062A720.001-1/FL9A24D062A721.001-1",
                "transform": [
                    0.8681621707358979, 3.263316941167798e-15, 0.49628061145196245,
                    1.8625372068510237e-16, -1.0, 6.249727342028963e-15,
                    0.49628061145196245, -5.333342745376553e-15, -0.8681621707358979,
                    -0.7594785364039722, 0.5828292352278822, -0.24657712115897057,
                    1.0, 0.0, 0.0, 0.0,
                ],
                "evidence": "clean-disk prototype parent-context Transform2, A721",
            },
        ],
        "maintenanceEnvelopeProfiles": [
            {
                "envelopeId": "cleaning-vertical-service-approach",
                "bounds": [0.1193125, -0.055155435, 0.1893125, 0.014844565],
                "heightRangeMeters": [0.2045, 0.45],
                "enforcement": "hard",
                "status": "prototype-derived-coarse-estimate",
            },
            {
                "envelopeId": "weighing-vertical-service-approach",
                "bounds": [-0.2764875, 0.025344565, -0.2064875, 0.095344565],
                "heightRangeMeters": [0.2104, 0.45],
                "enforcement": "hard",
                "status": "prototype-derived-coarse-estimate",
            },
            {
                "envelopeId": "cleaning-operator-access",
                "bounds": [0.0843125, -0.155155435, 0.2243125, -0.055155435],
                "heightRangeMeters": [0.0, 0.3],
                "enforcement": "advisory",
                "status": "pending-engineer-confirmation",
            },
            {
                "envelopeId": "weighing-operator-access",
                "bounds": [-0.3114875, -0.074655435, -0.1714875, 0.025344565],
                "heightRangeMeters": [0.0, 0.3],
                "enforcement": "advisory",
                "status": "pending-engineer-confirmation",
            },
        ],
    },
    "A300": {
        "mateNames": ["距离19", "距离20", "重合39"],
        "displayName": "A300排胶模组安装端口",
        "interfaceType": "a300_frame_installation",
        "contextInterfaceType": "a600_a300_installation",
        "solvingState": "rigid",
        "caseAnchored": True,
        "caseAnchorReason": (
            "The two source distance mates admit a mirrored branch from a remote deterministic "
            "start pose.  Keep the Project02 source pose as an explicit provisional branch anchor "
            "until a vendor datum or a signed half-space rule replaces it."
        ),
        "distanceCreationFlipOverrides": {"距离20": False},
        "maintenanceEnvelopeProfiles": [
            {
                "envelopeId": "dual-drain-cup-vertical-approach",
                "bounds": [0.424456743, -0.039666667, 0.584456743, 0.030333333],
                "heightRangeMeters": [0.209, 0.45],
                "enforcement": "hard",
                "status": "prototype-derived-coarse-estimate",
            }
        ],
    },
}


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
            "purpose": "Use A600 as the fixed installation context for a service module.",
        },
    }


def build_base_effective_graph(graph: dict[str, Any]) -> dict[str, Any]:
    base = build_base_graph(graph)
    base["SchemaVersion"] = "editable-module-mate-graph/v1"
    base["EditPolicy"] = {
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "sourceGraphImmutable": True,
        "fixedModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": [],
    }
    return base


def build_a100_parent_context_pose_anchors() -> list[dict[str, Any]]:
    """Select a compact static-pose anchor set from the clean prototype audit.

    A100 is flexible.  Its independent file opens at a valid but different internal
    motion state.  Keep every unstable direct child, add moving nested assemblies
    whose displacement differs from their direct parent, and keep unstable children
    below an otherwise stable direct child.  This is deliberately a static-layout
    snapshot, not a replacement for the internal motion mate graph.
    """

    snapshot = read_json(A100_REFERENCE_SNAPSHOT)
    comparison = read_json(A100_REFERENCE_COMPARISON)
    source_by_path = {
        item["relativeHierarchyPath"]: item for item in snapshot["components"]
    }
    comparison_by_path = {
        item["relativeHierarchyPath"]: item for item in comparison["comparisons"]
    }
    unstable = {
        path: item for path, item in comparison_by_path.items() if not item["stable"]
    }
    selected: set[str] = set()
    direct_distance: dict[str, float] = {}
    for path, item in unstable.items():
        direct = path.split("/", 1)[0]
        if "/" not in path:
            selected.add(path)
            direct_distance[direct] = float(item["translationDistanceMeters"])

    for path, item in unstable.items():
        if "/" not in path:
            continue
        direct = path.split("/", 1)[0]
        source = source_by_path.get(path) or {}
        source_is_assembly = str(source.get("path") or "").lower().endswith(".sldasm")
        if direct not in unstable:
            selected.add(path)
        elif source_is_assembly and abs(
            float(item["translationDistanceMeters"]) - direct_distance[direct]
        ) > 1e-6:
            selected.add(path)

    anchors: list[dict[str, Any]] = []
    for path in sorted(selected, key=lambda value: (value.count("/"), value)):
        source = source_by_path[path]
        resolver_path = path.split("/@module/")[-1]
        anchors.append(
            {
                "relativeLeafHierarchyPath": resolver_path,
                "transform": source["transform"],
                "evidence": (
                    "clean-disk prototype parent-context Transform2, A100 static layout; "
                    f"canonicalSnapshotPath={path}"
                ),
            }
        )
    return anchors


def build_catalog(
    graph: dict[str, Any], endpoint_catalog: dict[str, Any], token: str
) -> dict[str, Any]:
    config = MODULE_CONFIG[token]
    module = find_module(graph, token)
    a600 = find_module(graph, "A600")
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    mate_steps: list[dict[str, Any]] = []
    for mate_name in config["mateNames"]:
        mate = find_mate(graph, mate_name)
        target_endpoints = endpoints_for(mate, token)
        context_endpoints = endpoints_for(mate, "A600")
        target_roles = [f"{mate_name}-target-{index}" for index in range(len(target_endpoints))]
        context_roles = [f"{mate_name}-context-{index}" for index in range(len(context_endpoints))]
        for role, endpoint in zip(target_roles, target_endpoints, strict=True):
            target_bindings.append({"role": role, "endpointId": endpoint_id_for(endpoint_catalog, endpoint)})
        for role, endpoint in zip(context_roles, context_endpoints, strict=True):
            context_bindings.append({"role": role, "endpointId": endpoint_id_for(endpoint_catalog, endpoint)})
        step: dict[str, Any] = {
            "mateName": mate_name,
            "mateType": mate["MateType"],
            "mateTypeName": mate["MateTypeName"],
            "alignment": mate["Alignment"],
            "alignmentName": mate["AlignmentName"],
        }
        if len(target_roles) == len(context_roles) == 1:
            step["endpointRoleA"] = target_roles[0]
            step["endpointRoleB"] = context_roles[0]
        else:
            step["endpointRoles"] = [
                *({"side": "B", "role": role} for role in context_roles),
                *({"side": "A", "role": role} for role in target_roles),
            ]
        if mate.get("Distance") is not None:
            step["distanceMeters"] = mate["Distance"]
        if mate.get("Angle") is not None:
            step["angleRadians"] = mate["Angle"]
        if mate.get("AdvancedOptions") is not None:
            step["advancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
            override = (config.get("distanceCreationFlipOverrides") or {}).get(mate_name)
            if override is not None:
                step["advancedOptions"]["DistanceFlipDimension"] = override
                step["sourceAdvancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
                step["creationOverrideReason"] = (
                    "SolidWorks IMate2 distance FlipDimension is a source/display semantic; "
                    "passing the same boolean to AddMate5 selected the opposite half-space. "
                    "The normalized creation flag was proven by the 2*390 mm V6/V7 branch error."
                )
        mate_steps.append(step)

    return {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": f"Install {token} on A600 and retain its provisional engineering envelopes.",
        "ports": [
            {
                "portId": f"{token}.frame_installation",
                "displayName": config["displayName"],
                "moduleToken": token,
                "moduleHierarchyPath": module["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": config["interfaceType"],
                "capabilities": ["installation", "service_access"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": target_bindings,
                "evidence": [f"原型配合：{'、'.join(config['mateNames'])}"],
            },
            {
                "portId": f"A600.{token.lower()}_installation",
                "displayName": f"A600-{token}安装端口",
                "moduleToken": "A600",
                "moduleHierarchyPath": a600["HierarchyPath"],
                "category": "mechanical",
                "interfaceType": config["contextInterfaceType"],
                "capabilities": ["installation", "service_support"],
                "status": "confirmed-from-source-mates",
                "endpointBindings": context_bindings,
                "evidence": [f"原型配合：{'、'.join(config['mateNames'])}"],
            },
        ],
        "maintenanceEnvelopeProfiles": [
            {
                **copy.deepcopy(item),
                "moduleToken": token,
                "coordinateFrame": "project02-layout-frame-at-prototype-pose",
                "portableAfterModuleMove": False,
                "minimumClearanceMeters": 0.01,
                "evidencePath": "demo/layout_previews/project02_collision_iteration_h8/preview.json",
            }
            for item in config["maintenanceEnvelopeProfiles"]
        ],
        "mateCreationOverrides": [
            {
                "mateName": mate_name,
                "sourceDistanceFlipDimension": find_mate(graph, mate_name).get("AdvancedOptions", {}).get("DistanceFlipDimension"),
                "normalizedAddMate5FlipDimension": value,
                "status": "project02-cad-verified-normalization-pending",
            }
            for mate_name, value in (config.get("distanceCreationFlipOverrides") or {}).items()
        ],
        "connectionTemplates": [
            {
                "templateId": f"{token}_to_A600_source_installation",
                "purposes": ["installation"],
                "interfaceTypeA": config["interfaceType"],
                "interfaceTypeB": config["contextInterfaceType"],
                "constraintEffect": {
                    "purpose": f"Reproduce all source {token}/A600 installation mates.",
                    "fullyLocatesAddedComponent": "requires_cad_verification",
                    "requiredSolvingState": config["solvingState"],
                },
                "mateSteps": mate_steps,
            }
        ],
    }


def build_module_artifacts(graph: dict[str, Any], token: str, output_root: Path) -> dict[str, Any]:
    config = MODULE_CONFIG[token]
    endpoint_catalog = build_face_endpoint_catalog_from_source_mates(graph, config["mateNames"])
    catalog = build_catalog(graph, endpoint_catalog, token)
    request = {
        "schemaVersion": "semantic-assembly-plan/v1",
        "planId": f"project02-add-{token}-complete-source-installation-v1",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": [token] if config.get("caseAnchored") else [],
        "componentToAdd": copy.deepcopy(find_module(graph, token)),
        "connections": [
            {
                "connectionId": f"{token}-installed-on-A600",
                "portAId": f"{token}.frame_installation",
                "portBId": f"A600.{token.lower()}_installation",
                "templateId": f"{token}_to_A600_source_installation",
            }
        ],
    }
    result = build_semantic_assembly_plan(build_base_graph(graph), catalog, endpoint_catalog, request)
    if config.get("caseAnchored"):
        result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})["caseAnchorEvidence"] = {
            "scope": "project02_only",
            "source": f"prototype {token} SourceTransform",
            "reason": config["caseAnchorReason"],
            "notVendorDatum": True,
        }
    result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})["mateCreationOverrides"] = copy.deepcopy(
        catalog["mateCreationOverrides"]
    )
    output_dir = output_root / token
    artifacts = {
        "base_A600_graph.json": build_base_graph(graph),
        "base_A600_effective.json": build_base_effective_graph(graph),
        "face_endpoint_catalog.json": endpoint_catalog,
        "semantic_port_catalog.json": catalog,
        "assembly_plan_request.json": request,
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "assembly_plan_summary.json": {
            "schemaVersion": "project02-service-semantic-installation-build/v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "moduleToken": token,
            "drivingMates": config["mateNames"],
            "requiredSolvingState": config["solvingState"],
            "caseAnchored": bool(config.get("caseAnchored")),
            "maintenanceEnvelopeCount": len(config["maintenanceEnvelopeProfiles"]),
            "maintenanceEnvelopeStatus": "coarse-and-not-portable-after-module-move",
            "summary": result["summary"],
        },
    }
    if token == "A700":
        static_installation_effective = copy.deepcopy(result["effectiveGraph"])
        static_installation_effective["EditPolicy"]["caseAnchoredModuleTokens"] = [
            "A700"
        ]
        static_installation_effective["EditPolicy"][
            "targetLeafPoseAnchors"
        ] = copy.deepcopy(config["staticLeafPoseAnchors"])
        static_installation_effective.setdefault("SemanticAssemblyPlanAudit", {})[
            "staticInstallationPolicy"
        ] = {
            "status": "project02-calibrated-static-installation-demo",
            "reason": (
                "The six source installation mates preserve the real A700/A600 relation, "
                "but they leave a valid residual root pose that is not compatible with the "
                "downstream A500 spacing check. The Project02 calibrated root transform and "
                "two parent-context internal state anchors select the demonstrated static branch."
            ),
            "sourceDrivingMatesApplied": config["mateNames"],
            "caseAnchorIsVendorDatum": False,
            "leafPoseAnchorCount": len(config["staticLeafPoseAnchors"]),
            "motionSemanticsPreserved": False,
            "requiresEngineerApprovalForProduction": True,
        }
        artifacts["static_installation_effective.json"] = (
            static_installation_effective
        )
        static_effective = copy.deepcopy(result["effectiveGraph"])
        static_effective["Mates"] = []
        static_effective["InterModuleMateCount"] = 0
        target_module = next(item for item in static_effective["Modules"] if item["ModuleToken"] == "A700")
        target_module["SolvingState"] = 1
        target_module["SolvingStateName"] = "swComponentFlexibleSolving"
        static_effective["EditPolicy"]["caseAnchoredModuleTokens"] = ["A700"]
        static_effective["EditPolicy"]["targetLeafPoseAnchors"] = copy.deepcopy(
            config["staticLeafPoseAnchors"]
        )
        static_effective.setdefault("SemanticAssemblyPlanAudit", {})["staticSnapshotPolicy"] = {
            "status": "project02-provisional-static-demo",
            "reason": (
                "Current milestone validates static layout and interference, not A700 motion. "
                "The six source mates require flexible solving and allow parent-context leaf motion; "
                "therefore the static branch uses the calibrated source top-level pose plus the "
                "two parent-context assembly-node poses that differ from the independent file."
            ),
            "sourceDrivingMatesRetainedAsEvidence": config["mateNames"],
            "sourceDrivingMatesApplied": [],
            "motionSemanticsPreserved": False,
            "leafPoseAnchorCount": len(config["staticLeafPoseAnchors"]),
            "requiresEngineerApprovalForProduction": True,
        }
        artifacts["static_snapshot_effective.json"] = static_effective
    if token == "A100":
        top_level_effective = copy.deepcopy(result["effectiveGraph"])
        top_level_effective.setdefault("SemanticAssemblyPlanAudit", {})[
            "motionStatePolicy"
        ] = {
            "status": "top-level-installation-closed-internal-motion-state-provisional",
            "reason": (
                "The three A100/A600 installation mates locate the gantry root, while the "
                "independent flexible A100 file can solve to a different valid internal motion state."
            ),
            "topLevelInstallationMayRelease": True,
            "internalProcessPoseMayRelease": False,
            "requiresInternalMotionMateGraphOrConfiguration": True,
        }
        artifacts["top_level_installation_effective.json"] = top_level_effective
        anchors = build_a100_parent_context_pose_anchors()
        target_module = next(
            item for item in result["effectiveGraph"]["Modules"] if item["ModuleToken"] == "A100"
        )
        target_module["SolvingState"] = 0
        target_module["SolvingStateName"] = "swComponentRigidSolving"
        result["effectiveGraph"]["EditPolicy"]["targetLeafPoseAnchors"] = anchors
        result["effectiveGraph"].setdefault("SemanticAssemblyPlanAudit", {})[
            "staticSnapshotPolicy"
        ] = {
            "status": "project02-provisional-static-demo",
            "reason": (
                "A100 is flexible and its independent module opens at a different internal motion state. "
                "The selected parent-context component poses freeze the prototype working state for static "
                "layout and interference verification."
            ),
            "sourceSolvingState": "swComponentFlexibleSolving",
            "staticDemoSolvingState": "swComponentRigidSolving",
            "sourceDrivingMatesApplied": config["mateNames"],
            "motionSemanticsPreserved": False,
            "leafPoseAnchorCount": len(anchors),
            "requiresEngineerApprovalForProduction": True,
            "referenceSnapshot": str(A100_REFERENCE_SNAPSHOT),
            "referenceComparison": str(A100_REFERENCE_COMPARISON),
        }
        artifacts["assembly_plan_effective.json"] = result["effectiveGraph"]
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
    return artifacts["assembly_plan_summary.json"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    graph = read_json(SOURCE_GRAPH)
    summaries = [
        build_module_artifacts(graph, token, args.output_root.resolve())
        for token in ("A700", "A300", "A100")
    ]
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
