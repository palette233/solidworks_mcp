"""Finalize the Project03 AG00 service-cluster incremental checkpoint."""

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
)


def _get(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _token(text: str) -> str:
    matches = [token for token in TOKENS if token in str(text).upper()]
    if len(matches) != 1:
        raise ValueError(f"Cannot identify one Project03 module in {text!r}.")
    return matches[0]


def build_project03_ag00_incremental_closure(
    *,
    source_graph: dict[str, Any],
    diagnostic_result: dict[str, Any],
    anchored_result: dict[str, Any],
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
        raise ValueError("Expected exactly the six modules through AG00.")
    pose_rows = []
    for token in TOKENS:
        errors = [
            abs(float(a) - float(b))
            for a, b in zip(source[token]["SourceTransform"], observed[token]["Transform"])
        ]
        maximum_error = max(errors, default=0.0)
        source_path = Path(str(observed[token]["Path"]))
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        pose_rows.append(
            {
                "moduleToken": token,
                "maximumTransformElementError": maximum_error,
                "sourcePoseEquivalent": maximum_error <= 1e-12,
                "sourceFileSha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            }
        )
    pose_ok = all(row["sourcePoseEquivalent"] for row in pose_rows)

    diagnostic_tool = diagnostic_result.get("toolResult") or {}
    residual_dof_proven = bool(
        diagnostic_result.get("success") is False
        and int(_get(diagnostic_tool, "CreatedMateCount", -1)) == 2
        and _get(diagnostic_tool, "ReopenedMateParametersMatch") is True
        and _get(diagnostic_tool, "MateSolveClean") is True
        and _get(diagnostic_tool, "TargetFullyConstrained") is False
    )
    tool = anchored_result.get("toolResult") or {}
    anchored_ok = bool(
        anchored_result.get("success")
        and _get(tool, "IndependentComponentInserted") is True
        and _get(tool, "TargetCaseAnchored") is True
        and _get(tool, "CaseAnchorPoseMatch") is True
        and float(_get(tool, "CaseAnchorTranslationErrorMeters", 1.0)) <= 1e-12
        and float(_get(tool, "CaseAnchorRotationError", 1.0)) <= 1e-12
        and int(_get(tool, "CreatedMateCount", -1)) == 2
        and _get(tool, "ReopenedMateParametersMatch") is True
        and _get(tool, "TargetFullyConstrained") is True
        and _get(tool, "MateSolveClean") is True
    )

    ag_ports = [
        row
        for row in service_points.get("servicePorts") or []
        if str(row.get("sourceSubassembly") or "").upper().startswith("FL9A24D063AG")
    ]
    expected_capabilities = {
        "cleaning": 2,
        "weighing": 1,
        "glue_hardness_test": 1,
        "glue_drain": 2,
    }
    actual_capabilities = {
        capability: sum(row.get("capability") == capability for row in ag_ports)
        for capability in expected_capabilities
    }
    service_static_ok = bool(
        pose_ok
        and len(ag_ports) == 6
        and actual_capabilities == expected_capabilities
        and all(len(row.get("worldMeters") or []) == 3 for row in ag_ports)
        and service_points.get("coarseLayoutUsable") is True
    )
    service_production_ready = bool(
        service_static_ok and service_points.get("engineeringConfirmed") is True
    )

    pair_rows = []
    for row in screening.get("broadPhase") or []:
        pair = sorted((_token(row["pair"][0]), _token(row["pair"][1])))
        decision = (
            "accepted-by-identical-source-files-and-relative-pose"
            if row.get("requiresExactLeafBrep") is True
            else "accepted-by-strict-world-aabb-separation"
        )
        pair_rows.append({
            "pair": pair,
            "broadPhaseStatus": row.get("broadPhaseStatus"),
            "decision": decision,
            "accepted": True,
        })
    collision_ok = bool(
        len(pair_rows) == 15
        and int(screening.get("aabbProvenPairCount") or 0) == 5
        and int(screening.get("exactCandidatePairCount") or 0) == 10
        and pose_ok
    )
    success = bool(
        residual_dof_proven
        and anchored_ok
        and pose_ok
        and service_static_ok
        and collision_ok
    )
    timing = {
        "nonAnchoredDofDiagnosticSeconds": float(diagnostic_result.get("durationSeconds") or 0.0),
        "anchoredIncrementalInsertSeconds": float(anchored_result.get("durationSeconds") or 0.0),
        "poseCaptureSeconds": float(poses.get("durationSeconds") or 0.0),
        "broadPhaseCaptureSeconds": float((screening.get("timing") or {}).get("totalDurationSeconds") or 0.0),
    }
    timing["anchoredSuccessfulPathMeasuredSeconds"] = (
        timing["anchoredIncrementalInsertSeconds"]
        + timing["poseCaptureSeconds"]
        + timing["broadPhaseCaptureSeconds"]
    )
    timing["engineeringIterationMeasuredSeconds"] = sum(
        value for key, value in timing.items() if key.endswith("Seconds") and "Measured" not in key
    )
    return {
        "schemaVersion": "project03-ag00-incremental-closure/v1",
        "projectId": "project03",
        "status": "PROJECT03_AG00_STATIC_INCREMENT_CLOSED_WITH_EXPLICIT_RESIDUAL_ANCHOR" if success else "PROJECT03_AG00_INCREMENT_BLOCKED",
        "success": success,
        "staticDemoCheckpointPassed": success,
        "productionReady": False,
        "zeroInterferenceClaimed": False,
        "noNewInterferenceOverPrototype": collision_ok,
        "assemblyPath": str(assembly_path),
        "assemblySha256": hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        "componentCount": len(observed),
        "installationSemantics": {
            "passed": anchored_ok and residual_dof_proven,
            "sourceDrivingMateCount": 2,
            "sourceMateBundleFullyLocatesTarget": False,
            "expectedResidualDof": 1,
            "diagnosticConfirmedResidualDof": residual_dof_proven,
            "residualAnchorApplied": True,
            "residualAnchorAuthority": "project03-prototype-source-transform-temporary-fallback",
            "caseAnchorTranslationErrorMeters": _get(tool, "CaseAnchorTranslationErrorMeters"),
            "caseAnchorRotationError": _get(tool, "CaseAnchorRotationError"),
        },
        "poseAudit": {
            "passed": pose_ok,
            "maximumTransformElementError": max(row["maximumTransformElementError"] for row in pose_rows),
            "modules": pose_rows,
        },
        "serviceTargetGate": {
            "passedForStaticDemo": service_static_ok,
            "productionReady": service_production_ready,
            "targetCount": len(ag_ports),
            "capabilityCounts": actual_capabilities,
            "targetsAreCoarseProxies": True,
        },
        "collisionGate": {
            "passed": collision_ok,
            "pairCount": len(pair_rows),
            "aabbSeparatedPairCount": sum("strict-world-aabb" in row["decision"] for row in pair_rows),
            "sourcePoseEquivalentCandidatePairCount": sum("source-files-and-relative-pose" in row["decision"] for row in pair_rows),
            "pairs": pair_rows,
        },
        "timingSeconds": timing,
        "blockers": [
            "AG00源配合缺少防转基准；当前Demo依赖显式原型姿态残差锚点。",
            "六个服务目标是CAD几何代理，缺少工程师确认的真实喷嘴接触/插入深度。",
            "维护包络、Z向插入、工具扫掠和动态状态尚未验证。",
            "10个AABB候选仅由原型相对位姿等价证明无新增干涉，未形成绝对零干涉结论。",
        ],
        "nextStep": (
            "把AG00登记为带显式原型残差锚点的静态Demo动作；随后建立AH00校准模组安装端口。"
            if success
            else "暂停AH00；先修复AG00自由度、服务目标、位姿或碰撞门禁。"
        ),
    }
