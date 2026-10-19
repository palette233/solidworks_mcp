#!/usr/bin/env python3
"""Clone an assembly, translate one nested component, save/reopen, and verify."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--component", required=True)
    parser.add_argument("--delta", required=True, nargs=3, type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def select(rows: list[dict], token: str) -> dict:
    token_key = token.casefold()
    matches = [
        row
        for row in rows
        if token_key in str(row.get("Name", "")).casefold()
        and int(row.get("Depth", -1)) > 0
    ]
    exact_tail = [
        row
        for row in matches
        if str(row.get("Name", "")).casefold().endswith(token_key)
    ]
    if len(exact_tail) == 1:
        return exact_tail[0]
    if len(matches) != 1:
        raise RuntimeError(f"Nested selector {token!r} resolved to {len(matches)} components.")
    return matches[0]


def translation_error(before: dict, after: dict, delta: list[float]) -> float:
    expected = [float(before["Translation"][i]) + delta[i] for i in range(3)]
    return max(abs(float(after["Translation"][i]) - expected[i]) for i in range(3))


def main() -> int:
    args = parse_args()
    exe, source, target, output = (
        args.exe.resolve(),
        args.source.resolve(),
        args.target.resolve(),
        args.output.resolve(),
    )
    for required in (exe, source):
        if not required.is_file():
            raise SystemExit(f"Required file does not exist: {required}")
    if target.exists():
        raise SystemExit(f"Target already exists; refusing to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    delta = [float(value) for value in args.delta]

    result: dict = {
        "success": False,
        "sourceAssemblyPath": str(source),
        "targetAssemblyPath": str(target),
        "componentSelector": args.component,
        "requestedWorldDeltaMeters": delta,
    }
    with McpClient(exe, "CodexNestedResidualAnchor", args.timeout, "newline", direct_stdio=True) as client:
        client.call_tool("solid_works_connect", {})
        result["openedSource"] = client.call_tool("open_document", {"path": str(source)})
        before_rows = client.call_tool("list_component_poses", {"topLevelOnly": False})
        before = select(before_rows, args.component)
        result["before"] = before
        result["saveAs"] = client.call_tool(
            "save_document_as", {"outputPath": str(target), "saveAsCopy": False}
        )
        result["move"] = client.call_tool(
            "move_component",
            {
                "componentName": before["Name"],
                "deltaX": delta[0],
                "deltaY": delta[1],
                "deltaZ": delta[2],
            },
        )
        result["save"] = client.call_tool("save_document", {"path": str(target)})
        after_rows = client.call_tool("list_component_poses", {"topLevelOnly": False})
        result["after"] = select(after_rows, args.component)
        result["immediateTranslationErrorMeters"] = translation_error(before, result["after"], delta)
        result["close"] = client.call_tool_text("close_document", {"path": str(target)})
        result["reopened"] = client.call_tool("open_document", {"path": str(target)})
        reopened_rows = client.call_tool("list_component_poses", {"topLevelOnly": False})
        result["reopenedState"] = select(reopened_rows, args.component)
        result["reopenedTranslationErrorMeters"] = translation_error(
            before, result["reopenedState"], delta
        )

    result["success"] = (
        bool(result["move"].get("Success"))
        and result["immediateTranslationErrorMeters"] <= 1e-6
        and result["reopenedTranslationErrorMeters"] <= 1e-6
    )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
