#!/usr/bin/env python3
"""Inspect, plan or advance the next action in the station-closure program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.station_closure_program import (  # noqa: E402
    build_station_closure_program_status,
)
from demo_backend.six_role_goal_acceptance_audit import (  # noqa: E402
    build_six_role_goal_acceptance_audit,
)


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def _build_status(args: argparse.Namespace) -> dict:
    return build_station_closure_program_status(
        ROOT,
        [_resolve(path) for path in args.saved_output_batch_report],
        [_resolve(path) for path in args.fresh_validation_queue_dir],
        _resolve(args.scanner_chain_batch_report),
        (
            _resolve(args.six_role_chain_batch_report)
            if args.six_role_chain_batch_report
            else None
        ),
    )


def _write_status(path: Path | None, status: dict) -> None:
    if path is None:
        return
    output = _resolve(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_goal_audit(args: argparse.Namespace) -> None:
    if args.goal_audit_output is None:
        return
    report = build_six_role_goal_acceptance_audit(
        ROOT,
        _resolve(args.goal_coverage),
        _resolve(args.goal_gap_queue),
        _resolve(args.status_output),
        _resolve(args.six_role_chain_batch_report),
        _resolve(args.goal_failure_plan),
    )
    output = _resolve(args.goal_audit_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_command(args: argparse.Namespace, status: dict) -> list[str] | None:
    action = status.get("nextAction") or {}
    phase = action.get("phaseId")
    if action.get("action") == "review_failure":
        return None
    if phase == "saved_output_readonly_postchecks":
        command = [
            sys.executable,
            "scripts/run_saved_output_station_inspection_batch.py",
            "run-next",
        ]
        for report in args.saved_output_batch_report:
            command.extend(["--batch-report", str(report)])
        command.extend(["--session-check-timeout", str(args.session_check_timeout)])
        return command
    if phase == "fresh_nonprototype_cad_validations":
        command = [
            sys.executable,
            "scripts/run_parameterized_datum_validation_batch.py",
            "run-next",
        ]
        for queue in args.fresh_validation_queue_dir:
            command.extend(["--queue-dir", str(queue)])
        command.extend(["--session-check-timeout", str(args.session_check_timeout)])
        return command
    if phase == "scanner_current_context_chains":
        return [
            sys.executable,
            "scripts/run_staged_chain_execution_batch.py",
            "run-next",
            str(args.scanner_chain_batch_report),
            "--session-check-timeout",
            str(args.session_check_timeout),
        ]
    if phase == "new_six_role_cumulative_chain":
        command = [
            sys.executable,
            "scripts/run_staged_chain_execution_batch.py",
            "run-next",
            str(args.six_role_chain_batch_report),
            "--session-check-timeout",
            str(args.session_check_timeout),
        ]
        if args.six_role_inject_failure_chain_id:
            command.extend(
                [
                    "--inject-failure-chain-id",
                    args.six_role_inject_failure_chain_id,
                    "--inject-failure-before-stage",
                    args.six_role_inject_failure_before_stage,
                ]
            )
        return command
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "plan-next", "run-next"))
    parser.add_argument(
        "--saved-output-batch-report", type=Path, action="append", required=True
    )
    parser.add_argument(
        "--fresh-validation-queue-dir", type=Path, action="append", required=True
    )
    parser.add_argument("--scanner-chain-batch-report", type=Path, required=True)
    parser.add_argument("--six-role-chain-batch-report", type=Path)
    parser.add_argument("--six-role-inject-failure-chain-id")
    parser.add_argument("--six-role-inject-failure-before-stage")
    parser.add_argument(
        "--status-output",
        type=Path,
        help=(
            "Write the current status for status/plan-next, or the refreshed "
            "post-action status for run-next."
        ),
    )
    parser.add_argument("--goal-audit-output", type=Path)
    parser.add_argument("--goal-coverage", type=Path)
    parser.add_argument("--goal-gap-queue", type=Path)
    parser.add_argument("--goal-failure-plan", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    args = parser.parse_args()
    if bool(args.six_role_inject_failure_chain_id) != bool(
        args.six_role_inject_failure_before_stage
    ):
        parser.error(
            "--six-role-inject-failure-chain-id and "
            "--six-role-inject-failure-before-stage must be used together"
        )
    goal_values = (
        args.goal_audit_output,
        args.goal_coverage,
        args.goal_gap_queue,
        args.goal_failure_plan,
        args.status_output,
        args.six_role_chain_batch_report,
    )
    if any(value is not None for value in goal_values[:4]) and not all(
        value is not None for value in goal_values
    ):
        parser.error(
            "--goal-audit-output requires --goal-coverage, --goal-gap-queue, "
            "--goal-failure-plan, --status-output and "
            "--six-role-chain-batch-report"
        )
    status = _build_status(args)
    if args.action == "status":
        _write_status(args.status_output, status)
        _write_goal_audit(args)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    command = _build_command(args, status)
    if not command:
        _write_status(args.status_output, status)
        _write_goal_audit(args)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["status"] == "complete" else 2
    if args.action == "plan-next":
        _write_status(args.status_output, status)
        _write_goal_audit(args)
        print(
            json.dumps(
                {**status, "nextCommand": command}, ensure_ascii=False, indent=2
            )
        )
        return 0
    result = subprocess.run(command, cwd=ROOT, check=False)
    # A non-zero result can be an intentionally injected failure.  Always
    # rebuild and persist status so the next invocation sees ``resume`` rather
    # than relying on the stale pre-action snapshot.
    refreshed = _build_status(args)
    _write_status(args.status_output, refreshed)
    _write_goal_audit(args)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
