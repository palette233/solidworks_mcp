#!/usr/bin/env python3
"""Capture one component subtree's local transforms for parent-context audits."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--component", required=True, help="Top-level component token, for example A700.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def pick(row: dict, key: str, default=None):
    return row.get(key, row.get(key[0].lower() + key[1:], default))


def main() -> int:
    args = parse_args()
    assembly = args.assembly.resolve()
    exe = args.exe.resolve()
    output = args.output.resolve()
    for required in (assembly, exe):
        if not required.is_file():
            raise FileNotFoundError(required)
    output.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    with McpClient(exe, "ComponentSubtreePoseCapture", args.timeout, "newline", direct_stdio=True) as client:
        client.call_tool("solid_works_connect", {})
        opened = client.call_tool("open_document", {"path": str(assembly)})
        activated = client.call_tool("activate_document_by_title", {"title": assembly.stem})
        rows = client.call_tool("list_component_poses", {"topLevelOnly": False})

    token = args.component.casefold()
    roots = [
        row
        for row in rows
        if int(pick(row, "Depth", -1)) == 0 and token in str(pick(row, "Name", "")).casefold()
    ]
    if len(roots) != 1:
        raise RuntimeError(f"Component token {args.component!r} resolved to {len(roots)} top-level roots.")
    root_path = str(pick(roots[0], "HierarchyPath"))
    root_instance_name = str(pick(roots[0], "Name", "")).split("/")[-1]
    root_instance_base = re.sub(r"-\d+$", "", root_instance_name, flags=re.IGNORECASE)
    prefix = root_path + "/"
    selected = [
        row
        for row in rows
        if str(pick(row, "HierarchyPath", "")) == root_path
        or str(pick(row, "HierarchyPath", "")).startswith(prefix)
    ]
    normalized = []
    for row in selected:
        hierarchy = str(pick(row, "HierarchyPath", ""))
        relative = "@root" if hierarchy == root_path else hierarchy[len(prefix) :]
        # SolidWorks recursively reports a nested child's hierarchy with the
        # module root instance repeated once.  A freshly inserted module gets a
        # new instance suffix (-2 instead of -1), so remove that implementation
        # detail before comparing the same subtree across assemblies.
        if relative != "@root" and "/" in relative:
            first, remainder = relative.split("/", 1)
            if first.casefold() == root_instance_name.casefold():
                relative = remainder
        if relative != "@root":
            relative = "/".join(
                "@module"
                if re.sub(r"-\d+$", "", segment, flags=re.IGNORECASE).casefold()
                == root_instance_base.casefold()
                else segment
                for segment in relative.split("/")
            )
        normalized.append(
            {
                "name": pick(row, "Name"),
                "path": pick(row, "Path"),
                "hierarchyPath": hierarchy,
                "relativeHierarchyPath": relative,
                "depthFromModuleRoot": 0 if relative == "@root" else relative.count("/") + 1,
                "transform": pick(row, "Transform"),
                "translation": pick(row, "Translation"),
                "referencedConfiguration": pick(row, "ReferencedConfiguration"),
                "solvingState": pick(row, "SolvingState"),
                "solvingStateName": pick(row, "SolvingStateName"),
            }
        )
    normalized.sort(key=lambda row: (row["depthFromModuleRoot"], row["relativeHierarchyPath"].casefold()))
    result = {
        "schemaVersion": "component-subtree-pose-snapshot/v1",
        "capturedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": time.perf_counter() - started,
        "assemblyPath": str(assembly),
        "componentToken": args.component,
        "rootHierarchyPath": root_path,
        "componentCount": len(normalized),
        "opened": opened,
        "activated": activated,
        "components": normalized,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "componentCount": len(normalized), "durationSeconds": result["durationSeconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
