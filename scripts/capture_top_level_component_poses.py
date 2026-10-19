#!/usr/bin/env python3
"""Capture top-level poses or one bounded top-level subtree from a saved assembly."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument(
        "--subtree",
        help="Optional top-level hierarchy path/name; capture only this component and its descendants.",
    )
    args = parser.parse_args()

    assembly = args.assembly.resolve()
    output = args.output.resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    with McpClient(
        args.exe.resolve(),
        "CaptureTopLevelComponentPoses",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        client.call_tool("open_document", {"path": str(assembly)})
        client.call_tool("activate_document_by_title", {"title": assembly.stem})
        components = (
            client.call_tool(
                "list_top_level_component_subtree_poses",
                {"hierarchyPath": args.subtree},
            )
            if args.subtree
            else client.call_tool("list_component_poses", {"topLevelOnly": True})
        )
        try:
            client.call_tool_text("close_document", {"path": str(assembly)})
        except RuntimeError:
            pass
    payload = {
        "schemaVersion": (
            "assembly-top-level-component-subtree-poses/v1"
            if args.subtree
            else "assembly-top-level-component-poses/v1"
        ),
        "assemblyPath": str(assembly),
        "subtreeSelector": args.subtree,
        "startedAt": started_at.isoformat(),
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "componentCount": len(components),
        "components": components,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"componentCount": len(components), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
