#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project_calibration import build_calibration_portfolio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a normalized Project01/02/03/05/06 calibration readiness report."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/layout_previews/multi_project_calibration_readiness.json",
    )
    args = parser.parse_args()
    report = build_calibration_portfolio(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
