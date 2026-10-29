#!/usr/bin/env python3
"""Evaluate a module-local scanner/barcode point pair in one saved CAD state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.scanner_point_pair_binding import (  # noqa: E402
    build_scanner_point_pair_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", required=True, type=Path)
    parser.add_argument("--measurement", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; preserve old evidence and choose a new path")
    report = build_scanner_point_pair_report(
        rule_path=args.rule, measurement_path=args.measurement, state_path=args.state
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "status": report["status"],
                "targetAssociationBound": report["targetAssociationBound"],
                "processProxyValidationPassed": report[
                    "processProxyValidationPassed"
                ],
                "cadExecuted": report["cadExecuted"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
