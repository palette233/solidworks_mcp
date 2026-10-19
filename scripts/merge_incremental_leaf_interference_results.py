#!/usr/bin/env python3
"""Merge a baseline exact B-Rep batch with an incremental recheck batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-batch", required=True, type=Path)
    parser.add_argument("--incremental-batch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def canonical_pair(values: list[str]) -> tuple[str, str]:
    if len(values) != 2:
        raise ValueError(f"Expected a two-component pair, got {values!r}")
    return tuple(sorted(str(value) for value in values))


def load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def detail_metrics(pair: dict) -> dict[str, int]:
    path = Path(str(pair.get("outputPath") or ""))
    if not path.is_file():
        return {"failedBodyPairCount": 0}
    detail = load(path)
    return {"failedBodyPairCount": int(detail.get("FailedBodyPairCount", 0))}


def main() -> int:
    args = parse_args()
    baseline = load(args.baseline_batch)
    incremental = load(args.incremental_batch)
    merged: dict[tuple[str, str], dict] = {}

    for source_name, batch in (("baseline", baseline), ("incremental", incremental)):
        for item in batch.get("pairs", []):
            pair = dict(item)
            pair["resultSource"] = source_name
            pair.update(detail_metrics(pair))
            merged[canonical_pair(pair["pair"])] = pair

    pairs = [merged[key] for key in sorted(merged)]
    exact_count = sum(bool(item.get("exactCheckComplete")) for item in pairs)
    interfering_pairs = [item for item in pairs if bool(item.get("hasInterference"))]
    failed_body_pairs = sum(int(item.get("failedBodyPairCount") or 0) for item in pairs)
    result = {
        "success": exact_count == len(pairs) and failed_body_pairs == 0,
        "staticInterferenceFree": not interfering_pairs,
        "baselineBatch": str(args.baseline_batch.resolve()),
        "incrementalBatch": str(args.incremental_batch.resolve()),
        "mergeRule": "Incremental results override baseline results for the same unordered component pair.",
        "pairCount": len(pairs),
        "exactCheckCompleteCount": exact_count,
        "failedBodyPairCount": failed_body_pairs,
        "interferingModulePairCount": len(interfering_pairs),
        "interferingBodyPairCount": sum(
            int(item.get("interferingBodyPairCount") or 0) for item in pairs
        ),
        "interferingPairs": [
            {
                "pair": item["pair"],
                "interferingBodyPairCount": int(item.get("interferingBodyPairCount") or 0),
                "resultSource": item["resultSource"],
                "outputPath": item.get("outputPath"),
            }
            for item in interfering_pairs
        ],
        "pairs": pairs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
