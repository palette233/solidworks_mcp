from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project05-live-adapter-closure/v1"
EXPECTED_TOKENS = ["D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _action_evidence_accepted(path: Path) -> bool:
    if not path.is_file():
        return False
    payload = _load(path)
    return payload.get("success") is True or payload.get("accepted") is True


def build_project05_uninterrupted_live_closure(
    summary_path: Path,
) -> dict[str, Any]:
    """Validate one unseeded D000-to-B000 live-CAD job and its checkpoint chain."""

    summary_file = summary_path.resolve()
    summary = _load(summary_file)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    missing: list[str] = []
    rejected: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    prior_output: Path | None = None

    for step in job.get("steps") or []:
        token = str(step.get("moduleToken") or "")
        checkpoint = step.get("checkpoint") or {}
        input_path = Path(str(checkpoint.get("inputAssemblyPath") or "")).resolve()
        output_path = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        gate = _load(gate_path) if gate_path.is_file() else {}
        action_paths = [
            Path(str(value)).resolve()
            for value in checkpoint.get("cadActionEvidencePaths") or []
        ]
        for index, action_path in enumerate(action_paths, start=1):
            if not action_path.is_file():
                missing.append(f"{token}:cad-action-{index}")
        declared_source_paths: list[Path] = []
        for action_path in action_paths:
            if not action_path.is_file():
                continue
            action_payload = _load(action_path)
            source_values = [
                action_payload.get("resumeCheckpoint"),
                action_payload.get("sourceCheckpointPath"),
            ]
            source_values.extend(
                stage.get("sourceCheckpointPath")
                for stage in action_payload.get("stages") or []
                if isinstance(stage, dict)
            )
            for source_value in source_values:
                if source_value:
                    declared_source_paths.append(Path(str(source_value)).resolve())
        if prior_output is None:
            # The executor passes ``None`` to the first runner. The Project05
            # adapter resolves that to the versioned A000 base internally and
            # records it in the stage result.
            chain_input_valid = input_path.is_file() or any(
                path.is_file() for path in declared_source_paths
            )
        else:
            chain_input_valid = input_path.is_file() and input_path == prior_output
        checks = {
            "jobStepSucceeded": step.get("status") == "succeeded",
            "singleAttempt": int(step.get("attemptCount") or 0) == 1,
            "checkpointInputExistsAndIsPreviousOutput": chain_input_valid,
            "assemblyExists": output_path.is_file(),
            "gateEvidenceExists": gate_path.is_file(),
            "collisionGateAccepted": gate.get("accepted") is True,
            "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
            "cadActionEvidenceComplete": bool(action_paths)
            and all(_action_evidence_accepted(path) for path in action_paths),
        }
        if not all(checks.values()):
            rejected.append({"moduleToken": token, "checks": checks})
        attempts = step.get("attempts") or []
        timing = gate.get("timingSeconds") or {}
        stages.append(
            {
                "moduleToken": token,
                "durationSeconds": sum(
                    float(item.get("durationSeconds") or 0.0) for item in attempts
                ),
                "inputAssemblyPath": (
                    str(input_path)
                    if checkpoint.get("inputAssemblyPath")
                    else str(next((path for path in declared_source_paths if path.is_file()), declared_source_paths[0]))
                    if declared_source_paths
                    else None
                ),
                "assemblyPath": str(output_path),
                "evidencePath": str(gate_path),
                "accepted": all(checks.values()),
                "checks": checks,
                "collisionSummary": {
                    "pairCount": int(gate.get("pairCount") or 0),
                    "strictAabbAcceptedCount": int(gate.get("strictAabbAcceptedCount") or 0),
                    "cacheAcceptedCount": int(gate.get("cacheAcceptedCount") or 0),
                    "installationContactAcceptedCount": int(
                        gate.get("installationContactAcceptedCount") or 0
                    ),
                    "unresolvedExactPairCount": int(
                        gate.get("unresolvedExactPairCount") or 0
                    ),
                    "conditionalBrepSeconds": float(
                        timing.get("conditionalBrep") or 0.0
                    )
                    if isinstance(timing, dict)
                    else 0.0,
                    "gateDurationSeconds": float(timing.get("total") or 0.0)
                    if isinstance(timing, dict)
                    else float(timing or 0.0),
                },
            }
        )
        prior_output = output_path

    observed_tokens = [stage["moduleToken"] for stage in stages]
    final_checkpoint = job.get("lastCommittedCheckpoint") or {}
    final_assembly = Path(str(final_checkpoint.get("assemblyPath") or "")).resolve()
    no_external_seed = not job.get("initialCommittedCheckpoint")
    passed = all(
        (
            summary.get("singleUninterruptedJob") is True,
            summary.get("status") == "succeeded",
            job.get("status") == "succeeded",
            observed_tokens == EXPECTED_TOKENS,
            no_external_seed,
            job.get("rollback") is None,
            job.get("error") is None,
            manifest.get("evidenceComplete") is True,
            manifest.get("staticExecutionAccepted") is True,
            final_assembly.is_file(),
            not missing,
            not rejected,
            all(stage["accepted"] for stage in stages),
        )
    )
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project05",
        "status": (
            "PROJECT05_LIVE_ADAPTER_UNINTERRUPTED_FULL_CHAIN_CLOSED"
            if passed
            else "PROJECT05_LIVE_ADAPTER_UNINTERRUPTED_CLOSURE_INCOMPLETE"
        ),
        "expectedTokens": EXPECTED_TOKENS,
        "observedTokens": observed_tokens,
        "allActionsLiveCadValidated": passed,
        "liveCadApiMayStart": passed,
        "singleUninterruptedJob": True,
        "unseededJob": no_external_seed,
        "productionReady": False,
        "productionBlockers": [
            "B000/Z000权威机械行程限位尚未提供",
            "动态运动扫掠、软管/供胶可达和维护空间尚未形成现场验收证据",
            "F000扫描与M000视觉光学基准仍含原型估计参数",
        ],
        "totalMeasuredDurationSeconds": float(
            job.get("executionDurationSeconds") or 0.0
        ),
        "totalMeasuredDurationMinutes": float(
            job.get("executionDurationSeconds") or 0.0
        )
        / 60.0,
        "summaryPath": str(summary_file),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "finalAssemblyPath": str(final_assembly),
        "finalAssemblyExists": final_assembly.is_file(),
        "missingEvidence": missing,
        "rejectedEvidence": rejected,
        "stages": stages,
    }


def build_project05_live_adapter_closure(
    *,
    pilot_stage_path: Path,
    tail_summary_path: Path,
) -> dict[str, Any]:
    """Consolidate the D000 pilot and the seeded tail into one auditable release gate.

    The resulting artifact deliberately does not claim that the eight actions were
    executed by one uninterrupted job.  It proves that every action in the chain
    has passed the same live-CAD save/reopen and pair-local collision gates.
    """

    pilot_path = pilot_stage_path.resolve()
    tail_path = tail_summary_path.resolve()
    pilot = _load(pilot_path)
    pilot_execution_path = pilot_path.parent / "project05_ordered_direct_execution.json"
    pilot_execution = _load(pilot_execution_path) if pilot_execution_path.is_file() else {}
    tail = _load(tail_path)
    job_path = Path(str(tail.get("jobPath") or "")).resolve()
    manifest_path = Path(str(tail.get("evidenceManifestPath") or "")).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}

    missing: list[str] = []
    rejected: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []

    pilot_assembly = Path(str(pilot.get("targetCheckpointPath") or "")).resolve()
    pilot_checks = {
        "stageAccepted": pilot.get("accepted") is True,
        "topLevelAudit": (pilot.get("topLevelAudit") or {}).get("success") is True,
        "poseAudit": (pilot.get("poseAudit") or {}).get("success") is True,
        "leafExtentAudit": (pilot.get("boundingBoxExtentAudit") or {}).get("success") is True,
        "assemblyExists": pilot_assembly.is_file(),
    }
    if not all(pilot_checks.values()):
        rejected.append({"moduleToken": "D000", "checks": pilot_checks})
    stages.append(
        {
            "moduleToken": "D000",
            "executionSource": "verified-pilot",
            "durationSeconds": float(pilot.get("durationSeconds") or 0.0),
            "assemblyPath": str(pilot_assembly),
            "evidencePath": str(pilot_path),
            "accepted": all(pilot_checks.values()),
            "checks": pilot_checks,
        }
    )

    for step in job.get("steps") or []:
        token = str(step.get("moduleToken") or "")
        checkpoint = step.get("checkpoint") or {}
        assembly_path = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        gate = _load(gate_path) if gate_path.is_file() else {}
        action_paths = [Path(str(value)).resolve() for value in checkpoint.get("cadActionEvidencePaths") or []]
        action_success: list[bool] = []
        for index, action_path in enumerate(action_paths, start=1):
            if not action_path.is_file():
                missing.append(f"{token}:cad-action-{index}")
                action_success.append(False)
            else:
                action_payload = _load(action_path)
                action_success.append(
                    action_payload.get("success") is True
                    or action_payload.get("accepted") is True
                )
        checks = {
            "jobStepSucceeded": step.get("status") == "succeeded",
            "assemblyExists": assembly_path.is_file(),
            "gateEvidenceExists": gate_path.is_file(),
            "collisionGateAccepted": gate.get("accepted") is True,
            "unresolvedPairCountIsZero": int(gate.get("unresolvedExactPairCount") or 0) == 0,
            "cadActionEvidenceComplete": bool(action_paths) and all(action_success),
        }
        if not all(checks.values()):
            rejected.append({"moduleToken": token, "checks": checks})
        attempts = step.get("attempts") or []
        duration = sum(float(item.get("durationSeconds") or 0.0) for item in attempts)
        timing = gate.get("timingSeconds") or {}
        gate_duration = (
            float(timing.get("total") or 0.0)
            if isinstance(timing, dict)
            else float(timing or 0.0)
        )
        stages.append(
            {
                "moduleToken": token,
                "executionSource": "seeded-durable-job",
                "durationSeconds": duration,
                "assemblyPath": str(assembly_path),
                "evidencePath": str(gate_path),
                "accepted": all(checks.values()),
                "checks": checks,
                "collisionSummary": {
                    "pairCount": int(gate.get("pairCount") or 0),
                    "strictAabbAcceptedCount": int(gate.get("strictAabbAcceptedCount") or 0),
                    "cacheAcceptedCount": int(gate.get("cacheAcceptedCount") or 0),
                    "installationContactAcceptedCount": int(
                        gate.get("installationContactAcceptedCount") or 0
                    ),
                    "exactBrepBatchExecuted": bool(gate.get("exactBatchEvidencePath")),
                    "gateDurationSeconds": gate_duration,
                },
            }
        )

    observed_tokens = [stage["moduleToken"] for stage in stages]
    final_checkpoint = job.get("lastCommittedCheckpoint") or {}
    final_assembly = Path(str(final_checkpoint.get("assemblyPath") or "")).resolve()
    evidence_complete = manifest.get("evidenceComplete") is True
    all_actions_validated = all(
        (
            observed_tokens == EXPECTED_TOKENS,
            pilot.get("accepted") is True,
            job.get("status") == "succeeded",
            tail.get("status") == "succeeded",
            evidence_complete,
            final_assembly.is_file(),
            not missing,
            not rejected,
            all(stage["accepted"] for stage in stages),
        )
    )
    committed_step_duration = sum(float(stage["durationSeconds"]) for stage in stages)
    pilot_pipeline_duration = float(
        pilot_execution.get("durationSeconds") or pilot.get("durationSeconds") or 0.0
    )
    tail_pipeline_duration = float(job.get("executionDurationSeconds") or 0.0)
    measured_end_to_end_duration = pilot_pipeline_duration + tail_pipeline_duration
    status = (
        "PROJECT05_LIVE_ADAPTER_FULL_ACTION_CHAIN_CLOSED_WITH_D000_SEED_HANDOFF"
        if all_actions_validated
        else "PROJECT05_LIVE_ADAPTER_CLOSURE_INCOMPLETE"
    )
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project05",
        "status": status,
        "expectedTokens": EXPECTED_TOKENS,
        "observedTokens": observed_tokens,
        "allActionsLiveCadValidated": all_actions_validated,
        "liveCadApiMayStart": all_actions_validated,
        "singleUninterruptedJob": False,
        "singleJobLimitation": (
            "D000由独立试点作业验证，K000至B000由已验证D000检查点接续；"
            "尚未执行一次从A000基座开始的八动作不间断作业。"
        ),
        "productionReady": False,
        "productionBlockers": [
            "B000/Z000权威机械行程限位尚未提供",
            "动态运动扫掠、软管/供胶可达和维护空间尚未形成现场验收证据",
            "F000扫描与M000视觉光学基准仍含原型估计参数",
        ],
        "totalCommittedStepDurationSeconds": committed_step_duration,
        "totalMeasuredDurationSeconds": measured_end_to_end_duration,
        "totalMeasuredDurationMinutes": measured_end_to_end_duration / 60.0,
        "timingBoundary": {
            "pilotPipelineDurationSeconds": pilot_pipeline_duration,
            "tailJobDurationSeconds": tail_pipeline_duration,
            "note": "包含D000试点完整运行时间与接续作业墙钟时间；两段之间的人工间隔不计入。",
        },
        "pilotStagePath": str(pilot_path),
        "pilotExecutionPath": str(pilot_execution_path),
        "tailSummaryPath": str(tail_path),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "manifestEvidenceComplete": evidence_complete,
        "finalAssemblyPath": str(final_assembly),
        "finalAssemblyExists": final_assembly.is_file(),
        "missingEvidence": missing,
        "rejectedEvidence": rejected,
        "stages": stages,
    }


def write_project05_live_adapter_closure(
    *,
    pilot_stage_path: Path,
    tail_summary_path: Path,
    output_path: Path,
    uninterrupted_summary_path: Path | None = None,
) -> Path:
    payload = (
        build_project05_uninterrupted_live_closure(uninterrupted_summary_path)
        if uninterrupted_summary_path is not None
        and uninterrupted_summary_path.resolve().is_file()
        else build_project05_live_adapter_closure(
            pilot_stage_path=pilot_stage_path,
            tail_summary_path=tail_summary_path,
        )
    )
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target
