from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / "demo/semantic_ports"
BASE = SEMANTIC / "project03_ad20_context_rebased_dynamic_closure_v1.json"
ANGLE = 16
SNAPSHOT = SEMANTIC / "project03_ad20_context_rebased_16deg_snapshot_v1/project03_ad20_intermediate_snapshot_closure.json"
PARENT = SEMANTIC / "project03_ad20_context_rebased_16deg_ad10_parent_pilot_v1/project03_ad20_snapshot_ad10_parent_pilot.json"
FULL = SEMANTIC / "project03_ad00_full_context_left_context_rebased_16deg_v1"
CONSTRUCTION = FULL / "project03_full_context_left-context-rebased-16deg_closure.json"
DIAGNOSTIC = FULL / "project03_nested_total_transform_diagnostic_v1.json"
POSE = FULL / "project03_ad20_snapshot_pose_mapping_assessment_v1.json"
BREP = FULL / "project03_full_context_left-context-rebased-16deg_final_assessment_v1.json"
OUTPUT = SEMANTIC / "project03_ad20_context_rebased_dynamic_refinement_closure_v1.json"
PAIR_REFINEMENT = SEMANTIC / "project03_ad20_first_contact_pair_refinement_v4/project03_ad20_first_contact_pair_refinement.json"


def load(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    base = load(BASE)
    snapshot, parent, construction, diagnostic, pose, brep = map(
        load, (SNAPSHOT, PARENT, CONSTRUCTION, DIAGNOSTIC, POSE, BREP)
    )
    pair_refinement = load(PAIR_REFINEMENT)
    assessment = brep["baselineAssessment"]
    durations = {
        "snapshotSeconds": float(snapshot.get("durationSeconds") or 0.0),
        "parentPilotSeconds": float(parent.get("durationSeconds") or 0.0),
        "constructionSeconds": float(construction.get("durationSeconds") or 0.0),
        "diagnosticSeconds": float(diagnostic.get("durationSeconds") or 0.0),
        "brepSeconds": float(brep.get("durationSeconds") or 0.0),
    }
    durations["totalSeconds"] = sum(durations.values())
    state = {
        "angleDegrees": ANGLE,
        "passedNoNewInterferenceGate": bool(assessment.get("passed")),
        "poseMappingStatus": pose.get("status"),
        "capturedPoseCount": len(pose.get("comparisons") or []),
        "maximumTransformElementError": pose.get("maximumTransformElementError"),
        "exactCheckComplete": assessment.get("exactCheckComplete") is True,
        "failedBodyPairCount": int(assessment.get("failedBodyPairCount") or 0),
        "interferingBodyPairCount": int(assessment.get("actualInterferingBodyPairCount") or 0),
        "newLeafSourcePairs": assessment.get("newLeafSourcePairs") or [],
        "missingBaselineLeafSourcePairs": assessment.get("missingBaselineLeafSourcePairs") or [],
        "constructionStatus": construction.get("status"),
        "recoveredAndVerifiedAfterCleanRestart": True,
        "sourceFilesUnchanged": brep.get("sourceFilesUnchanged") is True,
        "durations": durations,
        "evidence": {
            "snapshot": str(SNAPSHOT),
            "parentPilot": str(PARENT),
            "construction": str(CONSTRUCTION),
            "diagnostic": str(DIAGNOSTIC),
            "pose": str(POSE),
            "brep": str(BREP),
        },
    }
    states = [row for row in base.get("states") or [] if int(row["angleDegrees"]) != ANGLE]
    states.append(state)
    states.sort(key=lambda row: float(row["angleDegrees"]))
    passed = [row["angleDegrees"] for row in states if row["passedNoNewInterferenceGate"]]
    rejected = [row["angleDegrees"] for row in states if not row["passedNoNewInterferenceGate"]]
    result = {
        **base,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "states": states,
        "verifiedSafeSampledAnglesDegrees": passed,
        "rejectedSampledAnglesDegrees": rejected,
        "firstObservedCollisionBracketDegrees": [15, 16],
        "refinementRequestedAnglesDegrees": [16, 17, 18, 19],
        "refinementExecutedAnglesDegrees": [16],
        "refinementSkippedAnglesDegrees": [17, 18, 19],
        "refinementStopReason": (
            "16 degrees already introduced the same new leaf-source interference pair seen at 20 degrees; "
            "higher samples cannot widen the verified collision-free interval."
        ),
        "knownPairFirstContactRefinement": {
            "scope": pair_refinement.get("scope"),
            "lastObservedSafeAngleDegrees": pair_refinement.get(
                "lastObservedSafeAngleDegrees"
            ),
            "firstObservedCollisionAngleDegrees": pair_refinement.get(
                "firstObservedCollisionAngleDegrees"
            ),
            "firstObservedCollisionBracketDegrees": pair_refinement.get(
                "firstObservedCollisionBracketDegrees"
            ),
            "exactSampleCount": len(pair_refinement.get("samples") or []),
            "evidencePath": str(PAIR_REFINEMENT),
            "doesNotProveWholeMachineContinuousSafety": True,
        },
        "totalRecordedCadEvidenceSeconds": round(
            float(base.get("totalRecordedCadEvidenceSeconds") or 0.0)
            + durations["totalSeconds"]
            + float(pair_refinement.get("durationSeconds") or 0.0),
            6,
        ),
        "supersedes": str(BASE),
        "status": "FAILED_PROJECT03_AD20_FIRST_COLLISION_OBSERVED_BETWEEN_15_AND_16_DEGREES",
        "productionReady": False,
        "continuousPathVerified": False,
        "fullRequestedRangePassed": False,
    }
    result["problems"] = list(base.get("problems") or []) + [
        "The 16-degree state introduces the same AD20/electrical-part leaf interference first observed in the coarse 20-degree sample."
    ]
    result["blockers"] = list(base.get("blockers") or []) + [
        "The collision-free continuous limit is below 16 degrees; the exact first-contact angle remains unresolved inside (15,16]."
    ]
    result["blockers"][-1] = (
        "The known AD20002/electrical-part pair first contacts inside (15.5,15.6] degrees; "
        "other whole-machine pairs still lack continuous swept-volume proof."
    )
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
