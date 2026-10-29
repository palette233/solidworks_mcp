from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import run_station_closure_program as subject  # noqa: E402


def test_run_next_persists_refreshed_status_after_nonzero_action(
    tmp_path: Path, monkeypatch
) -> None:
    before = {
        "status": "ready_for_next_serial_action",
        "nextAction": {
            "phaseId": "saved_output_readonly_postchecks",
            "action": "run_readonly_postcheck",
            "input": "request.json",
        },
    }
    after = {
        "status": "ready_for_next_serial_action",
        "nextAction": {
            "phaseId": "saved_output_readonly_postchecks",
            "action": "run_readonly_postcheck",
            "input": "next-request.json",
        },
    }
    statuses = iter([before, after])
    monkeypatch.setattr(subject, "_build_status", lambda _args: next(statuses))
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=9),
    )
    output = tmp_path / "status.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_station_closure_program.py",
            "run-next",
            "--saved-output-batch-report",
            "saved.json",
            "--fresh-validation-queue-dir",
            "fresh",
            "--scanner-chain-batch-report",
            "scanner.json",
            "--status-output",
            str(output),
        ],
    )
    assert subject.main() == 9
    assert json.loads(output.read_text(encoding="utf-8")) == after


def test_status_action_persists_current_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    status = {"status": "complete", "nextAction": None}
    monkeypatch.setattr(subject, "_build_status", lambda _args: status)
    output = tmp_path / "status.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_station_closure_program.py",
            "status",
            "--saved-output-batch-report",
            "saved.json",
            "--fresh-validation-queue-dir",
            "fresh",
            "--scanner-chain-batch-report",
            "scanner.json",
            "--status-output",
            str(output),
        ],
    )
    assert subject.main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == status


def test_run_next_refreshes_goal_audit_from_post_action_status(
    tmp_path: Path, monkeypatch
) -> None:
    before = {
        "status": "ready_for_next_serial_action",
        "nextAction": {
            "phaseId": "saved_output_readonly_postchecks",
            "action": "run_readonly_postcheck",
            "input": "request.json",
        },
    }
    after = {"status": "complete", "nextAction": None}
    statuses = iter([before, after])
    monkeypatch.setattr(subject, "_build_status", lambda _args: next(statuses))
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    observed: dict = {}

    def fake_audit(_workspace, _coverage, _gap, closure, _batch, _failure):
        observed["closure"] = json.loads(Path(closure).read_text(encoding="utf-8"))
        return {"schemaVersion": "audit/v1", "goalComplete": True}

    monkeypatch.setattr(subject, "build_six_role_goal_acceptance_audit", fake_audit)
    status_output = tmp_path / "status.json"
    audit_output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_station_closure_program.py",
            "run-next",
            "--saved-output-batch-report",
            "saved.json",
            "--fresh-validation-queue-dir",
            "fresh",
            "--scanner-chain-batch-report",
            "scanner.json",
            "--six-role-chain-batch-report",
            "six-role.json",
            "--status-output",
            str(status_output),
            "--goal-audit-output",
            str(audit_output),
            "--goal-coverage",
            "coverage.json",
            "--goal-gap-queue",
            "gap.json",
            "--goal-failure-plan",
            "failure.json",
        ],
    )
    assert subject.main() == 0
    assert observed["closure"] == after
    assert json.loads(audit_output.read_text(encoding="utf-8"))["goalComplete"] is True
