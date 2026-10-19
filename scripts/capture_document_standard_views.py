#!/usr/bin/env python3
"""Open a SolidWorks document and export its six standard orthographic views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    document = args.document.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with McpClient(
        exe,
        client_name="CodexDocumentStandardViews",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        opened = client.call_tool("open_document", {"path": str(document)})
        active = client.call_tool("get_active_document", {})
        views = client.call_tool(
            "export_standard_view_png_set",
            {
                "outputDirectory": str(output_dir),
                "fileNamePrefix": args.prefix,
                "width": args.width,
                "height": args.height,
                "includeBase64Data": False,
            },
        )
        try:
            client.call_tool_text("close_document", {"path": str(document)})
        except RuntimeError:
            # The evidence files are already complete; a read-only/shared close
            # warning must not discard them.
            pass

    print(
        json.dumps(
            {
                "status": "STANDARD_VIEWS_READY",
                "document": str(document),
                "opened": opened,
                "active": active,
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
