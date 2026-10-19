#!/usr/bin/env python3
"""Resolve failed leaf-body B-rep pairs with SolidWorks' official selector check."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from capture_assembly_entity_annotations import McpClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--leaf-result", required=True, type=Path)
    parser.add_argument(
        "--pair",
        nargs=2,
        metavar=("FIRST", "SECOND"),
        help="When --leaf-result is a batch/full report, select this module pair's embedded result.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument("--force-new-instance", action="store_true")
    return parser.parse_args()


def pick(item: dict, pascal: str, camel: str):
    return item.get(pascal, item.get(camel))


def parse_failure(value: str) -> tuple[str, str]:
    pair_text = value.rsplit(": ", 1)[0]
    parts = pair_text.split(" <-> ")
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError(f"Could not parse failed leaf pair: {value}")
    return parts[0].strip(), parts[1].strip()


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    assembly = args.assembly.resolve()
    leaf_result_path = args.leaf_result.resolve()
    output = args.output.resolve()
    source_document = json.loads(leaf_result_path.read_text(encoding="utf-8-sig"))
    source = source_document
    if args.pair and isinstance(source_document.get("exactChecks"), list):
        requested = {value.casefold() for value in args.pair}
        matches = [
            row
            for row in source_document["exactChecks"]
            if {str(value).casefold() for value in row.get("pair") or []} == requested
        ]
        if len(matches) != 1:
            raise ValueError(f"Embedded module pair {args.pair!r} resolved to {len(matches)} results")
        source = matches[0]["result"]
    failures = [str(value) for value in (pick(source, "Failures", "failures") or [])]
    pairs = list(dict.fromkeys(parse_failure(value) for value in failures))
    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    started = time.perf_counter()
    opened_by_script = False
    results = []
    close_warning = None
    with McpClient(
        exe,
        "CodexLeafInterferenceFailureFallback",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        active = None
        try:
            active = client.call_tool("get_active_document", {})
        except RuntimeError:
            pass
        active_path = str(pick(active, "Path", "path") or "") if isinstance(active, dict) else ""
        if not active_path or Path(active_path).resolve() != assembly:
            opened = client.call_tool("open_document", {"path": str(assembly)})
            opened_by_script = True
        else:
            opened = {"reusedAlreadyOpenDocument": True, "document": active}

        for index, pair in enumerate(pairs, start=1):
            pair_started = time.perf_counter()
            try:
                result = client.call_tool(
                    "check_interference",
                    {
                        "hierarchyPaths": list(pair),
                        "treatCoincidenceAsInterference": False,
                    },
                )
                results.append(
                    {
                        "index": index,
                        "hierarchyPaths": list(pair),
                        "success": True,
                        "hasInterference": pick(result, "HasInterference", "hasInterference"),
                        "result": result,
                        "durationSeconds": round(time.perf_counter() - pair_started, 6),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "index": index,
                        "hierarchyPaths": list(pair),
                        "success": False,
                        "error": str(exc),
                        "durationSeconds": round(time.perf_counter() - pair_started, 6),
                    }
                )

        if opened_by_script:
            try:
                client.call_tool_text("close_document", {"path": str(assembly)})
            except RuntimeError as exc:
                close_warning = str(exc)

    payload = {
        "schemaVersion": "leaf-interference-failure-fallback/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "assemblyPath": str(assembly),
        "sourceLeafResult": str(leaf_result_path),
        "opened": opened,
        "requestedFailurePairCount": len(pairs),
        "completedFallbackPairCount": sum(row["success"] for row in results),
        "success": all(row["success"] for row in results),
        "results": results,
        "closeWarning": close_warning,
        "durationSeconds": round(time.perf_counter() - started, 6),
        "interpretation": (
            "These checks use SolidWorks ToolsCheckInterference2 on the exact leaf component pair "
            "when the lower-level modeler/Boolean B-rep methods returned an error."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": payload["success"], "pairCount": len(pairs), "output": str(output)}, ensure_ascii=False))
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
