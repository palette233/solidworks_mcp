"""Fast Project 01 Top-3 coarse-layout solver.

This is deliberately case-parameterized but rule-driven: transport/flip are
installed first, scanner stays tied to the recovered optical geometry, service
modules use the operation side, and the gantry anchor is solved last from the
intersection of all valve-reach target intervals.  SolidWorks is never called.
"""

from __future__ import annotations

import itertools
import math
from typing import Any


OBJECT_TYPES = {
    "frame-context": ("frame", "base"),
    "transport-process-group": ("transport", "functional"),
    "flip-positioning-module": ("positioning", "functional"),
    "gantry-motion-group": ("gantry", "gantry"),
    "combined-service-module": ("service", "functional"),
    "calibration-module": ("calibration", "functional"),
    "scanner-module": ("scanner", "functional"),
    "glue-supply-module": ("glue_supply", "functional"),
}

SHIFT_OPTIONS = {
    "combined-service-module": ((0.0, 0.0), (-0.030, 0.0), (0.030, 0.0), (0.0, -0.030), (0.0, 0.030)),
    "calibration-module": ((0.0, 0.0), (-0.030, 0.0), (0.030, 0.0), (0.0, -0.030), (0.0, 0.030)),
    "glue-supply-module": ((0.0, 0.0), (-0.040, 0.0), (0.040, 0.0), (0.0, -0.040), (0.0, 0.040)),
}


def _bounds_union(boxes: list[dict[str, Any]]) -> list[float]:
    return [
        min(box["installationBoundsMeters"]["minU"] for box in boxes),
        min(box["installationBoundsMeters"]["minV"] for box in boxes),
        max(box["installationBoundsMeters"]["maxU"] for box in boxes),
        max(box["installationBoundsMeters"]["maxV"] for box in boxes),
    ]


def _height_union(boxes: list[dict[str, Any]]) -> list[float]:
    return [
        min(box["installationBoundsMeters"]["minN"] for box in boxes),
        max(box["installationBoundsMeters"]["maxN"] for box in boxes),
    ]


def _shift_bounds(bounds: list[float], shift: tuple[float, float]) -> list[float]:
    return [bounds[0] + shift[0], bounds[1] + shift[1], bounds[2] + shift[0], bounds[3] + shift[1]]


def _boxes_touch(first: dict[str, Any], second: dict[str, Any], margin: float) -> bool:
    a = first["bounds"]
    b = second["bounds"]
    if a[2] + margin < b[0] - margin or b[2] + margin < a[0] - margin:
        return False
    if a[3] + margin < b[1] - margin or b[3] + margin < a[1] - margin:
        return False
    ah = first["height"]
    bh = second["height"]
    return not (ah[1] + margin < bh[0] - margin or bh[1] + margin < ah[0] - margin)


def _shifted_boxes(
    obj: dict[str, Any], shift: tuple[float, float], *, leaf: bool
) -> list[dict[str, Any]]:
    source = obj["leafBodyOccupancyBoxes"] if leaf else obj["occupancyBoxes"]
    result = []
    for box in source:
        raw = box["installationBoundsMeters"]
        result.append(
            {
                "bounds": [
                    raw["minU"] + shift[0], raw["minV"] + shift[1],
                    raw["maxU"] + shift[0], raw["maxV"] + shift[1],
                ],
                "height": [raw["minN"], raw["maxN"]],
            }
        )
    return result


def _any_box_touch(first: list[dict[str, Any]], second: list[dict[str, Any]], margin: float) -> bool:
    # Axis sort avoids the worst full Cartesian scan for the three leaf-scoped pairs.
    second_sorted = sorted(second, key=lambda item: item["bounds"][0])
    for left in first:
        maximum_u = left["bounds"][2] + 2.0 * margin
        for right in second_sorted:
            if right["bounds"][0] > maximum_u:
                break
            if _boxes_touch(left, right, margin):
                return True
    return False


def _object_center(obj: dict[str, Any]) -> list[float]:
    bounds = _bounds_union(obj["occupancyBoxes"])
    return [(bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0]


def _reach_anchor_interval(
    reach: dict[str, float], targets: list[tuple[float, float]]
) -> list[float]:
    du_min = max(target[0] - reach["maxU"] for target in targets)
    du_max = min(target[0] - reach["minU"] for target in targets)
    dv_min = max(target[1] - reach["maxV"] for target in targets)
    dv_max = min(target[1] - reach["minV"] for target in targets)
    if du_min > du_max or dv_min > dv_max:
        raise ValueError("Project01 service/work targets have no common dual-valve gantry anchor interval")
    return [du_min, dv_min, du_max, dv_max]


def _closest_to_zero(low: float, high: float) -> float:
    return min(high, max(low, 0.0))


def solve_project01_top3(
    occupancy: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
    valve_reach: dict[str, Any],
    scanner_geometry: dict[str, Any],
    *,
    expected_occupancy_status: str = "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY",
    case_id: str = "project01",
    case_label: str = "Project01",
    containment_tolerance_meters: float = 0.010,
    solver_mode: str = "project01-sequential-bounded-top-k",
    anchor_target_source: str = "JJ00-SS00 one coincident plane plus two concentric holes",
    assumption_warnings: list[str] | None = None,
    sequence: list[str] | None = None,
) -> dict[str, Any]:
    if occupancy.get("status") != expected_occupancy_status:
        raise ValueError(f"{case_label} occupancy/collision gate is not ready")
    objects = {item["id"]: item for item in occupancy["layoutObjects"]}
    centers = {key: _object_center(value) for key, value in objects.items()}
    policy = occupancy["staticCollisionPolicy"]
    margin = float(policy["aabbInflationPerSideMeters"])
    strict_profiles = {
        frozenset(item["pair"]): item for item in policy["strictPairProfiles"]
    }
    fixed_shifts = {
        "frame-context": (0.0, 0.0),
        "transport-process-group": (0.0, 0.0),
        "flip-positioning-module": (0.0, 0.0),
        "scanner-module": (0.0, 0.0),
    }
    frame_bounds = _bounds_union(objects["frame-context"]["occupancyBoxes"])
    target_rows: list[tuple[str, str, float, float]] = []
    for item in work_positions.get("workPositions") or []:
        point = item["installationFramePointMeters"]
        target_rows.append((str(item["stableId"]), "transport-process-group", float(point["u"]), float(point["v"])))
    for item in service_points.get("servicePorts") or []:
        point = item["installationFrameMeters"]
        object_id = "calibration-module" if item.get("capability") == "calibration" else "combined-service-module"
        target_rows.append((str(item["id"]), object_id, float(point["u"]), float(point["v"])))

    collision_cache: dict[tuple[Any, ...], bool] = {}

    def strict_clear(shifts: dict[str, tuple[float, float]]) -> bool:
        for pair, profile in strict_profiles.items():
            first_id, second_id = sorted(pair)
            first_shift = shifts.get(first_id, (0.0, 0.0))
            second_shift = shifts.get(second_id, (0.0, 0.0))
            key = (first_id, second_id, first_shift, second_shift, profile["occupancyMode"])
            if key not in collision_cache:
                leaf = profile["occupancyMode"] == "partner-scoped-leaf-body-boxes"
                collision_cache[key] = not _any_box_touch(
                    _shifted_boxes(objects[first_id], first_shift, leaf=leaf),
                    _shifted_boxes(objects[second_id], second_shift, leaf=leaf),
                    margin,
                )
            if not collision_cache[key]:
                return False
        return True

    candidates: list[dict[str, Any]] = []
    explored = 0
    for gn_shift, bd_shift, gj_shift in itertools.product(
        SHIFT_OPTIONS["combined-service-module"],
        SHIFT_OPTIONS["calibration-module"],
        SHIFT_OPTIONS["glue-supply-module"],
    ):
        explored += 1
        shifts = {
            **fixed_shifts,
            "combined-service-module": gn_shift,
            "calibration-module": bd_shift,
            "glue-supply-module": gj_shift,
        }
        targets = [
            (
                u + shifts.get(object_id, (0.0, 0.0))[0],
                v + shifts.get(object_id, (0.0, 0.0))[1],
            )
            for _, object_id, u, v in target_rows
        ]
        interval = _reach_anchor_interval(
            valve_reach["commonReachInstallationFrameMeters"], targets
        )
        gantry_shift = (
            _closest_to_zero(interval[0], interval[2]),
            _closest_to_zero(interval[1], interval[3]),
        )
        shifts["gantry-motion-group"] = gantry_shift

        # Coarse platform containment. Expected mounting-edge contact is allowed
        # by a 10 mm tolerance because JJ00 is represented only by its outer box.
        contained = True
        for object_id in objects:
            if object_id == "frame-context":
                continue
            bounds = _shift_bounds(_bounds_union(objects[object_id]["occupancyBoxes"]), shifts.get(object_id, (0.0, 0.0)))
            if bounds[0] < frame_bounds[0] - containment_tolerance_meters or bounds[1] < frame_bounds[1] - containment_tolerance_meters or bounds[2] > frame_bounds[2] + containment_tolerance_meters or bounds[3] > frame_bounds[3] + containment_tolerance_meters:
                contained = False
                break
        if not contained or not strict_clear(shifts):
            continue
        transport_v = centers["transport-process-group"][1]
        if centers["combined-service-module"][1] + gn_shift[1] <= transport_v + 0.10:
            continue
        if centers["calibration-module"][1] + bd_shift[1] <= transport_v + 0.10:
            continue

        conditional_hits = 0
        for item in policy["conditionalBrepPairs"]:
            first_id, second_id = item["pair"]
            first_bounds = _shift_bounds(_bounds_union(objects[first_id]["occupancyBoxes"]), shifts.get(first_id, (0.0, 0.0)))
            second_bounds = _shift_bounds(_bounds_union(objects[second_id]["occupancyBoxes"]), shifts.get(second_id, (0.0, 0.0)))
            if not (first_bounds[2] < second_bounds[0] or second_bounds[2] < first_bounds[0] or first_bounds[3] < second_bounds[1] or second_bounds[3] < first_bounds[1]):
                conditional_hits += 1
        displacement = sum(math.hypot(*shift) for key, shift in shifts.items() if key not in fixed_shifts)
        service_spread = abs((centers["combined-service-module"][1] + gn_shift[1]) - (centers["calibration-module"][1] + bd_shift[1]))
        score = displacement * 1000.0 + conditional_hits * 0.25 + service_spread * 2.0
        candidates.append(
            {
                "score": score,
                "shifts": shifts,
                "gantryAnchorFeasibleShiftRegion": interval,
                "conditionalBroadPhasePairCount": conditional_hits,
            }
        )

    candidates.sort(key=lambda item: (item["score"], sorted(item["shifts"].items())))
    selected: list[dict[str, Any]] = []
    signatures: set[tuple[Any, ...]] = set()
    for candidate in candidates:
        signature = tuple(
            round(value, 6)
            for object_id in ("combined-service-module", "calibration-module", "glue-supply-module", "gantry-motion-group")
            for value in candidate["shifts"][object_id]
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        selected.append(candidate)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        raise ValueError(f"{case_label} Top-3 search returned only {len(selected)} feasible candidates")

    object_name = {
        object_id: occupancy["modules"][obj["primaryCode"]]["componentName"]
        for object_id, obj in objects.items()
    }
    semantics: dict[str, Any] = {}
    roles: dict[str, str] = {}
    components: list[dict[str, Any]] = []
    for object_id, obj in objects.items():
        name = object_name[object_id]
        module_type, role = OBJECT_TYPES[object_id]
        roles[name] = role
        bounds = _bounds_union(obj["occupancyBoxes"])
        height = _height_union(obj["occupancyBoxes"])
        center = centers[object_id]
        local_boxes = []
        for box in obj["occupancyBoxes"]:
            raw = box["installationBoundsMeters"]
            local_boxes.append(
                {
                    "id": box["id"],
                    "bounds": [raw["minU"] - center[0], raw["minV"] - center[1], raw["maxU"] - center[0], raw["maxV"] - center[1]],
                    "heightRangeMeters": [raw["minN"], raw["maxN"]],
                    "componentCode": obj["primaryCode"],
                }
            )
        semantics[name] = {
            "moduleType": module_type,
            "parameters": {"occupancyBoxesLocal": local_boxes, "provisional": True},
            "points": {},
            "regions": {},
        }
        components.append(
            {
                "componentName": name,
                "filePath": occupancy["modules"][obj["primaryCode"]].get("filePath"),
                "layoutObjectId": object_id,
                "memberCodes": obj["memberCodes"],
                "layout2d": {"x": center[0], "y": center[1], "thetaDegrees": 0.0},
                "projectedFootprint": {"minU": bounds[0], "minV": bounds[1], "maxU": bounds[2], "maxV": bounds[3]},
                "constraintPlacement": {"rotationQuarters": 0},
                "interactionEnvelope": {"bounds": bounds, "heightRangeMeters": height},
                "hardBodyEnvelope": {"bounds": bounds, "heightRangeMeters": height},
            }
        )

    name_by_id = object_name
    for stable_id, object_id, u, v in target_rows:
        name = name_by_id[object_id]
        center = centers[object_id]
        semantics[name]["points"][stable_id] = {"u": u - center[0], "v": v - center[1]}
    scanner_name = name_by_id["scanner-module"]
    for item in scanner_geometry.get("scanners") or []:
        target = item.get("targetProxyInstallationFrameMeters") or item.get("opticalOriginInstallationFrameMeters")
        if isinstance(target, dict) and "u" in target and "v" in target:
            semantics[scanner_name]["points"][str(item.get("role") or "scan-target")] = {
                "u": float(target["u"]) - centers["scanner-module"][0],
                "v": float(target["v"]) - centers["scanner-module"][1],
            }
    gantry_name = name_by_id["gantry-motion-group"]
    reach = valve_reach["commonReachInstallationFrameMeters"]
    gantry_center = centers["gantry-motion-group"]
    semantics[gantry_name]["regions"]["dualValveReach"] = {
        "minU": reach["minU"] - gantry_center[0],
        "minV": reach["minV"] - gantry_center[1],
        "maxU": reach["maxU"] - gantry_center[0],
        "maxV": reach["maxV"] - gantry_center[1],
    }

    strict_name_pairs = [[name_by_id[a], name_by_id[b]] for a, b in policy["strictMultiAabbPairs"]]
    conditional_name_pairs = [[name_by_id[item["pair"][0]], name_by_id[item["pair"][1]]] for item in policy["conditionalBrepPairs"]]
    installation_name_pairs = [[name_by_id[item["pair"][0]], name_by_id[item["pair"][1]]] for item in policy["installationContactPairs"]]
    solutions = []
    for rank, candidate in enumerate(selected, 1):
        placements = []
        for object_id, obj in objects.items():
            shift = candidate["shifts"].get(object_id, (0.0, 0.0))
            center = centers[object_id]
            placements.append(
                {
                    "componentName": name_by_id[object_id],
                    "x": center[0] + shift[0],
                    "y": center[1] + shift[1],
                    "bounds": _shift_bounds(_bounds_union(obj["occupancyBoxes"]), shift),
                    "thetaDegrees": 0.0,
                    "rotationQuarters": 0,
                }
            )
        solutions.append(
            {
                "rank": rank,
                "score": candidate["score"],
                "candidateRanks": [rank],
                "placements": placements,
                "gantryAnchorFeasibleShiftRegion": candidate["gantryAnchorFeasibleShiftRegion"],
                "conditionalBroadPhasePairCount": candidate["conditionalBroadPhasePairCount"],
            }
        )

    validation = {
        "hardFeasible": True,
        "constraintCount": 1,
        "passedCount": 1,
        "diagnostics": [{"id": f"{case_id}-top3-gate", "type": f"{case_id}Top3Gate", "success": True, "hard": True, "message": f"{case_label}工艺、占用与碰撞输入门禁已通过"}],
    }
    return {
        "schemaVersion": 1,
        "caseId": case_id,
        "prototypePoseUsedForSolving": True,
        "sourceCapturePoseUsedForAnchoring": False,
        "components": components,
        "constraintPlan": {
            "sourcePositionIndependent": True,
            "solverMode": solver_mode,
            "longAxis": "u",
            "roles": roles,
            "moduleSemantics": semantics,
            "gantryComponentName": gantry_name,
            "minimumClearanceMeters": margin,
            "processValidation": validation,
            "spatialValidation": validation,
            "interactionValidation": validation,
            "reachValidation": {"hardFeasible": True, "diagnostics": []},
            "validation": {"productionReady": False, "overlapPairs": [], "conditionalInteractionReviewPairs": conditional_name_pairs},
            "jointSearch": {
                "solutionCount": len(solutions),
                "solutions": solutions,
                "exploredNodeCount": explored,
                "maximumSearchNodes": 125,
                "candidateCounts": {key: len(value) for key, value in SHIFT_OPTIONS.items()},
                "acceptedCandidateCounts": {"joint": len(candidates)},
                "collisionMatrix": {},
            },
            "staticCollisionPolicy": {
                "enabled": True,
                "pairCount": policy["pairCount"],
                "strictAabbPairCount": len(strict_name_pairs),
                "brepOnAabbOverlapPairCount": len(conditional_name_pairs),
                "installationContactPairCount": len(installation_name_pairs),
                "strictAabbPairs": strict_name_pairs,
                "brepOnAabbOverlapPairs": conditional_name_pairs,
                "installationContactPairs": installation_name_pairs,
                "aabbInflationPerSideMeters": margin,
                "solverInvokesBrep": False,
            },
            "caseAnchor": {
                "componentName": name_by_id["transport-process-group"],
                "targetKind": "prototype-mate-installation-frame",
                "targetSource": anchor_target_source,
                "scope": f"{case_id}-only",
                "prototypeDerivedParameter": True,
                "sourceCapturePoseReadForAnchor": False,
            },
            "assumptionWarnings": assumption_warnings or [
                "项目01使用自身原型参数，不继承项目02数值。",
                "操作侧、200 mm扫描光束和双阀刻度行程仅授权粗布局。",
                "候选选中后才Replay；条件B-rep不在求解阶段调用。",
            ],
            f"{case_id}Sequence": sequence or [
                "JJ00/HL00 fixed context",
                "SS00 transport installation",
                "FF00 work positioning",
                "SM00 scanner optical alignment",
                "GN00/BD00/GJ00 service-side placement",
                "LM00+ZZ00 inverse reach coverage",
            ],
        },
    }
