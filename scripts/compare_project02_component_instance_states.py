#!/usr/bin/env python3
"""Compare top-level module configuration/solving states in two assemblies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


DEFAULT_COMPONENTS = ["A500", "A700"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", action="append", required=True, type=Path)
    parser.add_argument("--component", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def pick_modules(poses: list[dict[str, Any]], tokens: list[str]) -> list[dict[str, Any]]:
    selected = []
    for token in tokens:
        matches = [
            row
            for row in poses
            if token.casefold()
            in str(row.get("Name", row.get("name", ""))).casefold()
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Token {token!r} resolved to {len(matches)} top-level components.")
        selected.append(matches[0])
    return selected


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    assemblies = [item.resolve() for item in args.assembly]
    tokens = args.component or DEFAULT_COMPONENTS
    output = args.output.resolve()
    for path in [exe, *assemblies]:
        if not path.is_file():
            raise SystemExit(f"Required file does not exist: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)

    captures: list[dict[str, Any]] = []
    with McpClient(
        exe,
        "CodexProject02ComponentStateComparison",
        args.timeout,
        "newline",
        direct_stdio=True,
    ) as client:
        client.call_tool("solid_works_connect", {})
        for assembly in assemblies:
            opened = client.call_tool("open_document", {"path": str(assembly)})
            poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
            modules = pick_modules(poses, tokens)
            captures.append(
                {
                    "assemblyPath": str(assembly),
                    "opened": opened,
                    "modules": modules,
                }
            )
            output.write_text(
                json.dumps({"complete": False, "captures": captures}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    result = {"complete": len(captures) == len(assemblies), "captures": captures}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
