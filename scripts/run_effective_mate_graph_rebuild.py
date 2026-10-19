#!/usr/bin/env python3
"""Rebuild one compiled editable mate graph and retain a timed audit envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient


DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def _pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild one editable-module-mate-graph/v1 document without overwriting outputs."
    )
    parser.add_argument("--effective", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument(
        "--direct-stdio",
        action="store_true",
        help="Connect to SolidWorks directly instead of using the shared MCP hub proxy.",
    )
    args = parser.parse_args()

    effective = args.effective.resolve()
    output = args.output.resolve()
    result_path = (args.result or output.with_suffix(".result.json")).resolve()
    exe = args.exe.resolve()
    if not effective.is_file():
        raise FileNotFoundError(effective)
    if effective.suffix.lower() != ".json":
        raise ValueError("--effective must reference a JSON document.")
    if output.suffix.lower() != ".sldasm":
        raise ValueError("--output must end in .SLDASM.")
    if output.exists() or result_path.exists():
        raise FileExistsError(f"Refusing to overwrite output or audit: {output} | {result_path}")
    if not exe.is_file():
        raise FileNotFoundError(exe)

    effective_bytes = effective.read_bytes()
    started_at = _utc_now()
    started = time.perf_counter()
    print(
        json.dumps(
            {
                "event": "rebuild-start",
                "effective": str(effective),
                "output": str(output),
                "startedAtUtc": started_at,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    with McpClient(
        exe,
        client_name="EffectiveMateGraphRebuild",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        tools = {str(tool.get("name") or "") for tool in client.list_tools()}
        if "rebuild_assembly_from_mate_graph" not in tools:
            raise RuntimeError("Published MCP build is missing rebuild_assembly_from_mate_graph")
        tool_result = client.call_tool(
            "RebuildAssemblyFromMateGraph",
            {
                "effectiveMateGraphPath": str(effective),
                "outputAssemblyPath": str(output),
            },
        )

    finished_at = _utc_now()
    duration = time.perf_counter() - started
    success = bool(_pick(tool_result, "Success", False)) and output.is_file()
    envelope = {
        "schemaVersion": "effective-mate-graph-rebuild-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": finished_at,
        "durationSeconds": duration,
        "effectiveGraphPath": str(effective),
        "effectiveGraphSha256": hashlib.sha256(effective_bytes).hexdigest(),
        "outputAssemblyPath": str(output),
        "toolResult": tool_result,
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("x", encoding="utf-8") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "event": "rebuild-finish",
                "success": success,
                "durationSeconds": duration,
                "requestedMateCount": _pick(tool_result, "RequestedActiveMateCount"),
                "createdMateCount": _pick(tool_result, "CreatedMateCount"),
                "reopenedMateCount": _pick(tool_result, "ReopenedMateCount"),
                "parametersMatch": _pick(tool_result, "ReopenedMateParametersMatch"),
                "creationErrorsClear": _pick(tool_result, "MateCreationErrorsClear"),
                "transientCreationErrorsResolved": _pick(
                    tool_result, "TransientMateCreationErrorsResolvedOnReopen"
                ),
                "reopenedMateFeatureErrorsClear": _pick(
                    tool_result, "ReopenedMateFeatureErrorsClear"
                ),
                "result": str(result_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
