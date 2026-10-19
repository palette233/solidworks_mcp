"""Replay the approved Project 02 layout into a new A600-rooted assembly.

All SolidWorks actions run in one MCP stdio session so the active document and
COM connection cannot be lost between open, Save As, Replay, save, and capture.
The source container assembly is never overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    ROOT
    / "apps"
    / "demo-backend"
    / "tools"
    / "McpToolRunner"
    / "bin"
    / "Release"
    / "net8.0"
    / "McpToolRunner.dll"
)
DEFAULT_MCP = ROOT / "artifacts" / "solidworks-mcp-20260810-startupready" / "SolidWorksMcpApp.exe"
DEFAULT_FACE_MAPPING = ROOT / "artifacts" / "solidworks-mcp" / "face_mappings.json"
A100_COMPONENT = "FL9A24D062A100.001-1"
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402


def resolved(value: str) -> Path:
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
    if not isinstance(payload, dict):
        return False
    for key in ("success", "Success"):
        if key in payload and payload[key] is False:
            return True
    return False


def movable_replay_layout(source: Path, directory: Path) -> tuple[Path, list[str]]:
    """Strip fixed environment roots from the motion payload.

    A600 already exists in a full Project 02 source assembly at the recorded world
    transform.  Asking the bottom-face Replay tool to place it again would both be
    unnecessary and require a fictitious A600 bottom-face mapping.
    """
    document = json.loads(source.read_text(encoding="utf-8"))
    components = document.get("components")
    if not isinstance(components, list):
        raise SystemExit("Replay layout does not contain a components array.")
    fixed = [
        str(item.get("componentName"))
        for item in components
        if bool((item.get("constraintPlacement") or {}).get("fixedEnvironment"))
    ]
    if not fixed:
        return source, []
    movable = [
        item
        for item in components
        if not bool((item.get("constraintPlacement") or {}).get("fixedEnvironment"))
    ]
    replay_document = dict(document)
    replay_document["components"] = movable
    replay_document["fixedEnvironmentReplay"] = {
        "preservedComponents": fixed,
        "policy": "preserve-source-world-transform",
        "movableComponentCount": len(movable),
    }
    path = directory / "project02_movable_replay_layout.json"
    path.write_text(
        json.dumps(replay_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path, fixed


def main() -> None:
    timing = PipelineTiming("project02.replay-selected-solution")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-assembly", required=True)
    parser.add_argument("--target-assembly", required=True)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--view-directory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mcp", default=str(DEFAULT_MCP))
    parser.add_argument("--face-mapping", default=str(DEFAULT_FACE_MAPPING))
    parser.add_argument(
        "--exit-solidworks-after-replay",
        action="store_true",
        help="Exit the isolated SolidWorks session after saving and exporting evidence.",
    )
    args = parser.parse_args()

    with timing.stage("resolve-and-validate-inputs"):
        source = resolved(args.source_assembly)
        target = resolved(args.target_assembly)
        layout = resolved(args.layout)
        screenshot = resolved(args.screenshot)
        view_directory = resolved(args.view_directory)
        output = resolved(args.output)
        mcp = resolved(args.mcp)
        face_mapping = resolved(args.face_mapping)

        if not source.exists():
            raise SystemExit(f"Source assembly does not exist: {source}")
        if not layout.exists():
            raise SystemExit(f"Replay layout does not exist: {layout}")
        if target.exists():
            raise SystemExit(f"Target assembly already exists; refusing to overwrite: {target}")
        if not mcp.exists():
            raise SystemExit(f"MCP executable does not exist: {mcp}")
        if not face_mapping.exists():
            raise SystemExit(f"Face mapping does not exist: {face_mapping}")

        target.parent.mkdir(parents=True, exist_ok=True)
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        view_directory.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)

    temporary_directory = tempfile.TemporaryDirectory(prefix="project02-replay-")
    temporary_path = Path(temporary_directory.name)
    applied_layout, fixed_environment_components = movable_replay_layout(
        layout,
        temporary_path,
    )

    tools = [
        {"tool": "solid_works_connect", "arguments": {}},
        {"tool": "get_face_mapping_store_info", "arguments": {}},
        {"tool": "open_document", "arguments": {"path": str(source)}},
        {
            "tool": "save_document_as",
            "arguments": {
                "outputPath": str(target),
                "sourcePath": str(source),
                "saveAsCopy": False,
            },
        },
        {"tool": "get_active_document", "arguments": {}},
        {
            "tool": "set_top_level_component_solving_state",
            "arguments": {
                "hierarchyPath": A100_COMPONENT,
                "solvingState": 0,
                "rebuild": True,
            },
        },
        {
            "tool": "apply_captured_common_base_layout",
            "arguments": {
                "layoutJsonPath": str(applied_layout),
                "assemblyPath": str(target),
                "screenshotPath": str(screenshot),
                "screenshotWidth": 1600,
                "screenshotHeight": 900,
                "includeScreenshotBase64Data": False,
                "validatePortalInterference": False,
            },
        },
        {
            "tool": "list_component_poses",
            "arguments": {"topLevelOnly": True},
        },
        {"tool": "get_active_document_rebuild_state", "arguments": {}},
        {"tool": "save_document", "arguments": {"path": str(target)}},
        {
            "tool": "export_standard_view_png_set",
            "arguments": {
                "outputDirectory": str(view_directory),
                "fileNamePrefix": "project02-static-v1",
                "width": 1600,
                "height": 900,
                "includeBase64Data": False,
            },
        },
        {"tool": "get_active_document", "arguments": {}},
    ]
    payload = {
        "serverCommand": str(mcp),
        "serverArguments": ["--stdio-direct"],
        "workingDirectory": str(mcp.parent),
        "tools": tools,
    }
    with timing.stage("solidworks-mcp-replay-session", toolCount=len(tools)):
        completed = subprocess.run(
            ["dotnet", str(RUNNER)],
            cwd=ROOT,
            input=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "DEMO_FACE_MAPPING_PATH": str(face_mapping)},
            check=False,
        )
    if completed.returncode != 0:
        details = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(details or f"MCP runner failed with exit code {completed.returncode}")

    with timing.stage("decode-and-audit-mcp-results"):
        raw = json.loads(completed.stdout.decode("utf-8"))
        raw_results = raw.get("results") or []
        steps = []
        for index, planned in enumerate(tools):
            result = raw_results[index] if index < len(raw_results) else {}
            parsed_payload = text_payload(result)
            steps.append(
                {
                    "tool": planned["tool"],
                    "isError": bool(result.get("isError")),
                    "businessFailed": payload_failed(parsed_payload),
                    "timing": result.get("timing"),
                    "payload": parsed_payload,
                }
            )

    successful = len(steps) == len(tools) and not any(
        step["isError"] or step["businessFailed"] for step in steps
    )
    summary = {
        "success": successful,
        "status": "REPLAY_SAVED_VISUAL_REVIEW_PENDING" if successful else "REPLAY_FAILED",
        "sourceAssemblyPath": str(source),
        "targetAssemblyPath": str(target),
        "layoutPath": str(layout),
        "appliedMovableLayoutPath": str(applied_layout),
        "fixedEnvironmentComponentsPreserved": fixed_environment_components,
        "staticRigidComponentsBeforeReplay": [A100_COMPONENT],
        "faceMappingPath": str(face_mapping),
        "screenshotPath": str(screenshot),
        "standardViewDirectory": str(view_directory),
        "mcpSessionTiming": raw.get("timing"),
        "steps": steps,
        "exitSolidWorks": {
            "requested": bool(args.exit_solidworks_after_replay),
            "status": "not_requested",
        },
    }
    if not target.exists():
        summary["success"] = False
        summary["status"] = "TARGET_ASSEMBLY_NOT_CREATED"
    # Persist the Replay evidence before attempting the optional lifecycle
    # cleanup.  Older published MCP packages do not expose exit_solid_works;
    # an unsupported cleanup tool must not discard an otherwise successful
    # saved Replay and its pose/view evidence.
    if args.exit_solidworks_after_replay:
        exit_payload = {
            "serverCommand": str(mcp),
            "serverArguments": ["--stdio-direct"],
            "workingDirectory": str(mcp.parent),
            "tools": [
                {
                    "tool": "exit_solid_works",
                    "arguments": {"confirmAllDocumentsSaved": True},
                }
            ],
        }
        with timing.stage("exit-solidworks-session"):
            exit_completed = subprocess.run(
                ["dotnet", str(RUNNER)],
                cwd=ROOT,
                input=json.dumps(exit_payload, ensure_ascii=True).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "DEMO_FACE_MAPPING_PATH": str(face_mapping)},
                check=False,
            )
        summary["exitSolidWorks"] = {
            "requested": True,
            "status": "completed" if exit_completed.returncode == 0 else "unsupported_or_failed",
            "returnCode": exit_completed.returncode,
            "message": exit_completed.stderr.decode("utf-8", errors="replace").strip(),
        }

    summary["timing"] = timing.finish(
        status="completed" if summary["success"] else "failed"
    )
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_directory.cleanup()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
