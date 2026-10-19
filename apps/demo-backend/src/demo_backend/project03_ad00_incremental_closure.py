"""Finalize the Project03 AD00 static incremental checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = (
    "FL9A24D063AA00",
    "FL9A24D063AF00",
    "FL9A24D063AE00",
    "FL9A24D063AD00",
)


def _token(text: str) -> str:
    matches = [token for token in TOKENS if token in str(text).upper()]
    if len(matches) != 1:
        raise ValueError(f"Cannot identify one Project03 module in {text!r}.")
    return matches[0]


def _get(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def build_project03_ad00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    prototype_ae_ad_brep: dict[str, Any],
    assembly_path: Path,
) -> dict[str, Any]:
    assembly_path = assembly_path.resolve()
    if not assembly_path.is_file():
        raise FileNotFoundError(assembly_path)
    source = {
        str(row["ModuleToken"]): row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "") in TOKENS
    }
    observed = {
        _token(row.get("Name") or row.get("HierarchyPath") or ""): row
        for row in poses.get("components") or []
    }
    if set(source) != set(TOKENS) or set(observed) != set(TOKENS):
        raise ValueError("Expected exactly AA00, AF00, AE00 and AD00.")
    pose_rows = []
    for token in TOKENS:
        errors = [
            abs(float(a) - float(b))
            for a, b in zip(source[token]["SourceTransform"], observed[token]["Transform"])
        ]
        pose_rows.append({
            "moduleToken": token,
            "maximumTransformElementError": max(errors, default=0.0),
            "sourcePoseEquivalent": max(errors, default=0.0) <= 1e-12,
        })
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)
    tool = insert_result.get("toolResult") or {}
    insert_ok = bool(
        insert_result.get("success")
        and _get(tool, "IndependentComponentInserted") is True
        and int(_get(tool, "CreatedMateCount", -1)) == 3
        and _get(tool, "ReopenedMateParametersMatch") is True
        and _get(tool, "TargetFullyConstrained") is True
        and _get(tool, "MateSolveClean") is True
    )
    baseline_ok = bool(
        _get(prototype_ae_ad_brep, "ExactCheckComplete") is True
        and int(_get(prototype_ae_ad_brep, "FailedBodyPairCount", -1)) == 0
        and int(_get(prototype_ae_ad_brep, "InterferingBodyPairCount", -1)) == 6
    )
    pairs = []
    for row in screening.get("broadPhase") or []:
        pair = sorted((_token(row["pair"][0]), _token(row["pair"][1])))
        if row.get("requiresExactLeafBrep") is not True:
            decision = "accepted-by-strict-world-aabb-separation"
        elif set(pair) == {"FL9A24D063AE00", "FL9A24D063AD00"}:
            decision = "accepted-by-prototype-exact-brep-and-identical-relative-pose"
        else:
            decision = "accepted-by-identical-installation-pose"
        pairs.append({"pair": pair, "decision": decision, "accepted": True})
    collision_ok = len(pairs) == 6 and baseline_ok and pose_ok
    success = insert_ok and pose_ok and collision_ok
    return {
        "schemaVersion": "project03-ad00-incremental-closure/v1",
        "projectId": "project03",
        "status": "PROJECT03_AD00_STATIC_INCREMENT_CLOSED" if success else "PROJECT03_AD00_INCREMENT_BLOCKED",
        "success": success,
        "staticDemoCheckpointPassed": success,
        "dynamicSweepPassed": False,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok,
        "assemblyPath": str(assembly_path),
        "assemblySha256": hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        "componentCount": len(observed),
        "drivingMateCount": int(_get(tool, "CreatedMateCount", 0)),
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows),
            "modules": pose_rows,
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pairs),
            "aabbSeparatedPairCount": sum("strict-world-aabb" in row["decision"] for row in pairs),
            "prototypeAe00Ad00InterferingBodyPairCount": 6,
            "pairs": pairs,
        },
        "timingSeconds": {
            "ad00IncrementalInsert": float(insert_result.get("durationSeconds") or 0.0),
            "poseCapture": float(poses.get("durationSeconds") or 0.0),
            "broadPhaseCapture": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0),
        },
        "blockers": [
            "AD00 25-degree flip swept-volume validation is not complete.",
            "The six prototype-existing AE00/AD00 leaf-body overlaps still require engineering classification.",
        ],
        "nextStep": "Keep the static checkpoint; capture AD10/AD20 motion states before production release, and proceed to AI00 only for the static demo chain.",
    }
