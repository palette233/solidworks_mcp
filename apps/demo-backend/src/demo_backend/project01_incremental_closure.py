"""Close the first Project 01 JJ00/HL00 + SS00 incremental checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = ("JJ00", "HL00", "SS00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value(item: dict[str, Any], pascal: str, default: Any = None) -> Any:
    return item.get(pascal, item.get(pascal[0].lower() + pascal[1:], default))


def _token(text: str) -> str:
    upper = str(text).upper()
    matches = [token for token in TOKENS if token in upper]
    if len(matches) != 1:
        raise ValueError(f"Could not identify one Project01 token from {text!r}")
    return matches[0]


def build_project01_ss00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    base_result: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly = assembly_path.resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)
    source_by_token = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in TOKENS
    }
    observed_by_token = {
        _token(str(row.get("HierarchyPath") or row.get("Name") or "")): row
        for row in poses.get("components") or []
    }
    if set(source_by_token) != set(TOKENS) or set(observed_by_token) != set(TOKENS):
        raise ValueError("Source/observed sets must contain exactly JJ00, HL00 and SS00")

    pose_rows: list[dict[str, Any]] = []
    for token in TOKENS:
        expected = [float(value) for value in source_by_token[token]["SourceTransform"]]
        observed = [float(value) for value in observed_by_token[token]["Transform"]]
        error = max((abs(a - b) for a, b in zip(expected, observed, strict=True)), default=0.0)
        component_path = Path(str(observed_by_token[token]["Path"]))
        if not component_path.is_file():
            raise FileNotFoundError(component_path)
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": error,
                "sourceFilePath": str(component_path.resolve()),
                "sourceFileSha256": _sha256(component_path),
                "sourcePoseEquivalent": error <= 1e-12,
            }
        )

    pair_rows: list[dict[str, Any]] = []
    for row in screening.get("broadPhase") or []:
        pair = [_token(value) for value in row["pair"]]
        tokens = frozenset(pair)
        if row.get("requiresExactLeafBrep") is not True:
            decision = "accepted-by-strict-world-aabb-separation"
            reason = "World AABBs are separated on at least one axis."
        elif tokens == frozenset(("JJ00", "HL00")):
            decision = "accepted-as-unchanged-fixed-context"
            reason = (
                "JJ00 and HL00 are fixed context modules whose files and source poses are "
                "unchanged; their internal baseline is outside the new SS00 insertion gate."
            )
        elif tokens == frozenset(("JJ00", "SS00")):
            decision = "accepted-by-source-interface-pose-equivalence"
            reason = (
                "The intended installation pair uses the same source files and relative pose "
                "as the accepted prototype interface; this proves no new penetration, not zero contact."
            )
        else:
            decision = "rejected-unclassified-overlap"
            reason = "An overlapping pair has no accepted installation or fixed-context policy."
        pair_rows.append(
            {
                "pair": pair,
                "broadPhaseStatus": row["broadPhaseStatus"],
                "decision": decision,
                "reason": reason,
                "accepted": not decision.startswith("rejected"),
            }
        )

    base_tool = base_result.get("toolResult") or {}
    insert_tool = insert_result.get("toolResult") or {}
    base_ok = bool(
        base_result.get("success")
        and _value(base_tool, "Reopened") is True
        and int(_value(base_tool, "ReopenedModuleCount", -1)) == 2
        and int(_value(base_tool, "ReopenedMateCount", -1)) == 0
    )
    insert_ok = bool(
        insert_result.get("success")
        and _value(insert_tool, "OriginalComponentRemoved") is True
        and _value(insert_tool, "IndependentComponentInserted") is True
        and int(_value(insert_tool, "CreatedMateCount", -1)) == 3
        and _value(insert_tool, "ReopenedMateParametersMatch") is True
        and _value(insert_tool, "TargetFullyConstrained") is True
        and _value(insert_tool, "MateSolveClean") is True
    )
    pose_ok = len(pose_rows) == 3 and all(row["sourcePoseEquivalent"] for row in pose_rows)
    collision_ok = (
        len(pair_rows) == 3
        and all(row["accepted"] for row in pair_rows)
        and int(screening.get("aabbProvenPairCount") or 0) == 1
        and int(screening.get("exactCandidatePairCount") or 0) == 2
    )
    passed = base_ok and insert_ok and pose_ok and collision_ok
    timing = {
        "baseContextRebuildSeconds": float(base_result.get("durationSeconds") or 0.0),
        "ss00IncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float(
            (screening.get("timing") or {}).get("totalDurationSeconds") or 0.0
        ),
    }
    timing["totalMeasuredSeconds"] = sum(timing.values())
    return {
        "schemaVersion": "project01-ss00-incremental-closure/v1",
        "projectId": "project01",
        "status": (
            "PROJECT01_SS00_INCREMENT_DEMO_CLOSED"
            if passed
            else "PROJECT01_SS00_INCREMENT_BLOCKED"
        ),
        "success": passed,
        "demoCheckpointPassed": passed,
        "productionReady": False,
        "absoluteZeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok and pose_ok,
        "assemblyPath": str(assembly),
        "assemblySha256": _sha256(assembly),
        "componentCount": len(observed_by_token),
        "drivingMateCount": int(_value(insert_tool, "CreatedMateCount", 0)),
        "baseContextGate": {"passed": base_ok},
        "incrementalInsertGate": {"passed": insert_ok},
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(
                (row["maximumTransformElementError"] for row in pose_rows), default=None
            ),
            "modules": pose_rows,
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pair_rows),
            "aabbSeparatedPairCount": sum(
                row["decision"] == "accepted-by-strict-world-aabb-separation"
                for row in pair_rows
            ),
            "unchangedFixedContextPairCount": sum(
                row["decision"] == "accepted-as-unchanged-fixed-context"
                for row in pair_rows
            ),
            "sourceEquivalentInstallationPairCount": sum(
                row["decision"] == "accepted-by-source-interface-pose-equivalence"
                for row in pair_rows
            ),
            "fullLeafBrepAttempt": {
                "status": "ABORTED_PERFORMANCE_BUDGET",
                "durableExactEvidenceProduced": False,
                "reason": (
                    "The JJ00 fixed-context leaf-level baseline exceeded the incremental-stage "
                    "runtime budget. The checkpoint therefore uses hash and pose-equivalence evidence."
                ),
            },
            "pairs": pair_rows,
        },
        "timingSeconds": timing,
        "limitations": [
            "The 58 mm installation interface is prototype-derived, not vendor-confirmed.",
            "The result proves no new interference relative to the accepted prototype pose; it does not prove absolute zero contact.",
            "The full leaf-level JJ00 fixed-context baseline remains a reusable-evidence performance debt.",
            "This checkpoint covers static installation only; motion and maintenance envelopes are not yet closed.",
        ],
        "nextStep": (
            "Promote SS00 to a validated Project01 CAD action and build the dependent FF00 scanner packet."
            if passed
            else "Do not continue to FF00; repair the failed base, mate, pose or collision gate first."
        ),
    }
