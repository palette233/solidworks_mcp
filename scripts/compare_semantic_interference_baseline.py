#!/usr/bin/env python3
"""Compare one candidate module-pair exact check against an accepted baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.semantic_assembly_safety import compare_interference_pair_to_baseline


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-report", required=True, type=Path)
    parser.add_argument("--first-token", required=True)
    parser.add_argument("--second-token", required=True)
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = load(args.candidate_report)
    matches = []
    for row in report.get("exactChecks") or []:
        pair_text = " ".join(str(value) for value in row.get("pair") or [])
        if args.first_token.casefold() in pair_text.casefold() and args.second_token.casefold() in pair_text.casefold():
            matches.append(row)
    if len(matches) != 1:
        raise SystemExit(f"Expected one exact check for {args.first_token}/{args.second_token}; found {len(matches)}")

    result = compare_interference_pair_to_baseline(matches[0]["result"], load(args.baseline_result))
    result["candidatePair"] = matches[0]["pair"]
    result["artifacts"] = {
        "candidateReportPath": str(args.candidate_report.resolve()),
        "baselineResultPath": str(args.baseline_result.resolve()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passesNoNewInterferenceGate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
