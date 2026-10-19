#!/usr/bin/env python3
"""Clone an assembly, change one top-level subassembly solve-as state, and verify reopen."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--solving-state", required=True, type=int, choices=(0, 1))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--views", type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def selected_state(rows: list[dict], selector: str) -> dict:
    matches = [row for row in rows if selector.casefold() in str(row.get("Name", "")).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Selector {selector!r} resolved to {len(matches)} top-level components.")
    return matches[0]


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    source = args.source.resolve()
    target = args.target.resolve()
    output = args.output.resolve()
    views = args.views.resolve() if args.views else None
    for required in (exe, source):
        if not required.is_file():
            raise SystemExit(f"Required file does not exist: {required}")
    if target.exists():
        raise SystemExit(f"Target already exists; refusing to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if views:
        views.mkdir(parents=True, exist_ok=True)

    result: dict = {
        "success": False,
        "sourceAssemblyPath": str(source),
        "targetAssemblyPath": str(target),
        "componentSelector": args.component,
        "requestedSolvingState": args.solving_state,
    }
    with McpClient(exe, "CodexSolveAsStateClone", args.timeout, "newline", direct_stdio=True) as client:
        client.call_tool("solid_works_connect", {})
        result["openedSource"] = client.call_tool("open_document", {"path": str(source)})
        before = client.call_tool("list_component_poses", {"topLevelOnly": True})
        result["before"] = selected_state(before, args.component)
        result["saveAs"] = client.call_tool(
            "save_document_as",
            {"outputPath": str(target), "saveAsCopy": False},
        )
        result["stateChange"] = client.call_tool(
            "set_top_level_component_solving_state",
            {
                "hierarchyPath": result["before"]["HierarchyPath"],
                "solvingState": args.solving_state,
                "rebuild": True,
            },
        )
        result["save"] = client.call_tool("save_document", {"path": str(target)})
        after = client.call_tool("list_component_poses", {"topLevelOnly": True})
        result["after"] = selected_state(after, args.component)
        if views:
            result["views"] = client.call_tool(
                "export_standard_view_png_set",
                {
                    "outputDirectory": str(views),
                    "fileNamePrefix": target.stem,
                    "width": 1600,
                    "height": 900,
                    "includeBase64Data": False,
                },
            )
        result["close"] = client.call_tool_text("close_document", {"path": str(target)})
        result["reopened"] = client.call_tool("open_document", {"path": str(target)})
        reopened = client.call_tool("list_component_poses", {"topLevelOnly": True})
        result["reopenedState"] = selected_state(reopened, args.component)

    actual = int(result["reopenedState"].get("SolvingState", -1))
    result["success"] = bool(result["stateChange"].get("Success")) and actual == args.solving_state
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
