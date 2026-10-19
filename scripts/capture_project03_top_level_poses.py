#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient


EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目03\01-项目3D图纸\FL9A24D063A000.001-0415\FL9A24D063A000.001.SLDASM"
)
OUTPUT = ROOT / "demo/layout_previews/project03_top_level_poses.json"


def main() -> int:
    with McpClient(
        EXE,
        client_name="Project03TopLevelPoseCapture",
        request_timeout=1200.0,
        framing="newline",
        direct_stdio=True,
    ) as client:
        opened = client.call_tool("open_document", {"path": str(SOURCE)})
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        close_warning = None
        try:
            client.call_tool_text("close_document", {"path": str(SOURCE)})
        except RuntimeError as exc:
            close_warning = str(exc)

    payload = {
        "schemaVersion": "project03-top-level-poses/v1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "sourceAssemblyPath": str(SOURCE),
        "opened": opened,
        "componentCount": len(poses) if isinstance(poses, list) else 0,
        "components": poses,
        "closeWarning": close_warning,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(OUTPUT), "componentCount": payload["componentCount"], "closeWarning": close_warning}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
