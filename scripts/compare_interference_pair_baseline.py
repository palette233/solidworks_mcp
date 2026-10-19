"""Compare exact interfering leaf pairs against an accepted prototype baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def pair_set(payload: dict) -> set[tuple[str, str]]:
    return {
        (
            str(item["FirstComponent"]["Name"]),
            str(item["SecondComponent"]["Name"]),
        )
        for item in payload.get("InterferingBodyPairs", [])
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    baseline_payload = json.loads(args.baseline.resolve().read_text(encoding="utf-8"))
    candidate_payload = json.loads(args.candidate.resolve().read_text(encoding="utf-8"))
    baseline = pair_set(baseline_payload)
    candidate = pair_set(candidate_payload)
    added = sorted(candidate - baseline)
    missing = sorted(baseline - candidate)
    exact_complete = (
        baseline_payload.get("ExactCheckComplete") is True
        and candidate_payload.get("ExactCheckComplete") is True
        and int(baseline_payload.get("FailedBodyPairCount", 0) or 0) == 0
        and int(candidate_payload.get("FailedBodyPairCount", 0) or 0) == 0
    )
    success = exact_complete and not added
    result = {
        "success": success,
        "exactChecksComplete": exact_complete,
        "baseline": str(args.baseline.resolve()),
        "candidate": str(args.candidate.resolve()),
        "baselineInterferingPairCount": len(baseline),
        "candidateInterferingPairCount": len(candidate),
        "addedInterferingPairs": added,
        "missingBaselinePairs": missing,
        "decision": "no_new_interference_over_baseline" if success else "candidate_adds_interference",
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
