#!/usr/bin/env python3
"""Capture the left AD20 contextual component poses from validated 0/25-degree full assemblies."""

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


def select_unique(rows: list[dict[str, Any]], predicate, label: str) -> dict[str, Any]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"{label} resolved to {len(matches)} components.")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    )
    parser.add_argument(
        "--zero",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/cad-working/step-07-ab00-attempt2/step07b_project03_full_10_object_hybrid_static.SLDASM",
    )
    parser.add_argument(
        "--twenty-five",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad00_full_context_left25_v1/project03_full_context_left-25deg.SLDASM",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_contextual_endpoint_poses_v1.json",
    )
    parser.add_argument("--timeout", type=float, default=1800.0)
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
        "schemaVersion": "project03-ad20-contextual-endpoint-poses/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "states": [],
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

    total_started = time.perf_counter()
    try:
        with McpClient(exe, "Project03AD20ContextualEndpointCapture", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            for state, angle, path in (("zero", 0.0, zero), ("twenty-five", 25.0, twenty_five)):
                operation(f"open-{state}", lambda path=path: client.call_tool("open_document", {"path": str(path)}))
                rows = operation(
                    f"list-all-component-poses-{state}",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": False}),
                )
                if state == "zero":
                    ad10 = select_unique(
                        rows,
                        lambda row: str(pick(row, "Name", "")).endswith("FL9A24D063AD10.001-1")
                        and int(pick(row, "Depth", -1)) == 1,
                        "zero left AD10",
                    )
                else:
                    ad10 = select_unique(
                        rows,
                        lambda row: "AD10_LEFT_left-25deg" in str(pick(row, "Name", ""))
                        and int(pick(row, "Depth", -1)) == 1,
                        "25-degree left AD10",
                    )
                ad10_name = str(pick(ad10, "Name", ""))
                ad20 = select_unique(
                    rows,
                    lambda row: str(pick(row, "Name", "")).startswith(ad10_name + "/")
                    and str(pick(row, "Name", "")).endswith("FL9A24D063AD20.001-1")
                    and int(pick(row, "Depth", -1)) == int(pick(ad10, "Depth", 0)) + 1,
                    f"{state} contextual AD20",
                )
                ad20_name = str(pick(ad20, "Name", ""))
                children = [
                    row
                    for row in rows
                    if str(pick(row, "Name", "")).startswith(ad20_name + "/")
                    and int(pick(row, "Depth", -1)) == int(pick(ad20, "Depth", 0)) + 1
                ]
                payload["states"].append(
                    {
                        "state": state,
                        "angleDegrees": angle,
                        "assemblyPath": str(path),
                        "totalComponentPoseCount": len(rows),
                        "ad10": ad10,
                        "ad20": ad20,
                        "directChildCount": len(children),
                        "directChildren": children,
                    }
                )
                atomic_write(output, payload)
                operation(f"close-{state}", lambda path=path: client.call_tool_text("close_document", {"path": str(path)}))
        counts = [state["directChildCount"] for state in payload["states"]]
        payload["status"] = (
            "PASSED_PROJECT03_AD20_CONTEXTUAL_ENDPOINT_CAPTURE"
            if counts == [29, 29]
            else "FAILED_PROJECT03_AD20_CONTEXTUAL_ENDPOINT_CAPTURE"
        )
        if counts != [29, 29]:
            payload["blocker"] = f"Expected 29 contextual AD20 children at both endpoints; found {counts}."
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
