#!/usr/bin/env python3
"""Build Project 02's solved layout in a genuinely clean eight-module assembly.

Unlike the historical replay scripts, this workflow never copies an existing
container assembly.  It creates a blank SolidWorks assembly, inserts exactly
the eight source modules declared by the solved-layout JSON, audits the actual
top-level component names and source paths, and only then applies the solved
poses.  A second whitelist audit is performed after replay and before the
result is reported as successful.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming, utc_now_iso  # noqa: E402
DEFAULT_LAYOUT = ROOT / "demo" / "layout_previews" / "project02_selected_solution_replay.json"
DEFAULT_TARGET = ROOT / "demo" / "FL9A24D062A000_8modules_clean_solved_v1.SLDASM"
DEFAULT_SCREENSHOT = ROOT / "demo" / "project02_8modules_clean_solved_v1.png"
DEFAULT_VIEWS = ROOT / "demo" / "project02_8modules_clean_solved_v1_views"
DEFAULT_OUTPUT = ROOT / "demo" / "layout_previews" / "project02_8modules_clean_solved_v1_result.json"
DEFAULT_MCP = ROOT / "artifacts" / "solidworks-mcp-20260810-startupready" / "SolidWorksMcpApp.exe"
DEFAULT_FACE_MAPPING = ROOT / "artifacts" / "solidworks-mcp" / "face_mappings.json"
EXPECTED_MODULE_COUNT = 8
FIXED_ANCHOR_NAME = "FL9A24D062A200.001-1"


def resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _get(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _normalized_path(value: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value)))


def load_layout(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    components = document.get("components") or []
    if len(components) != EXPECTED_MODULE_COUNT:
        raise ValueError(
            f"Solved layout must declare exactly {EXPECTED_MODULE_COUNT} components; "
            f"found {len(components)}."
        )

    names = [component.get("componentName") for component in components]
    if any(not name for name in names):
        raise ValueError("Every solved-layout component must have componentName.")
    if len(set(names)) != len(names):
        raise ValueError("Solved-layout componentName values must be unique.")
    if FIXED_ANCHOR_NAME not in names:
        raise ValueError(
            f"The clean assembly requires identity-oriented fixed anchor {FIXED_ANCHOR_NAME}."
        )

    for component in components:
        file_path = Path(component.get("filePath") or "")
        if not file_path.is_file():
            raise FileNotFoundError(
                f"Source module does not exist for {component['componentName']}: {file_path}"
            )
        translation = component.get("componentTranslation")
        if not isinstance(translation, list) or len(translation) != 3:
            raise ValueError(
                f"{component['componentName']} is missing a three-value componentTranslation."
            )

    anchor = next(item for item in components if item["componentName"] == FIXED_ANCHOR_NAME)
    expected_identity = ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    actual_axes = (
        anchor.get("targetXAxisWorld"),
        anchor.get("targetYAxisWorld"),
        anchor.get("targetZAxisWorld"),
    )
    if any(
        axis is None or any(abs(float(a) - b) > 1e-9 for a, b in zip(axis, expected))
        for axis, expected in zip(actual_axes, expected_identity)
    ):
        raise ValueError(
            f"Fixed anchor {FIXED_ANCHOR_NAME} no longer has identity target orientation."
        )
    return document


def insertion_components(layout: dict[str, Any]) -> list[dict[str, Any]]:
    """Return components in safe insertion order; first insert becomes fixed."""
    components = list(layout["components"])
    components.sort(key=lambda item: item["componentName"] != FIXED_ANCHOR_NAME)
    prepared: list[dict[str, Any]] = []
    for component in components:
        x, y, z = (float(value) for value in component["componentTranslation"])
        prepared.append(
            {
                "componentName": component["componentName"],
                "filePath": component["filePath"],
                "x": x,
                "y": y,
                "z": z,
                "bottomFaceName": component.get("bottomFaceName") or "底面",
            }
        )
    return prepared


def audit_top_level_components(
    actual_components: Iterable[dict[str, Any]],
    expected_components: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    actual = list(actual_components)
    expected = list(expected_components)
    expected_by_name = {
        item["componentName"]: _normalized_path(item["filePath"]) for item in expected
    }

    actual_rows: list[dict[str, str]] = []
    for item in actual:
        name = _get(item, "Name", "name", "componentName")
        path = _get(item, "Path", "path", "filePath")
        actual_rows.append({"name": str(name or ""), "path": str(path or "")})

    actual_names = [item["name"] for item in actual_rows]
    actual_set = set(actual_names)
    expected_set = set(expected_by_name)
    duplicate_names = sorted({name for name in actual_names if actual_names.count(name) > 1})
    missing_names = sorted(expected_set - actual_set)
    extra_names = sorted(actual_set - expected_set)
    path_mismatches: list[dict[str, str]] = []
    for item in actual_rows:
        name = item["name"]
        if name not in expected_by_name:
            continue
        actual_path = _normalized_path(item["path"])
        if actual_path != expected_by_name[name]:
            path_mismatches.append(
                {
                    "componentName": name,
                    "expectedPath": next(
                        row["filePath"] for row in expected if row["componentName"] == name
                    ),
                    "actualPath": item["path"],
                }
            )

    success = (
        len(actual_rows) == EXPECTED_MODULE_COUNT
        and len(expected_by_name) == EXPECTED_MODULE_COUNT
        and not duplicate_names
        and not missing_names
        and not extra_names
        and not path_mismatches
    )
    return {
        "success": success,
        "expectedCount": EXPECTED_MODULE_COUNT,
        "actualCount": len(actual_rows),
        "missingNames": missing_names,
        "extraNames": extra_names,
        "duplicateNames": duplicate_names,
        "pathMismatches": path_mismatches,
        "actualComponents": actual_rows,
    }


def call_and_record(
    client: McpClient,
    steps: list[dict[str, Any]],
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    started_at = utc_now_iso()
    started = time.perf_counter()
    payload = client.call_tool(tool, arguments or {})
    finished_at = utc_now_iso()
    failed = isinstance(payload, dict) and any(
        payload.get(key) is False for key in ("success", "Success") if key in payload
    )
    steps.append(
        {
            "tool": tool,
            "businessFailed": failed,
            "timing": {
                "startedAtUtc": started_at,
                "finishedAtUtc": finished_at,
                "durationSeconds": round(time.perf_counter() - started, 6),
            },
            "payload": payload,
        }
    )
    if failed:
        raise RuntimeError(f"{tool} reported business failure.")
    return payload


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    timing = PipelineTiming("project02.clean-eight-module-replay")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", default=str(DEFAULT_LAYOUT))
    parser.add_argument("--target-assembly", default=str(DEFAULT_TARGET))
    parser.add_argument("--screenshot", default=str(DEFAULT_SCREENSHOT))
    parser.add_argument("--view-directory", default=str(DEFAULT_VIEWS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mcp", default=str(DEFAULT_MCP))
    parser.add_argument("--face-mapping", default=str(DEFAULT_FACE_MAPPING))
    parser.add_argument("--request-timeout", type=float, default=300.0)
    args = parser.parse_args()

    layout_path = resolved(args.layout)
    target = resolved(args.target_assembly)
    screenshot = resolved(args.screenshot)
    view_directory = resolved(args.view_directory)
    output = resolved(args.output)
    mcp = resolved(args.mcp)
    face_mapping = resolved(args.face_mapping)

    if target.exists():
        raise SystemExit(f"Target already exists; refusing to reuse or overwrite it: {target}")
    if not layout_path.is_file():
        raise SystemExit(f"Solved layout does not exist: {layout_path}")
    if not mcp.is_file():
        raise SystemExit(f"MCP executable does not exist: {mcp}")
    if not face_mapping.is_file():
        raise SystemExit(f"Face mapping does not exist: {face_mapping}")

    layout = load_layout(layout_path)
    components = insertion_components(layout)
    target.parent.mkdir(parents=True, exist_ok=True)
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    view_directory.mkdir(parents=True, exist_ok=True)

    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "success": False,
        "status": "CLEAN_ASSEMBLY_BUILD_STARTED",
        "layoutPath": str(layout_path),
        "targetAssemblyPath": str(target),
        "screenshotPath": str(screenshot),
        "standardViewDirectory": str(view_directory),
        "whitelist": [
            {"componentName": item["componentName"], "filePath": item["filePath"]}
            for item in components
        ],
        "steps": steps,
    }

    previous_mapping = os.environ.get("DEMO_FACE_MAPPING_PATH")
    os.environ["DEMO_FACE_MAPPING_PATH"] = str(face_mapping)
    try:
        with McpClient(
            mcp,
            client_name="CodexProject02CleanEightModuleBuilder",
            request_timeout=args.request_timeout,
            framing="newline",
            direct_stdio=True,
        ) as client:
            call_and_record(client, steps, "solid_works_connect")
            call_and_record(
                client,
                steps,
                "initialize_common_base_assembly",
                {
                    "components": components,
                    "outputAssemblyPath": str(target),
                    "screenshotPath": None,
                    "includeScreenshotBase64Data": False,
                },
            )
            actual_before = call_and_record(client, steps, "list_components")
            before_audit = audit_top_level_components(actual_before, components)
            summary["preReplayTopLevelAudit"] = before_audit
            if not before_audit["success"]:
                summary["status"] = "PRE_REPLAY_TOP_LEVEL_WHITELIST_FAILED"
                raise RuntimeError("Clean assembly top-level whitelist failed before replay.")

            call_and_record(
                client,
                steps,
                "apply_captured_common_base_layout",
                {
                    "layoutJsonPath": str(layout_path),
                    "assemblyPath": str(target),
                    "screenshotPath": str(screenshot),
                    "screenshotWidth": 1600,
                    "screenshotHeight": 900,
                    "includeScreenshotBase64Data": False,
                    "validatePortalInterference": False,
                },
            )
            actual_after = call_and_record(client, steps, "list_components")
            after_audit = audit_top_level_components(actual_after, components)
            summary["postReplayTopLevelAudit"] = after_audit
            if not after_audit["success"]:
                summary["status"] = "POST_REPLAY_TOP_LEVEL_WHITELIST_FAILED"
                raise RuntimeError("Clean assembly top-level whitelist failed after replay.")

            poses = call_and_record(
                client, steps, "list_component_poses", {"topLevelOnly": True}
            )
            summary["topLevelPoseCount"] = len(poses) if isinstance(poses, list) else None
            if summary["topLevelPoseCount"] != EXPECTED_MODULE_COUNT:
                summary["status"] = "POST_REPLAY_POSE_COUNT_FAILED"
                raise RuntimeError("Top-level pose enumeration did not return exactly eight modules.")

            call_and_record(client, steps, "save_document", {"path": str(target)})
            call_and_record(
                client,
                steps,
                "export_standard_view_png_set",
                {
                    "outputDirectory": str(view_directory),
                    "fileNamePrefix": "project02-clean-8modules-v1",
                    "width": 1600,
                    "height": 900,
                    "includeBase64Data": False,
                },
            )
            call_and_record(client, steps, "get_active_document_rebuild_state")

        summary["success"] = target.is_file() and screenshot.is_file()
        summary["status"] = (
            "CLEAN_EIGHT_MODULE_REPLAY_SAVED_VISUAL_REVIEW_PENDING"
            if summary["success"]
            else "CLEAN_EIGHT_MODULE_OUTPUT_MISSING"
        )
    except Exception as exc:
        summary["error"] = str(exc)
        if summary["status"] == "CLEAN_ASSEMBLY_BUILD_STARTED":
            summary["status"] = "CLEAN_ASSEMBLY_BUILD_FAILED"
    finally:
        if previous_mapping is None:
            os.environ.pop("DEMO_FACE_MAPPING_PATH", None)
        else:
            os.environ["DEMO_FACE_MAPPING_PATH"] = previous_mapping
        summary["timing"] = timing.finish(
            status="completed" if summary.get("success") else "failed"
        )
        write_summary(output, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
