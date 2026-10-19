#!/usr/bin/env python3
"""Aggregate Project03 AD20 context-rebased 0..25 degree CAD evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / "demo" / "semantic_ports"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def operation_seconds(document: dict) -> float:
    return sum(float(row.get("durationSeconds") or 0.0) for row in document.get("operations", []))


def state_paths(angle: int) -> dict[str, Path]:
    if angle == 0:
        full_dir = SEMANTIC / "project03_ad00_full_context_both_context_rebased_0deg_v1"
        return {
            "snapshot": SEMANTIC / "project03_ad20_context_rebased_0deg_snapshot_v1/project03_ad20_intermediate_snapshot_closure.json",
            "parentPilot": SEMANTIC / "project03_ad20_context_rebased_0deg_ad10_parent_pilot_v1/project03_ad20_snapshot_ad10_parent_pilot.json",
            "construction": full_dir / "project03_full_context_both-context-rebased-0deg_closure.json",
            "diagnostic": full_dir / "project03_nested_total_transform_diagnostic_v3.json",
            "pose": full_dir / "project03_ad20_snapshot_pose_mapping_assessment_v3.json",
            "brep": full_dir / "project03_full_context_both-context-rebased-0deg_final_assessment_v1.json",
        }
    full_dir = SEMANTIC / f"project03_ad00_full_context_left_context_rebased_{angle}deg_v1"
    return {
        "snapshot": SEMANTIC / f"project03_ad20_context_rebased_{angle}deg_snapshot_v1/project03_ad20_intermediate_snapshot_closure.json",
        "parentPilot": SEMANTIC / f"project03_ad20_context_rebased_{angle}deg_ad10_parent_pilot_v1/project03_ad20_snapshot_ad10_parent_pilot.json",
        "construction": full_dir / f"project03_full_context_left-context-rebased-{angle}deg_closure.json",
        "diagnostic": full_dir / "project03_nested_total_transform_diagnostic_v1.json",
        "pose": full_dir / "project03_ad20_snapshot_pose_mapping_assessment_v1.json",
        "brep": full_dir / f"project03_full_context_left-context-rebased-{angle}deg_final_assessment_v1.json",
    }


def main() -> int:
    angles = [0, 5, 10, 15, 20, 25]
    states = []
    total_seconds = 0.0
    for angle in angles:
        paths = state_paths(angle)
        missing = [str(path) for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing evidence for {angle} degrees: {missing}")
        docs = {name: load(path) for name, path in paths.items()}
        pose = docs["pose"]
        brep = docs["brep"]
        assessment = brep["baselineAssessment"]
        exact = brep["exactInterference"]
        no_new = not assessment.get("newLeafSourcePairs")
        state_passed = (
            pose.get("status") == "PASSED_AD20_SNAPSHOT_POSE_MAPPING"
            and bool(exact.get("ExactCheckComplete"))
            and int(exact.get("FailedBodyPairCount", -1)) == 0
            and no_new
            and bool(brep.get("sourceFilesUnchanged"))
        )
        durations = {
            "snapshotSeconds": float(docs["snapshot"].get("durationSeconds") or 0.0),
            "parentPilotSeconds": float(docs["parentPilot"].get("durationSeconds") or 0.0),
            "constructionSeconds": float(docs["construction"].get("durationSeconds") or 0.0),
            "diagnosticSeconds": float(docs["diagnostic"].get("durationSeconds") or 0.0),
            "brepSeconds": float(brep.get("durationSeconds") or 0.0),
        }
        durations["totalSeconds"] = sum(durations.values())
        total_seconds += durations["totalSeconds"]
        states.append(
            {
                "angleDegrees": angle,
                "passedNoNewInterferenceGate": state_passed,
                "poseMappingStatus": pose.get("status"),
                "capturedPoseCount": pose.get("capturedDirectChildCount"),
                "maximumTransformElementError": pose.get("maximumTransformElementError"),
                "exactCheckComplete": exact.get("ExactCheckComplete"),
                "failedBodyPairCount": exact.get("FailedBodyPairCount"),
                "interferingBodyPairCount": exact.get("InterferingBodyPairCount"),
                "newLeafSourcePairs": assessment.get("newLeafSourcePairs", []),
                "missingBaselineLeafSourcePairs": assessment.get("missingBaselineLeafSourcePairs", []),
                "constructionStatus": docs["construction"].get("status"),
                "recoveredAndVerifiedAfterCleanRestart": docs["diagnostic"].get("status") == "PASSED_NESTED_TOTAL_TRANSFORM_DIAGNOSTIC",
                "sourceFilesUnchanged": brep.get("sourceFilesUnchanged"),
                "durations": durations,
                "evidence": {name: str(path) for name, path in paths.items()},
            }
        )

    passed_angles = [row["angleDegrees"] for row in states if row["passedNoNewInterferenceGate"]]
    rejected_angles = [row["angleDegrees"] for row in states if not row["passedNoNewInterferenceGate"]]
    result = {
        "schemaVersion": "project03-ad20-context-rebased-dynamic-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project03",
        "moduleId": "AD20",
        "authority": "full-context-zero-pose-plus-native-configuration-motion-delta",
        "engineeringConfirmed": False,
        "states": states,
        "verifiedSafeSampledAnglesDegrees": passed_angles,
        "rejectedSampledAnglesDegrees": rejected_angles,
        "firstObservedCollisionBracketDegrees": [15, 20],
        "continuousPathVerified": False,
        "fullRequestedRangePassed": not rejected_angles,
        "productionReady": False,
        "totalRecordedCadEvidenceSeconds": round(total_seconds, 6),
        "supersedes": str(SEMANTIC / "project03_ad00_three_state_full_context_closure_v1.json"),
        "status": (
            "PASSED_PROJECT03_AD20_CONTEXT_REBASED_FULL_RANGE"
            if not rejected_angles
            else "FAILED_PROJECT03_AD20_CONTEXT_REBASED_FULL_RANGE_COLLISION_AT_20_AND_25_DEGREES"
        ),
        "problems": [
            "The previous flexible three-state evidence did not preserve the commanded nested leaf poses.",
            "Immediate close/reopen inside the construction session is unstable; each state was recovered and independently verified in a clean session.",
            "The 20- and 25-degree states introduce new exact leaf-body interference pairs.",
        ],
        "blockers": [
            "The requested 0-to-25-degree dynamic range is not collision-free under the current inferred motion.",
            "Continuous swept-volume safety between discrete samples is not proven.",
            "Vendor-authoritative pivot, hard stops, speed, clearance, and allowed-contact classification remain unavailable.",
        ],
    }
    output = SEMANTIC / "project03_ad20_context_rebased_dynamic_closure_v1.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if result["fullRequestedRangePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
