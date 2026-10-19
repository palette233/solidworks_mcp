#!/usr/bin/env python3
"""Create a Project02 eight-module-only configuration from a verified context assembly.

The source-context component instances are preserved.  The active document is first
saved under a new path, then every non-target top-level component is hidden.
This avoids the flexible-subassembly/configuration drift observed when the same eight
modules were reinserted into a blank assembly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)
DEFAULT_SOURCE = ROOT / "demo/FL9A24D062A000_prototype_context_solved_v48.SLDASM"
DEFAULT_TARGET = ROOT / "demo/FL9A24D062A000_8modules_context_isolated_v51.SLDASM"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_v51_context_isolation_result.json"
DEFAULT_VIEWS = ROOT / "demo/project02_8modules_context_isolated_v51_views"
KEEP_COMPONENTS = [
    "FL9A24D062A100.001-1",
    "FL9A24D062A180.001-1",
    "FL9A24D062A200.001-1",
    "FL9A24D062A300.001-1",
    "FL9A24D062A500.001-1",
    "FL9A24D062A700.001-1",
    "FL9A24D062A800.001-1",
    "T401AA-07388-0-1",
]


def call(client: McpClient, steps: list[dict[str, Any]], tool: str, args=None):
    payload = client.call_tool(tool, args or {})
    steps.append({"tool": tool, "payload": payload})
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--views", type=Path, default=DEFAULT_VIEWS)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    exe = args.exe.resolve()
    source = args.source.resolve()
    target = args.target.resolve()
    output = args.output.resolve()
    views = args.views.resolve()
    for required in (exe, source):
        if not required.is_file():
            raise SystemExit(f"Required file does not exist: {required}")
    if target.exists():
        raise SystemExit(f"Target already exists; refusing to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    views.mkdir(parents=True, exist_ok=True)

    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "success": False,
        "status": "CONTEXT_ISOLATION_STARTED",
        "sourceAssemblyPath": str(source),
        "targetAssemblyPath": str(target),
        "keepComponentNames": KEEP_COMPONENTS,
        "steps": steps,
    }
    try:
        with McpClient(
            exe,
            client_name="CodexProject02ContextIsolation",
            request_timeout=args.timeout,
            framing="newline",
            direct_stdio=True,
        ) as client:
            call(client, steps, "solid_works_connect")
            active = call(client, steps, "get_active_document")
            active_path = Path(active.get("Path") or active.get("path") or "").resolve()
            if active_path != source:
                raise RuntimeError(
                    f"The verified source must already be active. Active={active_path}; expected={source}"
                )
            before = call(client, steps, "list_component_poses", {"topLevelOnly": True})
            before_by_name = {row["Name"]: row for row in before if row.get("Name") in KEEP_COMPONENTS}
            if set(before_by_name) != set(KEEP_COMPONENTS):
                raise RuntimeError("The active source does not expose all eight requested top-level modules.")

            call(
                client,
                steps,
                "save_document_as",
                {"outputPath": str(target), "saveAsCopy": False},
            )
            isolation = call(
                client,
                steps,
                "hide_top_level_components_except",
                {"keepComponentNames": KEEP_COMPONENTS, "rebuild": True},
            )
            if not isolation.get("Success", isolation.get("success", False)):
                summary["status"] = "TOP_LEVEL_ISOLATION_FAILED"
                raise RuntimeError("Top-level component isolation reported failure.")
            remaining = isolation.get("VisibleComponentNames") or isolation.get(
                "visibleComponentNames"
            )
            if set(remaining or []) != set(KEEP_COMPONENTS):
                summary["status"] = "RESOLVED_COMPONENT_AUDIT_FAILED"
                raise RuntimeError(f"Visible top-level audit failed: {remaining}")

            after = call(client, steps, "list_component_poses", {"topLevelOnly": True})
            after_by_name = {row["Name"]: row for row in after if row.get("Name") in KEEP_COMPONENTS}
            transform_errors: dict[str, float] = {}
            for name in KEEP_COMPONENTS:
                expected = before_by_name[name].get("Transform") or []
                actual = after_by_name.get(name, {}).get("Transform") or []
                if len(expected) != len(actual):
                    transform_errors[name] = float("inf")
                else:
                    transform_errors[name] = max(
                        (abs(float(a) - float(b)) for a, b in zip(expected, actual)),
                        default=0.0,
                    )
            summary["maximumIsolationTransformElementError"] = max(transform_errors.values())
            summary["isolationTransformErrors"] = transform_errors
            if summary["maximumIsolationTransformElementError"] > 1e-9:
                summary["status"] = "ISOLATION_MOVED_TARGET_MODULES"
                raise RuntimeError("Suppressing non-target context changed a target-module transform.")

            call(client, steps, "save_document", {"path": str(target)})
            call(
                client,
                steps,
                "export_standard_view_png_set",
                {
                    "outputDirectory": str(views),
                    "fileNamePrefix": "project02-context-isolated-v51",
                    "width": 1600,
                    "height": 900,
                    "includeBase64Data": False,
                },
            )
        summary["success"] = target.is_file()
        summary["status"] = "CONTEXT_ISOLATED_EIGHT_MODULE_ASSEMBLY_SAVED"
    except Exception as exc:
        summary["error"] = str(exc)
        if summary["status"] == "CONTEXT_ISOLATION_STARTED":
            summary["status"] = "CONTEXT_ISOLATION_FAILED"
    finally:
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
