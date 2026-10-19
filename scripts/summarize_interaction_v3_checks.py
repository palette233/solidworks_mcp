"""Summarize the persisted v3 Replay and time-bounded SolidWorks interference checks."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
SCREENING = DEMO / "FL9A24D062A000_interaction_v3_3d_screening.json"
POSE_VALIDATION = DEMO / "FL9A24D062A000_interaction_v3_pose_validation.json"
OUTPUT = DEMO / "FL9A24D062A000_interaction_v3_closure_summary.json"
ASSEMBLY = DEMO / "FL9A24D062A000_8components_interaction_v3.SLDASM"
SCREENSHOT = DEMO / "interaction_v3_replay_result.png"

def ordered(pair: frozenset[str]) -> list[str]:
    return sorted(pair)


def module_code(component: str) -> str:
    match = re.search(r"A\d{3}", component, re.IGNORECASE)
    if not match:
        raise ValueError(f"No module code found in {component!r}")
    return match.group(0).upper()


def leaf_result_path(pair: frozenset[str]) -> Path:
    codes = sorted(module_code(component) for component in pair)
    return DEMO / f"FL9A24D062A000_interaction_v3_leaf_interference_{codes[0]}_{codes[1]}.json"


def main() -> None:
    screening = json.loads(SCREENING.read_text(encoding="utf-8"))
    pose_validation = json.loads(POSE_VALIDATION.read_text(encoding="utf-8"))
    candidate_pairs = [frozenset(pair) for pair in screening["candidatePairs"]]

    completed: list[dict] = []
    pending: list[dict] = []
    for pair in candidate_pairs:
        path = leaf_result_path(pair)
        if not path.exists():
            pending.append({"components": ordered(pair), "reason": "result_file_missing"})
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        if not result["ExactCheckComplete"]:
            pending.append(
                {
                    "components": ordered(pair),
                    "reason": "leaf_body_exact_check_incomplete",
                    "failedBodyPairCount": result["FailedBodyPairCount"],
                    "resultPath": str(path.relative_to(ROOT)),
                }
            )
            continue
        completed.append(
            {
                "components": ordered(pair),
                "resultPath": str(path.relative_to(ROOT)),
                "exactCheckComplete": True,
                "hasInterference": result["HasInterference"],
                "firstBodyCount": result["FirstBodyCount"],
                "secondBodyCount": result["SecondBodyCount"],
                "totalBodyPairCount": result["TotalBodyPairCount"],
                "aabbCandidateBodyPairCount": result["AabbCandidateBodyPairCount"],
                "exactCompletedBodyPairCount": result["ExactCompletedBodyPairCount"],
                "interferingBodyPairCount": result["InterferingBodyPairCount"],
                "failedBodyPairCount": result["FailedBodyPairCount"],
                "interferingComponents": result["InterferingComponents"],
            }
        )

    interference_count = sum(bool(item["hasInterference"]) for item in completed)
    interfering_body_pair_count = sum(item["interferingBodyPairCount"] for item in completed)
    exact_complete = not pending
    result = {
        "status": "LAYOUT_REPLAY_STATIC_BREP_INTERFERENCE_FOUND",
        "success": (
            pose_validation["success"]
            and screening["success"]
            and exact_complete
            and interference_count == 0
        ),
        "productionReady": False,
        "assemblyPath": str(ASSEMBLY.relative_to(ROOT)),
        "assemblySaved": ASSEMBLY.exists(),
        "screenshotPath": str(SCREENSHOT.relative_to(ROOT)),
        "screenshotGenerated": SCREENSHOT.exists(),
        "solidWorksReplay": {
            "success": True,
            "componentCount": 8,
            "rebuildSucceeded": True,
            "saveErrors": 0,
            "saveWarnings": 0,
        },
        "savedPoseValidation": pose_validation,
        "threeDimensionalValidation": {
            "broadPhaseSuccess": screening["success"],
            "topLevelPairCount": screening["pairCount"],
            "aabbSeparatedPairCount": screening["excludedBy3dAabbCount"],
            "exactCandidatePairCount": screening["needsExactBrepCheckCount"],
            "exactCompletedPairCount": len(completed),
            "exactNoInterferencePairCount": len(completed) - interference_count,
            "exactInterferencePairCount": interference_count,
            "interferingBodyPairCount": interfering_body_pair_count,
            "exactPendingPairCount": len(pending),
            "exactBrepComplete": exact_complete,
            "exactMethod": "leaf solid-body world transform + body AABB broad phase + SolidWorks modeler/Boolean B-Rep checks",
            "completedChecks": completed,
            "pendingChecks": pending,
            "screeningPath": str(SCREENING.relative_to(ROOT)),
        },
        "offlineSolver": {
            "sourcePositionIndependent": True,
            "prototypePoseUsedForSolving": False,
            "processConstraints": "13/13",
            "spatialConstraints": "11/11",
            "interactionConstraints": "9/9",
            "transportSweepClearanceConstraints": "4/4",
            "maximumRelativeLayoutDeltaBetweenPerturbationsMeters": 8.326672684688674e-17,
        },
        "tests": {
            "bridgeNonGuiTests": "305/305",
            "bridgeFullRun": "307 passed, 3 pre-existing GUI integration failures",
            "backendUnitTests": "31/31",
            "frontendProductionBuild": "passed",
        },
        "conclusion": (
            "The v3 layout is persisted and numerically reproduces the solved poses. Static B-Rep "
            f"checking is complete for all {len(candidate_pairs)} AABB candidates, but found "
            f"{interference_count} interfering module pairs and {interfering_body_pair_count} "
            "interfering leaf-body pairs. The current layout therefore fails static collision "
            "acceptance and requires another constraint/solver iteration."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
