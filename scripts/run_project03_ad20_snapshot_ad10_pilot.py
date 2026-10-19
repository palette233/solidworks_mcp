#!/usr/bin/env python3
"""Replace AD20 with a static intermediate snapshot in an AD10 copy and verify persistence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient

DEFAULT_AD10 = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目03\01-项目3D图纸\FL9A24D063A000.001-0415\FL9A24D063AD10.001.SLDASM"
)


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def unique(rows: list[dict[str, Any]], token: str) -> dict[str, Any]:
    matches = [row for row in rows if token.casefold() in str(pick(row, "Name", "")).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Selector {token!r} resolved to {len(matches)} components.")
    return matches[0]


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


def max_transform_error(first: list[float], second: list[float]) -> float:
    if len(first) != 16 or len(second) != 16:
        return float("inf")
    return max(abs(float(a) - float(b)) for a, b in zip(first, second))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    )
    parser.add_argument("--ad10-source", type=Path, default=DEFAULT_AD10)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_intermediate_5deg_snapshot_v1/project03_AD20_static_5deg.SLDASM",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_5deg_ad10_parent_pilot_v1",
    )
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()
    exe, source, snapshot, output_dir = (
        args.exe.resolve(),
        args.ad10_source.resolve(),
        args.snapshot.resolve(),
        args.output_dir.resolve(),
    )
    for path in (exe, source, snapshot):
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "project03_AD10_with_AD20_static_5deg.SLDASM"
    manifest = output_dir / "project03_ad20_snapshot_ad10_parent_pilot.json"
    if target.exists() or manifest.exists():
        raise FileExistsError(f"Refusing to overwrite evidence in {output_dir}")

    protected = (source, snapshot)
    hashes_before = {str(path): sha256(path) for path in protected}
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-static-snapshot-ad10-pilot/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceAd10": str(source),
        "snapshotAd20": str(snapshot),
        "targetAd10": str(target),
        "sourceHashesBefore": hashes_before,
        "operations": [],
        "problems": [],
        "blockers": [],
        "productionReady": False,
    }
    atomic_write(manifest, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name}
        payload["operations"].append(row)
        atomic_write(manifest, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, durationSeconds=round(time.perf_counter() - started, 6), error=str(exc))
            payload["problems"].append(f"{name}: {exc}")
            atomic_write(manifest, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        atomic_write(manifest, payload)
        return value

    total_started = time.perf_counter()
    try:
        operation("copy-ad10", lambda: shutil.copy2(source, target))
        with McpClient(exe, "Project03AD20SnapshotAD10Pilot", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            operation("open-ad10-copy", lambda: client.call_tool("open_document", {"path": str(target)}))
            before_rows = operation(
                "list-before-replacement", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True})
            )
            original = unique(before_rows, "FL9A24D063AD20")
            payload["originalAd20"] = original
            payload["replacement"] = operation(
                "replace-ad20-with-static-snapshot",
                lambda: client.call_tool(
                    "replace_component",
                    {
                        "hierarchyPath": pick(original, "HierarchyPath", ""),
                        "replacementFilePath": str(snapshot),
                        "replaceAllInstances": False,
                        "reattachMates": False,
                    },
                ),
            )
            after_rows = operation(
                "list-after-replacement", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True})
            )
            replacement = unique(after_rows, snapshot.stem)
            payload["replacementAd20"] = replacement
            payload["snapshotSolvingState"] = operation(
                "set-static-snapshot-rigid",
                lambda: client.call_tool(
                    "set_top_level_component_solving_state",
                    {
                        "hierarchyPath": pick(replacement, "HierarchyPath", ""),
                        "solvingState": 0,
                        "rebuild": True,
                    },
                ),
            )
            payload["snapshotTransformLock"] = operation(
                "restore-static-snapshot-transform",
                lambda: client.call_tool(
                    "set_component_transform",
                    {
                        "componentName": pick(replacement, "Name", ""),
                        "transform": list(pick(original, "Transform", [])),
                        "rebuild": False,
                    },
                ),
            )
            after_rigid_rows = operation(
                "list-after-rigid-lock",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            replacement = unique(after_rigid_rows, snapshot.stem)
            payload["placementErrorBeforeSave"] = max_transform_error(
                list(pick(replacement, "Transform", [])), list(pick(original, "Transform", []))
            )
            payload["save"] = operation(
                "save-ad10-copy", lambda: client.call_tool("save_document", {"path": str(target)})
            )
            operation("close-ad10-copy", lambda: client.call_tool_text("close_document", {"path": str(target)}))
            operation("reopen-ad10-copy", lambda: client.call_tool("open_document", {"path": str(target)}))
            reopened_rows = operation(
                "list-reopened", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True})
            )
            reopened = unique(reopened_rows, snapshot.stem)
            payload["reopenedAd20"] = reopened
            payload["reopenedSolvingState"] = pick(reopened, "SolvingState")
            payload["placementErrorAfterReopen"] = max_transform_error(
                list(pick(reopened, "Transform", [])), list(pick(original, "Transform", []))
            )
            operation("close-reopened-ad10", lambda: client.call_tool_text("close_document", {"path": str(target)}))

        hashes_after = {str(path): sha256(path) for path in protected}
        payload["sourceHashesAfter"] = hashes_after
        payload["sourceFilesUnchanged"] = hashes_after == hashes_before
        passed = (
            target.is_file()
            and payload["placementErrorBeforeSave"] <= 1e-9
            and payload["placementErrorAfterReopen"] <= 1e-9
            and payload["reopenedSolvingState"] == 0
            and payload["sourceFilesUnchanged"]
        )
        payload["status"] = (
            "PASSED_PROJECT03_AD20_STATIC_SNAPSHOT_AD10_PARENT_PILOT"
            if passed
            else "FAILED_PROJECT03_AD20_STATIC_SNAPSHOT_AD10_PARENT_PILOT"
        )
        if not passed:
            payload["blockers"].append("Replacement placement persistence or source-integrity gate failed.")
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
        payload["blockers"].append("AD10 parent replacement did not reach a durable reopen-verification result.")
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        atomic_write(manifest, payload)

    print(manifest)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
