from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts/build_project01_live_adapter_timing_report.py"
)
SPEC = importlib.util.spec_from_file_location("project01_timing_report", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_timing_report_includes_failed_attempt_and_controlled_resume(
    tmp_path: Path,
) -> None:
    MODULE.ROOT = tmp_path
    job_id = "project01-job-fixture"
    job_dir = tmp_path / job_id
    _write(
        tmp_path / "latest_uninterrupted.json",
        {
            "singleDurableJob": True,
            "controlledResume": True,
            "durationBeforeResumeSeconds": 5.0,
            "resumeDurationSeconds": 7.0,
        },
    )
    _write(
        job_dir / "job.json",
        {
            "jobId": job_id,
            "status": "succeeded",
            "executionDurationSeconds": 12.0,
            "steps": [
                {
                    "stepId": "step-01-gj00",
                    "moduleToken": "GJ00",
                    "status": "succeeded",
                    "attemptCount": 2,
                }
            ],
        },
    )
    events = [
        {"timestamp": "2026-01-01T00:00:00Z", "eventType": "job-started"},
        {
            "timestamp": "2026-01-01T00:00:01Z",
            "eventType": "step-started",
            "stepId": "step-01-gj00",
        },
        {
            "timestamp": "2026-01-01T00:00:06Z",
            "eventType": "step-failed",
            "stepId": "step-01-gj00",
            "error": "collision",
        },
        {"timestamp": "2026-01-01T00:00:08Z", "eventType": "job-started"},
        {
            "timestamp": "2026-01-01T00:00:09Z",
            "eventType": "step-started",
            "stepId": "step-01-gj00",
        },
        {
            "timestamp": "2026-01-01T00:00:15Z",
            "eventType": "step-committed",
            "stepId": "step-01-gj00",
        },
        {"timestamp": "2026-01-01T00:00:16Z", "eventType": "job-succeeded"},
    ]
    (job_dir / "events.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (job_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(row) for row in events) + "\n",
        encoding="utf-8",
    )
    for attempt, duration in ((1, 2.0), (2, 3.0)):
        _write(
            job_dir
            / f"cad-working/step-01-gj00-attempt{attempt}/result.context-insert.result.json",
            {"durationSeconds": duration, "toolResult": {"PhaseDurationsSeconds": {}}},
        )
    _write(
        job_dir / "collision-gates/step-01-gj00/attempt2-gate.json",
        {"accepted": True, "timingSeconds": {"total": 2.5, "conditionalBrep": 2.0}},
    )

    result = MODULE.build(job_id)

    assert result["status"] == "succeeded"
    assert result["controlledResume"] is True
    assert result["wallClockDurationSeconds"] == 16.0
    assert result["pausedOrOperatorGapSeconds"] == 4.0
    assert [row["status"] for row in result["attempts"]] == ["failed", "succeeded"]
    assert result["recordedCadActionDurationSeconds"] == 5.0
