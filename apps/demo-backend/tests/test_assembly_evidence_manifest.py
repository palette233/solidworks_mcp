from __future__ import annotations

import json
from pathlib import Path

from demo_backend.assembly_evidence_manifest import (
    EVIDENCE_MANIFEST_SCHEMA,
    build_job_evidence_manifest,
    write_job_evidence_manifest,
)


def _job(tmp_path: Path) -> dict:
    assembly = tmp_path / "step.SLDASM"
    evidence = tmp_path / "gate.json"
    action = tmp_path / "cad-action.json"
    assembly.write_bytes(b"assembly")
    evidence.write_text("{}", encoding="utf-8")
    action.write_text("{}", encoding="utf-8")
    return {
        "schemaVersion": "project02-ordered-assembly-job/v1",
        "jobId": "job-test",
        "executionMode": "live_cad",
        "status": "succeeded",
        "plan": {
            "projectId": "project02",
            "projectProfile": {"profileVersion": "v1", "profileDigest": "abc"},
            "intentDigest": "intent",
            "planDigest": "plan",
        },
        "steps": [
            {
                "stepId": "step-01-a800",
                "moduleToken": "A800",
                "status": "succeeded",
                "attemptCount": 1,
                "attempts": [],
                "error": None,
                "checkpoint": {
                    "assemblyPath": str(assembly),
                    "evidencePath": str(evidence),
                    "cadActionEvidencePaths": [str(action)],
                    "inputAssemblyPath": "base.SLDASM",
                    "committedAt": "now",
                },
            }
        ],
        "lastCommittedCheckpoint": None,
        "executionDurationSeconds": 1.5,
    }


def test_complete_job_manifest_hashes_every_committed_artifact(tmp_path: Path) -> None:
    manifest = build_job_evidence_manifest(_job(tmp_path))
    assert manifest["schemaVersion"] == EVIDENCE_MANIFEST_SCHEMA
    assert manifest["evidenceComplete"] is True
    assert manifest["staticExecutionAccepted"] is True
    assert len(manifest["steps"][0]["assembly"]["sha256"]) == 64
    assert len(manifest["steps"][0]["gateEvidence"]["sha256"]) == 64


def test_missing_gate_evidence_fails_manifest_even_when_job_says_succeeded(tmp_path: Path) -> None:
    job = _job(tmp_path)
    job["steps"][0]["checkpoint"]["evidencePath"] = str(tmp_path / "missing.json")
    manifest = build_job_evidence_manifest(job)
    assert manifest["evidenceComplete"] is False
    assert manifest["staticExecutionAccepted"] is False
    assert manifest["missingEvidence"] == ["step-01-a800:gate-evidence"]


def test_manifest_is_written_atomically(tmp_path: Path) -> None:
    job_dir = tmp_path / "jobs/job-test"
    job_dir.mkdir(parents=True)
    (job_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (job_dir / "preflight.json").write_text("{}\n", encoding="utf-8")
    target = write_job_evidence_manifest(_job(tmp_path), job_dir)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["events"]["exists"] is True
    assert payload["preflightEvidence"]["exists"] is True
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_failed_step_discovers_uncommitted_cad_action_evidence(tmp_path: Path) -> None:
    job_dir = tmp_path / "jobs/job-failed"
    action = job_dir / "cad-working/step-01-a800-attempt1-action1.context-insert.result.json"
    action.parent.mkdir(parents=True)
    action.write_text("{}", encoding="utf-8")
    events = job_dir / "events.jsonl"
    events.write_text("{}\n", encoding="utf-8")
    job = {
        "jobId": "job-failed",
        "status": "failed",
        "steps": [
            {
                "stepId": "step-01-a800",
                "moduleToken": "A800",
                "status": "failed",
                "attemptCount": 1,
                "attempts": [],
                "checkpoint": None,
            }
        ],
    }

    manifest = build_job_evidence_manifest(job, events_path=events)

    assert manifest["steps"][0]["cadActionEvidence"][0]["exists"] is True
