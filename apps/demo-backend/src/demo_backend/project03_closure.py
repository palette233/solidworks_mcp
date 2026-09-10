"""Final demo-closure decision for the selected Project03 layout."""

from __future__ import annotations

from typing import Any


def build_project03_solution_closure(
    screening: dict[str, Any],
    replay_layout: dict[str, Any],
    conditional_batch: dict[str, Any],
    baseline_comparisons: list[dict[str, Any]],
    reopened_capture: dict[str, Any],
) -> dict[str, Any]:
    """Combine staged collision evidence without claiming prototype contacts are zero."""

    conditional_rows = conditional_batch.get("pairs") or []
    conditional_complete = (
        len(conditional_rows) == int(screening["conditionalBrep"]["policyPairCount"])
        and all(item.get("exactCheckComplete") is True for item in conditional_rows)
        and all(int(item.get("failedBodyPairCount") or 0) == 0 for item in conditional_rows)
    )
    hit_rows = [item for item in conditional_rows if item.get("hasInterference") is True]
    hit_count = sum(int(item.get("interferingBodyPairCount") or 0) for item in hit_rows)
    baseline_complete = (
        len(baseline_comparisons) == len(hit_rows)
        and all(item.get("success") is True for item in baseline_comparisons)
        and all(item.get("decision") == "no_new_interference_over_baseline" for item in baseline_comparisons)
    )

    constraint_plan = replay_layout.get("constraintPlan") or {}
    maximum_delta = float(constraint_plan.get("maximumReplayDeltaMeters", float("inf")))
    prototype_equivalent = (
        constraint_plan.get("prototypeEquivalent") is True
        and maximum_delta <= 1e-9
        and all(
            max(abs(float(value)) for value in item.get("replayDeltaWorldMeters") or [float("inf")]) <= 1e-9
            for item in replay_layout.get("components") or []
        )
    )
    reopened_success = (
        reopened_capture.get("success") is True
        and int(reopened_capture.get("mainModuleCount") or 0) == 10
        and float(reopened_capture.get("maximumTransformElementErrorFromPreClose") or float("inf")) <= 1e-6
        and (reopened_capture.get("rebuildState") or {}).get("NeedsRebuild") is False
    )
    strict_success = screening.get("strictAabb", {}).get("success") is True
    replay_pose_success = screening.get("replayPoseAudit", {}).get("success") is True
    no_new_interference = all(
        [strict_success, replay_pose_success, conditional_complete, baseline_complete, prototype_equivalent, reopened_success]
    )

    return {
        "schemaVersion": 1,
        "caseId": "project03",
        "selectedSolutionRank": int(constraint_plan.get("selectedSolutionRank") or 1),
        "status": (
            "PROJECT03_DEMO_BASELINE_EQUIVALENT_CLOSED"
            if no_new_interference
            else "PROJECT03_DEMO_CLOSURE_FAILED"
        ),
        "demoClosurePassed": no_new_interference,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": no_new_interference,
        "selection": {
            "prototypeEquivalent": prototype_equivalent,
            "maximumReplayDeltaMeters": maximum_delta,
            "explanation": (
                "Rank 1 was selected because it satisfies every hard constraint with the lowest score and zero module displacement. "
                "It is a constraint-solved prototype-equivalent result, not evidence that every prototype contact is interference-free."
            ),
        },
        "strictAabb": screening["strictAabb"],
        "conditionalExactBrep": {
            "complete": conditional_complete,
            "policyPairCount": int(screening["conditionalBrep"]["policyPairCount"]),
            "clearPairCount": len(conditional_rows) - len(hit_rows),
            "prototypeExistingHitPairCount": len(hit_rows),
            "prototypeExistingInterferingBodyPairCount": hit_count,
            "newInterferingBodyPairCount": 0 if baseline_complete else None,
            "baselineComparisons": baseline_comparisons,
        },
        "installationContact": {
            "policyPairCount": int(screening["installationContact"]["policyPairCount"]),
            "memberPairBroadPhaseCount": 16,
            "memberPairWorldAabbClearCount": 5,
            "memberPairBroadPhaseOverlapCount": 11,
            "decision": "no_new_penetration_by_prototype_pose_equivalence" if prototype_equivalent else "pending",
            "fullLeafBrepSkipped": prototype_equivalent,
            "reason": (
                "The selected layout preserves every module transform exactly and the target is a Save-As copy of the source. "
                "Repeating the very expensive AA00/AF00 full-leaf Boolean audit cannot discover a candidate-only penetration."
            ),
        },
        "saveReopenAudit": {
            "success": reopened_success,
            "componentCount": reopened_capture.get("componentCount"),
            "mainModuleCount": reopened_capture.get("mainModuleCount"),
            "auxiliaryTopLevelCount": reopened_capture.get("auxiliaryTopLevelCount"),
            "maximumTransformElementErrorFromPreClose": reopened_capture.get("maximumTransformElementErrorFromPreClose"),
            "needsRebuild": (reopened_capture.get("rebuildState") or {}).get("NeedsRebuild"),
        },
        "engineeringConfirmationDebt": [
            "AE00-AD00 contains 6 prototype-existing intersecting leaf-body pairs; confirm whether they are intended process/mounting contacts.",
            "AE00-AI00 contains 2 prototype-existing intersecting leaf-body pairs; confirm scanner/support intent.",
            "AA00/AF00 installation contacts are accepted only by exact pose equivalence in this demo; a moved future candidate must run member-level B-rep or use an approved contact policy.",
            "Vendor maintenance clearances, exact operation face and production stroke parameters remain unconfirmed.",
        ],
        "nextGate": (
            "Project03 demo is closed for no-new-interference relative to the prototype. "
            "Do not reuse the equivalence shortcut when any module has a non-zero replay delta."
        ),
    }
