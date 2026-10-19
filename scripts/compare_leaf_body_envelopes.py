#!/usr/bin/env python3
"""Compare two leaf-body envelope captures after removing their common rigid shift."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    return parser.parse_args()


def bodies(path: Path) -> list[dict]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    captures = payload.get("captures") or []
    if len(captures) != 1 or captures[0].get("CoverageComplete") is not True:
        raise RuntimeError(f"Expected one complete leaf capture: {path}")
    return captures[0].get("Bodies") or []


def key(body: dict) -> tuple[str, int]:
    component = body.get("Component") or {}
    return str(component.get("Name") or component.get("HierarchyPath")), int(body.get("BodyIndex", 0))


def center(box: list[float]) -> list[float]:
    return [(float(box[index]) + float(box[index + 3])) / 2.0 for index in range(3)]


def child_group(name: str) -> str:
    parts = name.split("/")
    return parts[1] if len(parts) > 1 else "@root"


def main() -> int:
    args = parse_args()
    reference = {key(item): item for item in bodies(args.reference)}
    candidate = {key(item): item for item in bodies(args.candidate)}
    common = sorted(set(reference) & set(candidate))
    if not common:
        raise RuntimeError("The captures have no matching component/body keys.")

    raw_deltas = []
    for item_key in common:
        first = center(reference[item_key]["BoundingBoxWorld"])
        second = center(candidate[item_key]["BoundingBoxWorld"])
        raw_deltas.append([second[index] - first[index] for index in range(3)])
    common_shift = [median(delta[index] for delta in raw_deltas) for index in range(3)]

    comparisons = []
    for item_key, delta in zip(common, raw_deltas):
        residual = [delta[index] - common_shift[index] for index in range(3)]
        magnitude = math.sqrt(sum(value * value for value in residual))
        comparisons.append(
            {
                "componentName": item_key[0],
                "bodyIndex": item_key[1],
                "childGroup": child_group(item_key[0]),
                "centerDeltaMeters": delta,
                "residualAfterCommonShiftMeters": residual,
                "residualMagnitudeMeters": magnitude,
                "changed": magnitude > args.tolerance,
            }
        )
    comparisons.sort(key=lambda item: item["residualMagnitudeMeters"], reverse=True)
    group_summary = []
    for group in sorted({item["childGroup"] for item in comparisons}):
        rows = [item for item in comparisons if item["childGroup"] == group]
        group_summary.append(
            {
                "childGroup": group,
                "bodyCount": len(rows),
                "changedBodyCount": sum(item["changed"] for item in rows),
                "maximumResidualMeters": max(item["residualMagnitudeMeters"] for item in rows),
            }
        )
    result = {
        "success": True,
        "reference": str(args.reference.resolve()),
        "candidate": str(args.candidate.resolve()),
        "toleranceMeters": args.tolerance,
        "referenceBodyCount": len(reference),
        "candidateBodyCount": len(candidate),
        "matchedBodyCount": len(common),
        "unmatchedReferenceBodyCount": len(set(reference) - set(candidate)),
        "unmatchedCandidateBodyCount": len(set(candidate) - set(reference)),
        "inferredCommonRigidShiftMeters": common_shift,
        "changedBodyCount": sum(item["changed"] for item in comparisons),
        "maximumResidualMeters": comparisons[0]["residualMagnitudeMeters"],
        "groupSummary": group_summary,
        "largestResiduals": comparisons[:30],
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
