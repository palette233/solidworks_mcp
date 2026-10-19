#!/usr/bin/env python3
"""Close, reopen and recapture the saved Project 01 solution 1 assembly."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_assembly_entity_annotations import McpClient  # noqa: E402


DEFAULT_EXE = ROOT / "artifacts/solidworks-mcp-20260810-startupready/SolidWorksMcpApp.exe"
DEFAULT_ASSEMBLY = ROOT / "demo/project01/FL9C24N074AA00_project01_solution1_v1.SLDASM"
DEFAULT_SCREENSHOT = ROOT / "demo/screenshots/project01_solution1_v1_reopened.png"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project01_solution1_v1_reopened_capture.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    assembly = args.assembly.resolve()
    screenshot = args.screenshot.resolve()
    output = args.output.resolve()
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    with McpClient(args.exe.resolve(), "Project01Solution1Reopen", 900.0, "newline", direct_stdio=True) as client:
        active_before = client.call_tool("get_active_document", {})
        active_path = str(active_before.get("Path", active_before.get("path", ""))) if isinstance(active_before, dict) else ""
        close_before = None
        if active_path and Path(active_path).resolve() == assembly:
            close_before = client.call_tool_text("close_document", {"path": str(assembly)})
        opened = client.call_tool("open_document", {"path": str(assembly)})
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        rebuild = client.call_tool("get_active_document_rebuild_state", {})
        image = client.call_tool("export_current_view_png", {
            "outputPath": str(screenshot), "width": 1600, "height": 900, "includeBase64Data": False,
        })
        close_after = client.call_tool_text("close_document", {"path": str(assembly)})

    payload = {
        "schemaVersion": 1,
        "caseId": "project01",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "assemblyPath": str(assembly),
        "activeBefore": active_before,
        "closeBefore": close_before,
        "opened": opened,
        "componentCount": len(poses) if isinstance(poses, list) else 0,
        "components": poses,
        "rebuildState": rebuild,
        "screenshot": image,
        "closeAfter": close_after,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": payload["componentCount"] == 10 and screenshot.is_file(), "componentCount": payload["componentCount"], "output": str(output), "screenshot": str(screenshot)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
