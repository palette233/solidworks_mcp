#!/usr/bin/env python3
"""Build a deduplicated semantic decision request; never start CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cleaning_service_region import (  # noqa: E402
    build_cleaning_capability_semantic_decision_request,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capability-index", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite decision evidence: {output}")
    report = build_cleaning_capability_semantic_decision_request(
        ROOT, args.capability_index
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
