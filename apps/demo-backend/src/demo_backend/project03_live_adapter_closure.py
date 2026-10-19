from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project03-ae00-live-adapter-closure/v1"
CHAIN_SCHEMA = "project03-ae00-ad00-live-adapter-closure/v1"
THREE_STEP_SCHEMA = "project03-ae00-ad00-ai00-live-adapter-closure/v1"
FOUR_STEP_SCHEMA = "project03-ae00-ad00-ai00-ag00-live-adapter-closure/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_project03_ae00_live_adapter_closure(summary_path: Path) -> dict[str, Any]:
    summary_file = summary_path.resolve()
    summary = _load(summary_file)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    steps = job.get("steps") or []
    step = steps[0] if len(steps) == 1 else {}
    checkpoint = step.get("checkpoint") or {}
    assembly = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
    gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
    gate = _load(gate_path) if gate_path.is_file() else {}
    action_paths = [
        Path(str(value)).resolve()
        for value in checkpoint.get("cadActionEvidencePaths") or []
    ]
    action = _load(action_paths[0]) if len(action_paths) == 1 and action_paths[0].is_file() else {}
    tool_result = action.get("toolResult") or {}
    checks = {
        "summarySucceeded": summary.get("status") == "succeeded",
        "jobSucceeded": job.get("status") == "succeeded",
        "singleAe00Step": len(steps) == 1 and step.get("moduleToken") == "AE00",
        "singleAttempt": int(step.get("attemptCount") or 0) == 1,
        "cadActionSucceeded": action.get("success") is True,
        "threeMatesCreated": int(tool_result.get("CreatedMateCount") or 0) == 3,
        "targetFullyConstrained": tool_result.get("TargetFullyConstrained") is True,
        "reopened": tool_result.get("Reopened") is True,
        "reopenedMateParametersMatch": tool_result.get("ReopenedMateParametersMatch") is True,
        "collisionGateAccepted": gate.get("accepted") is True,
        "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
        "assemblyExists": assembly.is_file(),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "manifestStaticAccepted": manifest.get("staticExecutionAccepted") is True,
        "noRollback": job.get("rollback") is None,
    }
    passed = all(checks.values())
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project03",
        "moduleToken": "AE00",
        "status": (
            "PROJECT03_AE00_LIVE_ADAPTER_PILOT_CLOSED"
            if passed
            else "PROJECT03_AE00_LIVE_ADAPTER_PILOT_INCOMPLETE"
        ),
        "success": passed,
        "liveCadApiMayStartForTokens": ["AE00"] if passed else [],
        "fullProjectLiveCadReady": False,
        "productionReady": False,
        "checks": checks,
        "summaryPath": str(summary_file),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "assemblyPath": str(assembly),
        "gateEvidencePath": str(gate_path),
        "timingReportPath": str(job_path.parent / "timing-report.json"),
        "executionDurationSeconds": float(job.get("executionDurationSeconds") or 0.0),
        "limitations": [
            "仅AE00三基准静态安装已验证，AD00及后续动作尚未发布。",
            "安装端口尺寸和相对位置仍来自项目03原型，不是厂商权威基准。",
            "动态翻转、龙门行程、光学和软管维护仍未验收。",
        ],
    }


def write_project03_ae00_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project03_ae00_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def _build_project03_live_prefix_closure(
    summary_path: Path,
    *,
    expected_tokens: list[str],
    schema: str,
    closed_status: str,
    incomplete_status: str,
    limitations: list[str],
) -> dict[str, Any]:
    """Close one uninterrupted, ordered Project03 live-CAD prefix.

    This is deliberately stricter than combining two historical single-step
    artifacts: AD00 must consume the assembly committed by AE00 in the same
    durable job, and every step must pass mate/reopen and collision evidence.
    """

    summary_file = summary_path.resolve()
    summary = _load(summary_file)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    steps = job.get("steps") or []
    observed_tokens = [str(step.get("moduleToken") or "") for step in steps]

    step_checks: list[dict[str, Any]] = []
    previous_assembly: Path | None = None
    for index, step in enumerate(steps):
        checkpoint = step.get("checkpoint") or {}
        assembly = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        input_assembly = Path(str(checkpoint.get("inputAssemblyPath") or "")).resolve()
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        gate = _load(gate_path) if gate_path.is_file() else {}
        action_paths = [
            Path(str(value)).resolve()
            for value in checkpoint.get("cadActionEvidencePaths") or []
        ]
        action = (
            _load(action_paths[0])
            if len(action_paths) == 1 and action_paths[0].is_file()
            else {}
        )
        tool_result = action.get("toolResult") or {}
        validation_results = tool_result.get("ValidationResults") or []
        module_token = str(step.get("moduleToken") or "")
        expected_mate_count = {"AG00": 2}.get(module_token, 3)
        continuity = index == 0 or (
            previous_assembly is not None and input_assembly == previous_assembly
        )
        checks = {
            "stepSucceeded": step.get("status") == "succeeded",
            "singleAttempt": int(step.get("attemptCount") or 0) == 1,
            "checkpointContinuity": continuity,
            "cadActionSucceeded": action.get("success") is True,
            "expectedDrivingMateCountCreated": int(
                tool_result.get("CreatedMateCount") or 0
            )
            == expected_mate_count,
            "targetFullyConstrained": tool_result.get("TargetFullyConstrained") is True,
            "reopened": tool_result.get("Reopened") is True,
            "reopenedMateParametersMatch": tool_result.get("ReopenedMateParametersMatch") is True,
            "validationRelationsPassed": all(
                item.get("Passed") is True for item in validation_results
            ),
            "ai00TwoDistanceValidations": module_token != "AI00"
            or len(validation_results) == 2,
            "ag00ResidualPoseAnchorDeclared": module_token != "AG00"
            or (
                tool_result.get("TargetCaseAnchored") is True
                and tool_result.get("CaseAnchorPoseMatch") is True
            ),
            "collisionGateAccepted": gate.get("accepted") is True,
            "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
            "assemblyExists": assembly.is_file(),
        }
        step_checks.append(
            {
                "moduleToken": step.get("moduleToken"),
                "success": all(checks.values()),
                "checks": checks,
                "assemblyPath": str(assembly),
                "inputAssemblyPath": str(input_assembly),
                "gateEvidencePath": str(gate_path),
                "cadActionEvidencePath": str(action_paths[0]) if action_paths else None,
                "conditionalBrepEvidencePath": gate.get("exactBatchEvidencePath"),
            }
        )
        previous_assembly = assembly

    checks = {
        "summarySucceeded": summary.get("status") == "succeeded",
        "jobSucceeded": job.get("status") == "succeeded",
        "expectedOrderedPrefix": observed_tokens == expected_tokens,
        "expectedCommittedStepCount": len(steps) == len(expected_tokens),
        "everyStepClosed": len(step_checks) == len(expected_tokens)
        and all(item["success"] for item in step_checks),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "manifestStaticAccepted": manifest.get("staticExecutionAccepted") is True,
        "noRollback": job.get("rollback") is None,
    }
    passed = all(checks.values())
    final_assembly = previous_assembly or Path()
    return {
        "schemaVersion": schema,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project03",
        "moduleTokens": expected_tokens,
        "status": closed_status if passed else incomplete_status,
        "success": passed,
        "singleUninterruptedJob": passed,
        "liveCadApiMayStartForTokens": expected_tokens if passed else [],
        "fullProjectLiveCadReady": False,
        "productionReady": False,
        "checks": checks,
        "steps": step_checks,
        "summaryPath": str(summary_file),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "assemblyPath": str(final_assembly),
        "timingReportPath": str(job_path.parent / "timing-report.json"),
        "executionDurationSeconds": float(job.get("executionDurationSeconds") or 0.0),
        "limitations": limitations,
    }


def build_project03_ae00_ad00_live_adapter_closure(
    summary_path: Path,
) -> dict[str, Any]:
    return _build_project03_live_prefix_closure(
        summary_path,
        expected_tokens=["AE00", "AD00"],
        schema=CHAIN_SCHEMA,
        closed_status="PROJECT03_AE00_AD00_LIVE_ADAPTER_PREFIX_CLOSED",
        incomplete_status="PROJECT03_AE00_AD00_LIVE_ADAPTER_PREFIX_INCOMPLETE",
        limitations=[
            "AE00和AD00静态安装前缀已验证；AI00及后续动作尚未发布到现场CAD API。",
            "AD00的25度翻转扫掠仍未完成动态实体闭环。",
            "安装端口尺寸和相对位置仍来自项目03原型，不是厂商权威基准。",
        ],
    )


def build_project03_ae00_ad00_ai00_live_adapter_closure(
    summary_path: Path,
) -> dict[str, Any]:
    return _build_project03_live_prefix_closure(
        summary_path,
        expected_tokens=["AE00", "AD00", "AI00"],
        schema=THREE_STEP_SCHEMA,
        closed_status="PROJECT03_AE00_AD00_AI00_LIVE_ADAPTER_PREFIX_CLOSED",
        incomplete_status="PROJECT03_AE00_AD00_AI00_LIVE_ADAPTER_PREFIX_INCOMPLETE",
        limitations=[
            "AE00、AD00和AI00静态安装前缀已验证；AG00及后续动作尚未发布到现场CAD API。",
            "AD00的25度翻转扫掠仍未完成动态实体闭环。",
            "AI00的100 mm工作距离和条码目标为CAD代理，不是厂商或现场权威数据。",
            "安装端口尺寸和相对位置仍来自项目03原型，不是厂商权威基准。",
        ],
    )


def build_project03_four_step_live_adapter_closure(
    summary_path: Path,
) -> dict[str, Any]:
    return _build_project03_live_prefix_closure(
        summary_path,
        expected_tokens=["AE00", "AD00", "AI00", "AG00"],
        schema=FOUR_STEP_SCHEMA,
        closed_status="PROJECT03_FOUR_STEP_LIVE_ADAPTER_PREFIX_CLOSED_WITH_AG00_RESIDUAL_ANCHOR",
        incomplete_status="PROJECT03_FOUR_STEP_LIVE_ADAPTER_PREFIX_INCOMPLETE",
        limitations=[
            "AG00静态安装使用显式原型残差姿态锚点补足第六自由度，不是去原型安装规则。",
            "AG00六个服务目标及维护包络仍是CAD代理。",
            "AD00的25度翻转扫掠和AI00权威光学参数尚未闭环。",
            "AH00及后续动作尚未发布到现场CAD API。",
        ],
    )


def write_project03_ae00_ad00_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project03_ae00_ad00_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    return target


def write_project03_ae00_ad00_ai00_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project03_ae00_ad00_ai00_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    return target


def write_project03_four_step_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project03_four_step_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    return target
