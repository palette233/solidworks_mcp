"""Close the first independent Project03 AA00/AF00 + AE00 CAD checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = ("FL9A24D063AA00", "FL9A24D063AF00", "FL9A24D063AE00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token(text: str) -> str:
    upper = str(text).upper()
    matches = [value for value in TOKENS if value in upper]
    if len(matches) != 1:
        raise ValueError(f"Could not identify one Project03 token from {text!r}.")
    return matches[0]


def _value(item: dict[str, Any], pascal: str, default: Any = None) -> Any:
    return item.get(pascal, item.get(pascal[0].lower() + pascal[1:], default))


def build_project03_ae00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    base_result: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly_path = assembly_path.resolve()
    if not assembly_path.is_file():
        raise FileNotFoundError(assembly_path)
    source_by_token = {
        str(item["ModuleToken"]): item
        for item in source_graph.get("Modules") or []
        if str(item.get("ModuleToken") or "") in TOKENS
    }
    observed_by_token = {
        _token(str(item.get("HierarchyPath") or item.get("Name") or "")): item
        for item in poses.get("components") or []
    }
    if set(source_by_token) != set(TOKENS) or set(observed_by_token) != set(TOKENS):
        raise ValueError("Source/observed module sets do not contain exactly AA00, AF00 and AE00.")

    pose_rows = []
    for token in TOKENS:
        expected = [float(value) for value in source_by_token[token]["SourceTransform"]]
        observed = [float(value) for value in observed_by_token[token]["Transform"]]
        if len(expected) != len(observed):
            raise ValueError(f"Transform length mismatch for {token}.")
        errors = [abs(a - b) for a, b in zip(expected, observed)]
        observed_path = Path(str(observed_by_token[token]["Path"]))
        if not observed_path.is_file():
            raise FileNotFoundError(observed_path)
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": max(errors, default=0.0),
                "sourceFilePath": str(observed_path.resolve()),
                "sourceFileSha256": _sha256(observed_path),
                "sourcePoseEquivalent": max(errors, default=0.0) <= 1e-12,
            }
        )

    broad = screening.get("broadPhase") or []
    pair_rows = []
    for row in broad:
        pair = [_token(value) for value in row["pair"]]
        requires_exact = row.get("requiresExactLeafBrep") is True
        if requires_exact:
            decision = "accepted-by-exact-source-pose-equivalence"
            reason = (
                "Both module files and their relative transform are identical to the "
                "accepted prototype installation; this proves no new penetration, not zero contact."
            )
        else:
            decision = "accepted-by-strict-world-aabb-separation"
            reason = "World AABBs are separated on at least one axis."
        pair_rows.append(
            {
                "pair": pair,
                "broadPhaseStatus": row["broadPhaseStatus"],
                "decision": decision,
                "reason": reason,
                "accepted": True,
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
    timings = {
        "baseContextRebuildSeconds": float(base_result.get("durationSeconds") or 0.0),
        "ae00IncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float(
            (screening.get("timing") or {}).get("totalDurationSeconds") or 0.0
        ),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
    }
    timings["totalMeasuredSeconds"] = sum(timings.values())
    return {
        "schemaVersion": "project03-ae00-incremental-closure/v1",
        "projectId": "project03",
        "status": (
            "PROJECT03_AE00_INCREMENT_DEMO_CLOSED"
            if passed
            else "PROJECT03_AE00_INCREMENT_BLOCKED"
        ),
        "success": passed,
        "demoCheckpointPassed": passed,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok and pose_ok,
        "assemblyPath": str(assembly_path),
        "assemblySha256": _sha256(assembly_path),
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
            "sourcePoseEquivalentInstallationPairCount": sum(
                row["decision"] == "accepted-by-exact-source-pose-equivalence"
                for row in pair_rows
            ),
            "pairs": pair_rows,
        },
        "timingSeconds": timings,
        "limitations": [
            "The installed pose is recovered solely by mates, but the interface dimensions still originate from the prototype.",
            "The collision result proves no new interference over the accepted prototype pose; it does not claim absolute zero contact.",
            "Vendor confirmation and later dynamic-state checks remain outside this checkpoint.",
        ],
        "nextStep": (
            "Promote AE00 to a validated single CAD action, then build the AA00/AD00 installation and dynamic-state packet."
            if passed
            else "Do not continue to AD00; repair the failed base, mate, pose or collision gate first."
        ),
    }
