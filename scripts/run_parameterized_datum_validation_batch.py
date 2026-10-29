#!/usr/bin/env python3
"""Inspect or advance one item in an ordered set of datum-validation queues."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameterized_datum_validation_batch import (  # noqa: E402
    build_parameterized_datum_validation_batch_status,
)


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "plan-next", "run-next"))
    parser.add_argument("--queue-dir", type=Path, action="append", required=True)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    args = parser.parse_args()
    queue_dirs = [_resolve(path) for path in args.queue_dir]
    status = build_parameterized_datum_validation_batch_status(ROOT, queue_dirs)
    if args.action == "status":
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    next_queue = status.get("nextQueueDirectory")
    if not next_queue:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["status"] == "complete" else 2
    command = [
        sys.executable,
        "scripts/run_parameterized_datum_validation_queue.py",
        "plan-next" if args.action == "plan-next" else "run-next",
        next_queue,
        "--session-check-timeout",
        str(args.session_check_timeout),
    ]
    if args.action == "plan-next":
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, check=False
        )
        payload = {
            **status,
            "nextCommand": command,
            "nextPlanReturnCode": completed.returncode,
            "nextPlanStdout": completed.stdout.decode("utf-8", errors="replace"),
            "nextPlanStderr": completed.stderr.decode("utf-8", errors="replace"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return completed.returncode
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
