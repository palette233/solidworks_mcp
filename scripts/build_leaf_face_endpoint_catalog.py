#!/usr/bin/env python3
"""Build one bounded leaf-face catalog and optionally merge it into an existing catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.face_endpoint_catalog import merge_face_endpoint_catalogs


DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan faces from one unique leaf component without traversing sibling leaves."
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--leaf", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-catalog", type=Path)
    parser.add_argument("--merged-output", type=Path)
    parser.add_argument("--minimum-face-area", type=float, default=1e-8)
    parser.add_argument("--maximum-face-count", type=int, default=500)
    parser.add_argument("--include-nonplanar", action="store_true")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite leaf catalog: {output}")
    if bool(args.base_catalog) != bool(args.merged_output):
        raise ValueError("--base-catalog and --merged-output must be supplied together.")
    merged_output = args.merged_output.resolve() if args.merged_output else None
    if merged_output and merged_output.exists():
        raise FileExistsError(f"Refusing to overwrite merged catalog: {merged_output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with McpClient(
        args.exe.resolve(),
        client_name="BuildLeafFaceEndpointCatalog",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "build_leaf_face_endpoint_catalog" not in tools:
            raise RuntimeError("Published MCP build is missing build_leaf_face_endpoint_catalog")
        result = client.call_tool(
            "BuildLeafFaceEndpointCatalog",
            {
                "sourceAssemblyPath": str(args.source.resolve()),
                "moduleToken": args.module,
                "leafSelector": args.leaf,
                "outputPath": str(output),
                "planarOnly": not args.include_nonplanar,
                "minimumFaceArea": args.minimum_face_area,
                "maximumFaceCount": args.maximum_face_count,
                "saveJson": True,
            },
        )

    merged_count = None
    if args.base_catalog and merged_output:
        base = json.loads(args.base_catalog.resolve().read_text(encoding="utf-8-sig"))
        leaf_catalog = json.loads(output.read_text(encoding="utf-8-sig"))
        merged = merge_face_endpoint_catalogs(base, leaf_catalog)
        merged_output.parent.mkdir(parents=True, exist_ok=True)
        merged_output.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        merged_count = merged["EndpointCount"]

    print(
        json.dumps(
            {
                "success": True,
                "leafCatalog": str(output),
                "leafEndpointCount": result.get("EndpointCount", result.get("endpointCount")),
                "mergedCatalog": str(merged_output) if merged_output else None,
                "mergedEndpointCount": merged_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
