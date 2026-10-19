#!/usr/bin/env python3
"""Select and visually focus one catalog EndpointId in SolidWorks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Highlight one saved face EndpointId in SolidWorks.")
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--endpoint-id", required=True)
    parser.add_argument("--no-zoom", action="store_true")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    with McpClient(
        args.exe.resolve(),
        client_name="SelectFaceEndpointInSolidWorks",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "select_face_endpoint_from_catalog" not in tools:
            raise RuntimeError("Published MCP build is missing select_face_endpoint_from_catalog")
        result = client.call_tool(
            "SelectFaceEndpointFromCatalog",
            {
                "catalogPath": str(args.catalog.resolve()),
                "endpointId": args.endpoint_id,
                "zoomToSelection": not args.no_zoom,
            },
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("Success", result.get("success", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
