#!/usr/bin/env python3
"""Build one batch review queue for all transport station gaps; no CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.transport_station_review_queue import (  # noqa: E402
    build_transport_station_review_queue,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gap-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.gap_report.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite review evidence: {output}")
    report = json.loads(source.read_text(encoding="utf-8-sig"))
    result = build_transport_station_review_queue(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        **result["summary"],
        "cadStarted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
