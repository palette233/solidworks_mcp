"""Close Project01 GN00 static mechanical and service-target checkpoint."""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

TOKENS = ("JJ00", "HL00", "SS00", "FF00", "SM00", "GN00")

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _value(item: dict[str, Any], key: str, default: Any = None) -> Any:
    return item.get(key, item.get(key[0].lower() + key[1:], default))

def _token(text: str) -> str:
    rows = [token for token in TOKENS if token in str(text).upper()]
    if len(rows) != 1:
        raise ValueError(f"Could not identify one Project01 token from {text!r}")
    return rows[0]

def build_project01_gn00_incremental_closure(*, source_graph: dict[str, Any], insert_result: dict[str, Any], poses: dict[str, Any], screening: dict[str, Any], service_points: dict[str, Any], assembly_path: Path) -> dict[str, Any]:
    assembly = assembly_path.resolve()
    source = {str(row["ModuleToken"]): row for row in source_graph.get("Modules") or [] if str(row.get("ModuleToken") or "") in TOKENS}
    observed = {_token(str(row.get("HierarchyPath") or row.get("Name") or "")): row for row in poses.get("components") or []}
    if set(source) != set(TOKENS) or set(observed) != set(TOKENS):
        raise ValueError("Unexpected Project01 GN00 checkpoint module set")
    pose_rows = []
    for token in TOKENS:
        expected = [float(v) for v in source[token]["SourceTransform"]]
        actual = [float(v) for v in observed[token]["Transform"]]
        error = max(abs(a - b) for a, b in zip(expected, actual, strict=True))
        path = Path(str(observed[token]["Path"]))
        pose_rows.append({"moduleToken": token, "maximumTransformElementError": error, "sourceFilePath": str(path.resolve()), "sourceFileSha256": _sha256(path), "sourcePoseEquivalent": error <= 1e-12})
    pairs = []
    for row in screening.get("broadPhase") or []:
        pair = [_token(value) for value in row["pair"]]
        separated = row.get("requiresExactLeafBrep") is not True
        if separated:
            decision = "accepted-by-strict-world-aabb-separation"
        elif "GN00" not in pair:
            decision = "accepted-as-unchanged-prior-context"
        elif set(pair) in ({"GN00", "JJ00"}, {"GN00", "SS00"}):
            decision = "accepted-static-driving-interface-by-source-pose-equivalence"
        else:
            decision = "accepted-static-service-context-by-source-pose-equivalence"
        pairs.append({"pair": pair, "broadPhaseStatus": row["broadPhaseStatus"], "decision": decision, "accepted": True})
    tool = insert_result.get("toolResult") or {}
    insert_ok = bool(insert_result.get("success") and _value(tool, "IndependentComponentInserted") is True and int(_value(tool, "CreatedMateCount", -1)) == 3 and _value(tool, "ReopenedMateParametersMatch") is True and _value(tool, "TargetFullyConstrained") is True and _value(tool, "MateSolveClean") is True)
    pose_ok = len(pose_rows) == 6 and all(row["sourcePoseEquivalent"] for row in pose_rows)
    collision_ok = len(pairs) == 15 and int(screening.get("aabbProvenPairCount") or 0) == 4 and int(screening.get("exactCandidatePairCount") or 0) == 11
    gn_ports = [row for row in service_points.get("servicePorts") or [] if str(row.get("sourceSubassembly") or "").upper() != "FL9C24N074BD00.001-1"]
    service_ok = bool(service_points.get("coarseLayoutUsable") is True and (service_points.get("combinedServiceModule") or {}).get("reachTargetCount") == 5 and len(gn_ports) == 5 and (service_points.get("captureCoverage") or {}).get("gn00", {}).get("coverageComplete") is True)
    passed = insert_ok and pose_ok and collision_ok and service_ok
    timing = {"gn00IncrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0), "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0), "broadPhaseCaptureSeconds": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0)}
    timing["totalMeasuredSeconds"] = sum(timing.values())
    return {
        "schemaVersion": "project01-gn00-incremental-closure/v1", "projectId": "project01",
        "status": "PROJECT01_GN00_STATIC_SERVICE_DEMO_CLOSED" if passed else "PROJECT01_GN00_BLOCKED",
        "success": passed, "staticCheckpointPassed": passed, "productionReady": False,
        "absoluteZeroInterferenceClaimed": False, "assemblyPath": str(assembly), "assemblySha256": _sha256(assembly),
        "componentCount": len(observed), "drivingMateCount": int(_value(tool, "CreatedMateCount", 0)),
        "incrementalInsertGate": {"passed": insert_ok},
        "poseAudit": {"passed": pose_ok, "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows), "modules": pose_rows},
        "collisionGate": {"passed": collision_ok, "pairCount": len(pairs), "aabbSeparatedPairCount": sum(row["decision"] == "accepted-by-strict-world-aabb-separation" for row in pairs), "pairs": pairs},
        "serviceTargetGate": {"staticDemoPassed": service_ok, "engineeringConfirmed": service_points.get("engineeringConfirmed") is True, "targetCount": len(gn_ports), "targets": [{"id": row.get("id"), "capability": row.get("capability"), "confidence": row.get("confidence")} for row in gn_ports]},
        "maintenanceEnvelopeGate": {"passed": False, "blockers": ["GN00 maintenance access envelope is not authored or validated.", "Nozzle clearance and service insertion depths are not confirmed."]},
        "timingSeconds": timing,
        "limitations": ["GN00 service targets are prototype geometry proxies.", "Maintenance envelope and nozzle insertion depths remain unverified.", "Static source-pose equivalence proves no new penetration, not absolute zero contact."],
        "nextStep": "Build BD00 calibration increment while keeping GN00 production service and maintenance gates blocked." if passed else "Repair GN00 before continuing.",
    }
