"""Release closure for Project01's uninterrupted static live-CAD chain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project01-full-live-adapter-closure/v2"
TOKENS = ["SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_project01_full_live_adapter_closure(summary_path: Path) -> dict[str, Any]:
    summary_file = summary_path.resolve()
    summary = _load(summary_file)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    timing_path = job_path.parent / "timing-report.json"
    timing = _load(timing_path) if timing_path.is_file() else {}
    steps = job.get("steps") or []
    observed_tokens = [str(row.get("moduleToken") or "") for row in steps]

    step_checks: list[dict[str, Any]] = []
    previous_output: Path | None = None
    for index, step in enumerate(steps):
        checkpoint = step.get("checkpoint") or {}
        output = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        source = Path(str(checkpoint.get("inputAssemblyPath") or "")).resolve()
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        gate = _load(gate_path) if gate_path.is_file() else {}
        action_paths = [
            Path(str(value)).resolve()
            for value in checkpoint.get("cadActionEvidencePaths") or []
        ]
        action = _load(action_paths[0]) if len(action_paths) == 1 and action_paths[0].is_file() else {}
        tool = action.get("toolResult") or {}
        token = str(step.get("moduleToken") or "")
        expected_mates = 0 if token == "LM00" else 3
        continuity = index == 0 or (
            previous_output is not None and source == previous_output
        )
        checks = {
            "stepSucceeded": step.get("status") == "succeeded",
            "checkpointContinuity": continuity,
            "cadActionSucceeded": action.get("success") is True,
            "expectedDrivingMateCountCreated": int(tool.get("CreatedMateCount") or 0)
            == expected_mates,
            "targetConstraintStateAccepted": tool.get("TargetConstraintStateAccepted") is True,
            "reopened": tool.get("Reopened") is True,
            "reopenedMateParametersMatch": tool.get("ReopenedMateParametersMatch") is True,
            "finalStaticSnapshotAnchored": token != "LM00"
            or (
                tool.get("TargetCaseAnchored") is True
                and tool.get("CaseAnchorPoseMatch") is True
            ),
            "collisionGateAccepted": gate.get("accepted") is True,
            "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
            "assemblyExists": output.is_file(),
        }
        step_checks.append(
            {
                "moduleToken": token,
                "success": all(checks.values()),
                "checks": checks,
                "inputAssemblyPath": str(source),
                "assemblyPath": str(output),
                "cadActionEvidencePath": str(action_paths[0]) if action_paths else None,
                "collisionGateEvidencePath": str(gate_path),
            }
        )
        previous_output = output

    controlled_resume = summary.get("controlledResume") is True
    prior_rollback = (summary.get("priorFailure") or {}).get("rollback") or {}
    checks = {
        "summarySucceeded": summary.get("status") == "succeeded",
        "jobSucceeded": job.get("status") == "succeeded",
        "singleDurableJob": summary.get("singleDurableJob") is True,
        "controlledResumeWasCheckpointSafe": not controlled_resume
        or (
            prior_rollback.get("mode") == "restore-last-committed-checkpoint"
            and prior_rollback.get("uncommittedOutputAccepted") is False
            and bool(prior_rollback.get("quarantinedArtifactPath"))
        ),
        "expectedOrderedTokens": observed_tokens == TOKENS,
        "everyStepClosed": len(step_checks) == len(TOKENS)
        and all(row["success"] for row in step_checks),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "manifestStaticAccepted": manifest.get("staticExecutionAccepted") is True,
        "timingReportComplete": timing.get("status") == "succeeded"
        and timing.get("jobId") == job.get("jobId"),
        "noRollback": job.get("rollback") is None,
    }
    passed = all(checks.values())
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project01",
        "status": (
            "PROJECT01_SINGLE_DURABLE_JOB_FULL_STATIC_CHAIN_CLOSED"
            if passed
            else "PROJECT01_FULL_LIVE_ADAPTER_CLOSURE_INCOMPLETE"
        ),
        "success": passed,
        "singleDurableJob": passed,
        "singleUninterruptedJob": passed
        and summary.get("singleUninterruptedJob") is True,
        "controlledResume": controlled_resume,
        "liveCadApiMayStartForTokens": TOKENS if passed else [],
        "fullProjectLiveCadReady": passed,
        "productionReady": False,
        "checks": checks,
        "steps": step_checks,
        "summaryPath": str(summary_file),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "assemblyPath": str(previous_output) if previous_output else None,
        "timingReportPath": str(timing_path),
        "executionDurationSeconds": float(job.get("executionDurationSeconds") or 0.0),
        "limitations": [
            "该闭包只验证静态逐步装配，不验证FF00连续翻转。",
            "LM00/ZZ00以已验证刚性父上下文快照插入，不代表独立运动学已重建。",
            "安装端口和行程仍包含项目01原型推断参数，生产发布保持关闭。",
        ],
    }


def write_project01_full_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project01_full_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
