from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "project03-full-live-adapter-closure/v1"
EXPECTED_TOKENS = ["AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"]
EXPECTED_ACTION_COUNTS = {**{token: 1 for token in EXPECTED_TOKENS}, "AB00": 2}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _action_checks(path: Path) -> dict[str, Any]:
    payload = _load(path) if path.is_file() else {}
    result = payload.get("toolResult") or {}
    validations = result.get("ValidationResults") or []
    diagnostics = [str(value) for value in result.get("Diagnostics") or []]
    verified_path_close = any(
        "closed by exact path before reopen" in value.casefold()
        for value in diagnostics
    )
    checks = {
        "evidenceExists": path.is_file(),
        "actionSucceeded": payload.get("success") is True,
        "toolSucceeded": result.get("Success") is True,
        "savedReopened": result.get("Reopened") is True,
        "mateParametersMatch": result.get("ReopenedMateParametersMatch") is True,
        "constraintStateAccepted": result.get("TargetConstraintStateAccepted") is True,
        "mateSolveClean": result.get("MateSolveClean") is True,
        "componentSemanticsMatch": result.get("ComponentSemanticsMatch") is True,
        "semanticValidationsPassed": all(
            validation.get("Passed") is True for validation in validations
        ),
    }
    return {
        "path": str(path),
        "accepted": all(checks.values()),
        "checks": checks,
        "durationSeconds": float(payload.get("durationSeconds") or 0.0),
        "requestedMateCount": int(result.get("RequestedMateCount") or 0),
        "createdMateCount": int(result.get("CreatedMateCount") or 0),
        "validationCount": len(validations),
        "verifiedPathCloseLifecycle": verified_path_close,
    }


def build_project03_full_live_adapter_closure(summary_path: Path) -> dict[str, Any]:
    summary_file = summary_path.resolve()
    summary = _load(summary_file)
    job_path = Path(str(summary.get("jobPath") or "")).resolve()
    manifest_path = Path(str(summary.get("evidenceManifestPath") or "")).resolve()
    independent_audit_path = (
        summary_file.parent
        / "independent_collision_audit"
        / "project03_final_independent_collision_audit.json"
    ).resolve()
    job = _load(job_path) if job_path.is_file() else {}
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    independent_audit = (
        _load(independent_audit_path) if independent_audit_path.is_file() else {}
    )
    events_path = job_path.parent / "events.jsonl"
    events = []
    if events_path.is_file():
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]

    stages: list[dict[str, Any]] = []
    missing: list[str] = []
    rejected: list[dict[str, Any]] = []
    prior_output: Path | None = None
    steps = job.get("steps") or []
    for index, step in enumerate(steps):
        token = str(step.get("moduleToken") or "")
        checkpoint = step.get("checkpoint") or {}
        output = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        input_value = checkpoint.get("inputAssemblyPath")
        input_path = Path(str(input_value)).resolve() if input_value else None
        gate_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        gate = _load(gate_path) if gate_path.is_file() else {}
        action_paths = [
            Path(str(value)).resolve()
            for value in checkpoint.get("cadActionEvidencePaths") or []
        ]
        actions = [_action_checks(path) for path in action_paths]
        for action_index, action in enumerate(actions, start=1):
            if not action["checks"]["evidenceExists"]:
                missing.append(f"{token}:cad-action-{action_index}")
        expected_attempts = 2 if token == "AB00" else 1
        attempts = step.get("attempts") or []
        chain_valid = (
            input_path is None
            if index == 0
            else input_path is not None and input_path == prior_output
        )
        checks = {
            "jobStepSucceeded": step.get("status") == "succeeded",
            "expectedAttemptCount": int(step.get("attemptCount") or 0)
            == expected_attempts
            and len(attempts) == expected_attempts,
            "checkpointContinuity": chain_valid,
            "assemblyExists": output.is_file(),
            "gateEvidenceExists": gate_path.is_file(),
            "collisionGateAccepted": gate.get("accepted") is True,
            "unresolvedPairCountIsZero": int(
                gate.get("unresolvedExactPairCount") or 0
            )
            == 0,
            "expectedCadActionCount": len(actions)
            == EXPECTED_ACTION_COUNTS.get(token, 1),
            "allCadActionsAccepted": bool(actions)
            and all(action["accepted"] for action in actions),
        }
        if not all(checks.values()):
            rejected.append({"moduleToken": token, "checks": checks})
        timing = gate.get("timingSeconds") or {}
        stages.append(
            {
                "moduleToken": token,
                "accepted": all(checks.values()),
                "checks": checks,
                "attemptCount": int(step.get("attemptCount") or 0),
                "attemptDurationSeconds": [
                    float(item.get("durationSeconds") or 0.0) for item in attempts
                ],
                "inputAssemblyPath": str(input_path) if input_path else None,
                "assemblyPath": str(output),
                "gateEvidencePath": str(gate_path),
                "cadActions": actions,
                "collisionSummary": {
                    "pairCount": int(gate.get("pairCount") or 0),
                    "strictAabbAcceptedCount": int(
                        gate.get("strictAabbAcceptedCount") or 0
                    ),
                    "cacheAcceptedCount": int(gate.get("cacheAcceptedCount") or 0),
                    "installationContactAcceptedCount": int(
                        gate.get("installationContactAcceptedCount") or 0
                    ),
                    "unresolvedExactPairCount": int(
                        gate.get("unresolvedExactPairCount") or 0
                    ),
                    "conditionalBrepSeconds": float(
                        timing.get("conditionalBrep") or 0.0
                    ),
                    "gateDurationSeconds": float(timing.get("total") or 0.0),
                },
            }
        )
        prior_output = output

    observed_tokens = [stage["moduleToken"] for stage in stages]
    final_checkpoint = job.get("lastCommittedCheckpoint") or {}
    final_assembly = Path(str(final_checkpoint.get("assemblyPath") or "")).resolve()
    event_types = [str(event.get("eventType") or "") for event in events]
    ab_step = next(
        (step for step in steps if step.get("moduleToken") == "AB00"), {}
    )
    ab_attempts = ab_step.get("attempts") or []
    ab_stage = next(
        (stage for stage in stages if stage.get("moduleToken") == "AB00"), {}
    )
    prior_failure = summary.get("priorFailure") or {}
    recovery_checks = {
        "ab00HasFailedThenSuccessfulAttempts": len(ab_attempts) == 2
        and all(item.get("completedAt") for item in ab_attempts),
        "rollbackWasRecorded": (
            (prior_failure.get("rollback") or {}).get("mode")
            == "restore-last-committed-checkpoint"
        ),
        "sameTitleFailureWasRecorded": "swFileWithSameTitleAlreadyOpen"
        in str(prior_failure.get("error") or ""),
        "resumeEventRecorded": "job-resumed" in event_types,
        "recoveredActionsUseVerifiedPathCloseLifecycle": bool(
            ab_stage.get("cadActions")
        )
        and all(
            action.get("verifiedPathCloseLifecycle") is True
            for action in ab_stage.get("cadActions") or []
        ),
        "finalRollbackCleared": job.get("rollback") is None,
        "finalErrorCleared": job.get("error") is None,
    }
    global_checks = {
        "summarySucceeded": summary.get("status") == "succeeded",
        "jobSucceeded": job.get("status") == "succeeded",
        "expectedSequence": observed_tokens == EXPECTED_TOKENS,
        "singleDurableJobWithoutExternalSeed": not job.get(
            "initialCommittedCheckpoint"
        ),
        "manifestEvidenceComplete": manifest.get("evidenceComplete") is True,
        "manifestStaticExecutionAccepted": manifest.get(
            "staticExecutionAccepted"
        )
        is True,
        "finalAssemblyExists": final_assembly.is_file(),
        "independentFinal45PairCollisionAuditAccepted": all(
            (
                independent_audit.get("success") is True,
                int(independent_audit.get("pairCount") or 0) == 45,
                int(independent_audit.get("unresolvedExactPairCount") or 0) == 0,
                Path(str(independent_audit.get("assemblyPath") or "")).resolve()
                == final_assembly,
            )
        ),
        "allStagesAccepted": bool(stages)
        and all(stage["accepted"] for stage in stages),
        "controlledRecoveryClosed": all(recovery_checks.values()),
        "noMissingEvidence": not missing,
        "noRejectedEvidence": not rejected,
    }
    success = all(global_checks.values())
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project03",
        "status": (
            "PROJECT03_SINGLE_DURABLE_JOB_FULL_STATIC_CHAIN_CLOSED_AFTER_CONTROLLED_RESUME"
            if success
            else "PROJECT03_FULL_LIVE_ADAPTER_CLOSURE_INCOMPLETE"
        ),
        "success": success,
        "allActionsLiveCadValidated": success,
        "liveCadApiMayStartForTokens": EXPECTED_TOKENS if success else [],
        "singleDurableJob": True,
        "controlledResumeUsed": True,
        "unseededJob": not job.get("initialCommittedCheckpoint"),
        "expectedTokens": EXPECTED_TOKENS,
        "observedTokens": observed_tokens,
        "globalChecks": global_checks,
        "recoveryChecks": recovery_checks,
        "totalMeasuredDurationSeconds": float(
            job.get("executionDurationSeconds") or 0.0
        ),
        "failedAttemptDurationSeconds": float(
            ab_attempts[0].get("durationSeconds") or 0.0
        )
        if len(ab_attempts) > 1
        else 0.0,
        "summaryPath": str(summary_file),
        "jobPath": str(job_path),
        "evidenceManifestPath": str(manifest_path),
        "eventsPath": str(events_path),
        "timingReportPath": str(job_path.parent / "timing-report.json"),
        "independentCollisionAuditPath": str(independent_audit_path),
        "independentCollisionSummary": {
            "pairCount": int(independent_audit.get("pairCount") or 0),
            "strictAabbAcceptedCount": int(
                independent_audit.get("strictAabbAcceptedCount") or 0
            ),
            "cacheAcceptedCount": int(
                independent_audit.get("cacheAcceptedCount") or 0
            ),
            "conditionalBrepSeconds": float(
                independent_audit.get("conditionalBrepSeconds") or 0.0
            ),
            "unresolvedExactPairCount": int(
                independent_audit.get("unresolvedExactPairCount") or 0
            ),
        },
        "finalAssemblyPath": str(final_assembly),
        "missingEvidence": missing,
        "rejectedEvidence": rejected,
        "stages": stages,
        "productionReady": False,
        "productionBlockers": [
            "AG00与AB00仍使用显式原型残差姿态锚点，尚未替换为厂商安装基准。",
            "AC00是完整静态几何混合快照，不保留原始内部层级、配合图和运动语义。",
            "AD00动态翻转扫掠、龙门权威行程、光学距离和供胶软管维护空间仍未完成现场验收。",
        ],
    }


def write_project03_full_live_adapter_closure(
    summary_path: Path, output_path: Path
) -> Path:
    payload = build_project03_full_live_adapter_closure(summary_path)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)
    return target
