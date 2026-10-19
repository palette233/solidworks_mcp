#!/usr/bin/env python3
"""Gracefully exit one SolidWorks COM session through the MCP lifecycle tool."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "apps/demo-backend/tools/McpToolRunner/bin/Release/net8.0/McpToolRunner.dll"
)
MCP_DLL = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/"
    "net8.0-windows/win-x64/SolidWorksMcpApp.dll"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-all-documents-saved",
        action="store_true",
        help="Required acknowledgement before SolidWorks is exited.",
    )
    args = parser.parse_args()
    if not args.confirm_all_documents_saved:
        raise SystemExit("Refusing to exit: pass --confirm-all-documents-saved.")

    payload = {
        "serverCommand": "dotnet",
        "serverArguments": [str(MCP_DLL), "--stdio-direct"],
        "workingDirectory": str(MCP_DLL.parent),
        "tools": [
            {
                "tool": "exit_solid_works",
                "arguments": {"confirmAllDocumentsSaved": True},
            }
        ],
    }
    completed = subprocess.run(
        ["dotnet", str(RUNNER)],
        cwd=ROOT,
        input=json.dumps(payload).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.decode("utf-8", errors="replace"))
    if completed.returncode != 0:
        print(completed.stderr.decode("utf-8", errors="replace"))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
