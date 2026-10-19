from __future__ import annotations

import hashlib
import json
from pathlib import Path

from demo_backend.released_long_chain_evidence import (
    build_released_order_compatibility_closure,
)


RELEASE_ID = "release-cumulative-1"
TEMPLATES = ["template/calibration", "template/transport"]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_job(directory: Path, order: list[str]) -> Path:
    steps = []
    previous_output: Path | None = None
    for index, token in enumerate(order, start=1):
        run = directory / f"run-{index}"
        output = run / f"{token}-{index}.SLDASM"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(f"{directory.name}-{token}-{index}".encode())
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        cad_path = run / "cad-result.json"
        _write(
            cad_path,
            {
                "success": True,
                "sourceAssemblyPath": str(previous_output or directory / "base.SLDASM"),
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
        checkpoint = {
            "assemblyPath": str(output),
            "inputAssemblyPath": str(previous_output) if previous_output else None,
            "cadActionEvidencePaths": [str(cad_path)],
        }
        steps.append(
            {
                "stepId": f"packet-{index:03d}",
                "moduleToken": token,
                "status": "succeeded",
                "attemptCount": 1,
                "attempts": [{"durationSeconds": 1.0}],
                "checkpoint": checkpoint,
            }
        )
        previous_output = output

    _write(
        directory / "job.json",
        {
            "jobId": directory.name,
            "projectId": "project03",
            "status": "succeeded",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "executionDurationSeconds": 2.0,
            "plan": {
                "contextId": directory.name,
                "releaseAuthority": {
                    "status": "verified",
                    "binding": {
                        "releaseId": RELEASE_ID,
                        "releaseDigest": "same-release-digest",
                    },
                    "authorizedDrivingTemplateIds": TEMPLATES,
                    "usedDrivingTemplateIds": TEMPLATES,
                },
            },
            "steps": steps,
            "lastCommittedCheckpoint": steps[-1]["checkpoint"],
        },
    )
    return directory


def test_two_real_cumulative_orders_have_equivalent_semantic_result(tmp_path: Path) -> None:
    first = _build_job(tmp_path / "first", ["SS00", "BD00"])
    second = _build_job(tmp_path / "second", ["BD00", "SS00"])

    report = build_released_order_compatibility_closure(
        [first, second],
        expected_orders=[["SS00", "BD00"], ["BD00", "SS00"]],
        expected_release_id=RELEASE_ID,
        base_module_token="AA00",
    )

    assert report["status"] == "passed"
    assert report["semanticResultEquivalent"] is True
    assert report["finalAssemblyBinaryIdentical"] is False
    assert report["binaryIdentityRequired"] is False
    assert all(case["allCumulativeLinksPassed"] for case in report["cases"])


def test_broken_cumulative_input_link_fails_closed(tmp_path: Path) -> None:
    first = _build_job(tmp_path / "first", ["SS00", "BD00"])
    second = _build_job(tmp_path / "second", ["BD00", "SS00"])
    job_path = second / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["steps"][1]["checkpoint"]["inputAssemblyPath"] = str(
        tmp_path / "unrelated.SLDASM"
    )
    _write(job_path, job)

    report = build_released_order_compatibility_closure(
        [first, second],
        expected_orders=[["SS00", "BD00"], ["BD00", "SS00"]],
        expected_release_id=RELEASE_ID,
        base_module_token="AA00",
    )

    assert report["status"] == "blocked"
    assert report["checks"]["allCumulativeLinksPassed"] is False
    assert report["semanticResultEquivalent"] is False
