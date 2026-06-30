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
    config = mcp_server_config("ApplyCapturedCommonBaseLayout")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply captured common-base layout2d positions to a SolidWorks assembly.")
    parser.add_argument("--layout", default=str(ROOT / "demo" / "captured_common_base_layout.json"), help="Captured layout JSON path.")
    parser.add_argument("--assembly", default=None, help="Optional target assembly path. If omitted, uses the active assembly.")
    parser.add_argument("--screenshot", default=str(ROOT / "demo" / "apply_captured_layout_result.png"), help="Optional output screenshot path.")
    args = parser.parse_args()

    layout_path = Path(args.layout)
    assembly_path = Path(args.assembly) if args.assembly else None
    screenshot_path = Path(args.screenshot) if args.screenshot else None

    arguments: dict[str, Any] = {
        "layoutJsonPath": str(layout_path if layout_path.is_absolute() else ROOT / layout_path),
        "assemblyPath": str(assembly_path if assembly_path is None or assembly_path.is_absolute() else ROOT / assembly_path) if assembly_path else None,
        "screenshotPath": str(screenshot_path if screenshot_path is None or screenshot_path.is_absolute() else ROOT / screenshot_path) if screenshot_path else None,
        "screenshotWidth": 1600,
        "screenshotHeight": 900,
        "includeScreenshotBase64Data": False,
    }
    result = call_tool("apply_captured_common_base_layout", arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
