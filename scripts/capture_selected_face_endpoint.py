#!/usr/bin/env python3
"""Capture the selected SolidWorks face and append it to a new catalog file."""

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

from demo_backend.face_endpoint_catalog import append_face_endpoint


DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite catalog: {output}")
    source_catalog = json.loads(args.catalog.resolve().read_text(encoding="utf-8-sig"))
    with McpClient(
        args.exe.resolve(),
        client_name="CaptureSelectedFaceEndpoint",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        entry = client.call_tool(
            "CaptureSelectedFaceEndpoint", {"moduleToken": args.module}
        )
    result = append_face_endpoint(source_catalog, entry)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), "endpointId": entry["EndpointId"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
