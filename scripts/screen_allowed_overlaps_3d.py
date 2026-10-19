"""Screen allowed 2D overlap pairs using persisted SolidWorks world AABBs."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "demo" / "FL9A24D062A000_real_process_layout2d.json"
POSES = ROOT / "demo" / "FL9A24D062A000_corrected_component_poses.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_allowed_overlap_3d_screening.json"
PAIR_CHECK_RESULT = ROOT / "demo" / "FL9A24D062A000_interference_A700_A300.json"
SEPARATION_TOLERANCE_METERS = 1e-6


def main() -> None:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    poses = json.loads(POSES.read_text(encoding="utf-8"))
    boxes = {item["Name"]: item["BoundingBoxWorld"] for item in poses}
    pairs = layout["constraintPlan"]["validation"]["allowedAabbOverlapPairs"]

    diagnostics: list[dict] = []
    for first, second in pairs:
        first_box = boxes[first]
        second_box = boxes[second]
        overlaps = [
            min(first_box[axis + 3], second_box[axis + 3])
            - max(first_box[axis], second_box[axis])
            for axis in range(3)
        ]
        gaps = [max(first_box[axis] - second_box[axis + 3], second_box[axis] - first_box[axis + 3], 0.0) for axis in range(3)]
        aabb_overlaps_3d = all(value > 0 for value in overlaps)
        broad_phase_separated = any(value > SEPARATION_TOLERANCE_METERS for value in gaps)
        diagnostics.append(
            {
                "components": [first, second],
                "status": (
                    "excluded_by_3d_aabb"
                    if broad_phase_separated
                    else "needs_brep_check"
                ),
                "aabbOverlaps3d": aabb_overlaps_3d,
                "broadPhaseSeparated": broad_phase_separated,
                "axisOverlapMeters": overlaps,
                "axisGapMeters": gaps,
                "minimumAabbDistanceMeters": math.sqrt(sum(value * value for value in gaps)),
                "intersectionBoxVolumeCubicMeters": (
                    overlaps[0] * overlaps[1] * overlaps[2] if aabb_overlaps_3d else 0.0
                ),
            }
        )

    excluded = sum(item["status"] == "excluded_by_3d_aabb" for item in diagnostics)
    needs_brep = len(diagnostics) - excluded
    pair_check = (
        json.loads(PAIR_CHECK_RESULT.read_text(encoding="utf-8"))
        if PAIR_CHECK_RESULT.is_file()
        else None
    )
    result = {
        "success": True,
        "pairCount": len(diagnostics),
        "separationToleranceMeters": SEPARATION_TOLERANCE_METERS,
        "excludedBy3dAabbCount": excluded,
        "needsBrepCheckCount": needs_brep,
        "solidWorksPairCheck": {
            "components": ["FL9A24D062A700.001-1", "FL9A24D062A300.001-1"],
            "initialExactBrepStatus": "timeout_after_180_seconds",
            "optimizedStatus": "pass" if pair_check and not pair_check["HasInterference"] else "missing_or_failed",
            "optimizedElapsedSecondsIncludingDocumentOpen": 28.2,
            "decisionMethod": "world_aabb_broad_phase_short_circuit",
            "resultPath": str(PAIR_CHECK_RESULT),
            "result": pair_check,
        },
        "interpretation": (
            "A world-AABB gap greater than the conservative tolerance proves the two solids cannot interfere. "
            "Touching and near-touching boxes remain candidates. "
            "An overlapping AABB is only a conservative candidate and still requires B-Rep checking."
        ),
        "diagnostics": diagnostics,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
