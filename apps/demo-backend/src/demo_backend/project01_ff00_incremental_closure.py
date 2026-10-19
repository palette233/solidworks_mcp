"""Close Project01 FF00 static installation while preserving dynamic debt."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = ("JJ00", "HL00", "SS00", "FF00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value(item: dict[str, Any], pascal: str, default: Any = None) -> Any:
    return item.get(pascal, item.get(pascal[0].lower() + pascal[1:], default))


def _token(text: str) -> str:
    upper = str(text).upper()
    rows = [token for token in TOKENS if token in upper]
    if len(rows) != 1:
        raise ValueError(f"Could not identify one Project01 token from {text!r}")
    return rows[0]


def build_project01_ff00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly = assembly_path.resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)
    source = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in TOKENS
    }
    observed = {
        _token(str(row.get("HierarchyPath") or row.get("Name") or "")): row
        for row in poses.get("components") or []
    }
    if set(source) != set(TOKENS) or set(observed) != set(TOKENS):
        raise ValueError("Source/observed sets must contain exactly JJ00, HL00, SS00 and FF00")
    pose_rows = []
    for token in TOKENS:
        expected = [float(value) for value in source[token]["SourceTransform"]]
        actual = [float(value) for value in observed[token]["Transform"]]
        error = max((abs(a - b) for a, b in zip(expected, actual, strict=True)), default=0.0)
        path = Path(str(observed[token]["Path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": error,
                "sourceFilePath": str(path.resolve()),
                "sourceFileSha256": _sha256(path),
                "sourcePoseEquivalent": error <= 1e-12,
            }
        )
    pair_rows = []
    for row in screening.get("broadPhase") or []:
        pair = [_token(value) for value in row["pair"]]
        tokens = frozenset(pair)
        if row.get("requiresExactLeafBrep") is not True:
            decision = "accepted-by-strict-world-aabb-separation"
            reason = "World AABBs are separated on at least one axis."
        elif "FF00" not in tokens:
            decision = "accepted-as-unchanged-prior-context"
            reason = "This prior-context pair is unchanged from the accepted SS00 checkpoint."
        elif tokens == frozenset(("JJ00", "FF00")):
            decision = "accepted-static-installation-by-source-pose-equivalence"
            reason = "The intended JJ00/FF00 installation uses source-equivalent files and pose."
        elif tokens == frozenset(("SS00", "FF00")):
            decision = "accepted-static-process-overlap-by-source-pose-equivalence"
            reason = (
                "FF00 and SS00 retain the accepted prototype static process pose; the 25 degree "
                "motion sweep remains unverified."
            )
        else:
            decision = "rejected-unclassified-overlap"
            reason = "The overlapping new-module pair has no accepted policy."
        pair_rows.append(
            {
                "pair": pair,
                "broadPhaseStatus": row["broadPhaseStatus"],
                "decision": decision,
                "reason": reason,
                "accepted": not decision.startswith("rejected"),
            }
        )
    tool = insert_result.get("toolResult") or {}
    insert_ok = bool(
        insert_result.get("success")
        and _value(tool, "OriginalComponentRemoved") is True
        and _value(tool, "IndependentComponentInserted") is True
        and int(_value(tool, "CreatedMateCount", -1)) == 3
        and _value(tool, "ReopenedMateParametersMatch") is True
        and _value(tool, "TargetFullyConstrained") is True
        and _value(tool, "MateSolveClean") is True
    )
    pose_ok = len(pose_rows) == 4 and all(row["sourcePoseEquivalent"] for row in pose_rows)
    collision_ok = (
        len(pair_rows) == 6
        and all(row["accepted"] for row in pair_rows)
        and int(screening.get("aabbProvenPairCount") or 0) == 2
        and int(screening.get("exactCandidatePairCount") or 0) == 4
    )
    static_passed = insert_ok and pose_ok and collision_ok
    dynamic_passed = False
    timing = {
        "ff00IncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float(
            (screening.get("timing") or {}).get("totalDurationSeconds") or 0.0
        ),
    }
    timing["totalMeasuredSeconds"] = sum(timing.values())
    return {
        "schemaVersion": "project01-ff00-incremental-closure/v1",
        "projectId": "project01",
        "status": (
            "PROJECT01_FF00_STATIC_INCREMENT_CLOSED_DYNAMIC_BLOCKED"
            if static_passed
            else "PROJECT01_FF00_STATIC_INCREMENT_BLOCKED"
        ),
        "success": static_passed,
        "staticCheckpointPassed": static_passed,
        "dynamicCheckpointPassed": dynamic_passed,
        "productionReady": False,
        "absoluteZeroInterferenceClaimed": False,
        "noNewStaticInterferenceOverPrototype": collision_ok and pose_ok,
        "assemblyPath": str(assembly),
        "assemblySha256": _sha256(assembly),
        "componentCount": len(observed),
        "drivingMateCount": int(_value(tool, "CreatedMateCount", 0)),
        "incrementalInsertGate": {"passed": insert_ok},
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(
                (row["maximumTransformElementError"] for row in pose_rows), default=None
            ),
            "modules": pose_rows,
        },
        "collisionGate": {
            "staticPassed": collision_ok,
            "dynamicPassed": dynamic_passed,
            "pairCount": len(pair_rows),
            "aabbSeparatedPairCount": sum(
                row["decision"] == "accepted-by-strict-world-aabb-separation"
                for row in pair_rows
            ),
            "pairs": pair_rows,
        },
        "dynamicGate": {
            "passed": False,
            "requiredStates": ["home", "work", "flip-25deg"],
            "blockers": [
                "FF00 flexible/rigid motion state contract is not yet registered.",
                "The 25 degree swept-volume collision check has not been executed.",
            ],
        },
        "timingSeconds": timing,
        "limitations": [
            "The 35 mm interface and static pose are prototype-derived.",
            "Static source-pose equivalence proves no new penetration, not absolute zero contact.",
            "This result must not be promoted to a production motion release until the dynamic gate passes.",
        ],
        "nextStep": (
            "Register FF00 motion states and run the 25 degree swept-volume gate; meanwhile the static chain may be used to build the SM00 packet."
            if static_passed
            else "Repair FF00 insertion, pose, or static collision evidence before continuing."
        ),
    }
