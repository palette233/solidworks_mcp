#!/usr/bin/env python3
"""Generate the read-only completion audit for the six-role Goal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.six_role_goal_acceptance_audit import (  # noqa: E402
    build_six_role_goal_acceptance_audit,
)


def _resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--gap-queue", type=Path, required=True)
    parser.add_argument("--closure-status", type=Path, required=True)
    parser.add_argument("--acceptance-batch", type=Path, required=True)
    parser.add_argument("--failure-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_six_role_goal_acceptance_audit(
        ROOT,
        _resolve(args.coverage),
        _resolve(args.gap_queue),
        _resolve(args.closure_status),
        _resolve(args.acceptance_batch),
        _resolve(args.failure_plan),
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = _resolve(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["goalComplete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
