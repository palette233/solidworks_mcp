#!/usr/bin/env python3
"""Inspect, plan or advance one chain from a recompilation batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_backend.staged_chain_execution_batch import (  # noqa: E402
    build_staged_chain_execution_batch_status,
)
from run_global_cad_transaction_packet import (  # noqa: E402
    capture_open_document_baseline,
)


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def _build_chain_command(
    next_action: dict[str, str],
    *,
    inject_failure_chain_id: str | None = None,
    inject_failure_before_stage: str | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_natural_language_staged_chain.py",
        next_action["action"],
        next_action["outputRoot"],
    ]
    if (
        next_action["action"] == "run"
        and inject_failure_chain_id == next_action["chainId"]
    ):
        command.extend(
            ["--inject-failure-before-stage", inject_failure_before_stage]
        )
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "plan-next", "run-next"))
    parser.add_argument("batch_report", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    parser.add_argument("--inject-failure-chain-id")
    parser.add_argument("--inject-failure-before-stage")
    args = parser.parse_args()
    if bool(args.inject_failure_chain_id) != bool(args.inject_failure_before_stage):
        parser.error(
            "--inject-failure-chain-id and --inject-failure-before-stage must be used together"
        )
    status = build_staged_chain_execution_batch_status(
        ROOT, _resolve(args.batch_report)
    )
    if args.action == "status":
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    next_action = status.get("nextAction")
    if not next_action:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["status"] == "complete" else 2
    command = _build_chain_command(
        next_action,
        inject_failure_chain_id=args.inject_failure_chain_id,
        inject_failure_before_stage=args.inject_failure_before_stage,
    )
    if args.action == "plan-next":
        print(
            json.dumps(
                {**status, "nextCommand": command}, ensure_ascii=False, indent=2
            )
        )
        return 0
    baseline = capture_open_document_baseline(timeout=args.session_check_timeout)
    if int(baseline.get("openDocumentCount") or 0) != 0:
        print(
            json.dumps(
                {
                    "success": False,
                    "reason": "solidworks_session_not_clean",
                    "baseline": baseline,
                    "cadStarted": False,
                },
                ensure_ascii=False,
            )
        )
        return 2
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
