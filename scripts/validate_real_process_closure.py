from __future__ import annotations

import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
LAYOUT = WORKSPACE / "demo" / "FL9A24D062A000_real_process_layout2d.json"
STATE = WORKSPACE / "demo" / "demo_state_real_process.json"
ASSEMBLY = WORKSPACE / "demo" / "FL9A24D062A000_8components_real_process_corrected.SLDASM"
SCREENSHOT = WORKSPACE / "demo" / "apply_captured_layout_result.png"
EVALUATION = WORKSPACE / "demo" / "FL9A24D062A000_corrected_layout_evaluation.json"
POSE_VALIDATION = WORKSPACE / "demo" / "FL9A24D062A000_corrected_pose_validation.json"
INTERFERENCE_SCREENING = (
    WORKSPACE / "demo" / "FL9A24D062A000_allowed_overlap_3d_screening.json"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    require(LAYOUT.is_file(), f"missing layout: {LAYOUT}")
    require(STATE.is_file(), f"missing replay state: {STATE}")
    require(ASSEMBLY.is_file(), f"missing replay assembly: {ASSEMBLY}")
    require(SCREENSHOT.is_file(), f"missing replay screenshot: {SCREENSHOT}")
    require(EVALUATION.is_file(), f"missing correction evaluation: {EVALUATION}")
    require(POSE_VALIDATION.is_file(), f"missing saved pose validation: {POSE_VALIDATION}")
    require(
        INTERFERENCE_SCREENING.is_file(),
        f"missing 3D interference screening: {INTERFERENCE_SCREENING}",
    )

    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    plan = layout["constraintPlan"]
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    pose_validation = json.loads(POSE_VALIDATION.read_text(encoding="utf-8"))
    interference_screening = json.loads(INTERFERENCE_SCREENING.read_text(encoding="utf-8"))
    semantics = plan["moduleSemantics"]
    process = plan["processValidation"]
    spatial = plan["spatialValidation"]
    reach = plan["reachValidation"]

    require(layout["success"], "constraint layout is not successful")
    require(len(layout["components"]) == 8, "layout must contain eight real CAD components")
    require(plan["provisionalPlaceholderCount"] == 0, "geometry placeholder is still present")
    require(semantics["FL9A24D062A180.001-1"]["moduleType"] == "scanner", "A180 is not scanner")
    require(
        semantics["FL9A24D062A700.001-1"]["parameters"].get("combinedFunctions")
        == ["cleaning", "weighing"],
        "A700 is not marked as the cleaning+weighing composite",
    )
    require(process["hardFeasible"], "process hard constraints are not feasible")
    require(process["passedCount"] == process["constraintCount"] == 13, "expected 13/13 process constraints")
    require(spatial["hardFeasible"], "spatial hard constraints are not feasible")
    require(spatial["passedCount"] == spatial["constraintCount"] == 6, "expected 6/6 spatial constraints")
    require(reach["hardFeasible"], "valve reach is not contained in the gantry")
    require(reach["diagnostics"][0]["overlapRatio"] == 1.0, "expected 100% reach containment")
    require(plan["containmentRelaxedComponents"] == [], "containment relaxation is still present")
    require(not plan["validation"]["productionReady"], "coarse semantic estimates must not be production-ready")
    require(evaluation["correctedAssemblyExists"], "corrected SolidWorks assembly was not saved")
    require(evaluation["solidWorksScreenshotExists"], "corrected SolidWorks screenshot is missing")
    require(
        evaluation["maxCorrectedTargetToPrototypeDistanceMeters"] == 0.0,
        "corrected target does not preserve the hard-feasible prototype layout",
    )
    require(
        evaluation["maxCorrectedSavedToPrototypeDistanceMeters"] <= 1e-9,
        "saved corrected assembly does not preserve the prototype-relative layout",
    )
    require(
        evaluation["solidWorksReplayEvidence"]["savedFileReopenedAsActiveDocument"],
        "saved corrected assembly was not reopened successfully",
    )
    require(pose_validation["success"], "saved SolidWorks pose validation failed")
    require(pose_validation["capturedPoseCount"] == 8, "expected eight saved component poses")
    require(pose_validation["capturedBottomProbeCount"] == 8, "expected eight saved bottom probes")
    require(
        evaluation["solidWorksReplayEvidence"]["coordinateRecaptureStatus"] == "pass",
        "evaluation did not record saved-coordinate recapture as passed",
    )
    require(interference_screening["success"], "3D AABB interference screening failed")
    require(interference_screening["pairCount"] == 12, "expected twelve allowed overlap pairs")
    require(
        interference_screening["excludedBy3dAabbCount"]
        + interference_screening["needsBrepCheckCount"]
        == interference_screening["pairCount"],
        "3D screening pair accounting is inconsistent",
    )

    print(
        json.dumps(
            {
                "result": "PASS_WITH_BREP_INTERFERENCE_PENDING",
                "realCadComponentCount": len(layout["components"]),
                "processConstraints": f"{process['passedCount']}/{process['constraintCount']}",
                "spatialConstraints": f"{spatial['passedCount']}/{spatial['constraintCount']}",
                "reachInsideGantryRatio": reach["diagnostics"][0]["overlapRatio"],
                "provisionalPlaceholderCount": plan["provisionalPlaceholderCount"],
                "productionReady": plan["validation"]["productionReady"],
                "maxOldPrototypeRelativeErrorMeters": evaluation["maxOldToPrototypeDistanceMeters"],
                "maxCorrectedTargetPrototypeRelativeErrorMeters": evaluation[
                    "maxCorrectedTargetToPrototypeDistanceMeters"
                ],
                "maxCorrectedSavedPrototypeRelativeErrorMeters": evaluation[
                    "maxCorrectedSavedToPrototypeDistanceMeters"
                ],
                "coordinateRecaptureStatus": evaluation["solidWorksReplayEvidence"][
                    "coordinateRecaptureStatus"
                ],
                "maxSavedTranslationErrorMeters": pose_validation["maxTranslationErrorMeters"],
                "maxSavedRotationErrorDegrees": pose_validation["maxRotationErrorDegrees"],
                "maxSavedBottomPlaneErrorMeters": pose_validation["maxBottomPlaneErrorMeters"],
                "minimumSavedBottomNormalDot": pose_validation["minimumBottomNormalDot"],
                "aabbExcludedPairs": interference_screening["excludedBy3dAabbCount"],
                "brepPendingPairs": interference_screening["needsBrepCheckCount"],
                "assembly": str(ASSEMBLY),
                "screenshot": str(SCREENSHOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
