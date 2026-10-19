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
    "P000/assembly_plan_effective.json"
)
DEFAULT_P000_CATALOG = ROOT / (
    "demo/semantic_ports/project05_p000_locator_discovery_v1/"
    "p000-mount-leaf-face-catalog-attempt02.json"
)
DEFAULT_A000_CATALOG = ROOT / (
    "demo/semantic_ports/project05_p000_locator_discovery_v1/"
    "a000-p000-support-leaf-face-catalog.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / "demo/semantic_ports/project05_p000_locator_discovery_v1"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
    result = [item / length for item in vector]
    for index, item in enumerate(result):
        if abs(item) < 1e-12:
            result[index] = 0.0
    return result


def _catalog_endpoint(
    catalog: dict[str, Any], body_index: int, face_index: int
) -> dict[str, Any]:
    matches = [
        row
        for row in catalog.get("Endpoints") or []
        if int((row.get("Endpoint") or {}).get("BodyIndex", -1)) == body_index
        and int((row.get("Endpoint") or {}).get("FaceIndexInBody", -1)) == face_index
    ]
    if len(matches) != 1:
        raise ValueError(
            f"面目录中的BodyIndex={body_index}, FaceIndexInBody={face_index}命中{len(matches)}项。"
        )
    return copy.deepcopy(matches[0]["Endpoint"])


def _target_endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [
        row
        for row in mate.get("Endpoints") or []
        if str(row.get("ModuleToken") or "").upper() == token
    ]
    if len(matches) != 1:
        raise ValueError(f"配合{mate.get('MateName')}中的{token}端点数量不是1。")
    return matches[0]


def _cylinders(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(row["Endpoint"])
        for row in catalog.get("Endpoints") or []
        if (row.get("Endpoint") or {}).get("SurfaceType") == "Cylinder"
    ]


def _planes(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(row["Endpoint"])
        for row in catalog.get("Endpoints") or []
        if (row.get("Endpoint") or {}).get("SurfaceType") == "Plane"
    ]


def _parallel(first: list[float], second: list[float], tolerance: float = 1e-6) -> bool:
    return abs(abs(_dot(_normalize(first), _normalize(second))) - 1.0) <= tolerance


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
        "reason": "P000从确定性的非原型初始位姿插入，仅允许配合图定位。",
        "caseAnchoredModuleTokens": [],
    }


def build_discovery(
    source_graph: dict[str, Any],
    effective_graph: dict[str, Any],
    p000_catalog: dict[str, Any],
    a000_catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    slot_matches = [
        copy.deepcopy(mate)
        for mate in source_graph.get("Mates") or []
        if int(mate.get("MateType", -1)) == 21
        and {str(token).upper() for token in mate.get("ModuleTokens") or []}
        == {"A000", "P000"}
    ]
    if len(slot_matches) != 1:
        raise ValueError(f"A000/P000槽口配合命中{len(slot_matches)}项，期望1项。")
    slot = slot_matches[0]
    advanced = slot.get("AdvancedOptions") or {}
    if int(advanced.get("SlotConstraint", -1)) != 0:
        raise ValueError("原型P000槽口配合不是Free模式，不能应用本发现流程。")
    target_slot_endpoint = _target_endpoint(slot, "P000")
    context_pin_endpoint = _target_endpoint(slot, "A000")
    selected_origin = _vector(target_slot_endpoint.get("CylinderOriginWorld"))
    selected_axis = _normalize(_vector(target_slot_endpoint.get("CylinderAxisWorld")))
    selected_radius = float(target_slot_endpoint.get("CylinderRadius"))

    companion_candidates = []
    for endpoint in _cylinders(p000_catalog):
        if int(endpoint.get("BodyIndex", -1)) != int(target_slot_endpoint.get("BodyIndex", -2)):
            continue
        if int(endpoint.get("FaceIndexInBody", -1)) == int(target_slot_endpoint.get("FaceIndexInBody", -2)):
            continue
        radius = endpoint.get("CylinderRadius")
        axis = endpoint.get("CylinderAxisWorld")
        origin = endpoint.get("CylinderOriginWorld")
        if radius is None or axis is None or origin is None:
            continue
        if abs(float(radius) - selected_radius) > 1e-7:
            continue
        if not _parallel(_vector(axis), selected_axis):
            continue
        delta = _subtract(_vector(origin), selected_origin)
        axial = abs(_dot(delta, selected_axis))
        planar = math.sqrt(max(0.0, _dot(delta, delta) - axial * axial))
        if axial <= 1e-7 and 0.01 <= planar <= 0.1:
            companion_candidates.append((planar, endpoint))
    companion_candidates.sort(key=lambda item: item[0])
    if not companion_candidates:
        raise ValueError(
            "P000源槽端面没有找到同半径、同轴向的伙伴圆柱面。"
        )
    if (
        len(companion_candidates) > 1
        and abs(companion_candidates[1][0] - companion_candidates[0][0]) <= 1e-7
    ):
        raise ValueError("P000源槽端面的最近伙伴不唯一。")
    companion = companion_candidates[0][1]
    companion_origin = _vector(companion.get("CylinderOriginWorld"))
    slot_direction = _normalize(_subtract(selected_origin, companion_origin))
    slot_length = abs(_dot(_subtract(selected_origin, companion_origin), slot_direction))
    slot_center = [
        (left + right) / 2.0 for left, right in zip(selected_origin, companion_origin)
    ]
    pin_origin = _vector(context_pin_endpoint.get("CylinderOriginWorld"))
    signed_offset = _dot(_subtract(pin_origin, slot_center), slot_direction)
    distance_from_companion = _dot(_subtract(pin_origin, companion_origin), slot_direction)
    percent_from_companion = 100.0 * distance_from_companion / slot_length
    slot["AnalysisGeometry"] = {
        "SlotDirectionWorld": slot_direction,
        "SlotAxisWorld": selected_axis,
        "SlotEndOriginsWorld": [companion_origin, selected_origin],
        "SlotCenterWorld": slot_center,
        "ContextPinOriginWorld": pin_origin,
        "SlotLengthMeters": slot_length,
        "SignedPinOffsetFromCenterMeters": signed_offset,
        "PinPercentFromCompanionEnd": percent_from_companion,
        "Derivation": "same-body same-radius companion cylindrical arc",
    }

    source_slot_graph = copy.deepcopy(effective_graph)
    source_mate_names = [str(mate.get("MateName")) for mate in source_slot_graph.get("Mates") or []]
    source_slot_graph.setdefault("Mates", []).append(slot)
    source_slot_graph["InterModuleMateCount"] = len(source_slot_graph["Mates"])
    source_mate_names.append(str(slot.get("MateName")))
    _prepare_nonanchor(source_slot_graph, source_mate_names)
    source_slot_graph["P000LocatorExperiment"] = {
        "schemaVersion": "project05-p000-locator-experiment/v1",
        "variant": "source_free_slot",
        "sourceSlotConstraint": 0,
        "sourceSlotConstraintName": "swSlotMateConstraintOption_Free",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": False,
    }
    free_slot_dof = analyze_target_mate_dof(source_slot_graph, "P000")

    p_side_candidates = [
        endpoint
        for endpoint in _planes(p000_catalog)
        if (endpoint.get("FaceNormalWorld") is not None)
        and _vector(endpoint["FaceNormalWorld"])[0] > 0.95
    ]
    a_side_candidates = [
        endpoint
        for endpoint in _planes(a000_catalog)
        if (endpoint.get("FaceNormalWorld") is not None)
        and _vector(endpoint["FaceNormalWorld"])[0] > 0.95
        and float(endpoint.get("FaceArea") or 0.0) > 0.01
    ]
    if len(p_side_candidates) != 1 or len(a_side_candidates) != 1:
        raise ValueError(
            "无法唯一确定P000左侧安装面或A000左侧结构基准面："
            f"P000={len(p_side_candidates)}, A000={len(a_side_candidates)}。"
        )
    p_side = p_side_candidates[0]
    a_side = a_side_candidates[0]
    p_center = _vector(p_side["FaceCenterWorld"])
    a_center = _vector(a_side["FaceCenterWorld"])
    distance = abs(_dot(_subtract(p_center, a_center), [1.0, 0.0, 0.0]))
    p_side["ModuleToken"] = "P000"
    a_side["ModuleToken"] = "A000"
    p_side["Index"] = 0
    a_side["Index"] = 1
    locating_distance = {
        "MateName": "P000_LOCATING_DISTANCE_X",
        "MateType": 5,
        "MateTypeName": "swMateDISTANCE",
        "Alignment": 0,
        "AlignmentName": "swMateAlignALIGNED",
        "Distance": distance,
        "Angle": None,
        "IsSuppressed": False,
        "ModuleTokens": ["P000", "A000"],
        "ModuleHierarchyPaths": [
            p_side["ModuleHierarchyPath"],
            a_side["ModuleHierarchyPath"],
        ],
        "Endpoints": [p_side, a_side],
        "AdvancedOptions": {
            "WidthConstraintType": None,
            "WidthPercentDistanceFromEnd": None,
            "WidthDistanceFromEnd": None,
            "WidthFlipDimension": None,
            "WidthEndpointIndices": [],
            "TabEndpointIndices": [],
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
            "distanceMeters": distance,
        },
    }
    distance_graph = copy.deepcopy(source_slot_graph)
    distance_graph["Mates"].append(locating_distance)
    distance_graph["InterModuleMateCount"] = len(distance_graph["Mates"])
    distance_graph["P000LocatorExperiment"] = {
        "schemaVersion": "project05-p000-locator-experiment/v1",
        "variant": "source_free_slot_plus_derived_x_distance",
        "sourceSlotConstraint": 0,
        "sourceSlotConstraintName": "swSlotMateConstraintOption_Free",
        "prototypePoseUsedForInitialPlacement": False,
        "prototypePoseUsedForParameterEstimation": True,
        "estimatedParameter": {
            "name": "P000 left-side plane to A000 left structural plane",
            "distanceMeters": distance,
        },
    }
    distance_dof = analyze_target_mate_dof(distance_graph, "P000")

    round_holes = [
        endpoint
        for endpoint in _cylinders(p000_catalog)
        if abs(float(endpoint.get("CylinderRadius") or 0.0) - 0.0025) <= 1e-7
    ]
    report = {
        "schemaVersion": "project05-p000-locator-discovery/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project05",
        "targetModuleToken": "P000",
        "sourceSlot": {
            "mateName": slot.get("MateName"),
            "constraint": 0,
            "constraintName": "swSlotMateConstraintOption_Free",
            "slotDirectionWorld": slot_direction,
            "slotAxisWorld": selected_axis,
            "slotEndOriginsWorld": [companion_origin, selected_origin],
            "slotLengthMeters": slot_length,
            "contextPinOriginWorld": pin_origin,
            "signedPinOffsetFromCenterMeters": signed_offset,
            "pinPercentFromCompanionEnd": percent_from_companion,
        },
        "candidateRoundHoleCountOnP000MountLeaf": len(round_holes),
        "candidateRoundHoles": [
            {
                "faceIndexInBody": endpoint.get("FaceIndexInBody"),
                "originWorld": endpoint.get("CylinderOriginWorld"),
                "radiusMeters": endpoint.get("CylinderRadius"),
            }
            for endpoint in round_holes
        ],
        "sourceFreeSlotDofAnalysis": free_slot_dof,
        "derivedDistanceDatum": locating_distance["DerivedEngineeringDatum"]
        | {
            "targetFaceIndexInBody": p_side.get("FaceIndexInBody"),
            "contextFaceIndexInBody": a_side.get("FaceIndexInBody"),
            "targetFaceCenterWorld": p_center,
            "contextFaceCenterWorld": a_center,
        },
        "derivedDistanceDofAnalysis": distance_dof,
        "conclusion": (
            "原型Free槽口只消除横槽方向，仍保留沿槽X向平移；没有发现可直接替代该自由度的原型第二配合。"
            "追加一个由原型测得的X向安装距离后，面级刚体约束秩达到6，可进入非原型初始位姿CAD验证。"
        ),
        "limitations": [
            "X向距离是原型估计参数，不是厂商权威安装尺寸。",
            "P000底脚虽有两个圆孔和两条槽，但原型顶层配合只使用一个Free槽口；未擅自把未配合孔解释为定位销孔。",
            "本报告不执行碰撞或B-rep检查。",
        ],
    }
    return report, source_slot_graph, distance_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="发现Project05 P000真实定位基准并生成无锚点候选图。")
    parser.add_argument("--source-graph", type=Path, default=DEFAULT_SOURCE_GRAPH)
    parser.add_argument("--effective-graph", type=Path, default=DEFAULT_EFFECTIVE_GRAPH)
    parser.add_argument("--p000-catalog", type=Path, default=DEFAULT_P000_CATALOG)
    parser.add_argument("--a000-catalog", type=Path, default=DEFAULT_A000_CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    report, free_graph, distance_graph = build_discovery(
        _read(args.source_graph.resolve()),
        _read(args.effective_graph.resolve()),
        _read(args.p000_catalog.resolve()),
        _read(args.a000_catalog.resolve()),
    )
    output_root = args.output_root.resolve()
    _write(output_root / "project05-p000-locator-discovery.json", report)
    _write(output_root / "p000-source-free-slot-nonanchor-effective.json", free_graph)
    _write(
        output_root / "p000-free-slot-plus-derived-x-distance-nonanchor-effective.json",
        distance_graph,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
