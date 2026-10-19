#!/usr/bin/env python3
"""Capture AD20 child transforms before and after insertion into the Project03 AD10 parent."""

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


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_intermediate_5deg_snapshot_v1/project03_AD20_static_5deg.SLDASM",
    )
    parser.add_argument(
        "--ad10-pilot",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_5deg_ad10_parent_pilot_v2/project03_AD10_with_AD20_static_5deg.SLDASM",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_5deg_ad10_parent_pilot_v2/project03_ad20_snapshot_stage_transforms_v1.json",
    )
    parser.add_argument("--timeout", type=float, default=1200.0)
    args = parser.parse_args()
    exe, snapshot, ad10_pilot, output = (
        args.exe.resolve(), args.snapshot.resolve(), args.ad10_pilot.resolve(), args.output.resolve()
    )
    for path in (exe, snapshot, ad10_pilot):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists():
        raise FileExistsError(output)
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-snapshot-stage-transforms/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "stages": [],
        "operations": [],
        "productionReady": False,
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

    started = time.perf_counter()
    try:
        with McpClient(exe, "Project03AD20SnapshotStageTransforms", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))

            operation("open-standalone-snapshot", lambda: client.call_tool("open_document", {"path": str(snapshot)}))
            standalone = operation(
                "capture-standalone-top-level",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            payload["stages"].append(
                {
                    "stage": "standalone-ad20-snapshot",
                    "assemblyPath": str(snapshot),
                    "parent": None,
                    "directChildCount": len(standalone),
                    "directChildren": standalone,
                }
            )
            atomic_write(output, payload)
            operation("close-standalone-snapshot", lambda: client.call_tool_text("close_document", {"path": str(snapshot)}))

            operation("open-ad10-pilot", lambda: client.call_tool("open_document", {"path": str(ad10_pilot)}))
            top = operation(
                "capture-ad10-top-level",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            parent_matches = [
                row
                for row in top
                if Path(str(pick(row, "Path", ""))).name.casefold() == snapshot.name.casefold()
            ]
            if len(parent_matches) != 1:
                raise RuntimeError(f"AD10 pilot snapshot parent resolved to {len(parent_matches)} rows.")
            parent = parent_matches[0]
            hierarchy = str(pick(parent, "HierarchyPath", pick(parent, "Name", "")))
            subtree = operation(
                "capture-ad10-snapshot-subtree",
                lambda: client.call_tool(
                    "list_top_level_component_subtree_poses", {"hierarchyPath": hierarchy}
                ),
            )
            children = [row for row in subtree if int(pick(row, "Depth", -1)) == 1]
            payload["stages"].append(
                {
                    "stage": "ad10-parent-pilot",
                    "assemblyPath": str(ad10_pilot),
                    "parent": parent,
                    "subtreePoseCount": len(subtree),
                    "directChildCount": len(children),
                    "directChildren": children,
                }
            )
            atomic_write(output, payload)
            operation("close-ad10-pilot", lambda: client.call_tool_text("close_document", {"path": str(ad10_pilot)}))

        payload["status"] = (
            "PASSED_AD20_SNAPSHOT_STAGE_TRANSFORM_CAPTURE"
            if [row["directChildCount"] for row in payload["stages"]] == [29, 29]
            else "FAILED_AD20_SNAPSHOT_STAGE_TRANSFORM_CAPTURE"
        )
        if not payload["status"].startswith("PASSED"):
            payload["blocker"] = "Expected 29 direct AD20 children in both stages."
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - started, 6)
        atomic_write(output, payload)
    print(output)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
