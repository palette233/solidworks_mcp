from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "apps" / "demo-backend" / "tools" / "McpToolRunner" / "bin" / "Release" / "net8.0" / "McpToolRunner.dll"
DEFAULT_MCP_CWD = ROOT / "vendor" / "solidworks-mcp" / "app" / "SolidWorksMcpApp" / "bin" / "Release" / "net8.0-windows" / "win-x64"


def mcp_server_config(client_name: str) -> dict[str, Any]:
    command = os.environ.get("DEMO_MCP_COMMAND", "dotnet")
    args_text = os.environ.get("DEMO_MCP_ARGS")
    args = shlex.split(args_text, posix=False) if args_text else [
        "SolidWorksMcpApp.dll",
        "--stdio-direct",
    ]
    cwd = Path(os.environ.get("DEMO_MCP_CWD", str(DEFAULT_MCP_CWD)))
    return {
        "serverCommand": command,
        "serverArguments": args,
        "workingDirectory": str(cwd),
    }


def call_tool(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    config = mcp_server_config("CaptureCommonBaseLayout")
    payload = json.dumps(
        {
            **config,
            "tools": [{"tool": tool, "arguments": arguments}],
        },
        ensure_ascii=True,
    )
    completed = subprocess.run(
        ["dotnet", str(RUNNER)],
        cwd=ROOT,
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.decode("utf-8", errors="replace"))

    data = json.loads(completed.stdout.decode("utf-8"))
    results = data.get("results", [])
    if not results:
        raise SystemExit("MCP runner returned no results.")

    text = ""
    for item in results[0].get("content", []):
        if item.get("type") == "text":
            text = item.get("text", "")
            break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"rawText": text}


def parse_component(value: str) -> dict[str, str]:
    if ":" in value:
        name, face = value.split(":", 1)
        return {"componentName": name, "bottomFaceName": face}
    return {"componentName": value, "bottomFaceName": "\u5e95\u9762"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture common-base 2D layout data from the active/source SolidWorks assembly.")
    parser.add_argument("--source", default=None, help="Optional source assembly path. If omitted, uses the active SolidWorks assembly.")
    parser.add_argument("--output", default=str(ROOT / "demo" / "captured_common_base_layout.json"), help="Output layout JSON path.")
    parser.add_argument("--base-component", default=None, help="Optional base component instance name. Defaults to the first captured component.")
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        help="Component to capture. Use NAME or NAME:FACE. Repeat for multiple components. If omitted, captures all top-level components.",
    )
    args = parser.parse_args()

    components = [parse_component(item) for item in args.component]
    arguments: dict[str, Any] = {
        "sourceAssemblyPath": args.source,
        "components": components or None,
        "baseComponentName": args.base_component,
        "outputPath": args.output,
    }
    result = call_tool("capture_common_base_layout_from_assembly", arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
