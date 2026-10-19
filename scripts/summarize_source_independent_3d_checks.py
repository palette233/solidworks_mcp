"""Combine broad-phase and time-bounded SolidWorks checks for the new layout."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENING = ROOT / "demo" / "FL9A24D062A000_source_independent_3d_screening.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_source_independent_3d_check_summary.json"
CONFIRMED = ROOT / "demo" / "interference_source_independent_A100_T401.json"
SAVE_RESULT = ROOT / "demo" / "FL9A24D062A000_source_independent_explicit_save_result.json"


def main() -> None:
    screening = json.loads(SCREENING.read_text(encoding="utf-8"))
    confirmed = json.loads(CONFIRMED.read_text(encoding="utf-8"))
    save_result = json.loads(SAVE_RESULT.read_text(encoding="utf-8"))
    candidates = screening["candidatePairs"]
    timed_out_pair = ["FL9A24D062A180.001-1", "FL9A24D062A200.001-1"]
    result = {
        "success": False,
        "completed": False,
        "status": "PARTIAL_BREP_PENDING",
        "assemblyPath": screening["assemblyPath"],
        "explicitSaveResultPath": str(SAVE_RESULT),
        "explicitSaveSucceeded": save_result["Errors"] == 0,
        "explicitSaveResult": save_result,
        "solidWorksReplayPoseValidated": True,
        "componentCount": screening["componentCount"],
        "allTopLevelPairCount": screening["pairCount"],
        "provenSeparatedByPersistedSolidWorksWorldAabbCount": screening[
            "excludedBy3dAabbCount"
        ],
        "solidWorksPairToolConfirmedNoInterferenceCount": 1,
        "solidWorksPairToolConfirmed": {
            "components": ["FL9A24D062A100.001-1", "T401AA-07388-0-1"],
            "method": "world_aabb_broad_phase_short_circuit_inside_check_interference",
            "resultPath": str(CONFIRMED),
            "result": confirmed,
        },
        "exactBrepCandidateCount": len(candidates),
        "exactBrepCompletedCount": 0,
        "exactBrepTimedOutCount": 1,
        "exactBrepNotAttemptedCount": len(candidates) - 1,
        "timedOutChecks": [
            {
                "components": timed_out_pair,
                "timeoutSeconds": 180,
                "result": "no_result",
                "solidWorksLog": str(
                    ROOT
                    / "artifacts"
                    / "solidworks-mcp-aabb-preflight"
                    / "logs"
                    / "ZENGSHUANG_20260806_100559.txt"
                ),
            }
        ],
        "pendingExactBrepPairs": candidates,
        "detectedInterferenceCount": 0,
        "conclusion": (
            "No interference was detected in the completed checks, but the new assembly is not B-Rep-cleared: "
            "13 of 28 pairs are proven separated by actual saved-pose world AABBs; 15 pairs remain exact "
            "candidates, and the first exact check timed out after 180 seconds."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
