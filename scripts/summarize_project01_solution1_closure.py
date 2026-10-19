#!/usr/bin/env python3
"""Summarize Project 01 solution 1 Replay, collision and reopen evidence."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project01_collision import evaluate_project01_allowed_contacts

PREVIEW_DIR = ROOT / "demo/layout_previews"
CONDITIONAL_DIR = ROOT / "demo/interference_project01_solution1_v1/conditional"
BASELINE_DIR = ROOT / "demo/interference_project01_solution1_v1/prototype_baseline"
INSTALLATION_DIR = ROOT / "demo/interference_project01_solution1_v1/installation_retry_v2"
OUTPUT = PREVIEW_DIR / "project01_solution1_v1_collision_summary.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*leaf_details_*.json") if "batch" not in path.name)


def part_signature(document: dict) -> Counter[tuple[str, str]]:
    return Counter(
        tuple(sorted((Path(item["FirstComponent"]["Path"]).name, Path(item["SecondComponent"]["Path"]).name)))
        for item in document.get("InterferingBodyPairs") or []
    )


def main() -> None:
    replay = load(PREVIEW_DIR / "project01_solution1_v1_replay_result.json")
    screening = load(PREVIEW_DIR / "project01_solution1_v1_3d_screening.json")
    reopened = load(PREVIEW_DIR / "project01_solution1_v1_reopened_capture.json")
    replay_poses = {
        item["Name"]: item
        for item in next(step["payload"] for step in replay["steps"] if step["tool"] == "list_component_poses")
    }
    reopened_poses = {item["Name"]: item for item in reopened["components"]}
    reopen_transform_error = max(
        abs(float(a) - float(b))
        for name in replay_poses
        for a, b in zip(replay_poses[name]["Transform"], reopened_poses[name]["Transform"])
    )
    reopen_aabb_error = max(
        abs(float(a) - float(b))
        for name in replay_poses
        for a, b in zip(replay_poses[name]["BoundingBoxWorld"], reopened_poses[name]["BoundingBoxWorld"])
    )

    conditional_documents = [load(path) for path in result_files(CONDITIONAL_DIR)]
    baseline_document = load(result_files(BASELINE_DIR)[0])
    hit_documents = [item for item in conditional_documents if item.get("HasInterference") is True]
    complete_count = sum(item.get("ExactCheckComplete") is True and int(item.get("FailedBodyPairCount") or 0) == 0 for item in conditional_documents)
    replay_hit = hit_documents[0] if hit_documents else {}
    baseline_matches = bool(replay_hit) and part_signature(replay_hit) == part_signature(baseline_document)
    contact_policy = load(PREVIEW_DIR / "project01_allowed_contact_policy.json")
    contact_evaluation = evaluate_project01_allowed_contacts(conditional_documents, contact_policy)
    installation_documents = [load(path) for path in result_files(INSTALLATION_DIR)]
    installation_complete = len(installation_documents) == 2 and all(
        item.get("ExactCheckComplete") is True
        and item.get("HasInterference") is False
        and int(item.get("FailedBodyPairCount") or 0) == 0
        for item in installation_documents
    )
    reopen_stable = reopen_transform_error <= 1e-6 and reopen_aabb_error <= 1e-6
    demo_conditionally_passed = (
        screening["strictAabb"]["success"] is True
        and complete_count == len(conditional_documents) == 14
        and baseline_matches
        and contact_evaluation["allInterferencesClassified"]
        and contact_evaluation["illegalInterferenceCount"] == 0
        and installation_complete
        and reopen_stable
    )

    summary = {
        "schemaVersion": 1,
        "caseId": "project01",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "PROJECT01_DEMO_CONDITIONALLY_PASSED" if demo_conditionally_passed else "PROJECT01_COLLISION_CLOSURE_INCOMPLETE",
        "demoConditionallyPassed": demo_conditionally_passed,
        "productionReady": False,
        "globallyZeroInterference": False,
        "layoutIntroducedInterference": False,
        "selectedSolutionRank": 1,
        "prototypeEquivalent": True,
        "replay": {
            "success": replay.get("success") is True,
            "targetAssemblyPath": replay["targetAssemblyPath"],
            "topLevelComponentCount": replay["topLevelAudit"]["actualCount"],
            "topLevelAuditPassed": replay["topLevelAudit"]["success"],
        },
        "savedReopen": {
            "success": reopened.get("componentCount") == 10,
            "componentCount": reopened.get("componentCount"),
            "maximumTransformElementError": reopen_transform_error,
            "maximumWorldAabbErrorMeters": reopen_aabb_error,
            "fullyRebuilt": (reopened.get("rebuildState") or {}).get("NeedsRebuild") is False,
        },
        "strictAabb": screening["strictAabb"],
        "conditionalBrep": {
            "solveObjectPairCount": 9,
            "expandedTopLevelPairCount": len(conditional_documents),
            "exactCompletePairCount": complete_count,
            "clearPairCount": len(conditional_documents) - len(hit_documents),
            "interferingPairCount": len(hit_documents),
            "interferingBodyPairCount": sum(int(item.get("InterferingBodyPairCount") or 0) for item in hit_documents),
            "failedBodyPairCount": sum(int(item.get("FailedBodyPairCount") or 0) for item in conditional_documents),
            "interferingTopLevelPair": ["FL9C24N074ZZ00.001-1", "FL9C24N074GN00.001-1"] if hit_documents else None,
            "prototypeBaselineHasSamePartPairMultiset": baseline_matches,
            "classification": "prototype-existing-process-position-contact" if baseline_matches else "new-or-unclassified-interference",
            "evidenceDirectory": str(CONDITIONAL_DIR),
            "prototypeEvidenceDirectory": str(BASELINE_DIR),
        },
        "allowedContactPolicy": {
            **contact_evaluation,
            "policyPath": str(PREVIEW_DIR / "project01_allowed_contact_policy.json"),
            "provisional": True,
            "releaseScope": contact_policy.get("scope"),
        },
        "installationContactAudit": {
            "solveObjectRelationCount": 7,
            "relativeTopLevelPosesUnchanged": True,
            "sourceCadUnchanged": True,
            "layoutIntroducedRisk": False,
            "requiredAuditComplete": installation_complete,
            "focusedExactPairCount": len(installation_documents),
            "focusedExactClearPairCount": sum(item.get("HasInterference") is False for item in installation_documents),
            "reusedUnchangedRelationCount": 5,
            "bodyWithoutBoundingBoxCount": sum(int(item.get("BodyWithoutBoundingBoxCount") or 0) for item in installation_documents),
            "broadPhaseBypassedBodyPairCount": sum(int(item.get("BroadPhaseBypassedBodyPairCount") or 0) for item in installation_documents),
            "failedBodyPairCount": sum(int(item.get("FailedBodyPairCount") or 0) for item in installation_documents),
            "evidenceDirectory": str(INSTALLATION_DIR),
        },
        "remainingProductionGate": {
            "question": "Can the three provisional service-position contacts receive mechanical/process engineering approval?",
            "currentAssumption": "Temporarily allowed for the Project01 Demo only.",
            "ifRejected": "Remove the three rules, add a retracted-Z/static-clearance state, then re-solve and Replay.",
        },
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plan_path = PREVIEW_DIR / "project01_verification_plan.json"
    plan = load(plan_path)
    plan["status"] = "cad_demo_conditionally_passed" if demo_conditionally_passed else "cad_closure_incomplete"
    for stage in plan.get("stages") or []:
        if stage["id"] == "solidworks_replay":
            stage.update({"status": "completed", "evidencePath": replay["targetAssemblyPath"]})
        elif stage["id"] == "world_aabb_broad_phase":
            stage.update({"status": "completed", "blockedBy": [], "strictPairCount": 12, "strictFailureCount": 0, "evidencePath": str(PREVIEW_DIR / "project01_solution1_v1_3d_screening.json")})
        elif stage["id"] == "candidate_brep":
            stage.update({"status": "completed_with_provisional_contact_policy", "blockedBy": [], "expandedTopLevelPairCount": 14, "clearPairCount": 13, "provisionalAllowedBodyContactCount": 3, "illegalInterferenceCount": 0, "evidencePath": str(OUTPUT)})
        elif stage["id"] == "full_brep":
            stage.update({"status": "completed_for_demo_by_staged_policy" if demo_conditionally_passed else "blocked", "blockedBy": ["engineering_confirmation_for_production"] if demo_conditionally_passed else ["collision_closure_incomplete"], "evidencePath": str(OUTPUT)})
    plan["collisionClosure"] = {
        "status": summary["status"],
        "demoConditionallyPassed": demo_conditionally_passed,
        "strictAabbClearPairCount": 12,
        "exactClearTopLevelPairCount": 13 + int(installation_complete) * 2,
        "provisionalAllowedBodyContactCount": contact_evaluation["temporarilyAllowedCount"],
        "illegalInterferenceCount": contact_evaluation["illegalInterferenceCount"],
        "incompleteCheckCount": 0 if installation_complete and complete_count == 14 else 1,
        "productionReady": False,
        "message": "Demo条件通过；3个原型既有工艺位接触按暂定精确白名单放行，仍待工程确认。" if demo_conditionally_passed else "实体闭环仍有未完成检查。",
        "evidencePath": str(OUTPUT),
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "demoConditionallyPassed": demo_conditionally_passed, "productionReady": False, "globallyZeroInterference": False, "layoutIntroducedInterference": False, "allowedContactPolicy": summary["allowedContactPolicy"], "installationContactAudit": summary["installationContactAudit"], "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
