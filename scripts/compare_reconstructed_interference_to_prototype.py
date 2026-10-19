#!/usr/bin/env python3
"""Compare reconstructed leaf-interference results with prototype baselines."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconstructed-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--baseline",
        action="append",
        nargs=3,
        metavar=("FIRST", "SECOND", "RESULT_JSON"),
        required=True,
    )
    return parser.parse_args()


def get_value(item: dict, pascal: str, camel: str):
    return item.get(pascal, item.get(camel))


def module_pair_key(first: str, second: str) -> str:
    return "||".join(sorted((first, second), key=str.casefold))


def leaf_identity(component: dict) -> str:
    # The full Name includes the occurrence suffix and therefore distinguishes
    # repeated fasteners that reference the same part file.
    name = str(get_value(component, "Name", "name") or "")
    path = str(get_value(component, "Path", "path") or "")
    # Virtual components are materialized below a process-specific SWX< pid >
    # temporary directory.  The directory is not persistent identity; the
    # occurrence-qualified component name plus referenced file basename is.
    referenced_file = path.replace("\\", "/").rsplit("/", 1)[-1]
    return f"{name.casefold()}@@{referenced_file.casefold()}"


def leaf_pair_counter(result: dict) -> Counter[str]:
    counter: Counter[str] = Counter()
    raw = get_value(result, "InterferingBodyPairs", "interferingBodyPairs") or []
    for item in raw:
        first = get_value(item, "FirstComponent", "firstComponent") or {}
        second = get_value(item, "SecondComponent", "secondComponent") or {}
        key = " <-> ".join(sorted((leaf_identity(first), leaf_identity(second))))
        counter[key] += 1
    return counter


def expanded(counter: Counter[str]) -> list[dict]:
    return [{"leafComponentPair": key, "multiplicity": count} for key, count in sorted(counter.items())]


def summarize_result(result: dict) -> dict:
    return {
        "exactCheckComplete": get_value(result, "ExactCheckComplete", "exactCheckComplete") is True,
        "failedBodyPairCount": int(get_value(result, "FailedBodyPairCount", "failedBodyPairCount") or 0),
        "interferingBodyPairCount": int(get_value(result, "InterferingBodyPairCount", "interferingBodyPairCount") or 0),
    }


def main() -> int:
    args = parse_args()
    reconstructed_path = args.reconstructed_report.resolve()
    report = json.loads(reconstructed_path.read_text(encoding="utf-8-sig"))
    reconstructed = {
        module_pair_key(*row["pair"]): row
        for row in report.get("exactChecks") or []
    }
    baselines: dict[str, tuple[list[str], Path, dict]] = {}
    for first, second, raw_path in args.baseline:
        path = Path(raw_path).resolve()
        baselines[module_pair_key(first, second)] = (
            [first, second],
            path,
            json.loads(path.read_text(encoding="utf-8-sig")),
        )

    comparisons = []
    for key, (pair, baseline_path, baseline_result) in sorted(baselines.items()):
        target_row = reconstructed.get(key)
        if target_row is None:
            comparisons.append({"pair": pair, "status": "MISSING_RECONSTRUCTED_RESULT", "success": False})
            continue
        target_result = target_row["result"]
        baseline_counter = leaf_pair_counter(baseline_result)
        target_counter = leaf_pair_counter(target_result)
        added = target_counter - baseline_counter
        missing = baseline_counter - target_counter
        target_summary = summarize_result(target_result)
        baseline_summary = summarize_result(baseline_result)
        complete = target_summary["exactCheckComplete"] and baseline_summary["exactCheckComplete"]
        equivalent = complete and not added and not missing
        comparisons.append(
            {
                "pair": pair,
                "pairKey": key,
                "status": "MATCHES_PROTOTYPE_BASELINE" if equivalent else "INCOMPLETE_BASELINE_COMPARISON" if not complete else "DIFFERS_FROM_PROTOTYPE_BASELINE",
                "success": equivalent,
                "prototypeResultPath": str(baseline_path),
                "prototype": baseline_summary,
                "reconstructed": target_summary,
                "addedLeafComponentPairs": expanded(added),
                "missingLeafComponentPairs": expanded(missing),
                "addedMultiplicity": sum(added.values()),
                "missingMultiplicity": sum(missing.values()),
            }
        )

    payload = {
        "schemaVersion": "project02-reconstructed-prototype-interference-diff/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "reconstructedReport": str(reconstructed_path),
        "comparedPairCount": len(comparisons),
        "matchingPairCount": sum(row.get("success") is True for row in comparisons),
        "differentPairCount": sum(row.get("status") == "DIFFERS_FROM_PROTOTYPE_BASELINE" for row in comparisons),
        "incompletePairCount": sum(row.get("status") == "INCOMPLETE_BASELINE_COMPARISON" for row in comparisons),
        "success": all(row.get("success") is True for row in comparisons),
        "comparisons": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("success", "comparedPairCount", "matchingPairCount", "differentPairCount", "incompletePairCount")}, ensure_ascii=False))
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
