#!/usr/bin/env python3
"""Derive a review-only scanner cross-track translation candidate; never CAD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_point_pair_binding import (  # noqa: E402
    derive_scanner_cross_track_translation_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evaluation_path = args.evaluation.resolve()
    output = args.output.resolve()
    for path in (evaluation_path, output.parent):
        path.relative_to(ROOT)
    if output.exists():
        parser.error("Output already exists; preserve old evidence and choose a new path")
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8-sig"))
    result = derive_scanner_cross_track_translation_candidate(evaluation)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "translationMagnitudeMeters": result[
                    "translationMagnitudeMeters"
                ],
                "cadLaunchAllowed": result["cadLaunchAllowed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
