from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project01_live_adapter_closure import (
    TOKENS,
    build_project01_full_live_adapter_closure,
)


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture(tmp_path: Path, *, break_gate: bool = False) -> Path:
    job_root = tmp_path / "job"
    job_root.mkdir(parents=True)
    previous = None
    steps = []
    for index, token in enumerate(TOKENS, start=1):
        output = job_root / f"step-{index:02d}-{token}.SLDASM"
        output.write_bytes(b"assembly")
        action = _write(
            job_root / f"step-{index:02d}-{token}.action.json",
            {
                "success": True,
                "toolResult": {
                    "CreatedMateCount": 0 if token == "LM00" else 3,
                    "TargetConstraintStateAccepted": True,
                    "Reopened": True,
                    "ReopenedMateParametersMatch": True,
                    "TargetCaseAnchored": token == "LM00",
                    "CaseAnchorPoseMatch": token == "LM00",
                },
            },
        )
        gate = _write(
            job_root / f"step-{index:02d}-{token}.gate.json",
            {
                "accepted": not (break_gate and token == "GN00"),
                "unresolvedExactPairCount": 1 if break_gate and token == "GN00" else 0,
            },
        )
        steps.append(
            {
                "moduleToken": token,
                "status": "succeeded",
                "checkpoint": {
                    "inputAssemblyPath": str(previous or (tmp_path / "base.SLDASM")),
                    "assemblyPath": str(output),
                    "evidencePath": str(gate),
                    "cadActionEvidencePaths": [str(action)],
                },
            }
        )
        previous = output
    job = _write(
        job_root / "job.json",
        {
            "status": "succeeded",
            "steps": steps,
            "rollback": None,
            "executionDurationSeconds": 123.0,
        },
    )
    manifest = _write(
        job_root / "evidence-manifest.json",
        {"evidenceComplete": True, "staticExecutionAccepted": True},
    )
    _write(
        job_root / "timing-report.json",
        {
            "schemaVersion": "project01-live-adapter-timing-report/v1",
            "status": "succeeded",
            "jobId": "job-fixture",
        },
    )
    job_payload = json.loads(job.read_text(encoding="utf-8"))
    job_payload["jobId"] = "job-fixture"
    job.write_text(json.dumps(job_payload), encoding="utf-8")
    return _write(
        tmp_path / "latest.json",
        {
            "status": "succeeded",
            "singleDurableJob": True,
            "singleUninterruptedJob": True,
            "controlledResume": False,
            "jobPath": str(job),
            "evidenceManifestPath": str(manifest),
        },
    )


def test_project01_full_live_adapter_closure_accepts_complete_chain(
    tmp_path: Path,
) -> None:
    result = build_project01_full_live_adapter_closure(_fixture(tmp_path))
    assert result["success"] is True
    assert result["singleDurableJob"] is True
    assert result["fullProjectLiveCadReady"] is True
    assert result["liveCadApiMayStartForTokens"] == TOKENS
    assert result["productionReady"] is False


def test_project01_full_live_adapter_closure_rejects_failed_collision_gate(
    tmp_path: Path,
) -> None:
    result = build_project01_full_live_adapter_closure(
        _fixture(tmp_path, break_gate=True)
    )
    assert result["success"] is False
    assert result["liveCadApiMayStartForTokens"] == []
    assert result["steps"][3]["checks"]["collisionGateAccepted"] is False
