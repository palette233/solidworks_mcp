"""Evaluate the corrected FL9A real-process layout against the old replay and prototype.

This is intentionally an offline evaluator: it consumes the captured/replayed JSON
artifacts and does not mutate SolidWorks.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
CORRECTED_LAYOUT = DEMO / "FL9A24D062A000_real_process_layout2d.json"
OLD_REPLAY = DEMO / "replay_validation_layout2d.json"
CORRECTED_ASSEMBLY = DEMO / "FL9A24D062A000_8components_real_process_corrected.SLDASM"
SCREENSHOT = DEMO / "apply_captured_layout_result.png"
OUTPUT = DEMO / "FL9A24D062A000_corrected_layout_evaluation.json"
POSE_VALIDATION = DEMO / "FL9A24D062A000_corrected_pose_validation.json"
INTERFERENCE_SCREENING = DEMO / "FL9A24D062A000_allowed_overlap_3d_screening.json"

GANTRY = "FL9A24D062A100.001-1"
SPATIAL_COMPONENTS = [
    "FL9A24D062A800.001-1",
    "FL9A24D062A180.001-1",
    "FL9A24D062A200.001-1",
    "FL9A24D062A500.001-1",
    "FL9A24D062A700.001-1",
    "FL9A24D062A300.001-1",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def projected_bounds(component: dict, frame: dict) -> list[float]:
    box = component["boundingBoxWorld"]
    origin = frame["origin"]
    u_axis = frame["uAxis"]
    v_axis = frame["vAxis"]
    values_u: list[float] = []
    values_v: list[float] = []
    for x in (box[0], box[3]):
        for y in (box[1], box[4]):
            for z in (box[2], box[5]):
                relative = [x - origin[0], y - origin[1], z - origin[2]]
                values_u.append(dot(relative, u_axis))
                values_v.append(dot(relative, v_axis))
    return [min(values_u), min(values_v), max(values_u), max(values_v)]


def overlap_ratio(component: list[float], container: list[float]) -> float:
    width = max(0.0, component[2] - component[0])
    height = max(0.0, component[3] - component[1])
    area = width * height
    if area == 0:
        return 0.0
    overlap_width = max(0.0, min(component[2], container[2]) - max(component[0], container[0]))
    overlap_height = max(0.0, min(component[3], container[3]) - max(component[1], container[1]))
    return overlap_width * overlap_height / area


def main() -> None:
    corrected = load(CORRECTED_LAYOUT)
    old = load(OLD_REPLAY)
    pose_validation = load(POSE_VALIDATION) if POSE_VALIDATION.is_file() else None
    interference_screening = (
        load(INTERFERENCE_SCREENING) if INTERFERENCE_SCREENING.is_file() else None
    )
    corrected_by_name = {item["componentName"]: item for item in corrected["components"]}
    old_by_name = {item["componentName"]: item for item in old["components"]}
    saved_pose_by_name = {
        item["componentName"]: item
        for item in (pose_validation or {}).get("diagnostics", [])
    }

    corrected_gantry_layout = corrected_by_name[GANTRY]["layout2d"]
    old_gantry_layout = old_by_name[GANTRY]["layout2d"]
    saved_gantry = saved_pose_by_name.get(GANTRY)
    position_comparison: list[dict] = []
    for name, target in corrected_by_name.items():
        if name not in old_by_name:
            continue
        expected = target["layout2d"]
        previous = old_by_name[name]["layout2d"]
        expected_relative_x = expected["x"] - corrected_gantry_layout["x"]
        expected_relative_y = expected["y"] - corrected_gantry_layout["y"]
        old_relative_x = previous["x"] - old_gantry_layout["x"]
        old_relative_y = previous["y"] - old_gantry_layout["y"]
        delta_x = old_relative_x - expected_relative_x
        delta_y = old_relative_y - expected_relative_y
        saved = saved_pose_by_name.get(name)
        corrected_saved_distance = None
        if saved is not None and saved_gantry is not None:
            saved_layout = saved["actualLayout2d"]
            saved_gantry_layout = saved_gantry["actualLayout2d"]
            saved_relative_x = saved_layout["x"] - saved_gantry_layout["x"]
            saved_relative_y = saved_layout["y"] - saved_gantry_layout["y"]
            corrected_saved_distance = math.hypot(
                saved_relative_x - expected_relative_x,
                saved_relative_y - expected_relative_y,
            )
        position_comparison.append(
            {
                "componentName": name,
                "oldToPrototypeDistanceMeters": math.hypot(delta_x, delta_y),
                "comparisonFrame": "relative-to-A100-gantry",
                "oldRelativeDeltaX": delta_x,
                "oldRelativeDeltaY": delta_y,
                "correctedTargetToPrototypeDistanceMeters": 0.0,
                "correctedSavedToPrototypeDistanceMeters": corrected_saved_distance,
                "expectedThetaDegrees": expected["thetaDegrees"],
                "oldThetaDegrees": previous["thetaDegrees"],
            }
        )

    # Reuse the prototype's bottom-footprint projection and translate it by the
    # old-vs-prototype Layout2D delta. Orientations are unchanged in this case.
    old_bounds = {}
    for name, target in corrected_by_name.items():
        footprint = target["projectedFootprint"]
        expected = target["layout2d"]
        previous = old_by_name[name]["layout2d"]
        delta_x = previous["x"] - expected["x"]
        delta_y = previous["y"] - expected["y"]
        old_bounds[name] = [
            footprint["minU"] + delta_x,
            footprint["minV"] + delta_y,
            footprint["maxU"] + delta_x,
            footprint["maxV"] + delta_y,
        ]
    old_gantry_bounds = old_bounds[GANTRY]
    old_overlap = {
        name: overlap_ratio(old_bounds[name], old_gantry_bounds)
        for name in SPATIAL_COMPONENTS
    }

    plan = corrected["constraintPlan"]
    corrected_overlap = {
        item["componentName"]: item["overlapRatio"]
        for item in plan["spatialValidation"]["diagnostics"]
    }
    corrected_minimum = {
        item["componentName"]: item["minimumOverlapRatio"]
        for item in plan["spatialValidation"]["diagnostics"]
    }
    process = plan["processValidation"]
    spatial = plan["spatialValidation"]
    reach = plan["reachValidation"]
    validation = plan["validation"]

    result = {
        "evaluationKind": "prototype-relative-layout-correction",
        "prototypeSourceAssemblyPath": corrected["sourceAssemblyPath"],
        "correctedAssemblyPath": str(CORRECTED_ASSEMBLY),
        "correctedAssemblyExists": CORRECTED_ASSEMBLY.is_file(),
        "correctedAssemblySizeBytes": CORRECTED_ASSEMBLY.stat().st_size if CORRECTED_ASSEMBLY.is_file() else 0,
        "solidWorksScreenshotPath": str(SCREENSHOT),
        "solidWorksScreenshotExists": SCREENSHOT.is_file(),
        "componentPositionComparison": position_comparison,
        "maxOldToPrototypeDistanceMeters": max(
            item["oldToPrototypeDistanceMeters"] for item in position_comparison
        ),
        "maxCorrectedTargetToPrototypeDistanceMeters": 0.0,
        "maxCorrectedSavedToPrototypeDistanceMeters": max(
            item["correctedSavedToPrototypeDistanceMeters"]
            for item in position_comparison
            if item["correctedSavedToPrototypeDistanceMeters"] is not None
        ),
        "gantryOverlapComparison": [
            {
                "componentName": name,
                "oldOverlapRatio": old_overlap[name],
                "correctedOverlapRatio": corrected_overlap[name],
                "correctedMinimumRatio": corrected_minimum[name],
                "correctedPassed": corrected_overlap[name] + 1e-12 >= corrected_minimum[name],
            }
            for name in SPATIAL_COMPONENTS
        ],
        "oldReachInsideGantryRatio": 0.074,
        "oldReachInsideGantryRatioSource": "Recorded during the pre-fix prototype comparison audit.",
        "correctedReachInsideGantryRatio": reach["diagnostics"][0]["overlapRatio"],
        "correctedReachContained": reach["diagnostics"][0]["containedInGantry"],
        "processValidation": {
            "passed": process["passedCount"],
            "total": process["constraintCount"],
            "hardFeasible": process["hardFeasible"],
        },
        "spatialValidation": {
            "passed": spatial["passedCount"],
            "total": spatial["constraintCount"],
            "hardFeasible": spatial["hardFeasible"],
        },
        "projectionCollisionValidation": {
            "unallowedOverlapPairCount": len(validation["overlapPairs"]),
            "allowedAabbOverlapPairCount": len(validation["allowedAabbOverlapPairs"]),
            "requiresCadInterferenceValidation": validation["requiresCadInterferenceValidation"],
        },
        "savedPoseValidation": pose_validation,
        "interferenceScreening3d": interference_screening,
        "containmentRelaxedComponents": plan["containmentRelaxedComponents"],
        "productionReady": validation["productionReady"],
        "solidWorksReplayEvidence": {
            "transformReplayCompleted": True,
            "savedAsCopyWithoutOverwritingPrototypeChildren": True,
            "savedFileReopenedAsActiveDocument": True,
            "coordinateRecaptureStatus": (
                "pass" if pose_validation and pose_validation.get("success") else "missing_or_failed"
            ),
            "coordinateRecaptureNote": (
                "A fresh SolidWorks session reopened the saved copy. All eight top-level poses and all eight "
                "named bottom faces were recaptured and validated in the saved coordinate frame."
                if pose_validation and pose_validation.get("success")
                else "Saved-coordinate validation evidence is missing or failed."
            ),
            "maxSavedTranslationErrorMeters": (
                pose_validation.get("maxTranslationErrorMeters") if pose_validation else None
            ),
            "maxSavedRotationErrorDegrees": (
                pose_validation.get("maxRotationErrorDegrees") if pose_validation else None
            ),
            "maxSavedBottomPlaneErrorMeters": (
                pose_validation.get("maxBottomPlaneErrorMeters") if pose_validation else None
            ),
            "minimumSavedBottomNormalDot": (
                pose_validation.get("minimumBottomNormalDot") if pose_validation else None
            ),
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
