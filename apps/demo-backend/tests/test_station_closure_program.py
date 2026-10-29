from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_backend import station_closure_program as subject


def _saved(status: str = "ready_for_next_readonly_postcheck") -> dict:
    return {
        "status": status,
        "requestCount": 15,
        "runtimeStateCounts": {"pending_readonly_postcheck": 15},
        "nextRequestPath": "saved/request.json" if status != "complete" else None,
    }


def _fresh(status: str = "ready_for_next_serial_cad_action") -> dict:
    return {
        "status": status,
        "pairCount": 2,
        "completePairCount": 0 if status != "complete" else 2,
        "nextQueueDirectory": "fresh/queue" if status != "complete" else None,
    }


def _chain(status: str = "ready_for_next_chain_action", root: str = "scanner/chain-01") -> dict:
    return {
        "status": status,
        "chainCount": 6,
        "completedChainCount": 0 if status != "complete" else 6,
        "nextAction": (
            {"action": "run", "outputRoot": root}
            if status != "complete"
            else None
        ),
    }


@pytest.fixture
def patch_worksets(monkeypatch: pytest.MonkeyPatch):
    values = {"saved": _saved(), "fresh": _fresh(), "scanner": _chain()}
    monkeypatch.setattr(
        subject,
        "build_saved_output_inspection_batch_status",
        lambda *_: values["saved"],
    )
    monkeypatch.setattr(
        subject,
        "build_parameterized_datum_validation_batch_status",
        lambda *_: values["fresh"],
    )
    monkeypatch.setattr(subject, "build_staged_chain_execution_batch_status", lambda *_: values["scanner"])
    return values


def _status(tmp_path: Path) -> dict:
    return subject.build_station_closure_program_status(
        tmp_path, [tmp_path / "saved.json"], [tmp_path / "fresh"], tmp_path / "scanner.json"
    )


def test_earliest_incomplete_phase_wins(
    tmp_path: Path, patch_worksets: dict
) -> None:
    status = _status(tmp_path)
    assert status["status"] == "ready_for_next_serial_action"
    assert status["nextAction"] == {
        "phaseId": "saved_output_readonly_postchecks",
        "action": "run_readonly_postcheck",
        "input": "saved/request.json",
    }


def test_fresh_phase_follows_completed_readonly_phase(
    tmp_path: Path, patch_worksets: dict
) -> None:
    patch_worksets["saved"] = _saved("complete")
    status = _status(tmp_path)
    assert status["nextAction"]["phaseId"] == "fresh_nonprototype_cad_validations"


def test_scanner_phase_follows_completed_cad_phases(
    tmp_path: Path, patch_worksets: dict
) -> None:
    patch_worksets["saved"] = _saved("complete")
    patch_worksets["fresh"] = _fresh("complete")
    status = _status(tmp_path)
    assert status["nextAction"] == {
        "phaseId": "scanner_current_context_chains",
        "action": "run_scanner_chain",
        "input": "scanner/chain-01",
    }


def test_blocked_phase_prevents_later_work(
    tmp_path: Path, patch_worksets: dict
) -> None:
    patch_worksets["saved"] = _saved("blocked_by_failed_or_incomplete_evidence")
    status = _status(tmp_path)
    assert status["status"] == "blocked_by_current_phase"
    assert status["nextAction"]["action"] == "review_failure"


def test_all_phases_complete(tmp_path: Path, patch_worksets: dict) -> None:
    patch_worksets["saved"] = _saved("complete")
    patch_worksets["fresh"] = _fresh("complete")
    patch_worksets["scanner"] = _chain("complete")
    status = _status(tmp_path)
    assert status["status"] == "complete"
    assert status["nextAction"] is None
    assert status["executionPolicy"]["serialAcrossPhases"] is True


def test_six_role_phase_follows_scanner_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subject, "build_saved_output_inspection_batch_status", lambda *_: _saved("complete"))
    monkeypatch.setattr(subject, "build_parameterized_datum_validation_batch_status", lambda *_: _fresh("complete"))
    calls = iter([_chain("complete"), _chain(root="six-role/chain-01")])
    monkeypatch.setattr(subject, "build_staged_chain_execution_batch_status", lambda *_: next(calls))
    status = subject.build_station_closure_program_status(
        tmp_path,
        [tmp_path / "saved.json"],
        [tmp_path / "fresh"],
        tmp_path / "scanner.json",
        tmp_path / "six-role.json",
    )
    assert status["nextAction"] == {
        "phaseId": "new_six_role_cumulative_chain",
        "action": "run_six_role_chain",
        "input": "six-role/chain-01",
    }


def test_saved_phase_reports_strict_passes_separately_from_deferred_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = {
        **_saved(),
        "requestCount": 14,
        "workItemCount": 15,
        "strictPassedCount": 0,
        "deferredCount": 1,
        "resolvedWorkItemCount": 1,
    }
    monkeypatch.setattr(
        subject, "build_saved_output_inspection_batch_status", lambda *_: saved
    )
    monkeypatch.setattr(
        subject,
        "build_parameterized_datum_validation_batch_status",
        lambda *_: _fresh(),
    )
    monkeypatch.setattr(
        subject, "build_staged_chain_execution_batch_status", lambda *_: _chain()
    )
    status = _status(tmp_path)
    phase = status["phases"][0]
    assert phase["totalCount"] == 15
    assert phase["completedCount"] == 1
    assert phase["strictPassedCount"] == 0
    assert phase["deferredCount"] == 1
