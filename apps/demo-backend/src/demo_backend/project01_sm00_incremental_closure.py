"""Close Project01 SM00 mechanical and static optical checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = ("JJ00", "HL00", "SS00", "FF00", "SM00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value(item: dict[str, Any], pascal: str, default: Any = None) -> Any:
    return item.get(pascal, item.get(pascal[0].lower() + pascal[1:], default))


def _token(text: str) -> str:
    rows = [token for token in TOKENS if token in str(text).upper()]
    if len(rows) != 1:
        raise ValueError(f"Could not identify one Project01 token from {text!r}")
    return rows[0]


def build_project01_sm00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    scanner_geometry: dict[str, Any],
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
        raise ValueError("Source/observed sets do not contain the five expected modules")
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
        elif "SM00" not in tokens:
            decision = "accepted-as-unchanged-prior-context"
            reason = "This pair was already accepted in a prior checkpoint."
        elif tokens == frozenset(("JJ00", "SM00")):
            decision = "accepted-static-installation-by-source-pose-equivalence"
            reason = "The intended JJ00/SM00 installation retains source files and relative pose."
        else:
            decision = "accepted-static-scanner-context-by-source-pose-equivalence"
            reason = "The new scanner/context pair retains the accepted prototype static pose."
        pair_rows.append(
            {
                "pair": pair,
                "broadPhaseStatus": row["broadPhaseStatus"],
                "decision": decision,
                "reason": reason,
                "accepted": True,
            }
        )
    tool = insert_result.get("toolResult") or {}
    insert_ok = bool(
        insert_result.get("success")
        and _value(tool, "IndependentComponentInserted") is True
        and int(_value(tool, "CreatedMateCount", -1)) == 3
        and _value(tool, "ReopenedMateParametersMatch") is True
        and _value(tool, "TargetFullyConstrained") is True
        and _value(tool, "MateSolveClean") is True
    )
    pose_ok = len(pose_rows) == 5 and all(row["sourcePoseEquivalent"] for row in pose_rows)
    collision_ok = (
        len(pair_rows) == 10
        and int(screening.get("aabbProvenPairCount") or 0) == 2
        and int(screening.get("exactCandidatePairCount") or 0) == 8
    )
    scanners = scanner_geometry.get("scanners") or []
    role_map = {str(row.get("role")): row for row in scanners}
    optical_ok = bool(
        scanner_geometry.get("coarseLayoutUsable") is True
        and scanner_geometry.get("scannerCount") == 2
        and set(role_map) == {"carrierBarcodeScanner", "productBarcodeScanner"}
        and all(abs(float(row.get("modeledWorkingDistanceMeters") or 0.0) - 0.2) <= 1e-9 for row in scanners)
        and role_map["carrierBarcodeScanner"].get("opticalDirectionWorld") == [1.0, 0.0, 0.0]
        and role_map["productBarcodeScanner"].get("opticalDirectionWorld") == [0.0, 1.0, 0.0]
        and role_map["productBarcodeScanner"].get("motionAxisWorld") == [0.0, 0.0, 1.0]
    )
    passed = insert_ok and pose_ok and collision_ok and optical_ok
    timing = {
        "sm00IncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0),
    }
    timing["totalMeasuredSeconds"] = sum(timing.values())
    return {
        "schemaVersion": "project01-sm00-incremental-closure/v1",
        "projectId": "project01",
        "status": "PROJECT01_SM00_STATIC_OPTICAL_DEMO_CLOSED" if passed else "PROJECT01_SM00_BLOCKED",
        "success": passed,
        "staticCheckpointPassed": passed,
        "productionReady": False,
        "absoluteZeroInterferenceClaimed": False,
        "assemblyPath": str(assembly),
        "assemblySha256": _sha256(assembly),
        "componentCount": len(observed),
        "drivingMateCount": int(_value(tool, "CreatedMateCount", 0)),
        "incrementalInsertGate": {"passed": insert_ok},
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max((row["maximumTransformElementError"] for row in pose_rows), default=None),
            "modules": pose_rows,
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pair_rows),
            "aabbSeparatedPairCount": sum(
                row["decision"] == "accepted-by-strict-world-aabb-separation" for row in pair_rows
            ),
            "pairs": pair_rows,
        },
        "opticalGate": {
            "staticDemoPassed": optical_ok,
            "engineeringConfirmed": scanner_geometry.get("engineeringConfirmed") is True,
            "scannerCount": scanner_geometry.get("scannerCount"),
            "roles": sorted(role_map),
            "modeledWorkingDistancesMeters": [row.get("modeledWorkingDistanceMeters") for row in scanners],
            "carrierDirectionWorld": role_map.get("carrierBarcodeScanner", {}).get("opticalDirectionWorld"),
            "productDirectionWorld": role_map.get("productBarcodeScanner", {}).get("opticalDirectionWorld"),
            "productMotionAxisWorld": role_map.get("productBarcodeScanner", {}).get("motionAxisWorld"),
        },
        "timingSeconds": timing,
        "limitations": [
            "The 22 mm installation interface is prototype-derived.",
            "The 200 mm beams are prototype CAD geometry, not vendor-certified working-distance limits.",
            "The actual barcode surfaces, trigger positions and product-reader travel endpoints are not registered.",
            "The collision statement is no-new-static-interference over the source pose, not absolute zero contact.",
        ],
        "nextStep": (
            "Promote SM00 as a static CAD demo action and build the GN00 multifunction packet; keep optical production release blocked."
            if passed
            else "Repair the mechanical, pose, collision, or optical gate before continuing."
        ),
    }
