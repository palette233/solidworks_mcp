#!/usr/bin/env python3
"""Read one SolidWorks document's configuration inventory without editing it."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--direct-stdio", action="store_true", default=True)
    return parser.parse_args()


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def normalized(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if not args.exe.exists():
        raise FileNotFoundError(args.exe)

    started = time.perf_counter()
    with McpClient(
        args.exe.resolve(),
        client_name="inspect-solidworks-document-configurations",
        request_timeout=args.timeout,
        framing="newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        client.call_tool("SolidWorksConnect", {})
        before = client.call_tool("ListDocuments", {})
        before_paths = {
            normalized(str(pick(item, "Path", "")))
            for item in (before or [])
            if str(pick(item, "Path", ""))
        }
        already_open = normalized(source) in before_paths

        inventory = client.call_tool("InspectDocumentConfigurations", {"path": str(source)})

        if not already_open:
            client.call_tool_text("CloseDocument", {"path": str(source)})

    payload = {
        "schemaVersion": "solidworks-document-configuration-inventory-v1",
        "capturedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceDocument": str(source),
        "sourceWasAlreadyOpen": already_open,
        "readOnly": True,
        "durationSeconds": round(time.perf_counter() - started, 6),
        "inventory": inventory,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
