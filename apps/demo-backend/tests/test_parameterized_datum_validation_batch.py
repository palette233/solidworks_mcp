from pathlib import Path

import demo_backend.parameterized_datum_validation_batch as batch_module
from demo_backend.parameterized_datum_validation_batch import (
    build_parameterized_datum_validation_batch_status,
)


ROOT = Path(__file__).resolve().parents[3]
QUEUES = [
    ROOT
    / "demo/station_gap_batch_20261028/n000-a600-bounded-role-station-v1/validation-queue-v1",
    ROOT / "demo/station_gap_batch_20261028/tpv3/p03-ae00--p03-aa00",
]


def test_current_fresh_cad_candidates_form_one_ordered_serial_batch():
    status = build_parameterized_datum_validation_batch_status(ROOT, QUEUES)
    assert status["queueCount"] == 2
    assert status["pairCount"] == 2
    assert {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for queue in status["queues"]
        for row in queue["pairs"]
    } == {
        ("project05::N000", "project02::A600"),
        ("project03::AE00", "project03::AA00"),
    }
    assert status["executionPolicy"] == {
        "serial": True,
        "stopAfterFailure": True,
        "skipCompletedPairs": True,
        "cleanSolidWorksSessionRequired": True,
        "nonPrototypeInitialPoseRequired": True,
        "saveCloseReopenRequired": True,
        "targetStationPostcheckRequired": True,
    }


def test_current_fresh_cad_batch_is_ready_complete_or_failed_closed():
    status = build_parameterized_datum_validation_batch_status(ROOT, QUEUES)
    assert status["status"] in {
        "ready_for_next_serial_cad_action",
        "complete",
        "blocked_by_failed_queue",
    }
    if status["status"] == "ready_for_next_serial_cad_action":
        assert status["nextQueueDirectory"] == QUEUES[0].relative_to(ROOT).as_posix()
    elif status["status"] == "complete":
        assert status["completePairCount"] == 2
        assert status["nextQueueDirectory"] is None
    else:
        assert status["failedPairCount"] > 0
        assert status["nextQueueDirectory"] is None


def _fake_status(queue_dir: Path, state: str) -> dict:
    token = queue_dir.name
    return {
        "queueDigest": f"digest-{token}",
        "runtimeStateCounts": {state: 1},
        "pairs": [
            {
                "moduleDefinitionId": f"project::{token}",
                "slotDefinitionId": "project::BASE",
                "moduleRole": "Role",
                "runtimeState": state,
                "candidateDirectory": str(queue_dir / "candidate"),
            }
        ],
    }


def test_later_failure_blocks_the_whole_ordered_workset(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for path in (first, second):
        path.mkdir()
        (path / "validation-queue.json").write_text("{}", encoding="utf-8")
    states = {
        "first": "pending_cad_validation",
        "second": "cad_failed_stop_queue",
    }
    monkeypatch.setattr(
        batch_module,
        "inspect_materialized_validation_queue",
        lambda path: _fake_status(path, states[path.name]),
    )
    status = build_parameterized_datum_validation_batch_status(
        tmp_path, [first, second]
    )
    assert status["status"] == "blocked_by_failed_queue"
    assert status["nextQueueDirectory"] is None
    assert status["failedPairCount"] == 1


def test_completed_first_queue_advances_to_second_queue(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for path in (first, second):
        path.mkdir()
        (path / "validation-queue.json").write_text("{}", encoding="utf-8")
    states = {
        "first": "relation_released_for_cumulative_execution",
        "second": "pending_cad_validation",
    }
    monkeypatch.setattr(
        batch_module,
        "inspect_materialized_validation_queue",
        lambda path: _fake_status(path, states[path.name]),
    )
    status = build_parameterized_datum_validation_batch_status(
        tmp_path, [first, second]
    )
    assert status["status"] == "ready_for_next_serial_cad_action"
    assert status["nextQueueDirectory"] == "second"
    assert status["completePairCount"] == 1
