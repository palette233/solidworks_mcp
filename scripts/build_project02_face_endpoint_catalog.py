#!/usr/bin/env python3
"""Build the Project 02 A500/A700 reusable planar face-endpoint catalog."""

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
DEFAULT_SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目02\01-项目3D图纸\FL9A24D062A000.001\FL9A24D062A000.001.SLDASM"
)
DEFAULT_OUTPUT = ROOT / "demo/mate_graph_edit/face_catalog/project02_A500_A700_planar_faces_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tokens", nargs="+", default=["A500", "A700"])
    parser.add_argument("--minimum-face-area", type=float, default=1e-4)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite catalog: {output}")

    with McpClient(
        args.exe.resolve(),
        client_name="Project02FaceEndpointCatalog",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "build_face_endpoint_catalog" not in tools:
            raise RuntimeError("Published MCP build is missing build_face_endpoint_catalog")
        result = client.call_tool(
            "BuildFaceEndpointCatalog",
            {
                "sourceAssemblyPath": str(args.source.resolve()),
                "moduleTokens": args.tokens,
                "outputPath": str(output),
                "sourceMateFacesOnly": True,
                "planarOnly": True,
                "minimumFaceArea": args.minimum_face_area,
                "saveJson": True,
            },
        )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "moduleCount": result.get("ModuleCount", result.get("moduleCount")),
                "endpointCount": result.get("EndpointCount", result.get("endpointCount")),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
