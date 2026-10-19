"""Summarize the corrected source-independent Replay closure."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
REPLAY = DEMO / "FL9A24D062A000_source_independent_corrected_replay_result.json"
POSE_VALIDATION = DEMO / "FL9A24D062A000_source_independent_corrected_pose_validation.json"
SCREENING = DEMO / "FL9A24D062A000_source_independent_corrected_3d_screening.json"
SOURCE_INDEPENDENT = DEMO / "FL9A24D062A000_source_independent_validation.json"
OUTPUT = DEMO / "FL9A24D062A000_source_independent_corrected_closure_summary.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    replay = read_json(REPLAY)
    poses = read_json(POSE_VALIDATION)
    screening = read_json(SCREENING)
    independent = read_json(SOURCE_INDEPENDENT)

    save_result = replay.get("saveResult", {})
    separations = screening["requiredTransportSeparationValidation"]
    spatial = screening["actualSpatialValidation"]
    targeted_closed = all(
        (
            replay.get("success") is True,
            save_result.get("errors") == 0,
            save_result.get("warnings") == 0,
            poses.get("success") is True,
            screening.get("success") is True,
            separations.get("success") is True,
            spatial.get("success") is True,
            independent.get("success") is True,
        )
    )

    result = {
        "success": targeted_closed,
        "completed": targeted_closed,
        "status": (
            "TARGETED_LAYOUT_FIXES_CLOSED_BREP_PENDING"
            if targeted_closed
            else "TARGETED_LAYOUT_FIXES_FAILED"
        ),
        "assemblyPath": screening["assemblyPath"],
        "targetedDefectsClosed": {
            "scannerOrientation": poses["maxFullOrientationErrorDegrees"] == 0.0,
            "allComponentFullOrientations": poses["maxFullOrientationErrorDegrees"] == 0.0,
            "calibrationTransportContact": separations["diagnostics"][0]["success"],
            "cleaningWeighingTransportContact": separations["diagnostics"][1]["success"],
            "glueDrainTransportContact": separations["diagnostics"][2]["success"],
            "functionalGantryCoverage": spatial["success"],
        },
        "savedReplay": {
            "saveErrors": save_result.get("errors"),
            "saveWarnings": save_result.get("warnings"),
            "rebuildSucceeded": replay.get("rebuild", {}).get("rebuildSucceeded"),
        },
        "savedPoseValidation": {
            "componentCount": poses["componentCount"],
            "maxTranslationErrorMeters": poses["maxTranslationErrorMeters"],
            "maxRotationErrorDegrees": poses["maxRotationErrorDegrees"],
            "maxFullOrientationErrorDegrees": poses["maxFullOrientationErrorDegrees"],
            "maxBottomPlaneErrorMeters": poses["maxBottomPlaneErrorMeters"],
            "minimumBottomNormalAlignment": poses["minimumBottomNormalAlignment"],
        },
        "transportClearances": separations["diagnostics"],
        "actualGantryCoverage": spatial["diagnostics"],
        "sourceIndependentValidation": {
            "maxRelativeLayoutDeltaBetweenPerturbationsMeters": independent[
                "maxRelativeLayoutDeltaBetweenPerturbationsMeters"
            ],
            "processConstraints": independent["processConstraints"],
            "spatialConstraints": independent["spatialConstraints"],
            "unallowedOverlapCount": independent["unallowedOverlapPairCount"],
            "containmentRelaxationCount": len(
                independent["containmentRelaxedComponents"]
            ),
        },
        "fullAssemblyExactBrepCleared": False,
        "remainingExactBrepCandidateCount": screening["needsExactBrepCheckCount"],
        "remainingExactBrepCandidatePairs": screening["candidatePairs"],
        "productionReady": False,
        "limitations": [
            "The three reported transport-contact defects are proven separated by saved-pose world AABBs.",
            "Thirteen other conservative AABB candidates still require exact B-Rep/minimum-clearance checks.",
            "Provisional service points, valve reach and optical parameters still require project measurements.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
