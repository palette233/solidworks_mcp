#!/usr/bin/env python3
"""Capture transformed leaf-body AABBs for selected SolidWorks module instances."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--component", action="append", required=True)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument(
        "--reuse-active",
        action="store_true",
        help="Reuse the active document when it is already the requested assembly.",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse complete component captures already present in --output.",
    )
    return parser.parse_args()


def capture_name(capture: dict[str, object]) -> str:
    top = capture.get("TopLevelComponent") or capture.get("topLevelComponent") or {}
    if not isinstance(top, dict):
        return ""
    return str(top.get("Name") or top.get("name") or top.get("HierarchyPath") or top.get("hierarchyPath") or "")


def write_progress(
    output: Path,
    assembly: Path,
    opened: object,
    captures: list[dict[str, object]],
    requested: list[str],
    *,
    error: str | None = None,
) -> None:
    payload = {
        "schemaVersion": 2,
        "assemblyPath": str(assembly),
        "opened": opened,
        "captures": captures,
        "requestedComponents": requested,
        "completedComponents": [capture_name(item) for item in captures],
        "complete": error is None and len(captures) == len(requested),
        "error": error,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    assembly = args.assembly.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    captures: list[dict[str, object]] = []
    if args.reuse_existing and output.is_file():
        existing = json.loads(output.read_text(encoding="utf-8-sig"))
        captures = [
            item
            for item in existing.get("captures") or []
            if item.get("CoverageComplete", item.get("coverageComplete")) is True
        ]
    existing_names = {capture_name(item).casefold() for item in captures}
    opened: object = None
    opened_by_script = False
    with McpClient(
        exe,
        "CodexLeafBodyEnvelopeCapture",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        try:
            if args.reuse_active:
                active = client.call_tool("get_active_document", {})
                active_path = str(active.get("Path", active.get("path", ""))) if isinstance(active, dict) else ""
                if active_path and Path(active_path).resolve() == assembly:
                    opened = {"reusedAlreadyOpenDocument": True, "document": active}
                else:
                    opened = client.call_tool("open_document", {"path": str(assembly)})
                    opened_by_script = True
            else:
                opened = client.call_tool("open_document", {"path": str(assembly)})
                opened_by_script = True
            write_progress(output, assembly, opened, captures, args.component)
            for component in args.component:
                if any(component.casefold() in name for name in existing_names):
                    continue
                result = client.call_tool(
                    "capture_leaf_body_envelopes",
                    {"hierarchyPath": component},
                )
                captures.append(result)
                existing_names.add(capture_name(result).casefold())
                write_progress(output, assembly, opened, captures, args.component)
        except BaseException as exc:
            write_progress(output, assembly, opened, captures, args.component, error=str(exc))
            raise
        finally:
            if opened_by_script:
                try:
                    client.call_tool_text("close_document", {"path": str(assembly)})
                except RuntimeError:
                    # Durable incremental captures take precedence over a
                    # read-only/sharing close warning.
                    pass

    write_progress(output, assembly, opened, captures, args.component)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
