#!/usr/bin/env python3
"""Build Project 02 directly as an independent nine-module assembly.

This workflow does not copy or Replay a prototype/container assembly.  It can
either create a blank SolidWorks assembly, inserting A600 first as the fixed
datum, or update an earlier independently generated direct assembly.  In both
cases the nine source subassemblies are placed at final target transforms from
the approved constraint solution.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
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


DEFAULT_LAYOUT = ROOT / "demo/layout_previews/project02_selected_solution.json"
DEFAULT_POSES = ROOT / "demo/layout_previews/project02_a600_fixed_projected_poses.json"
DEFAULT_TARGET = ROOT / "demo/FL9A24D062A000_9modules_direct_solved_v2.SLDASM"
DEFAULT_SCREENSHOT = ROOT / "demo/project02_9modules_direct_solved_v2.png"
DEFAULT_VIEWS = ROOT / "demo/project02_9modules_direct_solved_v2_views"
DEFAULT_SAVED_POSES = ROOT / "demo/layout_previews/project02_9modules_direct_solved_v2_poses.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_9modules_direct_solved_v2_result.json"
DEFAULT_MCP = ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
EXPECTED_MODULE_COUNT = 9
FIXED_ENVIRONMENT_CODE = "A600"


def resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_path(value: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value)))


def component_code(name: str) -> str:
    matches = re.findall(r"([A-Z]{1,2}\d{3})\.001", name.upper())
    if matches:
        return matches[-1]
    marker = "D062A"
    if marker in name:
        return "A" + name.split(marker, 1)[1].split(".", 1)[0]
    return name.split("-", 1)[0]


def resolve_component_selectors(
    manifest: Iterable[dict[str, Any]], selectors: Iterable[str]
) -> list[str]:
    """Resolve exact names or unique component codes for solve-as overrides."""

    rows = list(manifest)
    result: list[str] = []
    for raw_selector in selectors:
        selector = str(raw_selector).strip()
        matches = [
            row["componentName"]
            for row in rows
            if row["componentName"].casefold() == selector.casefold()
            or row["componentCode"].casefold() == selector.casefold()
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Solve-as selector '{selector}' resolved to {len(matches)} components."
            )
        if matches[0] not in result:
            result.append(matches[0])
    return result


def load_direct_manifest(
    layout_path: Path,
    pose_path: Path,
    *,
    expected_module_count: int = EXPECTED_MODULE_COUNT,
    fixed_environment_code: str = FIXED_ENVIRONMENT_CODE,
) -> list[dict[str, Any]]:
    layout = read_json(layout_path)
    poses = read_json(pose_path)
    components = list(layout.get("components") or [])
    if len(components) != expected_module_count:
        raise ValueError(
            f"Approved layout must contain {expected_module_count} components; "
            f"found {len(components)}."
        )
    approval = layout.get("visualApproval") or {}
    if approval.get("approved") is not True:
        raise ValueError("Direct generation requires an explicitly approved solution.")

    pose_by_name = {str(item.get("Name") or ""): item for item in poses}
    rows: list[dict[str, Any]] = []
    for component in components:
        name = str(component.get("componentName") or "")
        file_path = Path(str(component.get("filePath") or ""))
        pose = pose_by_name.get(name)
        if not name or pose is None:
            raise ValueError(f"No target pose exists for layout component '{name}'.")
        if not file_path.is_file():
            raise FileNotFoundError(f"Source module does not exist: {file_path}")
        pose_path_value = str(pose.get("Path") or "").strip()
        if pose_path_value and normalized_path(pose_path_value) != normalized_path(file_path):
            raise ValueError(f"Target pose source path mismatch for '{name}'.")
        translation = [float(value) for value in pose.get("Translation") or []]
        axes = {
            "xAxis": [float(value) for value in pose.get("XAxis") or []],
            "yAxis": [float(value) for value in pose.get("YAxis") or []],
            "zAxis": [float(value) for value in pose.get("ZAxis") or []],
        }
        bounding_box = [float(value) for value in pose.get("BoundingBoxWorld") or []]
        if len(translation) != 3 or any(len(axis) != 3 for axis in axes.values()):
            raise ValueError(f"Target pose for '{name}' is incomplete.")
        if len(bounding_box) != 6:
            raise ValueError(f"Target pose for '{name}' has no six-value world bounding box.")
        placement = component.get("constraintPlacement") or {}
        fixed = bool(placement.get("fixedEnvironment"))
        rows.append(
            {
                "componentName": name,
                "componentCode": component_code(name),
                "filePath": str(file_path),
                "translation": translation,
                "boundingBoxWorld": bounding_box,
                **axes,
                "fixedEnvironment": fixed,
            }
        )

    fixed_rows = [row for row in rows if row["fixedEnvironment"]]
    if len(fixed_rows) != 1 or fixed_rows[0]["componentCode"] != fixed_environment_code:
        raise ValueError(
            f"Exactly one fixed {fixed_environment_code} environment component is required."
        )
    names = [row["componentName"] for row in rows]
    if len(set(names)) != expected_module_count:
        raise ValueError(f"All {expected_module_count} component names must be unique.")
    rows.sort(key=lambda row: not row["fixedEnvironment"])
    return rows


def insertion_components(manifest: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in manifest:
        insertion_point = list(row["translation"])
        if row["fixedEnvironment"]:
            box = row["boundingBoxWorld"]
            # SolidWorks AddComponent5 positions the inserted model by its body-box
            # center, not by Transform2 translation.  A600 is inserted first and is
            # immediately fixed, so its requested insertion point must be its target
            # world-box center to produce the desired identity Transform2.
            insertion_point = [
                (box[index] + box[index + 3]) / 2.0 for index in range(3)
            ]
        result.append({
            "componentName": row["componentName"],
            "filePath": row["filePath"],
            "x": insertion_point[0],
            "y": insertion_point[1],
            "z": insertion_point[2],
            "bottomFaceName": "DIRECT_FINAL_POSE",
        })
    return result


def movement_deltas(
    current_poses: Iterable[dict[str, Any]],
    expected_manifest: Iterable[dict[str, Any]],
    *,
    tolerance: float = 1e-9,
) -> list[dict[str, Any]]:
    current_by_name = {
        str(item.get("Name", item.get("name", ""))): item for item in current_poses
    }
    result: list[dict[str, Any]] = []
    for expected in expected_manifest:
        if expected["fixedEnvironment"]:
            continue
        current = current_by_name.get(expected["componentName"])
        if current is None:
            raise ValueError(f"Cannot move missing component '{expected['componentName']}'.")
        translation = current.get("Translation", current.get("translation")) or []
        if len(translation) != 3:
            raise ValueError(f"Current translation is incomplete for '{expected['componentName']}'.")
        delta = [
            expected["translation"][index] - float(translation[index])
            for index in range(3)
        ]
        result.append(
            {
                "componentName": expected["componentName"],
                "delta": delta,
                "requiresMove": max(abs(value) for value in delta) > tolerance,
            }
        )
    return result


def audit_top_level_components(
    actual_components: Iterable[dict[str, Any]],
    expected_manifest: Iterable[dict[str, Any]],
    *,
    expected_module_count: int = EXPECTED_MODULE_COUNT,
) -> dict[str, Any]:
    actual = list(actual_components)
    expected = list(expected_manifest)
    expected_by_name = {
        item["componentName"]: normalized_path(item["filePath"]) for item in expected
    }
    actual_rows = [
        {
            "name": str(item.get("Name", item.get("name", ""))),
            "path": str(item.get("Path", item.get("path", ""))),
        }
        for item in actual
    ]
    actual_names = [item["name"] for item in actual_rows]
    missing = sorted(set(expected_by_name) - set(actual_names))
    extra = sorted(set(actual_names) - set(expected_by_name))
    duplicates = sorted({name for name in actual_names if actual_names.count(name) > 1})
    path_mismatches = [
        {
            "componentName": item["name"],
            "expectedPath": next(
                row["filePath"]
                for row in expected
                if row["componentName"] == item["name"]
            ),
            "actualPath": item["path"],
        }
        for item in actual_rows
        if item["name"] in expected_by_name
        and normalized_path(item["path"]) != expected_by_name[item["name"]]
    ]
    success = (
        len(actual_rows) == expected_module_count
        and len(expected_by_name) == expected_module_count
        and not missing
        and not extra
        and not duplicates
        and not path_mismatches
    )
    return {
        "success": success,
        "expectedCount": expected_module_count,
        "actualCount": len(actual_rows),
        "missingNames": missing,
        "extraNames": extra,
        "duplicateNames": duplicates,
        "pathMismatches": path_mismatches,
        "actualComponents": actual_rows,
    }


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def audit_poses(
    actual_poses: Iterable[dict[str, Any]],
    expected_manifest: Iterable[dict[str, Any]],
    *,
    translation_tolerance: float = 1e-6,
    axis_dot_tolerance: float = 1e-8,
    expected_module_count: int = EXPECTED_MODULE_COUNT,
) -> dict[str, Any]:
    actual_by_name = {
        str(item.get("Name", item.get("name", ""))): item for item in actual_poses
    }
    rows: list[dict[str, Any]] = []
    for expected in expected_manifest:
        name = expected["componentName"]
        actual = actual_by_name.get(name)
        if actual is None:
            rows.append({"componentName": name, "success": False, "reason": "missing"})
            continue
        actual_translation = actual.get("Translation", actual.get("translation")) or []
        translation_error = max(
            abs(float(actual_translation[index]) - expected["translation"][index])
            for index in range(3)
        )
        axis_dots = {
            key: _dot(
                actual.get(api_key, actual.get(api_key[0].lower() + api_key[1:], [])),
                expected[key],
            )
            for key, api_key in (
                ("xAxis", "XAxis"),
                ("yAxis", "YAxis"),
                ("zAxis", "ZAxis"),
            )
        }
        success = translation_error <= translation_tolerance and all(
            value >= 1.0 - axis_dot_tolerance for value in axis_dots.values()
        )
        rows.append(
            {
                "componentName": name,
                "success": success,
                "translationMaxErrorMeters": translation_error,
                "axisDots": axis_dots,
                "fixedEnvironment": expected["fixedEnvironment"],
            }
        )
    return {
        "success": len(rows) == expected_module_count and all(row["success"] for row in rows),
        "translationToleranceMeters": translation_tolerance,
        "axisDotTolerance": axis_dot_tolerance,
        "components": rows,
    }


def audit_source_orientation_compatibility(
    actual_poses: Iterable[dict[str, Any]],
    expected_manifest: Iterable[dict[str, Any]],
    *,
    axis_dot_tolerance: float = 1e-8,
    expected_module_count: int = EXPECTED_MODULE_COUNT,
) -> dict[str, Any]:
    """Reject incremental reuse when a module must rotate.

    A flexible subassembly can report the requested top-level Transform2 while
    some of its leaf components retain their previous solved positions.  A
    translation-only update is safe for the current direct-assembly workflow;
    an orientation change must start from a blank assembly so every module is
    inserted from its source file at the final pose.
    """
    actual_by_name = {
        str(item.get("Name", item.get("name", ""))): item for item in actual_poses
    }
    rows: list[dict[str, Any]] = []
    for expected in expected_manifest:
        name = expected["componentName"]
        actual = actual_by_name.get(name)
        if actual is None:
            rows.append({"componentName": name, "success": False, "reason": "missing"})
            continue
        axis_dots = {
            key: _dot(
                actual.get(api_key, actual.get(api_key[0].lower() + api_key[1:], [])),
                expected[key],
            )
            for key, api_key in (
                ("xAxis", "XAxis"),
                ("yAxis", "YAxis"),
                ("zAxis", "ZAxis"),
            )
        }
        success = all(value >= 1.0 - axis_dot_tolerance for value in axis_dots.values())
        rows.append(
            {
                "componentName": name,
                "success": success,
                "axisDots": axis_dots,
                "fixedEnvironment": expected["fixedEnvironment"],
            }
        )
    return {
        "success": len(rows) == expected_module_count and all(row["success"] for row in rows),
        "axisDotTolerance": axis_dot_tolerance,
        "orientationMismatchComponents": [
            row["componentName"] for row in rows if not row["success"]
        ],
        "components": rows,
    }


def audit_bounding_box_extents(
    actual_poses: Iterable[dict[str, Any]],
    expected_manifest: Iterable[dict[str, Any]],
    *,
    extent_tolerance_meters: float = 0.005,
    expected_module_count: int = EXPECTED_MODULE_COUNT,
) -> dict[str, Any]:
    """Detect flexible-child drift that a top-level pose audit cannot see."""
    actual_by_name = {
        str(item.get("Name", item.get("name", ""))): item for item in actual_poses
    }
    rows: list[dict[str, Any]] = []
    for expected in expected_manifest:
        name = expected["componentName"]
        actual = actual_by_name.get(name)
        actual_box = (actual or {}).get("BoundingBoxWorld", (actual or {}).get("boundingBoxWorld")) or []
        expected_box = expected.get("boundingBoxWorld") or []
        if len(actual_box) != 6 or len(expected_box) != 6:
            rows.append({"componentName": name, "success": False, "reason": "missingBoundingBox"})
            continue
        actual_extents = [
            float(actual_box[index + 3]) - float(actual_box[index]) for index in range(3)
        ]
        expected_extents = [
            float(expected_box[index + 3]) - float(expected_box[index]) for index in range(3)
        ]
        errors = [abs(actual_extents[index] - expected_extents[index]) for index in range(3)]
        success = max(errors) <= extent_tolerance_meters
        rows.append(
            {
                "componentName": name,
                "success": success,
                "expectedExtentsMeters": expected_extents,
                "actualExtentsMeters": actual_extents,
                "extentErrorsMeters": errors,
                "maximumExtentErrorMeters": max(errors),
                "fixedEnvironment": expected["fixedEnvironment"],
            }
        )
    return {
        "success": len(rows) == expected_module_count and all(row["success"] for row in rows),
        "extentToleranceMeters": extent_tolerance_meters,
        "mismatchComponents": [row["componentName"] for row in rows if not row["success"]],
        "components": rows,
    }


def call_and_record(
    client: McpClient,
    steps: list[dict[str, Any]],
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    started_at = utc_now_iso()
    started = time.perf_counter()
    try:
        payload = client.call_tool(tool, arguments or {})
    except Exception as exc:
        steps.append(
            {
                "tool": tool,
                "businessFailed": True,
                "invocationFailed": True,
                "arguments": arguments or {},
                "timing": {
                    "startedAtUtc": started_at,
                    "finishedAtUtc": utc_now_iso(),
                    "durationSeconds": round(time.perf_counter() - started, 6),
                },
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise RuntimeError(f"{tool} invocation failed: {exc}") from exc
    failed = isinstance(payload, dict) and any(
        payload.get(key) is False for key in ("success", "Success") if key in payload
    )
    steps.append(
        {
            "tool": tool,
            "businessFailed": failed,
            "timing": {
                "startedAtUtc": started_at,
                "finishedAtUtc": utc_now_iso(),
                "durationSeconds": round(time.perf_counter() - started, 6),
            },
            "payload": payload,
        }
    )
    if failed:
        raise RuntimeError(f"{tool} reported business failure.")
    return payload


def call_text_and_record(
    client: McpClient,
    steps: list[dict[str, Any]],
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> str:
    """Record MCP tools whose successful protocol payload is intentionally text."""
    started_at = utc_now_iso()
    started = time.perf_counter()
    try:
        payload = client.call_tool_text(tool, arguments or {})
    except Exception as exc:
        steps.append(
            {
                "tool": tool,
                "businessFailed": True,
                "invocationFailed": True,
                "arguments": arguments or {},
                "timing": {
                    "startedAtUtc": started_at,
                    "finishedAtUtc": utc_now_iso(),
                    "durationSeconds": round(time.perf_counter() - started, 6),
                },
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise RuntimeError(f"{tool} invocation failed: {exc}") from exc
    steps.append(
        {
            "tool": tool,
            "businessFailed": False,
            "timing": {
                "startedAtUtc": started_at,
                "finishedAtUtc": utc_now_iso(),
                "durationSeconds": round(time.perf_counter() - started, 6),
            },
            "payload": payload,
        }
    )
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_direct_save_as_arguments(source: Path, target: Path) -> dict[str, Any]:
    """Switch an opened independent source assembly to a distinct target before mutation."""
    return {
        "outputPath": str(target),
        "sourcePath": str(source),
        "saveAsCopy": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", default=str(DEFAULT_LAYOUT))
    parser.add_argument("--poses", default=str(DEFAULT_POSES))
    parser.add_argument("--target-assembly", default=str(DEFAULT_TARGET))
    parser.add_argument("--screenshot", default=str(DEFAULT_SCREENSHOT))
    parser.add_argument("--view-directory", default=str(DEFAULT_VIEWS))
    parser.add_argument("--saved-poses", default=str(DEFAULT_SAVED_POSES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--mcp", default=str(DEFAULT_MCP))
    parser.add_argument("--request-timeout", type=float, default=900.0)
    parser.add_argument("--expected-module-count", type=int, default=EXPECTED_MODULE_COUNT)
    parser.add_argument("--fixed-environment-code", default=FIXED_ENVIRONMENT_CODE)
    parser.add_argument(
        "--source-direct-assembly",
        default=None,
        help=(
            "Optional earlier independent nine-module assembly to update in place and "
            "save as --target-assembly. This is not a prototype Replay."
        ),
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Resume verification of an already-saved direct target instead of rebuilding it.",
    )
    parser.add_argument(
        "--rigid-component",
        action="append",
        default=[],
        help=(
            "Exact top-level component name or unique component code to force into "
            "rigid solve-as state before the final rebuild. Repeat as needed."
        ),
    )
    args = parser.parse_args()

    timer = PipelineTiming("project02.direct-nine-module-build")
    layout_path = resolved(args.layout)
    pose_path = resolved(args.poses)
    target = resolved(args.target_assembly)
    screenshot = resolved(args.screenshot)
    view_directory = resolved(args.view_directory)
    saved_poses = resolved(args.saved_poses)
    output = resolved(args.output)
    mcp = resolved(args.mcp)
    source_direct = (
        resolved(args.source_direct_assembly) if args.source_direct_assembly else None
    )
    if args.resume_existing and source_direct is not None:
        raise SystemExit("--resume-existing and --source-direct-assembly are mutually exclusive.")
    if target.exists() and not args.resume_existing:
        raise SystemExit(f"Target already exists; refusing to overwrite: {target}")
    if args.resume_existing and not target.is_file():
        raise SystemExit(f"Cannot resume because target does not exist: {target}")
    for required in (layout_path, pose_path, mcp):
        if not required.is_file():
            raise SystemExit(f"Required input does not exist: {required}")
    if source_direct is not None:
        if not source_direct.is_file():
            raise SystemExit(f"Source direct assembly does not exist: {source_direct}")
        if normalized_path(source_direct) == normalized_path(target):
            raise SystemExit("Source and target direct assembly paths must be different.")

    with timer.stage("load-and-validate-final-nine-module-manifest"):
        manifest = load_direct_manifest(
            layout_path,
            pose_path,
            expected_module_count=args.expected_module_count,
            fixed_environment_code=args.fixed_environment_code,
        )
        components = insertion_components(manifest)
        rigid_component_names = resolve_component_selectors(
            manifest, args.rigid_component
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    view_directory.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "success": False,
        "status": "DIRECT_NINE_MODULE_BUILD_STARTED",
        "generationMode": (
            "existing-direct-assembly-final-pose-update"
            if source_direct is not None
            else "blank-assembly-direct-final-pose-insertion"
        ),
        "prototypeAssemblyCopied": False,
        "replayLayoutToolUsed": False,
        "resumedExistingDirectTarget": bool(args.resume_existing),
        "sourceDirectAssemblyPath": str(source_direct) if source_direct else None,
        "layoutPath": str(layout_path),
        "targetPosePath": str(pose_path),
        "targetAssemblyPath": str(target),
        "savedPosePath": str(saved_poses),
        "screenshotPath": str(screenshot),
        "standardViewDirectory": str(view_directory),
        "manifest": manifest,
        "requestedRigidComponents": rigid_component_names,
        "steps": steps,
    }
    try:
        with McpClient(
            mcp,
            client_name="CodexProject02DirectNineModuleBuilder",
            request_timeout=args.request_timeout,
            framing="newline",
            direct_stdio=True,
        ) as client:
            call_and_record(client, steps, "solid_works_connect")
            if args.resume_existing:
                call_and_record(client, steps, "open_document", {"path": str(target)})
            elif source_direct is not None:
                call_and_record(
                    client, steps, "open_document", {"path": str(source_direct)}
                )
                source_poses = call_and_record(
                    client, steps, "list_component_poses", {"topLevelOnly": True}
                )
                summary["sourceOrientationCompatibilityAudit"] = (
                    audit_source_orientation_compatibility(
                        source_poses,
                        manifest,
                        expected_module_count=args.expected_module_count,
                    )
                )
                if not summary["sourceOrientationCompatibilityAudit"]["success"]:
                    mismatches = summary["sourceOrientationCompatibilityAudit"][
                        "orientationMismatchComponents"
                    ]
                    raise RuntimeError(
                        "Incremental source reuse is unsafe because target orientation differs "
                        f"for {mismatches}; rebuild from a blank assembly."
                    )
                call_and_record(
                    client,
                    steps,
                    "save_document_as",
                    source_direct_save_as_arguments(source_direct, target),
                )
            else:
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
            actual = call_and_record(client, steps, "list_components")
            summary["postInsertTopLevelAudit"] = audit_top_level_components(
                actual, manifest, expected_module_count=args.expected_module_count
            )
            if not summary["postInsertTopLevelAudit"]["success"]:
                raise RuntimeError("Post-insert top-level whitelist audit failed.")

            if not args.resume_existing:
                rigid_state_results = []
                for component_name in rigid_component_names:
                    rigid_state_results.append(
                        call_and_record(
                            client,
                            steps,
                            "set_top_level_component_solving_state",
                            {
                                "hierarchyPath": component_name,
                                "solvingState": 0,
                                "rebuild": False,
                            },
                        )
                    )
                summary["rigidSolveAsResults"] = rigid_state_results
                for row in manifest:
                    if row["fixedEnvironment"]:
                        continue
                    call_and_record(
                        client,
                        steps,
                        "set_component_orientation",
                        {
                            "componentName": row["componentName"],
                            "xAxis": row["xAxis"],
                            "yAxis": row["yAxis"],
                            "zAxis": row["zAxis"],
                            "rebuild": False,
                        },
                    )
                current_poses = call_and_record(
                    client, steps, "list_component_poses", {"topLevelOnly": True}
                )
                direct_moves = movement_deltas(current_poses, manifest)
                summary["directTranslationCorrections"] = direct_moves
                for move in direct_moves:
                    if not move["requiresMove"]:
                        continue
                    call_and_record(
                        client,
                        steps,
                        "move_component",
                        {
                            "componentName": move["componentName"],
                            "deltaX": move["delta"][0],
                            "deltaY": move["delta"][1],
                            "deltaZ": move["delta"][2],
                        },
                    )
                call_and_record(client, steps, "force_rebuild_active_document", {"topOnly": False})
                call_and_record(client, steps, "save_document", {"path": str(target)})
                call_text_and_record(client, steps, "close_document", {"path": str(target)})
                call_and_record(client, steps, "open_document", {"path": str(target)})

            reopened_components = call_and_record(client, steps, "list_components")
            summary["reopenedTopLevelAudit"] = audit_top_level_components(
                reopened_components,
                manifest,
                expected_module_count=args.expected_module_count,
            )
            reopened_poses = call_and_record(
                client, steps, "list_component_poses", {"topLevelOnly": True}
            )
            write_json(saved_poses, reopened_poses)
            summary["reopenedPoseAudit"] = audit_poses(
                reopened_poses,
                manifest,
                expected_module_count=args.expected_module_count,
            )
            summary["reopenedBoundingBoxExtentAudit"] = audit_bounding_box_extents(
                reopened_poses,
                manifest,
                expected_module_count=args.expected_module_count,
            )
            if not summary["reopenedTopLevelAudit"]["success"]:
                raise RuntimeError("Reopened top-level whitelist audit failed.")
            if not summary["reopenedPoseAudit"]["success"]:
                raise RuntimeError("Reopened target-pose audit failed.")
            if not summary["reopenedBoundingBoxExtentAudit"]["success"]:
                raise RuntimeError(
                    "Reopened body-envelope audit failed; a flexible subassembly may have "
                    "retained stale leaf positions."
                )

            # Standard-view export ends on "bottom".  Without resetting the
            # viewport, a later incremental candidate inherits that camera and
            # its primary review screenshot becomes misleading.
            call_text_and_record(
                client,
                steps,
                "show_standard_view",
                {"view": "isometric"},
            )
            call_and_record(
                client,
                steps,
                "export_current_view_png",
                {
                    "outputPath": str(screenshot),
                    "width": 1600,
                    "height": 900,
                    "includeBase64Data": False,
                    "fitToView": True,
                },
            )
            call_and_record(
                client,
                steps,
                "export_standard_view_png_set",
                {
                    "outputDirectory": str(view_directory),
                    "fileNamePrefix": target.stem,
                    "width": 1600,
                    "height": 900,
                    "includeBase64Data": False,
                },
            )
            summary["rebuildState"] = call_and_record(
                client, steps, "get_active_document_rebuild_state"
            )

        summary["success"] = target.is_file() and screenshot.is_file() and saved_poses.is_file()
        summary["status"] = (
            "DIRECT_NINE_MODULE_ASSEMBLY_SAVED_REOPENED_AND_POSE_VERIFIED"
            if summary["success"]
            else "DIRECT_NINE_MODULE_OUTPUT_MISSING"
        )
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        summary["status"] = "DIRECT_NINE_MODULE_BUILD_FAILED"
    summary["timing"] = timer.finish(status="completed" if summary["success"] else "failed")
    write_json(output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
