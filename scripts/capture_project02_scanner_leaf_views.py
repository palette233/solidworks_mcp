from __future__ import annotations

import argparse
import json
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor"
    / "solidworks-mcp"
    / "app"
    / "SolidWorksMcpApp"
    / "bin"
    / "Release"
    / "net8.0-windows"
    / "win-x64"
    / "SolidWorksMcpApp.exe"
)
DEFAULT_OUTPUT = ROOT / "demo" / "screenshots" / "project02_scanner_leaf_views"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export six standard views of the Project02 SR-X100 leaf document."
    )
    parser.add_argument("--document-title", default="FL9A24D062A000.001")
    parser.add_argument("--leaf-component", default="sr-x100")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with McpClient(
        args.exe.resolve(),
        client_name="Project02ScannerLeafViews",
        request_timeout=120.0,
        framing="lsp",
        direct_stdio=True,
    ) as client:
        assembly = client.call_tool(
            "activate_document_by_title", {"title": args.document_title}
        )
        activation = client.call_tool(
            "activate_leaf_component_document",
            {"componentName": args.leaf_component},
        )
        active_leaf = client.call_tool("get_active_document", {})
        views = client.call_tool(
            "export_standard_view_png_set",
            {
                "outputDirectory": str(output_dir),
                "fileNamePrefix": "project02-sr-x100",
                "width": 1600,
                "height": 1000,
                "includeBase64Data": False,
            },
        )
        client.call_tool(
            "activate_document_by_title", {"title": args.document_title}
        )

    print(
        json.dumps(
            {
                "status": "SCANNER_LEAF_VIEWS_READY",
                "assembly": assembly,
                "activation": activation,
                "activeLeaf": active_leaf,
                "views": views,
                "outputDirectory": str(output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
