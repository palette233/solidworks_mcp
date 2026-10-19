#!/usr/bin/env python3
"""Capture AD20 internal component poses in its native 0-degree and 25-degree configurations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient

DEFAULT_SOURCE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目03\01-项目3D图纸\FL9A24D063A000.001-0415\FL9A24D063AD20.001.SLDASM"
)


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(path: str | Path) -> str:
    return str(Path(path).resolve()).casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe",
        type=Path,
        default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_internal_endpoint_poses_v1.json",
    )
    parser.add_argument("--zero-configuration", default="0度")
    parser.add_argument("--twenty-five-configuration", default="25度")
    parser.add_argument(
        "--close-even-if-initially-open",
        action="store_true",
        help="Close the source after capture even when it was already open (used to clean up a prior interrupted run).",
    )
    parser.add_argument("--timeout", type=float, default=1200.0)
    args = parser.parse_args()
    exe, source, output = args.exe.resolve(), args.source.resolve(), args.output.resolve()
    for path in (exe, source):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists():
        raise FileExistsError(output)

    source_sha_before = sha256(source)
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-internal-endpoint-poses/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "sourceSha256Before": source_sha_before,
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
    initially_open = False
    initial_configuration: str | None = None
    client: McpClient | None = None
    try:
        with McpClient(exe, "Project03AD20InternalEndpointCapture", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            documents = operation("list-documents-before", lambda: client.call_tool("list_documents", {}))
            initially_open = any(normalized(pick(row, "Path", "")) == normalized(source) for row in documents)
            operation("open-source", lambda: client.call_tool("open_document", {"path": str(source)}))
            inventory = operation(
                "inspect-configurations",
                lambda: client.call_tool("inspect_active_document_configurations", {}),
            )
            initial_configuration = pick(inventory, "ActiveConfiguration")
            names = list(pick(inventory, "ConfigurationNames", []))
            requested = [args.zero_configuration, args.twenty_five_configuration]
            missing = [name for name in requested if name not in names]
            if missing:
                raise RuntimeError(f"AD20 is missing requested configurations: {missing}; available={names}")

            for state, angle, configuration in (
                ("zero", 0.0, args.zero_configuration),
                ("twenty-five", 25.0, args.twenty_five_configuration),
            ):
                switched = operation(
                    f"activate-{state}",
                    lambda configuration=configuration: client.call_tool(
                        "set_active_document_configuration",
                        {"configurationName": configuration, "rebuild": True},
                    ),
                )
                if not pick(switched, "Success", False):
                    raise RuntimeError(f"Failed to activate configuration {configuration}: {switched}")
                rows = operation(
                    f"list-{state}-top-level-poses",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
                )
                payload["states"].append(
                    {
                        "state": state,
                        "angleDegrees": angle,
                        "configuration": configuration,
                        "switchResult": switched,
                        "topLevelComponentCount": len(rows),
                        "topLevelComponentPoses": rows,
                    }
                )
                atomic_write(output, payload)

            if initial_configuration and initial_configuration in names:
                restored = operation(
                    "restore-initial-configuration",
                    lambda: client.call_tool(
                        "set_active_document_configuration",
                        {"configurationName": initial_configuration, "rebuild": True},
                    ),
                )
                if not pick(restored, "Success", False):
                    raise RuntimeError(f"Failed to restore configuration {initial_configuration}: {restored}")
            if not initially_open or args.close_even_if_initially_open:
                operation("close-source-without-save", lambda: client.call_tool_text("close_document", {"path": str(source)}))

        source_sha_after = sha256(source)
        payload["sourceSha256After"] = source_sha_after
        payload["sourceUnchanged"] = source_sha_after == source_sha_before
        if not payload["sourceUnchanged"]:
            raise RuntimeError("AD20 source SHA changed during a read-only capture.")
        payload["status"] = "PASSED_AD20_INTERNAL_ENDPOINT_POSE_CAPTURE"
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
        payload["sourceSha256After"] = sha256(source)
        payload["sourceUnchanged"] = payload["sourceSha256After"] == source_sha_before
    finally:
        payload["initiallyOpen"] = initially_open
        payload["initialConfiguration"] = initial_configuration
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        atomic_write(output, payload)

    print(output)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
