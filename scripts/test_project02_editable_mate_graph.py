#!/usr/bin/env python3
"""Compile-time inputs already prepared; rebuild and verify editable Project 02 mate graphs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)
DEFAULT_DIR = ROOT / "demo/mate_graph_edit"
SCENARIOS = {
    "baseline": "project02_A500_A700_baseline",
    "delete": "project02_A500_A700_delete",
    "update": "project02_A500_A700_distance60",
    "add": "project02_A500_A700_replace_distance",
    "endpoint_ids": "project02_A500_A700_endpoint_ids_distance60",
    "selected_face_perpendicular": "project02_A500_A700_selected_face_perpendicular",
    "leaf_scanned_perpendicular": "project02_A500_A700_leaf_scanned_perpendicular",
}


def pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--scenarios", nargs="+", choices=sorted(SCENARIOS), default=list(SCENARIOS))
    parser.add_argument("--version", default="v1")
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    directory = args.dir.resolve()
    outputs: dict[str, dict[str, Any]] = {}
    for scenario in args.scenarios:
        stem = SCENARIOS[scenario]
        effective = directory / f"{stem}.effective.json"
        output = directory / f"{stem}_rebuilt_{args.version}.SLDASM"
        result_path = directory / f"{stem}_rebuilt_{args.version}.result.json"
        if not effective.exists():
            raise FileNotFoundError(effective)
        if output.exists() or result_path.exists():
            raise FileExistsError(f"Refusing to overwrite scenario '{scenario}': {output}")
        outputs[scenario] = {
            "effective": str(effective),
            "output": str(output),
            "result": str(result_path),
        }

    with McpClient(
        args.exe.resolve(),
        client_name="Project02EditableMateGraphClosure",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "rebuild_assembly_from_mate_graph" not in tools:
            raise RuntimeError("Published MCP build is missing rebuild_assembly_from_mate_graph")
        for scenario in args.scenarios:
            item = outputs[scenario]
            result = client.call_tool(
                "RebuildAssemblyFromMateGraph",
                {
                    "effectiveMateGraphPath": item["effective"],
                    "outputAssemblyPath": item["output"],
                },
            )
            Path(item["result"]).write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            item.update(
                {
                    "success": bool(pick(result, "Success", False)),
                    "requestedMateCount": int(pick(result, "RequestedActiveMateCount", -1)),
                    "createdMateCount": int(pick(result, "CreatedMateCount", -1)),
                    "reopenedMateCount": int(pick(result, "ReopenedMateCount", -1)),
                    "parametersMatch": bool(pick(result, "ReopenedMateParametersMatch", False)),
                }
            )
            print(json.dumps({"scenario": scenario, **item}, ensure_ascii=False), flush=True)

    summary = {
        "schemaVersion": "editable-mate-graph-closure-summary/v1",
        "success": all(item.get("success") for item in outputs.values()),
        "scenarios": outputs,
    }
    summary_path = directory / f"project02_A500_A700_editable_closure_{args.version}.summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "success": summary["success"]}, ensure_ascii=False))
    return 0 if summary["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
