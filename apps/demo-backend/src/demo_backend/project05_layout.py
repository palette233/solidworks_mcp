"""Deterministic Project05 coarse Top-3 layout solver.

The solver is intentionally prototype-calibrated, not a prototype copy.  The
A000/E000 frame, D000 transport, K000 lift, F000 scanner and M000 CCD retain
their recovered installation relationships.  G000/N000/P000 are enumerated in
the operation-side service strip, strict pairs use complete leaf-body AABBs,
and the B000/Z000 gantry translation is solved last from the intersection of
all work/service target reach intervals.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from .project01_layout import (
    _any_box_touch,
    _bounds_union,
    _closest_to_zero,
    _height_union,
    _object_center,
    _reach_anchor_interval,
    _shift_bounds,
    _shifted_boxes,
)


OBJECT_TYPES = {
    "frame-context": ("frame", "base"),
    "transport-process-group": ("transport", "functional"),
    "lift-positioning-module": ("positioning", "functional"),
    "gantry-motion-group": ("gantry", "gantry"),
    "scanner-module": ("scanner", "functional"),
    "calibration-weighing-module": ("calibration", "functional"),
    "product-ccd-module": ("ccd", "functional"),
    "cleaning-module": ("cleaning", "functional"),
    "drain-module": ("functional", "functional"),
}

SERVICE_OBJECT_BY_MODULE = {
    "G000": "calibration-weighing-module",
    "N000": "cleaning-module",
    "P000": "drain-module",
}

# Thirteen deterministic, millimetre-scale alternatives per independent
# service object.  They are small enough for a fast bounded search but expose
# both axial and diagonal collision-escape choices.
SERVICE_SHIFT_OPTIONS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (-0.030, 0.0), (0.030, 0.0), (0.0, -0.030), (0.0, 0.030),
    (-0.060, 0.0), (0.060, 0.0), (0.0, -0.060), (0.0, 0.060),
    (-0.030, -0.030), (-0.030, 0.030),
    (0.030, -0.030), (0.030, 0.030),
)


def _inside_strip(bounds: list[float], strip: dict[str, float]) -> bool:
    return (
        bounds[0] >= float(strip["minU"])
        and bounds[2] <= float(strip["maxU"])
        and bounds[1] >= float(strip["minV"])
        and bounds[3] <= float(strip["maxV"])
    )


def solve_project05_top3(
    occupancy: dict[str, Any],
    work_positions: dict[str, Any],
    service_points: dict[str, Any],
    valve_reach: dict[str, Any],
    optical_geometry: dict[str, Any],
    operation_side: dict[str, Any],
) -> dict[str, Any]:
    if occupancy.get("status") != "PROJECT05_COLLISION_POLICY_AND_OCCUPANCY_READY":
        raise ValueError("Project05 occupancy/collision gate is not ready")
    if occupancy.get("solverOccupancyReady") is not True:
        raise ValueError("Project05 complete leaf-body occupancy is unavailable")
    if operation_side.get("coarseLayoutUsable") is not True:
        raise ValueError("Project05 operation-side strip is unavailable")
    if valve_reach.get("allTargetsInsideCommonPlanarReach") is not True:
        raise ValueError("Project05 common planar reach is unavailable")

    objects = {item["id"]: item for item in occupancy["layoutObjects"]}
    expected = set(OBJECT_TYPES)
    if set(objects) != expected:
        raise ValueError(f"Project05 layout-object contract mismatch: {sorted(set(objects) ^ expected)}")
    centers = {key: _object_center(value) for key, value in objects.items()}
    policy = occupancy["staticCollisionPolicy"]
    if policy.get("strictPairOccupancyMode") != "complete-leaf-body-aabbs":
        raise ValueError("Project05 strict collision policy is not leaf-body based")
    margin = float(policy["aabbInflationPerSideMeters"])
    strict_pairs = [tuple(item) for item in policy["strictMultiAabbPairs"]]
    service_ids = tuple(SERVICE_OBJECT_BY_MODULE.values())
    fixed_shifts = {
        "frame-context": (0.0, 0.0),
        "transport-process-group": (0.0, 0.0),
        "lift-positioning-module": (0.0, 0.0),
        "scanner-module": (0.0, 0.0),
        "product-ccd-module": (0.0, 0.0),
    }
    strip = operation_side["coarseServiceStripInstallationMeters"]

    target_rows: list[tuple[str, str | None, float, float]] = []
    for item in work_positions.get("workPositions") or []:
        point = item["installationFramePointMeters"]
        target_rows.append((str(item["stableId"]), None, float(point["u"]), float(point["v"])))
    for item in service_points.get("servicePorts") or []:
        object_id = SERVICE_OBJECT_BY_MODULE.get(str(item.get("sourceModule") or ""))
        if object_id is None:
            raise ValueError(f"Unknown Project05 service module: {item.get('sourceModule')}")
        point = item["installationFrameMeters"]
        target_rows.append((str(item["id"]), object_id, float(point["u"]), float(point["v"])))
    if len(target_rows) != 8:
        raise ValueError(f"Project05 expected 8 reach targets; found {len(target_rows)}")

    collision_cache: dict[tuple[Any, ...], bool] = {}

    def strict_clear(shifts: dict[str, tuple[float, float]]) -> bool:
        for first_id, second_id in strict_pairs:
            first_shift = shifts.get(first_id, (0.0, 0.0))
            second_shift = shifts.get(second_id, (0.0, 0.0))
            key = (first_id, second_id, first_shift, second_shift)
            if key not in collision_cache:
                collision_cache[key] = not _any_box_touch(
                    _shifted_boxes(objects[first_id], first_shift, leaf=True),
                    _shifted_boxes(objects[second_id], second_shift, leaf=True),
                    margin,
                )
            if not collision_cache[key]:
                return False
        return True

    candidates: list[dict[str, Any]] = []
    rejection_counts = {"operationSideStrip": 0, "commonReach": 0, "strictLeafAabb": 0}
    explored = 0
    for g_shift, n_shift, p_shift in itertools.product(SERVICE_SHIFT_OPTIONS, repeat=3):
        explored += 1
        shifts = {
            **fixed_shifts,
            "calibration-weighing-module": g_shift,
            "cleaning-module": n_shift,
            "drain-module": p_shift,
        }
        if any(
            not _inside_strip(
                _shift_bounds(_bounds_union(objects[object_id]["occupancyBoxes"]), shifts[object_id]),
                strip,
            )
            for object_id in service_ids
        ):
            rejection_counts["operationSideStrip"] += 1
            continue

        targets = [
            (
                u + shifts.get(object_id or "", (0.0, 0.0))[0],
                v + shifts.get(object_id or "", (0.0, 0.0))[1],
            )
            for _, object_id, u, v in target_rows
        ]
        try:
            interval = _reach_anchor_interval(
                valve_reach["commonPlanarReachInstallationMeters"], targets
            )
        except ValueError:
            rejection_counts["commonReach"] += 1
            continue
        shifts["gantry-motion-group"] = (
            _closest_to_zero(interval[0], interval[2]),
            _closest_to_zero(interval[1], interval[3]),
        )
        if not strict_clear(shifts):
            rejection_counts["strictLeafAabb"] += 1
            continue

        conditional_hits = 0
        for item in policy["conditionalBrepPairs"]:
            first_id, second_id = item["pair"]
            first = _shift_bounds(
                _bounds_union(objects[first_id]["occupancyBoxes"]), shifts.get(first_id, (0.0, 0.0))
            )
            second = _shift_bounds(
                _bounds_union(objects[second_id]["occupancyBoxes"]), shifts.get(second_id, (0.0, 0.0))
            )
            if not (
                first[2] < second[0] or second[2] < first[0]
                or first[3] < second[1] or second[3] < first[1]
            ):
                conditional_hits += 1
        displacement = sum(math.hypot(*shifts[object_id]) for object_id in service_ids)
        service_centres = [
            (centers[object_id][0] + shifts[object_id][0], centers[object_id][1] + shifts[object_id][1])
            for object_id in service_ids
        ]
        minimum_service_spacing = min(
            math.dist(first, second)
            for first, second in itertools.combinations(service_centres, 2)
        )
        score = displacement * 1000.0 + conditional_hits * 0.25 - minimum_service_spacing * 0.1
        candidates.append({
            "score": score,
            "shifts": shifts,
            "gantryAnchorFeasibleShiftRegion": interval,
            "conditionalBroadPhasePairCount": conditional_hits,
            "minimumServiceCenterSpacingMeters": minimum_service_spacing,
        })

    candidates.sort(key=lambda item: (item["score"], sorted(item["shifts"].items())))
    selected: list[dict[str, Any]] = []
    signatures: set[tuple[Any, ...]] = set()
    for candidate in candidates:
        signature = tuple(
            round(value, 6)
            for object_id in (*service_ids, "gantry-motion-group")
            for value in candidate["shifts"][object_id]
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        selected.append(candidate)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        raise ValueError(f"Project05 Top-3 search returned only {len(selected)} feasible candidates")

    object_names = {
        object_id: occupancy["modules"][item["primaryCode"]]["componentName"]
        for object_id, item in objects.items()
    }
    semantics: dict[str, Any] = {}
    roles: dict[str, str] = {}
    components: list[dict[str, Any]] = []
    for object_id, item in objects.items():
        name = object_names[object_id]
        module_type, role = OBJECT_TYPES[object_id]
        roles[name] = role
        bounds = _bounds_union(item["occupancyBoxes"])
        height = _height_union(item["occupancyBoxes"])
        center = centers[object_id]
        local_boxes = []
        for box in item["leafBodyOccupancyBoxes"]:
            raw = box["installationBoundsMeters"]
            local_boxes.append({
                "id": box["id"],
                "bounds": [
                    raw["minU"] - center[0], raw["minV"] - center[1],
                    raw["maxU"] - center[0], raw["maxV"] - center[1],
                ],
                "heightRangeMeters": [raw["minN"], raw["maxN"]],
                "componentCode": box.get("memberCode", item["primaryCode"]),
            })
        semantics[name] = {
            "moduleType": module_type,
            "parameters": {"occupancyBoxesLocal": local_boxes, "provisional": True},
            "points": {},
            "regions": {},
        }
        components.append({
            "componentName": name,
            "filePath": occupancy["modules"][item["primaryCode"]].get("filePath"),
            "layoutObjectId": object_id,
            "memberCodes": item["memberCodes"],
            "layout2d": {"x": center[0], "y": center[1], "thetaDegrees": 0.0},
            "projectedFootprint": {
                "minU": bounds[0], "minV": bounds[1], "maxU": bounds[2], "maxV": bounds[3]
            },
            "constraintPlacement": {"rotationQuarters": 0},
            "interactionEnvelope": {"bounds": bounds, "heightRangeMeters": height},
            "hardBodyEnvelope": {"bounds": bounds, "heightRangeMeters": height},
        })

    for stable_id, object_id, u, v in target_rows:
        if object_id is None:
            name = object_names["transport-process-group"]
            center = centers["transport-process-group"]
        else:
            name = object_names[object_id]
            center = centers[object_id]
        semantics[name]["points"][stable_id] = {"u": u - center[0], "v": v - center[1]}

    scanner_name = object_names["scanner-module"]
    scan_station = (optical_geometry.get("scanner") or {}).get("scanStation") or {}
    for key in ("carrierBarcodeTargetProxyInstallationMeters", "productBarcodeTargetProxyInstallationMeters"):
        point = scan_station.get(key)
        if isinstance(point, dict):
            semantics[scanner_name]["points"][key] = {
                "u": float(point["u"]) - centers["scanner-module"][0],
                "v": float(point["v"]) - centers["scanner-module"][1],
            }
    ccd_name = object_names["product-ccd-module"]
    for item in (optical_geometry.get("ccd") or {}).get("workPositionOpticalTargets") or []:
        point = item["requiredOpticalOriginInstallationMeters"]
        semantics[ccd_name]["points"][str(item["id"])] = {
            "u": float(point["u"]) - centers["product-ccd-module"][0],
            "v": float(point["v"]) - centers["product-ccd-module"][1],
        }
    gantry_name = object_names["gantry-motion-group"]
    reach = valve_reach["commonPlanarReachInstallationMeters"]
    gantry_center = centers["gantry-motion-group"]
    semantics[gantry_name]["regions"]["dualValveReach"] = {
        "minU": float(reach["minU"]) - gantry_center[0],
        "minV": float(reach["minV"]) - gantry_center[1],
        "maxU": float(reach["maxU"]) - gantry_center[0],
        "maxV": float(reach["maxV"]) - gantry_center[1],
    }

    strict_name_pairs = [[object_names[a], object_names[b]] for a, b in strict_pairs]
    conditional_name_pairs = [
        [object_names[item["pair"][0]], object_names[item["pair"][1]]]
        for item in policy["conditionalBrepPairs"]
    ]
    installation_name_pairs = [
        [object_names[item["pair"][0]], object_names[item["pair"][1]]]
        for item in policy["installationContactPairs"]
    ]
    solutions = []
    for rank, candidate in enumerate(selected, 1):
        placements = []
        for object_id, item in objects.items():
            shift = candidate["shifts"].get(object_id, (0.0, 0.0))
            center = centers[object_id]
            placements.append({
                "componentName": object_names[object_id],
                "x": center[0] + shift[0],
                "y": center[1] + shift[1],
                "bounds": _shift_bounds(_bounds_union(item["occupancyBoxes"]), shift),
                "thetaDegrees": 0.0,
                "rotationQuarters": 0,
            })
        solutions.append({
            "rank": rank,
            "score": candidate["score"],
            "candidateRanks": [rank],
            "placements": placements,
            "gantryAnchorFeasibleShiftRegion": candidate["gantryAnchorFeasibleShiftRegion"],
            "conditionalBroadPhasePairCount": candidate["conditionalBroadPhasePairCount"],
            "minimumServiceCenterSpacingMeters": candidate["minimumServiceCenterSpacingMeters"],
            "movedObjectIds": [
                object_id for object_id in (*service_ids, "gantry-motion-group")
                if candidate["shifts"][object_id] != (0.0, 0.0)
            ],
        })

    validation = {
        "hardFeasible": True,
        "constraintCount": 3,
        "passedCount": 3,
        "diagnostics": [
            {"id": "project05-operation-strip", "type": "operationSideStrip", "success": True, "hard": True, "message": "G000/N000/P000位于操作侧服务带"},
            {"id": "project05-strict-leaf-aabb", "type": "strictLeafAabb", "success": True, "hard": True, "message": "15组普通模组对通过膨胀叶实体AABB严格分离"},
            {"id": "project05-common-reach", "type": "inverseGantryReach", "success": True, "hard": True, "message": "8个工作/服务点存在双阀公共可达的龙门锚点交集"},
        ],
    }
    return {
        "schemaVersion": 1,
        "caseId": "project05",
        "prototypePoseUsedForSolving": True,
        "sourceCapturePoseUsedForAnchoring": True,
        "components": components,
        "constraintPlan": {
            "sourcePositionIndependent": False,
            "solverMode": "project05-prototype-calibrated-sequential-bounded-top-k",
            "longAxis": "u",
            "roles": roles,
            "moduleSemantics": semantics,
            "gantryComponentName": gantry_name,
            "minimumClearanceMeters": margin,
            "processValidation": validation,
            "spatialValidation": validation,
            "interactionValidation": validation,
            "reachValidation": {"hardFeasible": True, "diagnostics": validation["diagnostics"][2:]},
            "validation": {
                "productionReady": False,
                "overlapPairs": [],
                "conditionalInteractionReviewPairs": conditional_name_pairs,
            },
            "jointSearch": {
                "success": True,
                "solutionCount": len(solutions),
                "solutions": solutions,
                "exploredNodeCount": explored,
                "maximumSearchNodes": len(SERVICE_SHIFT_OPTIONS) ** 3,
                "candidateCounts": {object_id: len(SERVICE_SHIFT_OPTIONS) for object_id in service_ids},
                "acceptedCandidateCounts": {"joint": len(candidates)},
                "rejectionCounts": rejection_counts,
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
                "strictPairOccupancyMode": "complete-leaf-body-aabbs",
                "solverInvokesBrep": False,
            },
            "caseAnchor": {
                "componentName": object_names["transport-process-group"],
                "targetKind": "prototype-mate-installation-frame",
                "targetSource": "A000-D000 one coincident plane, one 312 mm distance and one width mate",
                "scope": "project05-only",
                "prototypeDerivedParameter": True,
                "sourceCapturePoseReadForAnchor": True,
            },
            "assumptionWarnings": [
                "项目05只使用自身原型与PPT证据，不继承项目01/02/03数值。",
                "D000/K000/F000/M000安装关系暂按项目05原型标定保留；这不是完全去原型求解。",
                "950L/800L公共行程、服务点和操作面侧只授权粗静态布局。",
                "候选选中后才允许Replay；13组条件B-rep和8组安装接触需在真实CAD中复核。",
            ],
            "project05Sequence": [
                "A000/E000 fixed context",
                "D000 transport installation",
                "K000 two work positions",
                "F000 scanner and M000 CCD optical alignment",
                "G000/N000/P000 operation-side service placement",
                "B000+Z000 inverse eight-target common reach coverage",
            ],
        },
    }
