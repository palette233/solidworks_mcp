#!/usr/bin/env python3
"""Compare two component-subtree pose snapshots by relative hierarchy path."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    return parser.parse_args()


def load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def pick(row: dict, name: str, default=None):
    return row.get(name, row.get(name[0].upper() + name[1:], default))


def indexed_components(payload: dict) -> dict[str, dict]:
    rows = payload.get("components", payload.get("Components", []))
    if not rows:
        return {}
    root_hierarchy = str(pick(rows[0], "hierarchyPath", ""))
    result: dict[str, dict] = {}
    for row in rows:
        relative = pick(row, "relativeHierarchyPath")
        if not relative:
            hierarchy = str(pick(row, "hierarchyPath", ""))
            if hierarchy == root_hierarchy:
                relative = "@root"
            elif root_hierarchy and hierarchy.startswith(root_hierarchy + "/"):
                relative = hierarchy[len(root_hierarchy) + 1 :]
            else:
                relative = hierarchy
        normalised = dict(row)
        normalised["transform"] = pick(row, "transform")
        normalised["translation"] = pick(row, "translation")
        result[str(relative)] = normalised
    return result


def transform_error(left: list[float] | None, right: list[float] | None) -> float | None:
    if left is None or right is None or len(left) != len(right):
        return None
    return max(abs(float(a) - float(b)) for a, b in zip(left, right, strict=True))


def translation_distance(left: list[float] | None, right: list[float] | None) -> float | None:
    if left is None or right is None or len(left) < 3 or len(right) < 3:
        return None
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def main() -> int:
    args = parse_args()
    reference = load(args.reference)
    candidate = load(args.candidate)
    ref = indexed_components(reference)
    got = indexed_components(candidate)
    rows = []
    for path in sorted(set(ref) | set(got), key=str.casefold):
        left, right = ref.get(path), got.get(path)
        error = transform_error(left and left.get("transform"), right and right.get("transform"))
        distance = translation_distance(left and left.get("translation"), right and right.get("translation"))
        rows.append(
            {
                "relativeHierarchyPath": path,
                "presentInReference": left is not None,
                "presentInCandidate": right is not None,
                "maximumTransformElementError": error,
                "translationDistanceMeters": distance,
                "stable": left is not None and right is not None and error is not None and error <= args.tolerance,
            }
        )
    unstable = [row for row in rows if not row["stable"]]
    result = {
        "schemaVersion": "component-subtree-pose-comparison/v1",
        "referencePath": str(args.reference.resolve()),
        "candidatePath": str(args.candidate.resolve()),
        "tolerance": args.tolerance,
        "comparedCount": len(rows),
        "unstableCount": len(unstable),
        "maximumTranslationDistanceMeters": max(
            (row["translationDistanceMeters"] for row in rows if row["translationDistanceMeters"] is not None),
            default=None,
        ),
        "maximumTransformElementError": max(
            (row["maximumTransformElementError"] for row in rows if row["maximumTransformElementError"] is not None),
            default=None,
        ),
        "stable": not unstable,
        "comparisons": rows,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("comparedCount", "unstableCount", "maximumTranslationDistanceMeters", "stable")}, ensure_ascii=False))
    return 0 if result["stable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
