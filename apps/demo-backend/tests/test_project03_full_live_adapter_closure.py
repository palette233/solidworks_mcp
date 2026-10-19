from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_full_live_adapter_closure import (
    EXPECTED_TOKENS,
    build_project03_full_live_adapter_closure,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    job_dir = tmp_path / "job"
    steps = []
    previous = None
    for index, token in enumerate(EXPECTED_TOKENS, start=1):
        output = job_dir / f"{index}-{token}.SLDASM"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"assembly")
        gate = job_dir / f"{index}-{token}-gate.json"
        _write(
            gate,
            {
                "accepted": True,
                "unresolvedExactPairCount": 0,
                "pairCount": index,
                "timingSeconds": {"total": 1.0},
            },
        )
        action_paths = []
        for action_index in range(2 if token == "AB00" else 1):
            action = job_dir / f"{index}-{token}-action{action_index}.json"
            _write(
                action,
                {
                    "success": True,
                    "durationSeconds": 2.0,
                    "toolResult": {
                        "Success": True,
                        "Reopened": True,
                        "ReopenedMateParametersMatch": True,
                        "TargetConstraintStateAccepted": True,
                        "MateSolveClean": True,
                        "ComponentSemanticsMatch": True,
                        "ValidationResults": [],
                        "Diagnostics": [
                            "Saved output document was closed by exact path before reopen."
                        ],
                    },
                },
            )
            action_paths.append(str(action))
        attempt_count = 2 if token == "AB00" else 1
        attempts = [
            {
                "attempt": attempt,
                "completedAt": "2026-01-01T00:00:00Z",
                "durationSeconds": float(attempt),
            }
            for attempt in range(1, attempt_count + 1)
        ]
        steps.append(
            {
                "moduleToken": token,
                "status": "succeeded",
                "attemptCount": attempt_count,
                "attempts": attempts,
                "checkpoint": {
                    "inputAssemblyPath": str(previous) if previous else None,
                    "assemblyPath": str(output),
                    "evidencePath": str(gate),
                    "cadActionEvidencePaths": action_paths,
                },
            }
        )
        previous = output
    job = {
        "status": "succeeded",
        "steps": steps,
        "lastCommittedCheckpoint": steps[-1]["checkpoint"],
        "rollback": None,
        "error": None,
        "executionDurationSeconds": 20.0,
    }
    job_path = job_dir / "job.json"
    manifest_path = job_dir / "evidence-manifest.json"
    _write(job_path, job)
    _write(
        manifest_path,
        {"evidenceComplete": True, "staticExecutionAccepted": True},
    )
    (job_dir / "events.jsonl").write_text(
        json.dumps({"eventType": "job-resumed"}) + "\n", encoding="utf-8"
    )
    summary_path = tmp_path / "summary.json"
    _write(
        summary_path,
        {
            "status": "succeeded",
            "jobPath": str(job_path),
            "evidenceManifestPath": str(manifest_path),
            "priorFailure": {
                "error": "swFileWithSameTitleAlreadyOpen",
                "rollback": {"mode": "restore-last-committed-checkpoint"},
            },
        },
    )
    _write(
        tmp_path
        / "independent_collision_audit"
        / "project03_final_independent_collision_audit.json",
        {
            "success": True,
            "assemblyPath": str(previous),
            "pairCount": 45,
            "strictAabbAcceptedCount": 22,
            "cacheAcceptedCount": 23,
            "conditionalBrepSeconds": 0.0,
            "unresolvedExactPairCount": 0,
        },
    )
    return summary_path


def test_full_live_adapter_closes_controlled_resume(tmp_path: Path) -> None:
    result = build_project03_full_live_adapter_closure(_fixture(tmp_path))

    assert result["success"] is True
    assert result["observedTokens"] == EXPECTED_TOKENS
    assert result["recoveryChecks"]["resumeEventRecorded"] is True
    assert result["stages"][-1]["attemptCount"] == 2
    assert len(result["stages"][-1]["cadActions"]) == 2


def test_full_live_adapter_rejects_unresolved_collision(tmp_path: Path) -> None:
    summary = _fixture(tmp_path)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    job = json.loads(Path(payload["jobPath"]).read_text(encoding="utf-8"))
    gate = Path(job["steps"][-1]["checkpoint"]["evidencePath"])
    gate_payload = json.loads(gate.read_text(encoding="utf-8"))
    gate_payload["unresolvedExactPairCount"] = 1
    _write(gate, gate_payload)

    result = build_project03_full_live_adapter_closure(summary)

    assert result["success"] is False
    assert result["globalChecks"]["allStagesAccepted"] is False
