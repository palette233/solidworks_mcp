#!/usr/bin/env python3
"""Capture Project05 top-level poses and the module-level mate graph in one read-only load."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_assembly_entity_annotations import McpClient  # noqa: E402
from export_project02_module_mate_graph import make_summary, pick  # noqa: E402


EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目05\01-项目3D图纸\1.CITLD254098_L3 Apply epoxy glue to CMC header [4台]"
    r"\1.CITLD254098_L3 Apply epoxy glue to CMC header [4台]\FL9C254098AA00.001.SLDASM"
)
POSE_OUTPUT = ROOT / "demo/layout_previews/project05_top_level_poses.json"
GRAPH_OUTPUT = ROOT / "demo/layout_previews/project05_module_mate_graph.json"
SUMMARY_OUTPUT = ROOT / "demo/layout_previews/project05_module_mate_graph.summary.md"
TOKENS = ["A000", "B000", "Z000", "D000", "E000", "F000", "G000", "K000", "M000", "N000", "P000"]


def main() -> int:
    POSE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    close_warning = None
    with McpClient(
        EXE,
        client_name="Project05FirstStageCapture",
        request_timeout=1800.0,
        framing="newline",
        direct_stdio=True,
    ) as client:
        opened = client.call_tool("open_document", {"path": str(SOURCE)})
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        graph = client.call_tool(
            "ExportModuleMateGraph",
            {
                "sourceAssemblyPath": str(SOURCE),
                "moduleTokens": TOKENS,
                "outputPath": str(GRAPH_OUTPUT),
                "saveJson": True,
            },
        )
        try:
            client.call_tool_text("close_document", {"path": str(SOURCE)})
        except RuntimeError as exc:
            close_warning = str(exc)

    pose_payload = {
        "schemaVersion": "project05-top-level-poses/v1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "sourceAssemblyPath": str(SOURCE),
        "opened": opened,
        "componentCount": len(poses) if isinstance(poses, list) else 0,
        "components": poses,
        "closeWarning": close_warning,
    }
    POSE_OUTPUT.write_text(json.dumps(pose_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_OUTPUT.write_text(make_summary(graph, "项目05"), encoding="utf-8")
    result = {
        "success": True,
        "poseOutput": str(POSE_OUTPUT),
        "componentCount": pose_payload["componentCount"],
        "graphOutput": str(GRAPH_OUTPUT),
        "summaryOutput": str(SUMMARY_OUTPUT),
        "moduleCount": pick(graph, "ModuleCount", 0),
        "interModuleMateCount": pick(graph, "InterModuleMateCount", 0),
        "mateBundleCount": pick(graph, "MateBundleCount", 0),
        "closeWarning": close_warning,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
