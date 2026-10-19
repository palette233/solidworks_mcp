#!/usr/bin/env python3
"""Extract one direct AC00 branch from its prototype parent-context snapshot."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def normalize_relative(path: str, branch: str) -> str:
    if path == branch:
        return "@root"
    prefix = f"{branch}/@module/{branch}/"
    if not path.startswith(prefix):
        raise ValueError(f"Path is not in the expected direct branch: {path}")
    result = path[len(prefix) :]
    return result.replace(f"@module/{branch}/", "@module/")


def extract(snapshot: dict[str, Any], branch: str) -> dict[str, Any]:
    source_rows = snapshot.get("components") or []
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        relative = str(row.get("relativeHierarchyPath") or "")
        if relative != branch and not relative.startswith(branch + "/"):
            continue
        item = copy.deepcopy(row)
        item["relativeHierarchyPath"] = normalize_relative(relative, branch)
        item["depthFromModuleRoot"] = (
            0
            if item["relativeHierarchyPath"] == "@root"
            else item["relativeHierarchyPath"].count("/") + 1
        )
        rows.append(item)
    if not rows or rows[0]["relativeHierarchyPath"] != "@root":
        raise ValueError(f"Direct branch root was not found: {branch}")
    rows.sort(key=lambda row: (row["depthFromModuleRoot"], row["relativeHierarchyPath"].casefold()))
    return {
        "schemaVersion": "component-subtree-pose-snapshot/v1",
        "assemblyPath": snapshot.get("assemblyPath"),
        "componentToken": branch,
        "componentCount": len(rows),
        "extractedFromParentContext": True,
        "components": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = extract(load(args.snapshot), args.branch)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output.resolve()), "componentCount": result["componentCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
