"""Merge staged AABB and leaf-level B-Rep results into one closure report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def pair_key(pair: list[str]) -> tuple[str, str]:
    return tuple(sorted(pair))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--brep-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    screening = json.loads(args.screening.read_text(encoding="utf-8"))
    exact_by_pair: dict[tuple[str, str], dict] = {}
    for batch_path in sorted(args.brep_root.rglob("*_leaf_details_batch.json")):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        for item in batch["pairs"]:
            key = pair_key(item["pair"])
            exact_by_pair[key] = {
                **item,
                "batchPath": str(batch_path.resolve()),
            }

    candidate_keys = {
        pair_key(item["components"])
        for item in screening["exactBrepCandidates"]
    }
    missing = sorted(candidate_keys - exact_by_pair.keys())
    unexpected = sorted(exact_by_pair.keys() - candidate_keys)
    incomplete = [
        item
        for key, item in exact_by_pair.items()
        if key in candidate_keys and item.get("exactCheckComplete") is not True
    ]
    exact_results = [exact_by_pair[key] for key in sorted(candidate_keys & exact_by_pair.keys())]
    interference = [item for item in exact_results if item.get("hasInterference") is True]
    exact_passes = [
        item
        for item in exact_results
        if item.get("exactCheckComplete") is True
        and item.get("hasInterference") is False
    ]
    fully_checked = not missing and not unexpected and not incomplete
    static_collision_passed = (
        screening.get("success") is True and fully_checked and not interference
    )
    payload = {
        "success": static_collision_passed,
        "status": (
            "STATIC_COLLISION_CLOSED"
            if static_collision_passed
            else "STATIC_COLLISION_INTERFERENCE_FOUND"
            if interference and fully_checked
            else "STATIC_COLLISION_VALIDATION_INCOMPLETE"
        ),
        "assemblyPath": screening["assemblyPath"],
        "pairCount": screening["pairCount"],
        "broadPhasePassCount": screening["broadPhasePassCount"],
        "exactBrepCandidateCount": screening["exactBrepCandidateCount"],
        "exactBrepCompleteCount": sum(
            item.get("exactCheckComplete") is True for item in exact_results
        ),
        "exactBrepNoInterferenceCount": len(exact_passes),
        "interferingModulePairCount": len(interference),
        "interferingLeafBodyPairCount": sum(
            int(item.get("interferingBodyPairCount") or 0) for item in interference
        ),
        "missingExactPairs": [list(item) for item in missing],
        "unexpectedExactPairs": [list(item) for item in unexpected],
        "incompleteExactPairs": incomplete,
        "interferingPairs": interference,
        "exactBrepPasses": exact_passes,
        "broadPhasePasses": screening["broadPhasePasses"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
