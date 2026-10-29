import json
from pathlib import Path

from demo_backend.saved_output_station_inspection_batch import (
    _completed_state_passed,
    build_saved_output_inspection_batch_status,
)


ROOT = Path(__file__).resolve().parents[3]
REPORTS = [
    ROOT
    / "demo/station_gap_batch_20261028/wastecup-saved-output-rechecks-v4/batch-report.json",
    ROOT
    / "demo/station_gap_batch_20261028/cleaning-saved-output-rechecks-v4/batch-report.json",
    ROOT
    / "demo/station_gap_batch_20261028/transport-saved-output-rechecks-v4/batch-report.json",
]
CURRENT_REPORTS = [
    ROOT
    / "demo/station_gap_batch_20261028/wastecup-saved-output-rechecks-v6/batch-report.json",
    ROOT
    / "demo/station_gap_batch_20261028/cleaning-saved-output-rechecks-v6/batch-report.json",
    ROOT
    / "demo/station_gap_batch_20261028/transport-saved-output-rechecks-v4/batch-report.json",
]


def test_v52_readonly_batches_form_one_serial_resume_safe_queue():
    status = build_saved_output_inspection_batch_status(ROOT, REPORTS)
    assert status["requestCount"] == 15
    assert len(status["batchReports"]) == 3
    assert all(len(row["sha256"]) == 64 for row in status["batchReports"])
    assert status["durationSeconds"] >= 0
    assert sum(status["runtimeStateCounts"].values()) == 15
    assert len(
        {
            (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"])
            for row in status["rows"]
        }
    ) == 15
    assert all(row["readOnly"] is True for row in status["rows"])
    assert all(row["recreatesMatesOrComponents"] is False for row in status["rows"])
    assert status["executionPolicy"] == {
        "serial": True,
        "stopAfterFailure": True,
        "skipPassedRequests": True,
        "cadReexecutionAllowed": False,
        "componentOrMateMutationAllowed": False,
        "cleanSolidWorksSessionRequired": True,
    }


def test_v52_readonly_queue_is_pending_or_resumable_without_duplicate_work():
    status = build_saved_output_inspection_batch_status(ROOT, REPORTS)
    assert status["status"] in {
        "ready_for_next_readonly_postcheck",
        "complete",
        "blocked_by_failed_or_incomplete_evidence",
    }
    if status["status"] == "ready_for_next_readonly_postcheck":
        assert status["nextRequestPath"]
        next_rows = [
            row
            for row in status["rows"]
            if row["requestPath"] == status["nextRequestPath"]
        ]
        assert len(next_rows) == 1
        assert next_rows[0]["runtimeState"] == "pending_readonly_postcheck"


def test_completed_state_must_bind_the_exact_request_and_assembly(tmp_path):
    request = tmp_path / "request.json"
    assembly = tmp_path / "assembly.SLDASM"
    state = tmp_path / "state.json"
    process = tmp_path / "process.json"
    request.write_text("{}", encoding="utf-8")
    assembly.write_bytes(b"assembly")
    plan = {
        "requestPath": str(request),
        "requestDigest": "request-digest",
        "outputAssemblyPath": str(assembly),
        "outputAssemblySha256": "assembly-digest",
        "outputStatePath": str(state),
        "processReportPath": str(process),
    }
    state.write_text(
        json.dumps(
            {
                "success": True,
                "assemblyPath": str(assembly),
                "assemblySha256": "assembly-digest",
                "checks": {"readOnly": True},
                "observed": {"readOnly": True},
            }
        ),
        encoding="utf-8",
    )
    process_payload = {
        "requestPath": str(request),
        "requestDigest": "request-digest",
        "returnCode": 0,
        "cadReexecuted": False,
        "readOnly": True,
    }
    process.write_text(json.dumps(process_payload), encoding="utf-8")
    assert _completed_state_passed(plan) is True

    process_payload["requestDigest"] = "other-request"
    process.write_text(json.dumps(process_payload), encoding="utf-8")
    assert _completed_state_passed(plan) is False


def test_current_queue_keeps_explicit_deferrals_as_distinct_nonpassing_gaps():
    status = build_saved_output_inspection_batch_status(ROOT, CURRENT_REPORTS)
    assert status["workItemCount"] == 15
    assert status["requestCount"] == 13
    assert status["deferredCount"] == 2
    assert status["resolvedWorkItemCount"] >= 1
    assert status["strictPassedCount"] == status["runtimeStateCounts"].get(
        "passed_readonly_postcheck", 0
    )
    assert (
        status["runtimeStateCounts"][
            "deferred_source_model_unresolved_references"
        ]
        == 1
    )
    assert (
        status["runtimeStateCounts"][
            "deferred_historical_output_not_pair_isolated"
        ]
        == 1
    )
    deferred = status["deferredRows"]
    assert len(deferred) == 2
    assert {
        (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"])
        for row in deferred
    } == {
        ("project01::GN00", "project01::JJ00"),
        ("project02::A300", "project02::A600"),
    }
    assert all(row["strictStationValidationPassed"] is False for row in deferred)
