#!/usr/bin/env python3
"""Run the Project 02 two-subassembly mate export/rebuild/reopen closure."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


DEFAULT_SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目02\01-项目3D图纸\FL9A24D062A000.001\FL9A24D062A000.001.SLDASM"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--first", default="A180")
    parser.add_argument("--second", default="A800")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--candidates-only", action="store_true")
    parser.add_argument("--roundtrip-only", action="store_true")
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = (args.output or Path("demo/project02_A180_A800_mate_roundtrip_v1.SLDASM")).resolve()
    result_path = (args.result or output.with_suffix(".result.json")).resolve()
    export_path = output.with_suffix(".mates.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    with McpClient(
        args.exe.resolve(),
        client_name="Project02MatePairClosure",
        request_timeout=args.timeout,
        framing="newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        required = {"export_mate_pair", "find_mate_pair_candidates", "round_trip_mate_pair"}
        missing = sorted(required - tools)
        if missing:
            raise RuntimeError(f"Published MCP build is missing tools: {missing}")

        payload: dict[str, object] = {}
        inspection: dict[str, object] | None = None
        if not args.candidates_only and not args.roundtrip_only:
            inspection = client.call_tool(
                "ExportMatePair",
                {
                    "sourceAssemblyPath": str(args.source.resolve()),
                    "firstModuleSelector": args.first,
                    "secondModuleSelector": args.second,
                    "outputPath": str(export_path),
                    "saveJson": True,
                },
            )
            payload["inspection"] = inspection
        if args.candidates_only or (
            not args.roundtrip_only
            and int((inspection or {}).get("RebuildableMateCount", (inspection or {}).get("rebuildableMateCount", 0))) == 0
        ):
            payload["candidates"] = client.call_tool(
                "FindMatePairCandidates",
                {
                    "sourceAssemblyPath": str(args.source.resolve()),
                    "allowedModuleTokens": ["A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401"],
                    "maxResults": 10,
                },
            )

        if not args.inspect_only and not args.candidates_only:
            # RoundTripMatePair owns its output files and refuses to overwrite them.
            if export_path.exists():
                export_path.unlink()
            payload["roundTrip"] = client.call_tool(
                "RoundTripMatePair",
                {
                    "sourceAssemblyPath": str(args.source.resolve()),
                    "firstModuleSelector": args.first,
                    "secondModuleSelector": args.second,
                    "outputAssemblyPath": str(output),
                    "exportJsonPath": str(export_path),
                    "allowAutomaticFallback": True,
                    "allowedModuleTokens": ["A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401"],
                },
            )

    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(result_path), "output": str(output), "data": payload}, ensure_ascii=False))
    round_trip = payload.get("roundTrip")
    if isinstance(round_trip, dict):
        return 0 if bool(round_trip.get("Success", round_trip.get("success", False))) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
