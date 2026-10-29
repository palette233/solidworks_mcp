from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("six_role_timing_summary_target", ROOT / "scripts/summarize_six_role_chain_timings.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def inputs():
    timing = {"directStageExecution": 101, "directCadPacketSum": 80, "newCadPacket": 30,
              "readOnlyChainVerification": 10, "totalMeasuredExecution": 141, "signedSupportGeometryVerification": 0.001}
    closure = {"success": True, "timingSeconds": timing, "moduleSequence": ["AA00", "SS00", "AI00", "BD00", "AG00", "P000"],
               "finishedAtUtc": "2026-10-23T01:03:20Z"}
    outer = {"exitCode": 0, "wallSeconds": 40, "startedAtUtc": "2026-10-23T01:02:00Z", "finishedAtUtc": "2026-10-23T01:02:40Z"}
    steps = [{"stepId": f"packet-00{index}", "moduleToken": token, "status": "succeeded",
              "attempts": [{"attempt": 1, "durationSeconds": 25}]} for index, token in enumerate(("SS00", "AI00", "BD00", "AG00"), 1)]
    steps[0]["attempts"] = [{"attempt": 1, "durationSeconds": 0.157638}, {"attempt": 2, "durationSeconds": 25}]
    job = {"status": "succeeded", "executionDurationSeconds": 101, "startedAt": "2026-10-23T01:00:00Z", "steps": steps}
    return [closure, outer, job, {"preparationSeconds": 0.7}]


def test_outer_inner_and_retry_are_not_double_counted(inputs):
    before = copy.deepcopy(inputs)
    result = MODULE.summarize_case(*inputs)
    assert result["measuredOuterExecutionTotalSeconds"] == 151
    assert result["directSuccessfulPacketSeconds"] == 100
    assert result["directFailedAttemptSeconds"] == pytest.approx(0.157638)
    assert result["directAdapterSubtotalSeconds"] == 80
    assert result["appendOuterExecutionSeconds"] == 40
    assert result["appendAdapterSeconds"] == 30
    assert result["appendOuterMinusAdapterSeconds"] == 10
    assert result["elapsedWallSeconds"] == 200
    assert result["interStageWaitingAndUnmeasuredOverheadSeconds"] == 49
    assert result["directAttempts"][0]["outcome"] == "superseded_failed_attempt"
    assert result["directAttempts"][1]["outcome"] == "successful"
    assert inputs == before


def test_resume_reset_start_keeps_failed_attempt_and_debug_wait(inputs):
    job = inputs[2]
    job["startedAt"] = "2026-10-23T01:01:00Z"
    job["steps"][0]["attempts"][0]["startedAt"] = "2026-10-23T01:00:00Z"
    job["steps"][0]["attempts"][1]["startedAt"] = "2026-10-23T01:01:00Z"
    result = MODULE.summarize_case(*inputs)
    assert result["earliestAttemptOrJobStart"] == "2026-10-23T01:00:00Z"
    assert result["startedAtUtc"] == result["earliestAttemptOrJobStart"]
    assert result["latestRunStartedAt"] == "2026-10-23T01:01:00Z"
    assert result["elapsedWallSeconds"] == 200  # Not 140 measured only from resume.
    assert result["measuredOuterExecutionTotalSeconds"] == 151
    assert result["interStageWaitingAndUnmeasuredOverheadSeconds"] == 49
    assert result["directFailedAttemptSeconds"] == pytest.approx(0.157638)


def test_job_start_can_precede_first_actual_packet_attempt(inputs):
    inputs[2]["steps"][0]["attempts"][0]["startedAt"] = "2026-10-23T01:00:01Z"
    assert MODULE.summarize_case(*inputs)["earliestAttemptOrJobStart"] == "2026-10-23T01:00:00Z"


@pytest.mark.parametrize("value", [None, -1, float("nan"), float("inf"), True, "10"])
def test_invalid_timing_rejected(inputs, value):
    inputs[1]["wallSeconds"] = value
    with pytest.raises(ValueError):
        MODULE.summarize_case(*inputs)


@pytest.mark.parametrize("change", ["job_failed", "command_failed", "closure_failed", "missing_attempt", "duration_disagrees", "inner_exceeds_outer", "attempts_exceed_direct", "elapsed_too_short"])
def test_inconsistent_evidence_rejected(inputs, change):
    closure, outer, job, _ = inputs
    if change == "job_failed":
        job["status"] = "failed"
    elif change == "command_failed":
        outer["exitCode"] = 1
    elif change == "closure_failed":
        closure["success"] = False
    elif change == "missing_attempt":
        job["steps"][0]["attempts"] = []
    elif change == "duration_disagrees":
        job["executionDurationSeconds"] = 102
    elif change == "inner_exceeds_outer":
        outer["wallSeconds"] = 20
    elif change == "attempts_exceed_direct":
        job["steps"][0]["attempts"][0]["durationSeconds"] = 10
    else:
        closure["finishedAtUtc"] = "2026-10-23T01:01:00Z"
    with pytest.raises(ValueError):
        MODULE.summarize_case(*inputs)


@pytest.mark.parametrize("filename", ["timing-summary.json", "timing-summary-CN.md"])
def test_summary_refuses_existing_file(tmp_path, filename):
    (tmp_path / filename).write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        MODULE.write_summary(tmp_path, {})
    assert (tmp_path / filename).read_text(encoding="utf-8") == "keep"


def test_summary_writes_table_and_json(tmp_path, inputs):
    case = MODULE.summarize_case(*inputs)
    report = {"accountingRule": "Outer only", "excludes": "Development", "cases": {"standard": case, "reordered": case}}
    MODULE.write_summary(tmp_path, report)
    assert (tmp_path / "timing-summary.json").exists()
    text = (tmp_path / "timing-summary-CN.md").read_text(encoding="utf-8")
    assert "151.000" in text
    assert "superseded_failed_attempt" in text
