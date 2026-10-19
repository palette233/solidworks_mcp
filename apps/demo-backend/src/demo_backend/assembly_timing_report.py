from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIMING_REPORT_SCHEMA = "assembly-timing-report/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _try_load(path: Path) -> dict[str, Any] | None:
    try:
        value = _load(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _round(value: float) -> float:
    return round(float(value), 6)


def build_assembly_timing_report(job_directory: Path) -> dict[str, Any]:
    directory = job_directory.resolve()
    job_path = directory / "job.json"
    if not job_path.is_file():
        raise FileNotFoundError(f"Assembly job does not exist: {job_path}")
    job = _load(job_path)
    preflight_path = directory / "preflight.json"
    preflight = _load(preflight_path) if preflight_path.is_file() else {}
    rows: list[dict[str, Any]] = []
    phase_totals: dict[str, float] = {}
    action_total = 0.0
    gate_total = 0.0
    gate_and_orchestration_total = 0.0
    recovered_attempt_total = 0.0

    for step in job.get("steps") or []:
        checkpoint = step.get("checkpoint") or {}
        attempts = step.get("attempts") or [{}]
        attempt = attempts[-1]
        step_total = float(attempt.get("durationSeconds") or 0.0)
        all_attempt_total = sum(
            float(item.get("durationSeconds") or 0.0) for item in attempts
        )
        recovered_attempt_duration = max(0.0, all_attempt_total - step_total)
        recovered_attempt_total += recovered_attempt_duration
        actions = []
        step_action_total = 0.0
        action_values = list(checkpoint.get("cadActionEvidencePaths") or [])
        if not action_values:
            action_values = [
                str(path)
                for path in sorted(
                    (directory / "cad-working").glob(
                        f"{step.get('stepId')}-attempt*-action*.context-insert.result.json"
                    )
                )
            ]
        for value in action_values:
            path = Path(str(value)).resolve()
            if not path.is_file():
                actions.append({"path": str(path), "exists": False})
                continue
            payload = _try_load(path)
            if payload is None:
                actions.append(
                    {
                        "path": str(path),
                        "exists": True,
                        "readableJson": False,
                        "durationSeconds": 0.0,
                        "countedInCadActionTotal": False,
                        "evidenceRole": "non-json-supporting-evidence",
                        "phaseDurationsSeconds": {},
                    }
                )
                continue
            duration = float(payload.get("durationSeconds") or 0.0)
            supplemental_stage_result = all(
                (
                    payload.get("stageId") is not None,
                    payload.get("accepted") is not None,
                    payload.get("targetCheckpointPath") is not None,
                    payload.get("success") is None,
                )
            )
            counted_duration = 0.0 if supplemental_stage_result else duration
            phases = (
                (payload.get("toolResult") or {}).get("PhaseDurationsSeconds")
                or payload.get("phaseDurationsSeconds")
                or {}
            )
            normalized_phases = {str(key): _round(float(value)) for key, value in phases.items()}
            for key, value in normalized_phases.items():
                phase_totals[key] = phase_totals.get(key, 0.0) + value
            step_action_total += counted_duration
            actions.append(
                {
                    "path": str(path),
                    "exists": True,
                    "durationSeconds": _round(duration),
                    "countedInCadActionTotal": not supplemental_stage_result,
                    "evidenceRole": (
                        "supplemental-stage-result"
                        if supplemental_stage_result
                        else "primary-cad-action"
                    ),
                    "phaseDurationsSeconds": normalized_phases,
                }
            )
        action_total += step_action_total
        gate_path = checkpoint.get("evidencePath")
        gate_duration = 0.0
        if gate_path and Path(str(gate_path)).is_file():
            gate_payload = _try_load(Path(str(gate_path)).resolve()) or {}
            gate_duration = float((gate_payload.get("timingSeconds") or {}).get("total") or 0.0)
        gate_total += gate_duration
        residual = max(0.0, step_total - step_action_total)
        orchestration_residual = max(0.0, residual - gate_duration)
        gate_and_orchestration_total += residual
        rows.append(
            {
                "stepId": step.get("stepId"),
                "moduleToken": step.get("moduleToken"),
                "status": step.get("status"),
                "attemptCount": int(step.get("attemptCount") or len(attempts)),
                "attemptDurationsSeconds": [
                    _round(float(item.get("durationSeconds") or 0.0))
                    for item in attempts
                ],
                "stepDurationSeconds": _round(step_total),
                "allAttemptsDurationSeconds": _round(all_attempt_total),
                "recoveredFailedOrInterruptedAttemptDurationSeconds": _round(
                    recovered_attempt_duration
                ),
                "cadActionDurationSeconds": _round(step_action_total),
                "collisionGateDurationSeconds": _round(gate_duration),
                "orchestrationResidualSeconds": _round(orchestration_residual),
                "gateAndOrchestrationResidualSeconds": _round(residual),
                "cadActions": actions,
                "gateEvidencePath": gate_path,
                "gateEvidenceExists": bool(gate_path and Path(str(gate_path)).is_file()),
                "orchestratorTimingBreakdown": checkpoint.get("timingBreakdown") or {},
            }
        )

    total = float(job.get("executionDurationSeconds") or 0.0)
    return {
        "schemaVersion": TIMING_REPORT_SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job.get("jobId"),
        "executionMode": job.get("executionMode"),
        "status": job.get("status"),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
        "preflightTimingSeconds": {
            "pipelineAudit": float(
                ((preflight.get("pipelineAudit") or {}).get("timingSeconds") or {}).get("total")
                or 0.0
            ),
            "naturalLanguageParseAndPlan": float(
                ((preflight.get("previewAudit") or {}).get("timingSeconds") or {}).get("total")
                or (preflight.get("naturalLanguageCompilation") or {}).get("totalSeconds")
                or 0.0
            ),
        },
        "preflightPhaseBreakdownSeconds": (
            (preflight.get("naturalLanguageCompilation") or {}).get("phasesSeconds")
            or {}
        ),
        "totalDurationSeconds": _round(total),
        "cadActionDurationSeconds": _round(action_total),
        "collisionGateDurationSeconds": _round(gate_total),
        "orchestrationResidualSeconds": _round(
            max(0.0, gate_and_orchestration_total - gate_total)
        ),
        "gateAndOrchestrationResidualSeconds": _round(gate_and_orchestration_total),
        "recoveredFailedOrInterruptedAttemptDurationSeconds": _round(
            recovered_attempt_total
        ),
        "unattributedJobOverheadSeconds": _round(
            max(
                0.0,
                total
                - action_total
                - gate_and_orchestration_total
                - recovered_attempt_total,
            )
        ),
        "cadPhaseTotalsSeconds": {
            key: _round(value) for key, value in sorted(phase_totals.items())
        },
        "steps": rows,
    }


def write_assembly_timing_report(job_directory: Path) -> Path:
    directory = job_directory.resolve()
    payload = build_assembly_timing_report(directory)
    target = directory / "timing-report.json"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
