#!/usr/bin/env python3
"""Combine CAD reconstruction and exact interference reports into one hard gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.semantic_assembly_safety import build_semantic_assembly_release_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconstruction", required=True, type=Path)
    parser.add_argument("--interference", required=True, type=Path)
    parser.add_argument("--baseline-comparison", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    reconstruction = json.loads(args.reconstruction.read_text(encoding="utf-8-sig"))
    interference = json.loads(args.interference.read_text(encoding="utf-8-sig"))
    baseline_comparisons = [
        json.loads(path.read_text(encoding="utf-8-sig"))
        for path in args.baseline_comparison
    ]
    gate = build_semantic_assembly_release_gate(
        reconstruction, interference, baseline_comparisons
    )
    gate["artifacts"] = {
        "reconstructionResultPath": str(args.reconstruction.resolve()),
        "interferenceResultPath": str(args.interference.resolve()),
        "baselineComparisonPaths": [str(path.resolve()) for path in args.baseline_comparison],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["releaseAllowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
