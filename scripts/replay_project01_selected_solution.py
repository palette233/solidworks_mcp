#!/usr/bin/env python3
"""Replay one approved Project 01 solution into a new full assembly copy."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "apps/demo-backend/tools/McpToolRunner/bin/Release/net8.0/McpToolRunner.dll"
DEFAULT_MCP = ROOT / "artifacts/solidworks-mcp-20260810-startupready/SolidWorksMcpApp.exe"
DEFAULT_FACE_MAPPING = ROOT / "artifacts/solidworks-mcp/face_mappings.json"
DEFAULT_LAYOUT = ROOT / "demo/layout_previews/project01_selected_solution_replay.json"
DEFAULT_TARGET = ROOT / "demo/project01/FL9C24N074AA00_project01_solution1_v1.SLDASM"
DEFAULT_SCREENSHOT = ROOT / "demo/screenshots/project01_solution1_v1_replay.png"
DEFAULT_VIEWS = ROOT / "demo/screenshots/project01_solution1_v1_views"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project01_solution1_v1_replay_result.json"


def resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def text_payload(result: dict[str, Any]) -> Any:
    for block in result.get("content") or []:
        if block.get("type") != "text":
            continue
        text = block.get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return None


def payload_failed(payload: Any) -> bool:
    return isinstance(payload, dict) and any(
        payload.get(key) is False for key in ("success", "Success") if key in payload
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", default=str(DEFAULT_LAYOUT))
    parser.add_argument("--target-assembly", default=str(DEFAULT_TARGET))
    parser.add_argument("--screenshot", default=str(DEFAULT_SCREENSHOT))
    parser.add_argument("--view-directory", default=str(DEFAULT_VIEWS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mcp", default=str(DEFAULT_MCP))
    parser.add_argument("--face-mapping", default=str(DEFAULT_FACE_MAPPING))
    args = parser.parse_args()

    layout_path = resolved(args.layout)
    target = resolved(args.target_assembly)
    screenshot = resolved(args.screenshot)
    view_directory = resolved(args.view_directory)
    output = resolved(args.output)
    mcp = resolved(args.mcp)
    face_mapping = resolved(args.face_mapping)
    layout = json.loads(layout_path.read_text(encoding="utf-8-sig"))
    source = Path(layout["sourceAssemblyPath"])
    expected_names = {item["componentName"] for item in layout.get("components") or []}

    if layout.get("visualApproval", {}).get("approved") is not True:
        raise SystemExit("Project 01 visual approval gate is not open.")
    if len(expected_names) != 10:
        raise SystemExit(f"Project 01 Replay requires 10 top-level modules; found {len(expected_names)}.")
    for required in (source, layout_path, mcp, face_mapping, RUNNER):
        if not required.is_file():
            raise SystemExit(f"Required Replay input does not exist: {required}")
    if target.exists():
        raise SystemExit(f"Target already exists; refusing to overwrite: {target}")

    for directory in (target.parent, screenshot.parent, view_directory, output.parent):
        directory.mkdir(parents=True, exist_ok=True)

    tools = [
        {"tool": "solid_works_connect", "arguments": {}},
        {"tool": "get_face_mapping_store_info", "arguments": {}},
        {"tool": "open_document", "arguments": {"path": str(source)}},
        {
            "tool": "save_document_as",
            "arguments": {"outputPath": str(target), "sourcePath": str(source), "saveAsCopy": False},
        },
        {"tool": "get_active_document", "arguments": {}},
        {
            "tool": "apply_captured_common_base_layout",
            "arguments": {
                "layoutJsonPath": str(layout_path),
                "assemblyPath": str(target),
                "screenshotPath": str(screenshot),
                "screenshotWidth": 1600,
                "screenshotHeight": 900,
                "includeScreenshotBase64Data": False,
                "validatePortalInterference": False,
            },
        },
        {"tool": "list_component_poses", "arguments": {"topLevelOnly": True}},
        {"tool": "get_active_document_rebuild_state", "arguments": {}},
        {"tool": "save_document", "arguments": {"path": str(target)}},
        {
            "tool": "export_standard_view_png_set",
            "arguments": {
                "outputDirectory": str(view_directory),
                "fileNamePrefix": target.stem,
                "width": 1600,
                "height": 900,
                "includeBase64Data": False,
            },
        },
        {"tool": "get_active_document", "arguments": {}},
    ]
    request = {
        "serverCommand": str(mcp),
        "serverArguments": ["--stdio-direct"],
        "workingDirectory": str(mcp.parent),
        "tools": tools,
    }
    completed = subprocess.run(
        ["dotnet", str(RUNNER)],
        cwd=ROOT,
        input=json.dumps(request, ensure_ascii=True).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "DEMO_FACE_MAPPING_PATH": str(face_mapping)},
        check=False,
        timeout=1800,
    )
    if completed.returncode != 0:
        details = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(details or f"MCP runner failed with exit code {completed.returncode}.")

    raw = json.loads(completed.stdout.decode("utf-8"))
    raw_results = raw.get("results") or []
    steps: list[dict[str, Any]] = []
    for index, planned in enumerate(tools):
        result = raw_results[index] if index < len(raw_results) else {}
        payload = text_payload(result)
        steps.append(
            {
                "tool": planned["tool"],
                "isError": bool(result.get("isError")),
                "businessFailed": payload_failed(payload),
                "payload": payload,
            }
        )

    pose_step = next((item for item in steps if item["tool"] == "list_component_poses"), {})
    poses = pose_step.get("payload") if isinstance(pose_step.get("payload"), list) else []
    actual_names = {str(item.get("Name")) for item in poses if item.get("Name")}
    audit = {
        "expectedCount": 10,
        "actualCount": len(poses),
        "missingNames": sorted(expected_names - actual_names),
        "extraNames": sorted(actual_names - expected_names),
    }
    audit["success"] = (
        audit["actualCount"] == 10 and not audit["missingNames"] and not audit["extraNames"]
    )
    success = (
        len(steps) == len(tools)
        and not any(item["isError"] or item["businessFailed"] for item in steps)
        and audit["success"]
        and target.is_file()
        and screenshot.is_file()
    )
    summary = {
        "success": success,
        "status": "PROJECT01_REPLAY_SAVED_AABB_PENDING" if success else "PROJECT01_REPLAY_FAILED",
        "sourceAssemblyPath": str(source),
        "targetAssemblyPath": str(target),
        "layoutPath": str(layout_path),
        "screenshotPath": str(screenshot),
        "standardViewDirectory": str(view_directory),
        "selectedSolutionRank": int((layout.get("visualApproval") or {}).get("selectedSolutionRank") or 0),
        "prototypeEquivalent": bool(layout.get("constraintPlan", {}).get("prototypeEquivalent")),
        "topLevelAudit": audit,
        "steps": steps,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "steps"}, ensure_ascii=False, indent=2))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
