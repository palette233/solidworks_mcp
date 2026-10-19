#!/usr/bin/env python3
"""Verify that an incremental CAD operation did not move existing roots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def pick(row: dict[str, Any], name: str, default: Any = None) -> Any:
    return row.get(name, row.get(name[0].lower() + name[1:], default))


def build(before: dict[str, Any], after: dict[str, Any], tolerance: float) -> dict[str, Any]:
    def index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in payload.get("components") or []:
            key = str(Path(str(pick(row, "Path", ""))).resolve()).casefold()
            if key in result:
                raise ValueError(f"Top-level source path is not unique: {key}")
            result[key] = row
        return result

    left, right = index(before), index(after)
    rows: list[dict[str, Any]] = []
    for key, expected in left.items():
        observed = right.get(key)
        expected_transform = pick(expected, "Transform")
        observed_transform = pick(observed or {}, "Transform")
        error = None
        if isinstance(expected_transform, list) and isinstance(observed_transform, list):
            error = max(
                abs(float(a) - float(b))
                for a, b in zip(expected_transform, observed_transform, strict=True)
            )
        rows.append(
            {
                "sourcePath": str(pick(expected, "Path")),
                "beforeName": pick(expected, "Name"),
                "afterName": pick(observed or {}, "Name"),
                "presentAfter": observed is not None,
                "maximumTransformElementError": error,
                "stable": observed is not None and error is not None and error <= tolerance,
            }
        )
    added = [
        str(pick(row, "Path"))
        for key, row in right.items()
        if key not in left
    ]
    stable = all(row["stable"] for row in rows)
    return {
        "schemaVersion": "top-level-context-pose-comparison/v1",
        "tolerance": tolerance,
        "expectedContextCount": len(left),
        "observedTotalCount": len(right),
        "stableContextCount": sum(row["stable"] for row in rows),
        "addedTopLevelPaths": added,
        "maximumTransformElementError": max(
            (row["maximumTransformElementError"] for row in rows if row["maximumTransformElementError"] is not None),
            default=None,
        ),
        "stable": stable,
        "comparisons": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-10)
    args = parser.parse_args()
    result = build(load(args.before), load(args.after), args.tolerance)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: result[key] for key in ("stable", "expectedContextCount", "stableContextCount", "observedTotalCount", "maximumTransformElementError", "addedTopLevelPaths")}, ensure_ascii=False))
    return 0 if result["stable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
