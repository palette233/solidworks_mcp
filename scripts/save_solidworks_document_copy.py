#!/usr/bin/env python3
"""Open a SolidWorks document and save a referenced-document-preserving copy."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument("--direct-stdio", action="store_true")
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    with McpClient(
        exe,
        "CodexSaveSolidWorksDocumentCopy",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        opened = client.call_tool("open_document", {"path": str(source)})
        saved = client.call_tool(
            "save_document_as",
            {"outputPath": str(output), "saveAsCopy": True},
        )
        try:
            client.call_tool_text("close_document", {"path": str(source)})
        except RuntimeError:
            pass

    print(
        json.dumps(
            {"success": True, "source": str(source), "output": str(output), "opened": opened, "saved": saved},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
