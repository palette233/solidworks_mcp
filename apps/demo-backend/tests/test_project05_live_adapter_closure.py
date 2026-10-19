from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project05_live_adapter_closure import (
    EXPECTED_TOKENS,
    build_project05_live_adapter_closure,
    build_project05_uninterrupted_live_closure,
)


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_project05_live_adapter_closure_accepts_complete_split_chain(tmp_path: Path) -> None:
    pilot_assembly = tmp_path / "d000.SLDASM"
    pilot_assembly.write_bytes(b"pilot")
    pilot = _write(
        tmp_path / "pilot.json",
        {
            "accepted": True,
            "durationSeconds": 10,
            "targetCheckpointPath": str(pilot_assembly),
            "topLevelAudit": {"success": True},
            "poseAudit": {"success": True},
            "boundingBoxExtentAudit": {"success": True},
        },
    )
    _write(tmp_path / "project05_ordered_direct_execution.json", {"durationSeconds": 12})
    steps = []
    for index, token in enumerate(EXPECTED_TOKENS[1:], start=2):
        assembly = tmp_path / f"{token}.SLDASM"
        assembly.write_bytes(token.encode())
        gate = _write(
            tmp_path / f"{token}.gate.json",
            {
                "accepted": True,
                "pairCount": index,
                "unresolvedExactPairCount": 0,
                "strictAabbAcceptedCount": index,
            },
        )
        action = _write(tmp_path / f"{token}.action.json", {"success": True})
        steps.append(
            {
                "moduleToken": token,
                "status": "succeeded",
                "attempts": [{"durationSeconds": 5}],
                "checkpoint": {
                    "assemblyPath": str(assembly),
                    "evidencePath": str(gate),
                    "cadActionEvidencePaths": [str(action)],
                },
            }
        )
    job = _write(
        tmp_path / "job.json",
        {
            "status": "succeeded",
            "steps": steps,
            "lastCommittedCheckpoint": {"assemblyPath": steps[-1]["checkpoint"]["assemblyPath"]},
        },
    )
    manifest = _write(tmp_path / "manifest.json", {"evidenceComplete": True})
    tail = _write(
        tmp_path / "tail.json",
        {
            "status": "succeeded",
            "jobPath": str(job),
            "evidenceManifestPath": str(manifest),
        },
    )

    result = build_project05_live_adapter_closure(
        pilot_stage_path=pilot,
        tail_summary_path=tail,
    )

    assert result["allActionsLiveCadValidated"] is True
    assert result["liveCadApiMayStart"] is True
    assert result["singleUninterruptedJob"] is False
    assert result["observedTokens"] == EXPECTED_TOKENS
    assert result["totalCommittedStepDurationSeconds"] == 45
    assert result["totalMeasuredDurationSeconds"] == 12
    assert result["productionReady"] is False


def test_build_project05_live_adapter_closure_rejects_missing_gate(tmp_path: Path) -> None:
    pilot_assembly = tmp_path / "d000.SLDASM"
    pilot_assembly.write_bytes(b"pilot")
    pilot = _write(
        tmp_path / "pilot.json",
        {
            "accepted": True,
            "targetCheckpointPath": str(pilot_assembly),
            "topLevelAudit": {"success": True},
            "poseAudit": {"success": True},
            "boundingBoxExtentAudit": {"success": True},
        },
    )
    final_assembly = tmp_path / "final.SLDASM"
    final_assembly.write_bytes(b"final")
    job = _write(
        tmp_path / "job.json",
        {
            "status": "succeeded",
            "steps": [
                {
                    "moduleToken": token,
                    "status": "succeeded",
                    "checkpoint": {
                        "assemblyPath": str(final_assembly),
                        "evidencePath": str(tmp_path / "missing.json"),
                    },
                }
                for token in EXPECTED_TOKENS[1:]
            ],
            "lastCommittedCheckpoint": {"assemblyPath": str(final_assembly)},
        },
    )
    manifest = _write(tmp_path / "manifest.json", {"evidenceComplete": True})
    tail = _write(
        tmp_path / "tail.json",
        {"status": "succeeded", "jobPath": str(job), "evidenceManifestPath": str(manifest)},
    )

    result = build_project05_live_adapter_closure(
        pilot_stage_path=pilot,
        tail_summary_path=tail,
    )

    assert result["allActionsLiveCadValidated"] is False
    assert result["liveCadApiMayStart"] is False
    assert result["rejectedEvidence"]


def test_uninterrupted_closure_validates_checkpoint_continuity(tmp_path: Path) -> None:
    base = tmp_path / "base.SLDASM"
    base.write_bytes(b"base")
    prior = base
    steps = []
    for token in EXPECTED_TOKENS:
        output = tmp_path / f"{token}.SLDASM"
        output.write_bytes(token.encode())
        gate = _write(
            tmp_path / f"{token}.gate.json",
            {"accepted": True, "unresolvedExactPairCount": 0, "pairCount": 1},
        )
        action = _write(tmp_path / f"{token}.action.json", {"success": True})
        stage = _write(tmp_path / f"{token}.stage.json", {"accepted": True})
        steps.append(
            {
                "moduleToken": token,
                "status": "succeeded",
                "attemptCount": 1,
                "attempts": [{"durationSeconds": 2}],
                "checkpoint": {
                    "inputAssemblyPath": str(prior),
                    "assemblyPath": str(output),
                    "evidencePath": str(gate),
                    "cadActionEvidencePaths": [str(action), str(stage)],
                },
            }
        )
        prior = output
    job = _write(
        tmp_path / "job.json",
        {
            "status": "succeeded",
            "steps": steps,
            "lastCommittedCheckpoint": {"assemblyPath": str(prior)},
            "rollback": None,
            "error": None,
            "executionDurationSeconds": 16,
        },
    )
    manifest = _write(
        tmp_path / "manifest.json",
        {"evidenceComplete": True, "staticExecutionAccepted": True},
    )
    summary = _write(
        tmp_path / "summary.json",
        {
            "singleUninterruptedJob": True,
            "status": "succeeded",
            "jobPath": str(job),
            "evidenceManifestPath": str(manifest),
        },
    )

    result = build_project05_uninterrupted_live_closure(summary)

    assert result["status"] == "PROJECT05_LIVE_ADAPTER_UNINTERRUPTED_FULL_CHAIN_CLOSED"
    assert result["singleUninterruptedJob"] is True
    assert result["unseededJob"] is True
    assert result["allActionsLiveCadValidated"] is True
    assert result["totalMeasuredDurationSeconds"] == 16
