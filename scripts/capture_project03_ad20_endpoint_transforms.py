#!/usr/bin/env python3
"""Capture AD20 Transform2 at the validated 0-degree and 25-degree AD10 states."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def unique_ad20(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [row for row in rows if "FL9A24D063AD20" in str(pick(row, "Name", "")).upper()]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one AD20 top-level child, found {len(matches)}.")
    return matches[0]


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe")
    parser.add_argument(
        "--zero",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad00_full_context_baseline_v2/AD10_LEFT_both-0deg.SLDASM",
    )
    parser.add_argument(
        "--twenty-five",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad00_full_context_left25_v1/AD10_LEFT_left-25deg.SLDASM",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_endpoint_transforms_v1.json",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    exe, zero, twenty_five, output = (
        args.exe.resolve(), args.zero.resolve(), args.twenty_five.resolve(), args.output.resolve()
    )
    for path in (exe, zero, twenty_five):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists():
        raise FileExistsError(output)
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-endpoint-transforms/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "states": [],
        "operations": [],
    }
    atomic_write(output, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name}
        payload["operations"].append(row)
        atomic_write(output, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, durationSeconds=round(time.perf_counter() - started, 6), error=str(exc))
            atomic_write(output, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        atomic_write(output, payload)
        return value

    total_started = time.perf_counter()
    try:
        with McpClient(exe, "Project03AD20EndpointCapture", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            for state, angle, path in (("zero", 0.0, zero), ("twenty-five", 25.0, twenty_five)):
                operation(f"open-{state}", lambda path=path: client.call_tool("open_document", {"path": str(path)}))
                rows = operation(f"list-{state}", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
                ad20 = unique_ad20(rows)
                subtree = operation(
                    f"list-{state}-ad20-subtree",
                    lambda ad20=ad20: client.call_tool(
                        "list_top_level_component_subtree_poses",
                        {"hierarchyPath": pick(ad20, "HierarchyPath", "")},
                    ),
                )
                payload["states"].append(
                    {
                        "state": state,
                        "angleDegrees": angle,
                        "parentAssembly": str(path),
                        "componentName": pick(ad20, "Name", ""),
                        "referencedConfiguration": pick(ad20, "ReferencedConfiguration", ""),
                        "transform": pick(ad20, "Transform", []),
                        "translation": pick(ad20, "Translation", []),
                        "boundingBoxWorld": pick(ad20, "BoundingBoxWorld", []),
                        "subtreePoses": subtree,
                    }
                )
                atomic_write(output, payload)
                operation(f"close-{state}", lambda path=path: client.call_tool_text("close_document", {"path": str(path)}))
        payload["status"] = "PASSED_AD20_ENDPOINT_TRANSFORM_CAPTURE"
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        atomic_write(output, payload)
    print(output)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
