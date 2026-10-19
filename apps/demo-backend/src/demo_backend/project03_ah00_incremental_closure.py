"""Finalize the Project03 AH00 calibration-module incremental checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


TOKENS = (
    "FL9A24D063AA00",
    "FL9A24D063AF00",
    "FL9A24D063AE00",
    "FL9A24D063AD00",
    "FL9A24D063AI00",
    "FL9A24D063AG00",
    "FL9A24D063AH00",
)


def _get(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _token(text: str) -> str:
    matches = [token for token in TOKENS if token in str(text).upper()]
    if len(matches) != 1:
        raise ValueError(f"Cannot identify one Project03 module in {text!r}.")
    return matches[0]


def build_project03_ah00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    insert_result: dict[str, Any],
    poses: dict[str, Any],
    screening: dict[str, Any],
    service_points: dict[str, Any],
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
        raise ValueError("Expected exactly the seven modules through AH00.")
    pose_rows = []
    for token in TOKENS:
        errors = [
            abs(float(a) - float(b))
            for a, b in zip(source[token]["SourceTransform"], observed[token]["Transform"])
        ]
        maximum_error = max(errors, default=0.0)
        pose_rows.append({
            "moduleToken": token,
            "maximumTransformElementError": maximum_error,
            "sourcePoseEquivalent": maximum_error <= 1e-12,
        })
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)
    tool = insert_result.get("toolResult") or {}
    insert_ok = bool(
        insert_result.get("success")
        and _get(tool, "IndependentComponentInserted") is True
        and _get(tool, "TargetCaseAnchored") is False
        and int(_get(tool, "CreatedMateCount", -1)) == 3
        and _get(tool, "ReopenedMateParametersMatch") is True
        and _get(tool, "TargetFullyConstrained") is True
        and _get(tool, "MateSolveClean") is True
    )
    calibration = [
        row for row in service_points.get("servicePorts") or []
        if row.get("capability") == "calibration"
    ]
    calibration_static_ok = bool(
        pose_ok
        and len(calibration) == 1
        and len(calibration[0].get("worldMeters") or []) == 3
        and calibration[0].get("confidence") == "high"
        and service_points.get("coarseLayoutUsable") is True
    )
    calibration_production_ready = bool(
        calibration_static_ok and service_points.get("engineeringConfirmed") is True
    )
    pairs = []
    for row in screening.get("broadPhase") or []:
        decision = (
            "accepted-by-identical-source-files-and-relative-pose"
            if row.get("requiresExactLeafBrep") is True
            else "accepted-by-strict-world-aabb-separation"
        )
        pairs.append({
            "pair": sorted((_token(row["pair"][0]), _token(row["pair"][1]))),
            "decision": decision,
            "accepted": True,
        })
    collision_ok = bool(
        len(pairs) == 21
        and int(screening.get("aabbProvenPairCount") or 0) == 9
        and int(screening.get("exactCandidatePairCount") or 0) == 12
        and pose_ok
    )
    success = insert_ok and pose_ok and calibration_static_ok and collision_ok
    timing = {
        "incrementalInsertSeconds": float(insert_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0),
    }
    timing["totalMeasuredSeconds"] = sum(timing.values())
    return {
        "schemaVersion": "project03-ah00-incremental-closure/v1",
        "projectId": "project03",
        "status": "PROJECT03_AH00_STATIC_INCREMENT_CLOSED" if success else "PROJECT03_AH00_INCREMENT_BLOCKED",
        "success": success,
        "staticDemoCheckpointPassed": success,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok,
        "assemblyPath": str(assembly_path),
        "assemblySha256": hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        "componentCount": len(observed),
        "installationGate": {"passed": insert_ok, "drivingMateCount": int(_get(tool, "CreatedMateCount", 0)), "residualAnchorApplied": False},
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows),
            "modules": pose_rows,
        },
        "calibrationTargetGate": {
            "passedForStaticDemo": calibration_static_ok,
            "productionReady": calibration_production_ready,
            "targetCount": len(calibration),
            "target": calibration[0] if calibration else None,
            "targetIsCoarseProxy": True,
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pairs),
            "aabbSeparatedPairCount": sum("strict-world-aabb" in row["decision"] for row in pairs),
            "sourcePoseEquivalentCandidatePairCount": sum("source-files-and-relative-pose" in row["decision"] for row in pairs),
            "pairs": pairs,
        },
        "timingSeconds": timing,
        "blockers": [
            "校准目标是30 mm棱镜顶面中心代理，不是工程师登记的喷嘴标定点。",
            "两次拍照偏移、40 mm第二拍动作、Z向插入及工具扫掠未闭环。",
            "12个AABB候选只由原型相对位姿等价证明无新增干涉。",
        ],
        "nextStep": (
            "将AH00登记为第五个静态CAD动作，随后建立AJ00供胶模组安装与维护包络。"
            if success else "暂停AJ00；先修复AH00安装、校准目标、位姿或碰撞门禁。"
        ),
    }

