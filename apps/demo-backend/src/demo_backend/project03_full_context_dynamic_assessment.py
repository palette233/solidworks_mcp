from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def _pick(value: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def leaf_source_pair_multiset(result: dict[str, Any]) -> Counter[tuple[str, str]]:
    """Return an orientation-independent multiset of interfering leaf source-file pairs."""

    identities: Counter[tuple[str, str]] = Counter()
    for row in _pick(result, "InterferingBodyPairs", "interferingBodyPairs", default=[]) or []:
        first = _pick(row, "FirstComponent", "firstComponent", default={}) or {}
        second = _pick(row, "SecondComponent", "secondComponent", default={}) or {}
        first_name = Path(str(_pick(first, "Path", "path", default=""))).name.casefold()
        second_name = Path(str(_pick(second, "Path", "path", default=""))).name.casefold()
        if not first_name or not second_name:
            raise ValueError("Interfering body pair is missing a leaf component source path.")
        identities[tuple(sorted((first_name, second_name)))] += 1
    return identities


def assess_against_prototype_baseline(
    actual: dict[str, Any],
    baseline: dict[str, Any],
    *,
    require_exact_baseline: bool,
) -> dict[str, Any]:
    actual_ids = leaf_source_pair_multiset(actual)
    baseline_ids = leaf_source_pair_multiset(baseline)
    new_ids = actual_ids - baseline_ids
    missing_ids = baseline_ids - actual_ids
    exact_complete = bool(_pick(actual, "ExactCheckComplete", "exactCheckComplete", default=False))
    failed_pairs = int(_pick(actual, "FailedBodyPairCount", "failedBodyPairCount", default=-1))
    identity_gate = not new_ids and (not require_exact_baseline or not missing_ids)
    passed = exact_complete and failed_pairs == 0 and identity_gate
    return {
        "passed": passed,
        "requireExactBaseline": require_exact_baseline,
        "exactCheckComplete": exact_complete,
        "failedBodyPairCount": failed_pairs,
        "actualInterferingBodyPairCount": sum(actual_ids.values()),
        "baselineInterferingBodyPairCount": sum(baseline_ids.values()),
        "actualLeafSourcePairs": _serialise(actual_ids),
        "baselineLeafSourcePairs": _serialise(baseline_ids),
        "newLeafSourcePairs": _serialise(new_ids),
        "missingBaselineLeafSourcePairs": _serialise(missing_ids),
        "status": (
            "PASSED_EXACT_SELECTED_BASELINE_REPRODUCTION"
            if passed and require_exact_baseline
            else "PASSED_NO_NEW_INTERFERENCE_OVER_SELECTED_BASELINE"
            if passed
            else "FAILED_FULL_CONTEXT_BASELINE_GATE"
        ),
    }


def _serialise(counter: Counter[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"leafSourcePair": list(pair), "count": count}
        for pair, count in sorted(counter.items())
        if count
    ]
