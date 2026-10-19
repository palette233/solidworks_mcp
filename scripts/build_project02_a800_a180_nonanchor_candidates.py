from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mate_dof_analysis import analyze_target_mate_dof  # noqa: E402


SOURCE_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v6_all_bodies.json"
A800_EFFECTIVE = ROOT / "demo/semantic_ports/project02_A800_case_anchored_installation_v1/assembly_plan_effective.json"
A180_EFFECTIVE = ROOT / "demo/semantic_ports/project02_A180_scanner_installation_v1/assembly_plan_effective.json"
DEFAULT_ROOT = ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _endpoint(catalog: dict[str, Any], face: int) -> dict[str, Any]:
    matches = [
        copy.deepcopy(row.get("Endpoint") or row)
        for row in catalog.get("Endpoints") or []
        if int((row.get("Endpoint") or row).get("FaceIndexInBody", -1)) == face
        and int((row.get("Endpoint") or row).get("BodyIndex", -1)) == 0
    ]
    if len(matches) != 1:
        raise ValueError(f"Body 0 / Face {face}命中{len(matches)}项。")
    return matches[0]


def _mate(graph: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [copy.deepcopy(row) for row in graph.get("Mates") or [] if row.get("MateName") == name]
    if len(matches) != 1:
        raise ValueError(f"配合{name}命中{len(matches)}项。")
    return matches[0]


def _distance(first: dict[str, Any], second: dict[str, Any], axis: list[float]) -> float:
    first_center = [float(value) for value in first["FaceCenterWorld"][:3]]
    second_center = [float(value) for value in second["FaceCenterWorld"][:3]]
    return abs(sum((left - right) * direction for left, right, direction in zip(first_center, second_center, axis)))


def _distance_mate(
    *,
    name: str,
    target: str,
    context: str,
    target_endpoint: dict[str, Any],
    context_endpoint: dict[str, Any],
    distance: float,
    purpose: str,
) -> dict[str, Any]:
    target_endpoint = copy.deepcopy(target_endpoint)
    context_endpoint = copy.deepcopy(context_endpoint)
    target_endpoint["Index"] = 0
    context_endpoint["Index"] = 1
    return {
        "MateName": name,
        "MateType": 5,
        "MateTypeName": "swMateDISTANCE",
        "Alignment": 0,
        "AlignmentName": "swMateAlignALIGNED",
        "Distance": distance,
        "Angle": None,
        "IsSuppressed": False,
        "IsBasicTwoFaceRebuildable": True,
        "ModuleTokens": [target, context],
        "ModuleHierarchyPaths": [
            target_endpoint["ModuleHierarchyPath"],
            context_endpoint["ModuleHierarchyPath"],
        ],
        "Endpoints": [target_endpoint, context_endpoint],
        "AdvancedOptions": {
            "DistanceFlipDimension": False,
            "SourceFeatureErrorCode": 0,
            "SourceFeatureIsWarning": False,
        },
        "DerivedEngineeringDatum": {
            "authority": "prototype_estimate",
            "purpose": purpose,
            "notVendorDatum": True,
            "productionReady": False,
            "distanceMeters": distance,
        },
    }


def _prepare_nonanchor(graph: dict[str, Any], target: str) -> None:
    source_names = [str(row.get("MateName")) for row in graph.get("Mates") or [] if not row.get("DerivedEngineeringDatum")]
    policy = graph.setdefault("EditPolicy", {})
    policy["initialPlacementMode"] = "deterministic"
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    policy["sourceMateNamesToSuppress"] = source_names
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit["caseAnchorEvidence"] = None
    audit["constraintAssessment"] = {
        "sourceSemanticMateSetReproduced": True,
        "fullyLocatesAddedComponent": "pending_dof_and_cad_verification",
        "reason": f"{target}从确定性的非原型初始位姿插入，仅允许配合图定位。",
        "caseAnchoredModuleTokens": [],
    }
    graph["InterModuleMateCount"] = len(graph.get("Mates") or [])


def build_candidates(
    source_graph: dict[str, Any],
    a800_effective: dict[str, Any],
    a180_effective: dict[str, Any],
    a600_catalog: dict[str, Any],
    a800_catalog: dict[str, Any],
    a180_catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    a600_side = _endpoint(a600_catalog, 0)

    # A800：原型重合＋宽度保留长轴滑移，用两端稳定侧面测得的49.5 mm封闭X。
    a800_target_side = _endpoint(a800_catalog, 106)
    a800_distance = _distance(a800_target_side, a600_side, [1.0, 0.0, 0.0])
    a800_graph = copy.deepcopy(a800_effective)
    a800_graph.setdefault("Mates", []).append(
        _distance_mate(
            name="A800_LOCATING_DISTANCE_X",
            target="A800",
            context="A600",
            target_endpoint=a800_target_side,
            context_endpoint=a600_side,
            distance=a800_distance,
            purpose="close A800 longitudinal translation left by support and width mates",
        )
    )
    _prepare_nonanchor(a800_graph, "A800")
    a800_graph["Project02LocatorExperiment"] = {
        "variant": "source_support_width_plus_derived_x_distance",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": True,
    }

    # A180：恢复原型Free槽的真实方向语义。静态线性模型会保守地留下X，
    # 但SolidWorks槽口求解还包含拓扑/高级配合语义，因此先以原型完整三关系
    # 进入权威CAD检查点；不得在CAD确认前擅自叠加距离造成过约束。
    slot = _mate(source_graph, "槽口3")
    slot_target = _endpoint(a180_catalog, 21)
    slot_context_first = _endpoint(a600_catalog, 110)
    slot_context_second = _endpoint(a600_catalog, 111)
    first_origin = [float(value) for value in slot_context_first["CylinderOriginWorld"][:3]]
    second_origin = [float(value) for value in slot_context_second["CylinderOriginWorld"][:3]]
    delta = [right - left for left, right in zip(first_origin, second_origin)]
    length = math.sqrt(sum(value * value for value in delta))
    direction = [value / length for value in delta]
    axis = [float(value) for value in slot_context_second["CylinderAxisWorld"][:3]]
    slot["Endpoints"] = [copy.deepcopy(slot_context_second), copy.deepcopy(slot_target)]
    for index, endpoint in enumerate(slot["Endpoints"]):
        endpoint["Index"] = index
    slot["AnalysisGeometry"] = {
        "SlotDirectionWorld": direction,
        "SlotAxisWorld": axis,
        "SlotReferencePointWorld": second_origin,
        "SlotEndOriginsWorld": [first_origin, second_origin],
        "SlotLengthMeters": length,
        "Derivation": "same-radius A600 slot-end cylindrical faces 110/111",
    }
    a180_graph = copy.deepcopy(a180_effective)
    a180_graph.setdefault("Mates", []).append(slot)
    _prepare_nonanchor(a180_graph, "A180")
    a180_graph["Project02LocatorExperiment"] = {
        "variant": "source_support_distance_and_rebuilt_free_slot",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": False,
        "slotLengthMeters": length,
        "slotDirectionWorld": direction,
        "staticDofModelStatus": "conservative_residual_one; authoritative CAD required",
    }

    a800_dof = analyze_target_mate_dof(a800_graph, "A800")
    a180_dof = analyze_target_mate_dof(a180_graph, "A180")
    report = {
        "schemaVersion": "project02-a800-a180-nonanchor-candidate-audit/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project02",
        "status": (
            "ready_for_authoritative_cad_checkpoint"
            if a800_dof["closed"] and not a180_dof["unsupportedRelations"]
            else "blocked"
        ),
        "modules": {
            "A800": {
                "sourceRelations": ["重合35", "宽度9"],
                "derivedRelation": "A800_LOCATING_DISTANCE_X",
                "derivedDistanceMeters": a800_distance,
                "parameterAuthority": "prototype_estimate",
                "dofAnalysis": a800_dof,
            },
            "A180": {
                "sourceRelations": ["重合34", "距离24", "槽口3"],
                "sourceSlotLengthMeters": length,
                "sourceSlotDirectionWorld": direction,
                "dofAnalysis": a180_dof,
                "staticModelInterpretation": (
                    "线性化模型保守留下tx；完整Free槽关系必须交由SolidWorks判断。"
                ),
            },
        },
        "sharedPolicy": {
            "initialPlacementMode": "deterministic",
            "caseAnchorAllowed": False,
            "targetLeafPoseAnchorAllowed": False,
            "collisionOrBrepRequiredForThisGate": False,
            "nextGate": "run A800 then A180 independent CAD checkpoints with save-close-reopen verification",
        },
        "limitations": [
            "A800 X向距离由原型稳定面测量，不是厂商权威尺寸。",
            "A180原型槽口保持Free，不把原始设计擅自改为Centered或Distance槽口。",
            "本报告只判断定位配合闭合，不判断光学可见性、碰撞或B-rep。",
        ],
    }
    return report, a800_graph, a180_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Project02 A800/A180 non-anchor positioning candidates.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    report, a800_graph, a180_graph = build_candidates(
        _read(SOURCE_GRAPH),
        _read(A800_EFFECTIVE),
        _read(A180_EFFECTIVE),
        _read(output_root / "a600-a180-support-leaf-face-catalog.json"),
        _read(output_root / "a800-mount-leaf-face-catalog.json"),
        _read(output_root / "a180-mount-leaf-face-catalog.json"),
    )
    _write(output_root / "project02-a800-a180-nonanchor-audit.json", report)
    _write(output_root / "a800-nonanchor-effective.json", a800_graph)
    _write(output_root / "a180-nonanchor-effective.json", a180_graph)
    print(json.dumps({"status": report["status"], "outputRoot": str(output_root)}, ensure_ascii=False))
    return 0 if report["status"] == "ready_for_authoritative_cad_checkpoint" else 2


if __name__ == "__main__":
    raise SystemExit(main())
