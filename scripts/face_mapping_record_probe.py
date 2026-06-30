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
        "--proxy",
        "--client",
        client_name,
    ]
    cwd = Path(os.environ.get("DEMO_MCP_CWD", str(DEFAULT_MCP_CWD)))
    return {
        "serverCommand": command,
        "serverArguments": args,
        "workingDirectory": str(cwd),
    }


def call_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    config = mcp_server_config("FaceMappingRecordProbe")
    payload = json.dumps(
        {
            **config,
            "tools": tools,
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
    return data.get("results", [])


def first_text(result: dict[str, Any]) -> str:
    for item in result.get("content", []):
        if item.get("type") == "text":
            return item.get("text", "")
    return ""


def parse_text_json(result: dict[str, Any]) -> dict[str, Any]:
    text = first_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"rawText": text}


def read_mapping(path: Path, component_name: str, face_name: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    component = data.get(component_name)
    if not isinstance(component, dict):
        return None
    value = component.get(face_name)
    return value if isinstance(value, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the currently selected face and print the stored mapping plus probe data.")
    parser.add_argument("--component", required=True, help="Component instance name, e.g. A-1")
    parser.add_argument("--face", default="\u5e95\u9762", help="Face mapping name. Default: bottom face")
    parser.add_argument("--print-mcp-config", action="store_true", help="Print the MCP command/cwd used by this script before running.")
    args = parser.parse_args()

    if args.print_mcp_config:
        print(json.dumps(mcp_server_config("FaceMappingRecordProbe"), ensure_ascii=False, indent=2))
        return

    results = call_tools(
        [
            {
                "tool": "record_face_mapping",
                "arguments": {"faceName": args.face, "componentName": args.component},
            },
            {
                "tool": "get_selected_face_mapping_probe",
                "arguments": {"faceName": args.face, "componentName": args.component},
            },
        ]
    )

    record_result = parse_text_json(results[0])
    probe_result = parse_text_json(results[1])
    mapping_path = Path(probe_result.get("MappingPath") or probe_result.get("mappingPath") or "")
    stored_mapping = read_mapping(mapping_path, args.component, args.face) if mapping_path else None

    print("=== RecordFaceMapping result ===")
    print(json.dumps(record_result, ensure_ascii=False, indent=2))
    print("\n=== Selected face probe ===")
    print(json.dumps(probe_result, ensure_ascii=False, indent=2))
    print("\n=== Stored mapping entry ===")
    print(f"path: {mapping_path}")
    print(json.dumps(stored_mapping, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
