#!/usr/bin/env python3
"""Inspect or execute the next item in one serial read-only recheck batch set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.saved_output_station_inspection_batch import (  # noqa: E402
    build_saved_output_inspection_batch_status,
)


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "plan-next", "run-next"))
    parser.add_argument("--batch-report", type=Path, action="append", required=True)
    parser.add_argument("--session-check-timeout", type=float, default=20.0)
    args = parser.parse_args()
    reports = [_resolve(path) for path in args.batch_report]
    status = build_saved_output_inspection_batch_status(ROOT, reports)
    if args.action == "status":
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    request = status.get("nextRequestPath")
    if not request:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["status"] == "complete" else 2
    command = [
        sys.executable,
        "scripts/run_saved_output_station_inspection.py",
        "plan" if args.action == "plan-next" else "run",
        request,
        "--session-check-timeout",
        str(args.session_check_timeout),
    ]
    if args.action == "plan-next":
        print(
            json.dumps(
                {**status, "nextCommand": command},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
