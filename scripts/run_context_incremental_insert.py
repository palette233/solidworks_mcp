#!/usr/bin/env python3
"""Insert one independent module into a copied assembly context and audit every phase."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient

DEFAULT_EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pick(payload: dict, pascal: str, default=None):
    return payload.get(pascal, payload.get(pascal[0].lower() + pascal[1:], default))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--effective", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", default="A500")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--direct-stdio", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    effective = args.effective.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".context-insert.result.json")).resolve()
    for path in (source, effective, args.exe.resolve()):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() or result.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result}")

    started_at = utc_now()
    started = time.perf_counter()
    print(json.dumps({
        "event": "context-incremental-insert-start",
        "source": str(source),
        "output": str(output),
        "startedAtUtc": started_at,
    }, ensure_ascii=False), flush=True)
    with McpClient(
        args.exe.resolve(),
        "ContextIncrementalInsert",
        args.timeout,
        "newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        tool_result = client.call_tool(
            "InsertComponentInAssemblyContextFromMateGraph",
            {
                "sourceAssemblyPath": str(source),
                "effectiveMateGraphPath": str(effective),
                "outputAssemblyPath": str(output),
                "targetModuleToken": args.target,
            },
        )
    duration = time.perf_counter() - started
    success = bool(pick(tool_result, "Success", False)) and output.is_file()
    envelope = {
        "schemaVersion": "context-incremental-insert-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now(),
        "durationSeconds": duration,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "effectiveGraphPath": str(effective),
        "effectiveGraphSha256": hashlib.sha256(effective.read_bytes()).hexdigest(),
        "outputAssemblyPath": str(output),
        "targetModuleToken": args.target,
        "toolResult": tool_result,
    }
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "event": "context-incremental-insert-finish",
        "success": success,
        "durationSeconds": duration,
        "originalComponentRemoved": pick(tool_result, "OriginalComponentRemoved"),
        "independentComponentInserted": pick(tool_result, "IndependentComponentInserted"),
        "createdMateCount": pick(tool_result, "CreatedMateCount"),
        "parametersMatch": pick(tool_result, "ReopenedMateParametersMatch"),
        "targetFullyConstrained": pick(tool_result, "TargetFullyConstrained"),
        "validationResults": pick(tool_result, "ValidationResults"),
        "contextPoseComparisons": pick(tool_result, "ContextPoseComparisons"),
        "phaseDurationsSeconds": pick(tool_result, "PhaseDurationsSeconds"),
        "result": str(result),
    }, ensure_ascii=False), flush=True)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
