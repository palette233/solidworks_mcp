#!/usr/bin/env python3
"""Bind a data-selected scanner/transport proxy to current saved CAD poses.

No CAD access. Omitting --rule preserves the original AI00/SS00/AA00 rule.
After any cumulative change, rerun against the new --state; never copy reports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_target_rule import build_current_scanner_target  # noqa: E402,F401


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rule", type=Path, help="scanner-target-rule/v1 JSON; repository-relative input paths")
    parser.add_argument("--scanner-instance")
    parser.add_argument("--transport-instance")
    parser.add_argument("--base-instance")
    parser.add_argument("--authorize-prototype-estimate", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; preserve old evidence and choose a fresh directory")
    selectors = {role: value for role, value in (
        ("scanner", args.scanner_instance), ("transport", args.transport_instance),
        ("targetBase", args.base_instance)) if value is not None}
    report = build_current_scanner_target(
        state_path=args.state, rule_path=args.rule, instance_selectors=selectors,
        authorize_prototype_estimate=args.authorize_prototype_estimate)
    args.output.mkdir(parents=True)
    for name, value in report.items():
        (args.output / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({**report["summary"], "timing": report["timing"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
