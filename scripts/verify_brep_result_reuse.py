"""Verify that an exact pair result can be reused after a new Replay.

A passing B-Rep result is reusable only when the two components preserve their
relative rigid transform.  A common global translation does not invalidate the
result; changing either component relative to the other does.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def replay_poses(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    step = next(
        item for item in payload.get("steps", []) if item.get("tool") == "list_component_poses"
    )
    return {item["Name"]: item for item in step["payload"]}


def dot(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def pair_signature(first: dict[str, Any], second: dict[str, Any]) -> list[float]:
    first_axes = [
        [float(value) for value in first[name]] for name in ("XAxis", "YAxis", "ZAxis")
    ]
    second_axes = [
        [float(value) for value in second[name]] for name in ("XAxis", "YAxis", "ZAxis")
    ]
    delta = [
        float(first["Translation"][index]) - float(second["Translation"][index])
        for index in range(3)
    ]
    relative_rotation = [dot(first_axis, second_axis) for first_axis in first_axes for second_axis in second_axes]
    relative_translation = [dot(delta, axis) for axis in second_axes]
    return [*relative_rotation, *relative_translation]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-replay", required=True, type=Path)
    parser.add_argument("--current-replay", required=True, type=Path)
    parser.add_argument("--previous-exact-result", required=True, type=Path)
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    args = parser.parse_args()

    previous = replay_poses(args.previous_replay.resolve())
    current = replay_poses(args.current_replay.resolve())
    exact = json.loads(args.previous_exact_result.resolve().read_text(encoding="utf-8"))
    old_signature = pair_signature(previous[args.first], previous[args.second])
    new_signature = pair_signature(current[args.first], current[args.second])
    maximum_error = max(abs(a - b) for a, b in zip(old_signature, new_signature, strict=True))
    exact_passed = (
        exact.get("ExactCheckComplete") is True
        and exact.get("HasInterference") is False
        and int(exact.get("FailedBodyPairCount", 0) or 0) == 0
    )
    eligible = exact_passed and math.isfinite(maximum_error) and maximum_error <= args.tolerance
    result = {
        "success": eligible,
        "reuseEligible": eligible,
        "firstComponent": args.first,
        "secondComponent": args.second,
        "previousReplay": str(args.previous_replay.resolve()),
        "currentReplay": str(args.current_replay.resolve()),
        "previousExactResult": str(args.previous_exact_result.resolve()),
        "previousExactResultPassed": exact_passed,
        "relativeTransformMaximumElementError": maximum_error,
        "tolerance": args.tolerance,
        "decision": "reuse_exact_pass" if eligible else "rerun_exact_brep",
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if eligible else 1


if __name__ == "__main__":
    raise SystemExit(main())
