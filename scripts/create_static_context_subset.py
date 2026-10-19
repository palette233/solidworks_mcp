#!/usr/bin/env python3
"""Create and audit a static subset from a solved parent assembly context."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_assembly_entity_annotations import McpClient

DEFAULT_EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pick(value: dict, name: str, default=None):
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--keep", required=True, action="append", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--direct-stdio", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".static-subset.result.json")).resolve()
    keep = [path.resolve() for path in args.keep]
    for path in [source, args.exe.resolve(), *keep]:
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() or result.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result}")
    started_at = now()
    started = time.perf_counter()
    print(json.dumps({"event": "static-subset-start", "source": str(source), "output": str(output), "keepCount": len(keep), "startedAtUtc": started_at}, ensure_ascii=False), flush=True)
    with McpClient(args.exe.resolve(), "StaticContextSubset", args.timeout, "newline", direct_stdio=args.direct_stdio) as client:
        tool = client.call_tool("CreateAssemblyStaticContextSubset", {
            "sourceAssemblyPath": str(source),
            "outputAssemblyPath": str(output),
            "keepComponentPaths": [str(path) for path in keep],
        })
    duration = time.perf_counter() - started
    success = bool(pick(tool, "Success", False)) and output.is_file()
    envelope = {
        "schemaVersion": "static-context-subset-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": now(),
        "durationSeconds": duration,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "outputAssemblyPath": str(output),
        "keptComponentPaths": [str(path) for path in keep],
        "toolResult": tool,
    }
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "static-subset-finish", "success": success, "durationSeconds": duration, "deleted": pick(tool, "DeletedTopLevelComponentCount"), "reopenedCount": pick(tool, "ReopenedTopLevelComponentCount"), "pathsMatch": pick(tool, "PathsMatch"), "rootPosesMatch": pick(tool, "RootPosesMatch"), "phaseDurationsSeconds": pick(tool, "PhaseDurationsSeconds"), "result": str(result)}, ensure_ascii=False), flush=True)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
