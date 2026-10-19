from __future__ import annotations

import json
from pathlib import Path

from demo_backend.assembly_timing_report import build_assembly_timing_report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_timing_report_separates_cad_actions_and_gate_residual(tmp_path: Path) -> None:
    action = tmp_path / "cad-action.json"
    gate = tmp_path / "gate.json"
    _write(
        action,
        {
            "durationSeconds": 7.0,
            "toolResult": {
                "PhaseDurationsSeconds": {"open": 2.0, "save": 3.0, "total": 6.5}
            },
        },
    )
    _write(gate, {"accepted": True, "timingSeconds": {"total": 2.5}})
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-1",
            "executionMode": "live_cad",
            "status": "succeeded",
            "executionDurationSeconds": 10.5,
            "steps": [
                {
                    "stepId": "step-1",
                    "moduleToken": "A800",
                    "status": "succeeded",
                    "attempts": [{"durationSeconds": 10.0}],
                    "checkpoint": {
                        "cadActionEvidencePaths": [str(action)],
                        "evidencePath": str(gate),
                    },
                }
            ],
        },
    )
    _write(
        tmp_path / "preflight.json",
        {
            "pipelineAudit": {"timingSeconds": {"total": 0.12}},
            "previewAudit": {"timingSeconds": {"total": 0.03}},
        },
    )

    report = build_assembly_timing_report(tmp_path)

    assert report["cadActionDurationSeconds"] == 7.0
    assert report["gateAndOrchestrationResidualSeconds"] == 3.0
    assert report["collisionGateDurationSeconds"] == 2.5
    assert report["orchestrationResidualSeconds"] == 0.5
    assert report["unattributedJobOverheadSeconds"] == 0.5
    assert report["cadPhaseTotalsSeconds"]["save"] == 3.0
    assert report["steps"][0]["gateEvidenceExists"] is True
    assert report["preflightTimingSeconds"] == {
        "pipelineAudit": 0.12,
        "naturalLanguageParseAndPlan": 0.03,
    }


def test_timing_report_keeps_missing_action_visible(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-2",
            "executionMode": "live_cad",
            "status": "failed",
            "executionDurationSeconds": 2.0,
            "steps": [
                {
                    "stepId": "step-1",
                    "moduleToken": "A800",
                    "status": "failed",
                    "attempts": [{"durationSeconds": 2.0}],
                    "checkpoint": {"cadActionEvidencePaths": [str(missing)]},
                }
            ],
        },
    )

    report = build_assembly_timing_report(tmp_path)

    assert report["steps"][0]["cadActions"][0]["exists"] is False
    assert report["steps"][0]["gateEvidenceExists"] is False


def test_timing_report_does_not_double_count_supplemental_stage_result(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "execution.json"
    supplemental = tmp_path / "stage-result.json"
    gate = tmp_path / "gate.json"
    _write(primary, {"success": True, "durationSeconds": 8.0, "stages": [{}]})
    _write(
        supplemental,
        {
            "stageId": "step01",
            "accepted": True,
            "targetCheckpointPath": "candidate.SLDASM",
            "durationSeconds": 6.0,
        },
    )
    _write(gate, {"accepted": True, "timingSeconds": {"total": 2.0}})
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-project05",
            "executionMode": "live_cad",
            "status": "succeeded",
            "executionDurationSeconds": 10.5,
            "steps": [
                {
                    "stepId": "step-01-d000",
                    "moduleToken": "D000",
                    "status": "succeeded",
                    "attempts": [{"durationSeconds": 10.0}],
                    "checkpoint": {
                        "cadActionEvidencePaths": [str(primary), str(supplemental)],
                        "evidencePath": str(gate),
                    },
                }
            ],
        },
    )

    report = build_assembly_timing_report(tmp_path)

    assert report["cadActionDurationSeconds"] == 8.0
    assert report["steps"][0]["cadActions"][0]["countedInCadActionTotal"] is True
    assert report["steps"][0]["cadActions"][1]["countedInCadActionTotal"] is False
    assert (
        report["steps"][0]["cadActions"][1]["evidenceRole"]
        == "supplemental-stage-result"
    )


def test_timing_report_attributes_recovered_failed_attempt(tmp_path: Path) -> None:
    action = tmp_path / "action.json"
    gate = tmp_path / "gate.json"
    _write(action, {"success": True, "durationSeconds": 6.0})
    _write(gate, {"accepted": True, "timingSeconds": {"total": 2.0}})
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-recovered",
            "executionMode": "live_cad",
            "status": "succeeded",
            "executionDurationSeconds": 14.5,
            "steps": [
                {
                    "stepId": "step-recovered",
                    "moduleToken": "AB00",
                    "status": "succeeded",
                    "attemptCount": 2,
                    "attempts": [
                        {"durationSeconds": 4.0},
                        {"durationSeconds": 10.0},
                    ],
                    "checkpoint": {
                        "cadActionEvidencePaths": [str(action)],
                        "evidencePath": str(gate),
                    },
                }
            ],
        },
    )

    report = build_assembly_timing_report(tmp_path)

    assert report["recoveredFailedOrInterruptedAttemptDurationSeconds"] == 4.0
    assert report["unattributedJobOverheadSeconds"] == 0.5
    assert report["steps"][0]["attemptDurationsSeconds"] == [4.0, 10.0]


def test_timing_report_ignores_non_json_supporting_evidence(tmp_path: Path) -> None:
    log = tmp_path / "stdout.log"
    log.write_text("ordinary process output", encoding="utf-8")
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job-with-log",
            "executionMode": "generic_cad_manifest",
            "status": "succeeded",
            "executionDurationSeconds": 1.0,
            "steps": [
                {
                    "stepId": "packet-001",
                    "moduleToken": "AE00",
                    "status": "succeeded",
                    "attempts": [{"durationSeconds": 1.0}],
                    "checkpoint": {"cadActionEvidencePaths": [str(log)]},
                }
            ],
        },
    )

    report = build_assembly_timing_report(tmp_path)

    action = report["steps"][0]["cadActions"][0]
    assert action["exists"] is True
    assert action["readableJson"] is False
    assert action["countedInCadActionTotal"] is False
