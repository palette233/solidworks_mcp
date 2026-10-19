from __future__ import annotations

import argparse
import json
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
EXE = (
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
OUTPUT = (
    ROOT
    / "demo"
    / "screenshots"
    / "project02_scanner_leaf_views"
    / "project02-sr-x100-bottom-face-0-selected.png"
)
DEFAULT_PART = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目02\01-项目3D图纸\FL9A24D062A000.001"
    r"\248004电气-sr-x100-0801A.SLDPRT"
)
DEFAULT_ASSEMBLY = ROOT / "demo" / "FL9A24D062A000_8modules_clean_solved_v1.SLDASM"
SCANNER_LEAF_IDENTITY = (
    "FL9A24D062A180.001-1/248004电气-sr-x100-0801A-1"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open the SR-X100 leaf silently and confirm its optical face 0."
    )
    parser.add_argument("--part", type=Path, default=DEFAULT_PART)
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--face-index", type=int, default=0)
    parser.add_argument("--proxy", action="store_true")
    args = parser.parse_args()

    part_path = args.part.resolve()
    if not part_path.is_file():
        raise SystemExit(f"Missing SR-X100 part: {part_path}")
    output_path = args.output.resolve()
    assembly_path = args.assembly.resolve()
    if not assembly_path.is_file():
        raise SystemExit(f"Missing lightweight eight-module assembly: {assembly_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with McpClient(
        EXE,
        client_name="Project02ScannerOpticalFaceConfirmation",
        request_timeout=120.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        active_before = client.call_tool("get_active_document", {})
        active_before_info = active_before if isinstance(active_before, dict) else {}
        title = str(
            active_before_info.get("Title")
            or active_before_info.get("title")
            or ""
        )
        if "sr-x100" not in title.lower():
            client.call_tool("open_document", {"path": str(assembly_path)})
            client.call_tool(
                "activate_leaf_component_document", {"componentName": "sr-x100"}
            )
        try:
            view_result = client.call_tool("show_standard_view", {"view": "bottom"})
        except RuntimeError as exc:
            if "Tool returned non-JSON text: Switched to Bottom view." not in str(exc):
                raise
            view_result = {"success": True, "message": "Switched to Bottom view."}
        selection = client.call_tool(
            "select_active_part_face_geometry", {"faceIndex": args.face_index}
        )
        screenshot = client.call_tool(
            "export_current_view_png",
            {
                "outputPath": str(output_path),
                "width": 1600,
                "height": 1000,
                "includeBase64Data": False,
                "fitToView": False,
            },
        )
        probe = client.call_tool(
            "get_selected_face_mapping_probe",
            {
                "faceName": "A180扫描出光面",
                "componentName": SCANNER_LEAF_IDENTITY,
            },
        )
        active_after = client.call_tool("get_active_document", {})

    print(
        json.dumps(
            {
                "status": "OPTICAL_FACE_VISUAL_CONFIRMATION_READY",
                "activeBefore": active_before,
                "activeAfter": active_after,
                "view": view_result,
                "selection": selection,
                "probe": probe,
                "screenshot": screenshot,
                "screenshotPath": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
