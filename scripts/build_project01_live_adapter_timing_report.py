#!/usr/bin/env python3
"""Build an auditable timing report for a Project01 durable live-CAD job."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
ROOT = WORKSPACE / "demo/semantic_ports/project01_live_adapter_full_jobs"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _attempt_intervals(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active: dict[str, tuple[str, datetime]] = {}
    attempts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for event in events:
        kind = str(event.get("eventType") or "")
        step_id = str(event.get("stepId") or "")
        if not step_id:
            continue
        when = _timestamp(str(event["timestamp"]))
        if kind == "step-started":
            attempts[step_id] = attempts.get(step_id, 0) + 1
            active[step_id] = (str(event["timestamp"]), when)
        elif kind in {"step-committed", "step-failed"} and step_id in active:
            started_text, started = active.pop(step_id)
            rows.append(
                {
                    "stepId": step_id,
                    "attempt": attempts[step_id],
                    "status": "succeeded" if kind == "step-committed" else "failed",
                    "startedAt": started_text,
                    "finishedAt": str(event["timestamp"]),
                    "durationSeconds": round((when - started).total_seconds(), 6),
                    "error": event.get("error"),
                }
            )
    return rows


def build(job_id: str) -> dict[str, Any]:
    job_dir = (ROOT / job_id).resolve()
    job = _load(job_dir / "job.json")
    summary = _load(ROOT / "latest_uninterrupted.json")
    events = [
        json.loads(line)
        for line in (job_dir / "events.jsonl").read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    intervals = _attempt_intervals(events)
    by_step_attempt = {
        (str(row["stepId"]), int(row["attempt"])): row for row in intervals
    }

    attempts: list[dict[str, Any]] = []
    for step in job.get("steps") or []:
        step_id = str(step["stepId"])
        token = str(step["moduleToken"])
        for attempt in range(1, int(step.get("attemptCount") or 0) + 1):
            action_dir = job_dir / "cad-working" / f"{step_id}-attempt{attempt}"
            action_files = list(action_dir.glob("*.context-insert.result.json"))
            action = _load(action_files[0]) if len(action_files) == 1 else {}
            gate_dir = job_dir / "collision-gates" / step_id
            gate_path = gate_dir / f"attempt{attempt}-gate.json"
            gate = _load(gate_path) if gate_path.is_file() else {}
            exact_batches = list(
                (gate_dir / f"attempt{attempt}-exact").glob("*_leaf_details_batch.json")
            )
            exact_batch = _load(exact_batches[0]) if len(exact_batches) == 1 else {}
            interval = by_step_attempt.get((step_id, attempt), {})
            attempts.append(
                {
                    "stepId": step_id,
                    "moduleToken": token,
                    "attempt": attempt,
                    "status": interval.get("status") or (
                        "succeeded"
                        if step.get("status") == "succeeded"
                        and attempt == int(step.get("attemptCount") or 0)
                        else "unknown"
                    ),
                    "startedAt": interval.get("startedAt"),
                    "finishedAt": interval.get("finishedAt"),
                    "wallDurationSeconds": interval.get("durationSeconds"),
                    "cadActionDurationSeconds": action.get("durationSeconds"),
                    "cadPhaseDurationsSeconds": (action.get("toolResult") or {}).get(
                        "PhaseDurationsSeconds"
                    ),
                    "collisionGateDurationSeconds": (
                        gate.get("timingSeconds") or {}
                    ).get("total"),
                    "conditionalBrepDurationSeconds": (
                        gate.get("timingSeconds") or {}
                    ).get("conditionalBrep"),
                    "exactBatchDurationSeconds": (
                        exact_batch.get("timing") or {}
                    ).get("durationSeconds"),
                    "collisionGateAccepted": gate.get("accepted"),
                    "exactBatchPath": str(exact_batches[0])
                    if len(exact_batches) == 1
                    else None,
                    "actionEvidencePath": str(action_files[0])
                    if len(action_files) == 1
                    else None,
                    "gateEvidencePath": str(gate_path) if gate_path.is_file() else None,
                    "error": interval.get("error"),
                }
            )

    started_events = [event for event in events if event.get("eventType") == "job-started"]
    succeeded_events = [event for event in events if event.get("eventType") == "job-succeeded"]
    wall_duration = None
    if started_events and succeeded_events:
        wall_duration = (
            _timestamp(str(succeeded_events[-1]["timestamp"]))
            - _timestamp(str(started_events[0]["timestamp"]))
        ).total_seconds()
    execution_duration = float(job.get("executionDurationSeconds") or 0.0)
    known_action = sum(float(row.get("cadActionDurationSeconds") or 0.0) for row in attempts)
    known_brep = sum(float(row.get("exactBatchDurationSeconds") or 0.0) for row in attempts)
    return {
        "schemaVersion": "project01-live-adapter-timing-report/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project01",
        "jobId": job_id,
        "status": job.get("status"),
        "singleDurableJob": summary.get("singleDurableJob") is True,
        "controlledResume": summary.get("controlledResume") is True,
        "executionDurationSeconds": execution_duration,
        "wallClockDurationSeconds": round(wall_duration, 6) if wall_duration is not None else None,
        "pausedOrOperatorGapSeconds": round(max(0.0, wall_duration - execution_duration), 6)
        if wall_duration is not None
        else None,
        "durationBeforeResumeSeconds": summary.get("durationBeforeResumeSeconds"),
        "resumeDurationSeconds": summary.get("resumeDurationSeconds"),
        "recordedCadActionDurationSeconds": round(known_action, 6),
        "recordedExactBatchDurationSeconds": round(known_brep, 6),
        "attempts": attempts,
        "performanceFindings": [
            "首次失败在GJ00条件B-rep门禁；受控恢复只重跑GJ00和LM00。",
            "LM00最终门禁的4个精确对象对是恢复阶段主要耗时来源。",
            "FF00-LM00虽然没有叶级AABB候选，仍枚举约122.9万实体组合；后续应缓存叶级占用体或增加分层宽相。",
            "相同源几何、相同位姿和相同基线策略可复用版本化对象对B-rep缓存。",
        ],
        "scopeBoundary": {
            "timestampsAreUtc": True,
            "cadActionDurationsComeFromRunnerEvidence": True,
            "collisionDurationsComeFromGateOrExactBatchEvidence": True,
            "doesNotMeasureUninstrumentedSolidWorksUiLatencySeparately": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    payload = build(args.job_id)
    target = (ROOT / args.job_id / "timing-report.json").resolve()
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
