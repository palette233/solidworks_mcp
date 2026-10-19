from __future__ import annotations

import hashlib
import json
from pathlib import Path

from demo_backend.released_long_chain_evidence import build_released_long_chain_closure


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _step(tmp_path: Path, index: int, token: str) -> dict:
    run = tmp_path / f"run-{index}"
    output = run / f"out-{index}.SLDASM"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(f"assembly-{index}".encode())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    cad = run / "cad-result.json"
    _write(
        cad,
        {
            "success": True,
            "outputAssemblyPath": str(output),
            "outputAssemblySha256": digest,
            "outputClosedAfterVerification": True,
            "sourceAssemblyUnchanged": True,
            "targetSourceSessionClean": True,
            "toolResult": {
                "RequestedMateCount": 3,
                "CreatedMateCount": 3,
                "TargetConstraintStateAccepted": True,
                "TargetFullyConstrained": True,
                "MateSolveClean": True,
                "Reopened": True,
                "ReopenedMateParametersMatch": True,
                "ComponentSemanticsMatch": True,
                "TargetCaseAnchored": False,
                "RequestedTargetLeafPoseAnchorCount": 0,
                "AppliedTargetLeafPoseAnchorCount": 0,
            },
        },
    )
    return {
        "stepId": f"packet-{index:03d}",
        "moduleToken": token,
        "status": "succeeded",
        "attemptCount": 1,
        "attempts": [{"durationSeconds": 1.5}],
        "checkpoint": {
            "assemblyPath": str(output),
            "cadActionEvidencePaths": [str(cad)],
        },
    }


def _job(tmp_path: Path, *, release_id: str = "release-1") -> Path:
    steps = [_step(tmp_path, 1, "D000"), _step(tmp_path, 2, "F000")]
    templates = ["template/d", "template/f"]
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-1",
            "projectId": "project05",
            "status": "succeeded",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "executionDurationSeconds": 3.0,
            "plan": {
                "contextId": "context-1",
                "releaseAuthority": {
                    "status": "verified",
                    "binding": {"releaseId": release_id, "releaseDigest": "digest"},
                    "authorizedDrivingTemplateIds": templates,
                    "usedDrivingTemplateIds": templates,
                },
            },
            "steps": steps,
            "lastCommittedCheckpoint": steps[-1]["checkpoint"],
        },
    )
    return tmp_path


def test_released_long_chain_closes_with_exact_order_and_release(tmp_path: Path) -> None:
    report = build_released_long_chain_closure(
        _job(tmp_path),
        expected_order=["D000", "F000"],
        expected_release_id="release-1",
    )
    assert report["status"] == "passed"
    assert report["actualOrder"] == ["D000", "F000"]
    assert report["checks"]["allPacketsPassed"] is True


def test_wrong_order_is_rejected_even_when_cad_steps_succeeded(tmp_path: Path) -> None:
    report = build_released_long_chain_closure(
        _job(tmp_path),
        expected_order=["F000", "D000"],
        expected_release_id="release-1",
    )
    assert report["status"] == "blocked"
    assert report["checks"]["expectedOrderExecuted"] is False


def test_wrong_release_is_rejected(tmp_path: Path) -> None:
    report = build_released_long_chain_closure(
        _job(tmp_path),
        expected_order=["D000", "F000"],
        expected_release_id="release-2",
    )
    assert report["status"] == "blocked"
    assert report["checks"]["expectedReleaseBound"] is False
