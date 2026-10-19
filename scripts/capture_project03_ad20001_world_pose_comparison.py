#!/usr/bin/env python3
"""Compare AD20001 world poses in the validated Project03 baseline and a candidate assembly."""

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
    parser.add_argument(
        "--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/cad-working/step-07-ab00-attempt2/step07b_project03_full_10_object_hybrid_static.SLDASM",
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--component-source-token", default="FL5A24D063AD20001.01.SLDPRT")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()
    exe, baseline, candidate, output = (
        args.exe.resolve(), args.baseline.resolve(), args.candidate.resolve(), args.output.resolve()
    )
    for path in (exe, baseline, candidate):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists():
        raise FileExistsError(output)
    payload: dict[str, Any] = {
        "schemaVersion": "project03-component-world-pose-comparison/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "componentSourceToken": args.component_source_token,
        "assemblies": [],
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
        with McpClient(exe, "Project03AD20001WorldPoseComparison", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            for label, path in (("validated-baseline", baseline), ("candidate", candidate)):
                operation(f"open-{label}", lambda path=path: client.call_tool("open_document", {"path": str(path)}))
                rows = operation(
                    f"list-all-component-poses-{label}",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": False}),
                )
                matches = [
                    row
                    for row in rows
                    if args.component_source_token.casefold() in str(pick(row, "Path", "")).casefold()
                ]
                payload["assemblies"].append(
                    {
                        "label": label,
                        "path": str(path),
                        "totalComponentPoseCount": len(rows),
                        "matchCount": len(matches),
                        "matches": matches,
                    }
                )
                atomic_write(output, payload)
                operation(f"close-{label}", lambda path=path: client.call_tool_text("close_document", {"path": str(path)}))
        counts = [row["matchCount"] for row in payload["assemblies"]]
        payload["status"] = (
            "PASSED_COMPONENT_WORLD_POSE_CAPTURE" if all(count > 0 for count in counts) else "FAILED_COMPONENT_WORLD_POSE_CAPTURE"
        )
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
