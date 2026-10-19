#!/usr/bin/env python3
"""Reopen the saved Project03 solution and verify persisted top-level poses."""

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
DEFAULT_ASSEMBLY = ROOT / "demo/project03/FL9A24D063A000_project03_solution1_v1.SLDASM"
DEFAULT_SCREENSHOT = ROOT / "demo/screenshots/project03_solution1_v1_reopened.png"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project03_solution1_v1_reopened_capture.json"
DEFAULT_REPLAY_RESULT = ROOT / "demo/layout_previews/project03_solution1_v1_replay_result.json"


def _pose_payload(replay_result: dict) -> list[dict]:
    return next(
        (
            step.get("payload")
            for step in replay_result.get("steps") or []
            if step.get("tool") == "list_component_poses"
        ),
        [],
    )


def _maximum_transform_error(expected: list[dict], actual: list[dict]) -> tuple[float, list[str]]:
    expected_by_name = {item["Name"]: item for item in expected}
    actual_by_name = {item["Name"]: item for item in actual}
    missing = sorted(set(expected_by_name) ^ set(actual_by_name))
    if missing:
        return float("inf"), missing
    maximum = max(
        max(abs(float(a) - float(b)) for a, b in zip(actual_by_name[name]["Transform"], expected_by_name[name]["Transform"]))
        for name in expected_by_name
    )
    return maximum, []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replay-result", type=Path, default=DEFAULT_REPLAY_RESULT)
    args = parser.parse_args()

    assembly = args.assembly.resolve()
    screenshot = args.screenshot.resolve()
    output = args.output.resolve()
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    replay_result = json.loads(args.replay_result.resolve().read_text(encoding="utf-8-sig"))

    with McpClient(args.exe.resolve(), "Project03Solution1Reopen", 1200.0, "newline", direct_stdio=True) as client:
        active_before = client.call_tool("get_active_document", {})
        active_path = str(active_before.get("Path", active_before.get("path", ""))) if isinstance(active_before, dict) else ""
        close_before = None
        if active_path and Path(active_path).resolve() == assembly:
            close_before = client.call_tool_text("close_document", {"path": str(assembly)})
        opened = client.call_tool("open_document", {"path": str(assembly)})
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        rebuild = client.call_tool("get_active_document_rebuild_state", {})
        image = client.call_tool(
            "export_current_view_png",
            {"outputPath": str(screenshot), "width": 1600, "height": 900, "includeBase64Data": False},
        )
        close_after = client.call_tool_text("close_document", {"path": str(assembly)})

    maximum_error, component_set_difference = _maximum_transform_error(_pose_payload(replay_result), poses)
    main_module_count = sum("D063A" in item["Name"] and "00.001-" in item["Name"] for item in poses)
    success = (
        len(poses) == 15
        and main_module_count == 10
        and maximum_error <= 1e-6
        and not component_set_difference
        and screenshot.is_file()
        and rebuild.get("NeedsRebuild") is False
    )
    payload = {
        "schemaVersion": 1,
        "caseId": "project03",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "assemblyPath": str(assembly),
        "success": success,
        "activeBefore": active_before,
        "closeBefore": close_before,
        "opened": opened,
        "componentCount": len(poses),
        "mainModuleCount": main_module_count,
        "auxiliaryTopLevelCount": len(poses) - main_module_count,
        "maximumTransformElementErrorFromPreClose": maximum_error,
        "componentSetDifference": component_set_difference,
        "components": poses,
        "rebuildState": rebuild,
        "screenshot": image,
        "closeAfter": close_after,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": success,
        "componentCount": len(poses),
        "mainModuleCount": main_module_count,
        "maximumTransformElementErrorFromPreClose": maximum_error,
        "output": str(output),
        "screenshot": str(screenshot),
    }, ensure_ascii=False, indent=2))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
