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


DEFAULT_SOURCE_GRAPH = ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"
DEFAULT_EFFECTIVE_GRAPH = ROOT / (
    "demo/semantic_ports/project05_global_installation_ports_v1/"
    "N000/assembly_plan_effective.json"
)
DEFAULT_N000_CATALOG = ROOT / (
    "demo/semantic_ports/project05_n000_locator_discovery_v1/"
    "n000-mount-leaf-face-catalog.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / "demo/semantic_ports/project05_n000_locator_discovery_v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _vector(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("需要三维向量。")
    return [float(item) for item in value[:3]]


def _subtract(first: list[float], second: list[float]) -> list[float]:
    return [left - right for left, right in zip(first, second)]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(left * right for left, right in zip(first, second))


def _length(vector: list[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: list[float]) -> list[float]:
    length = _length(vector)
    if length <= 1e-12:
        raise ValueError("零向量不能归一化。")
    return [0.0 if abs(item / length) < 1e-12 else item / length for item in vector]


def _parallel(first: list[float], second: list[float], tolerance: float = 1e-6) -> bool:
    return abs(abs(_dot(_normalize(first), _normalize(second))) - 1.0) <= tolerance


def _endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        row for row in mate.get("Endpoints") or []
        if str(row.get("ModuleToken") or "").upper() == token
    ]
    if len(matches) != 1:
        raise ValueError(f"配合{mate.get('MateName')}中的{token}端点数量不是1。")
    return copy.deepcopy(matches[0])


def _catalog_endpoints(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [copy.deepcopy(row["Endpoint"]) for row in catalog.get("Endpoints") or []]


def _prepare_nonanchor(graph: dict[str, Any], source_mate_names: list[str]) -> None:
    policy = graph.setdefault("EditPolicy", {})
    policy["initialPlacementMode"] = "deterministic"
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    policy["sourceMateNamesToSuppress"] = source_mate_names
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit["caseAnchorEvidence"] = None
    audit["constraintAssessment"] = {
        "sourceSemanticMateSetReproduced": True,
        "fullyLocatesAddedComponent": "pending_dof_and_cad_verification",
        "reason": "N000从确定性的非原型初始位姿插入，仅允许配合图定位。",
        "caseAnchoredModuleTokens": [],
    }


def build_discovery(
    source_graph: dict[str, Any],
    effective_graph: dict[str, Any],
    n000_catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    slot_matches = [
        copy.deepcopy(mate)
        for mate in source_graph.get("Mates") or []
        if int(mate.get("MateType", -1)) == 21
        and {str(token).upper() for token in mate.get("ModuleTokens") or []}
        == {"A000", "N000"}
    ]
    if len(slot_matches) != 1:
        raise ValueError(f"A000/N000槽口配合命中{len(slot_matches)}项，期望1项。")
    slot = slot_matches[0]
    advanced = slot.get("AdvancedOptions") or {}
    if "SlotConstraint" not in advanced or int(advanced["SlotConstraint"]) != 0:
        raise ValueError("原型N000槽口配合不是显式Free模式。")

    slot_wall = _endpoint(slot, "N000")
    context_pin = _endpoint(slot, "A000")
    pin_axis = _normalize(_vector(context_pin.get("CylinderAxisWorld")))
    pin_origin = _vector(context_pin.get("CylinderOriginWorld"))
    wall_center = _vector(slot_wall.get("FaceCenterWorld"))
    candidates: list[tuple[float, dict[str, Any]]] = []
    for endpoint in _catalog_endpoints(n000_catalog):
        if endpoint.get("SurfaceType") != "Cylinder":
            continue
        axis = endpoint.get("CylinderAxisWorld")
        origin = endpoint.get("CylinderOriginWorld")
        radius = endpoint.get("CylinderRadius")
        if axis is None or origin is None or radius is None:
            continue
        if not _parallel(_vector(axis), pin_axis):
            continue
        delta = _subtract(_vector(origin), wall_center)
        axial = abs(_dot(delta, pin_axis))
        planar = math.sqrt(max(0.0, _dot(delta, delta) - axial * axial))
        if axial <= 0.02 and planar <= 0.08:
            candidates.append((planar, endpoint))
    candidates.sort(key=lambda row: row[0])
    pair: tuple[dict[str, Any], dict[str, Any]] | None = None
    for index, (_, first) in enumerate(candidates):
        for _, second in candidates[index + 1:]:
            if abs(float(first["CylinderRadius"]) - float(second["CylinderRadius"])) > 1e-7:
                continue
            delta = _subtract(
                _vector(second["CylinderOriginWorld"]),
                _vector(first["CylinderOriginWorld"]),
            )
            separation = _length(delta)
            if 0.02 <= separation <= 0.08 and abs(_dot(_normalize(delta), pin_axis)) < 0.05:
                pair = (first, second)
                break
        if pair:
            break
    if pair is None:
        raise ValueError("N000槽壁附近没有找到唯一可用的同半径端部圆弧对。")
    first_origin = _vector(pair[0]["CylinderOriginWorld"])
    second_origin = _vector(pair[1]["CylinderOriginWorld"])
    slot_direction = _normalize(_subtract(second_origin, first_origin))
    if _dot(_subtract(pin_origin, first_origin), slot_direction) < 0:
        first_origin, second_origin = second_origin, first_origin
        slot_direction = _normalize(_subtract(second_origin, first_origin))
    slot_center = [(left + right) / 2.0 for left, right in zip(first_origin, second_origin)]
    slot_length = _length(_subtract(second_origin, first_origin))
    distance_from_first = _dot(_subtract(pin_origin, first_origin), slot_direction)
    slot["AnalysisGeometry"] = {
        "SlotDirectionWorld": slot_direction,
        "SlotAxisWorld": pin_axis,
        "SlotReferencePointWorld": pin_origin,
        "SlotEndOriginsWorld": [first_origin, second_origin],
        "SlotCenterWorld": slot_center,
        "ContextPinOriginWorld": pin_origin,
        "SlotLengthMeters": slot_length,
        "PinDistanceFromFirstEndMeters": distance_from_first,
        "PinPercentFromFirstEnd": 100.0 * distance_from_first / slot_length,
        "Derivation": "nearest same-radius slot-end cylindrical arc pair around exported slot wall",
    }

    free_graph = copy.deepcopy(effective_graph)
    source_names = [str(mate.get("MateName")) for mate in free_graph.get("Mates") or []]
    free_graph.setdefault("Mates", []).append(slot)
    source_names.append(str(slot.get("MateName")))
    free_graph["InterModuleMateCount"] = len(free_graph["Mates"])
    _prepare_nonanchor(free_graph, source_names)
    free_graph["N000LocatorExperiment"] = {
        "schemaVersion": "project05-n000-locator-experiment/v1",
        "variant": "source_free_slot",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": False,
    }
    free_dof = analyze_target_mate_dof(free_graph, "N000")

    parallel_matches = [
        mate for mate in free_graph["Mates"]
        if str(mate.get("MateName")) == "平行13"
    ]
    if len(parallel_matches) != 1:
        raise ValueError("N000定位平行面配合平行13不唯一。")
    target_plane = _endpoint(parallel_matches[0], "N000")
    context_plane = _endpoint(parallel_matches[0], "A000")
    target_center = _vector(target_plane["FaceCenterWorld"])
    context_center = _vector(context_plane["FaceCenterWorld"])
    if not _parallel(_vector(target_plane["FaceNormalWorld"]), slot_direction):
        raise ValueError("N000平行13目标面法向与槽方向不平行，不能作为沿槽定位基准。")
    if not _parallel(_vector(context_plane["FaceNormalWorld"]), slot_direction):
        raise ValueError("A000平行13上下文面法向与槽方向不平行。")
    distance = abs(_dot(_subtract(target_center, context_center), slot_direction))
    target_plane["Index"] = 0
    context_plane["Index"] = 1
    locating_distance = {
        "MateName": "N000_LOCATING_DISTANCE_X",
        "MateType": 5,
        "MateTypeName": "swMateDISTANCE",
        "Alignment": 0,
        "AlignmentName": "swMateAlignALIGNED",
        "Distance": distance,
        "Angle": None,
        "IsSuppressed": False,
        "ModuleTokens": ["N000", "A000"],
        "ModuleHierarchyPaths": [
            target_plane["ModuleHierarchyPath"],
            context_plane["ModuleHierarchyPath"],
        ],
        "Endpoints": [target_plane, context_plane],
        "AdvancedOptions": {
            "SlotConstraint": None,
            "SlotDistance": None,
            "SlotPercent": None,
            "SlotFlipDirection": None,
            "DistanceFlipDimension": False,
            "SourceFeatureErrorCode": 0,
            "SourceFeatureIsWarning": False,
        },
        "DerivedEngineeringDatum": {
            "authority": "prototype_estimate",
            "purpose": "close the source free-slot residual X translation",
            "notVendorDatum": True,
            "productionReady": False,
            "distanceMeters": distance,
        },
    }
    closed_graph = copy.deepcopy(free_graph)
    closed_graph["Mates"].append(locating_distance)
    closed_graph["InterModuleMateCount"] = len(closed_graph["Mates"])
    closed_graph["N000LocatorExperiment"] = {
        "schemaVersion": "project05-n000-locator-experiment/v1",
        "variant": "source_free_slot_plus_derived_x_distance",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": True,
        "estimatedParameter": {
            "name": "N000 side installation plane to A000 side structural plane",
            "distanceMeters": distance,
        },
    }
    closed_dof = analyze_target_mate_dof(closed_graph, "N000")

    report = {
        "schemaVersion": "project05-n000-locator-discovery/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project05",
        "targetModuleToken": "N000",
        "sourceSlot": {
            "mateName": slot.get("MateName"),
            "constraint": 0,
            "constraintName": "swSlotMateConstraintOption_Free",
            "slotDirectionWorld": slot_direction,
            "slotAxisWorld": pin_axis,
            "slotEndOriginsWorld": [first_origin, second_origin],
            "slotLengthMeters": slot_length,
            "pinDistanceFromFirstEndMeters": distance_from_first,
        },
        "sourceFreeSlotDofAnalysis": free_dof,
        "derivedDistanceDatum": locating_distance["DerivedEngineeringDatum"] | {
            "targetFaceIndexInBody": target_plane.get("FaceIndexInBody"),
            "contextFaceIndexInBody": context_plane.get("FaceIndexInBody"),
            "targetFaceCenterWorld": target_center,
            "contextFaceCenterWorld": context_center,
        },
        "derivedDistanceDofAnalysis": closed_dof,
        "conclusion": (
            "原型Free槽口保留沿槽X向平移；追加由原型平行13两端稳定平面测得的X向距离后，"
            "静态刚体约束应达到6/6，可进入非原型初始位姿CAD验证。"
        ),
        "limitations": [
            "X向距离是原型估计参数，不是厂商权威安装尺寸。",
            "自由槽原本允许安装调整；闭合距离表示Demo中的确定位置，而非改变零件设计。",
            "本报告不执行碰撞或B-rep检查。",
        ],
    }
    return report, free_graph, closed_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="审计Project05 N000自由槽并生成无锚点定位候选图。")
    parser.add_argument("--source-graph", type=Path, default=DEFAULT_SOURCE_GRAPH)
    parser.add_argument("--effective-graph", type=Path, default=DEFAULT_EFFECTIVE_GRAPH)
    parser.add_argument("--n000-catalog", type=Path, default=DEFAULT_N000_CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    report, free_graph, closed_graph = build_discovery(
        _read(args.source_graph.resolve()),
        _read(args.effective_graph.resolve()),
        _read(args.n000_catalog.resolve()),
    )
    output_root = args.output_root.resolve()
    _write(output_root / "project05-n000-locator-discovery.json", report)
    _write(output_root / "n000-source-free-slot-nonanchor-effective.json", free_graph)
    _write(
        output_root / "n000-free-slot-plus-derived-x-distance-nonanchor-effective.json",
        closed_graph,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
