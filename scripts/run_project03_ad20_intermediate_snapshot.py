#!/usr/bin/env python3
"""Build and reopen one static AD20 intermediate-angle snapshot from derived component poses."""

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


def transform_error(actual: list[float], expected: list[float]) -> float:
    if len(actual) != 16 or len(expected) != 16:
        return float("inf")
    return max(abs(float(a) - float(b)) for a, b in zip(actual, expected))


def sample_for(component: dict[str, Any], angle: float) -> dict[str, Any]:
    matches = [
        row
        for row in component["samples"]
        if abs(float(row["mechanismParameterDegrees"]) - angle) <= 1e-9
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {angle:g}-degree sample for {component['componentName']}; found {len(matches)}."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe",
        type=Path,
        default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe",
    )
    parser.add_argument(
        "--interpolation",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_transforms_v1.json",
    )
    parser.add_argument("--angle", type=float, default=5.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_5deg_snapshot_v1",
    )
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()
    exe, interpolation_path, output_dir = (
        args.exe.resolve(),
        args.interpolation.resolve(),
        args.output_dir.resolve(),
    )
    for path in (exe, interpolation_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    angle_tag = f"{args.angle:g}".replace("-", "minus").replace(".", "p")
    assembly_path = output_dir / f"project03_AD20_static_{angle_tag}deg.SLDASM"
    manifest_path = output_dir / "project03_ad20_intermediate_snapshot_closure.json"
    if assembly_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence in {output_dir}")

    interpolation = json.loads(interpolation_path.read_text(encoding="utf-8-sig"))
    components = list(interpolation["components"])
    if len(components) != int(interpolation["componentCount"]):
        raise RuntimeError("Interpolation component count is inconsistent.")
    expected = {
        row["componentName"]: list(sample_for(row, args.angle)["transform"])
        for row in components
    }
    source_paths = sorted({Path(row["componentPath"]).resolve() for row in components})
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing AD20 child sources: {missing}")
    source_hashes_before = {str(path): sha256(path) for path in source_paths}

    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-intermediate-static-snapshot-closure/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project03",
        "moduleId": "AD20",
        "mechanismParameterDegrees": args.angle,
        "sourceInterpolation": str(interpolation_path),
        "assemblyPath": str(assembly_path),
        "componentCount": len(components),
        "operations": [],
        "componentInstances": [],
        "problems": [],
        "blockers": [],
        "productionReady": False,
    }
    atomic_write(manifest_path, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name}
        payload["operations"].append(row)
        atomic_write(manifest_path, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, durationSeconds=round(time.perf_counter() - started, 6), error=str(exc))
            atomic_write(manifest_path, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        atomic_write(manifest_path, payload)
        return value

    total_started = time.perf_counter()
    try:
        with McpClient(exe, "Project03AD20IntermediateSnapshot", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            operation("new-assembly", lambda: client.call_tool("new_document", {"type": "Assembly"}))
            operation(
                "save-empty-snapshot",
                lambda: client.call_tool(
                    "save_document_as",
                    {"outputPath": str(assembly_path), "saveAsCopy": False},
                ),
            )

            for index, component in enumerate(components, start=1):
                source_path = str(Path(component["componentPath"]).resolve())
                expected_transform = expected[component["componentName"]]
                operation(
                    f"activate-before-insert-{index:02d}",
                    lambda: client.call_tool("activate_document_by_title", {"title": assembly_path.stem}),
                )
                before = client.call_tool("list_component_poses", {"topLevelOnly": True})
                before_names = {str(pick(row, "Name", "")) for row in before}
                operation(
                    f"insert-{index:02d}",
                    lambda source_path=source_path: client.call_tool(
                        "insert_component", {"filePath": source_path, "x": 0, "y": 0, "z": 0}
                    ),
                )
                operation(
                    f"reactivate-after-insert-{index:02d}",
                    lambda: client.call_tool("activate_document_by_title", {"title": assembly_path.stem}),
                )
                after = client.call_tool("list_component_poses", {"topLevelOnly": True})
                added = [row for row in after if str(pick(row, "Name", "")) not in before_names]
                if len(added) != 1:
                    raise RuntimeError(
                        f"Insertion {index} ({component['componentName']}) created {len(added)} resolvable instances."
                    )
                actual_name = str(pick(added[0], "Name", ""))
                operation(
                    f"transform-{index:02d}",
                    lambda actual_name=actual_name, expected_transform=expected_transform: client.call_tool(
                        "set_component_transform",
                        {"componentName": actual_name, "transform": expected_transform, "rebuild": False},
                    ),
                )
                payload["componentInstances"].append(
                    {
                        "sourceOccurrenceName": component["componentName"],
                        "snapshotOccurrenceName": actual_name,
                        "sourcePath": source_path,
                        "motionType": component["motionType"],
                    }
                )
                atomic_write(manifest_path, payload)

            payload["rebuild"] = operation(
                "rebuild-snapshot", lambda: client.call_tool("force_rebuild_active_document", {"topOnly": False})
            )
            payload["save"] = operation(
                "save-snapshot", lambda: client.call_tool("save_document", {"path": str(assembly_path)})
            )
            operation("close-snapshot", lambda: client.call_tool_text("close_document", {"path": str(assembly_path)}))
            operation("reopen-snapshot", lambda: client.call_tool("open_document", {"path": str(assembly_path)}))
            reopened = operation(
                "capture-reopened-poses", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True})
            )
            reopened_by_name = {str(pick(row, "Name", "")): row for row in reopened}
            verification = []
            for instance in payload["componentInstances"]:
                actual_name = instance["snapshotOccurrenceName"]
                row = reopened_by_name.get(actual_name)
                error = (
                    transform_error(list(pick(row, "Transform", [])), expected[instance["sourceOccurrenceName"]])
                    if row is not None
                    else float("inf")
                )
                verification.append(
                    {
                        "sourceOccurrenceName": instance["sourceOccurrenceName"],
                        "snapshotOccurrenceName": actual_name,
                        "foundAfterReopen": row is not None,
                        "maxTransformElementError": error,
                    }
                )
            payload["reopenVerification"] = verification
            payload["reopenedComponentCount"] = len(reopened)
            operation("close-reopened-snapshot", lambda: client.call_tool_text("close_document", {"path": str(assembly_path)}))

        source_hashes_after = {str(path): sha256(path) for path in source_paths}
        payload["sourceFilesUnchanged"] = source_hashes_after == source_hashes_before
        payload["maximumReopenTransformElementError"] = max(
            row["maxTransformElementError"] for row in payload["reopenVerification"]
        )
        passed = (
            assembly_path.is_file()
            and payload["reopenedComponentCount"] == len(components)
            and payload["maximumReopenTransformElementError"] <= 1e-8
            and payload["sourceFilesUnchanged"]
        )
        payload["status"] = (
            "PASSED_PROJECT03_AD20_INTERMEDIATE_STATIC_SNAPSHOT"
            if passed
            else "FAILED_PROJECT03_AD20_INTERMEDIATE_STATIC_SNAPSHOT"
        )
        if not passed:
            payload["blockers"].append("Static snapshot persistence or source-integrity gate failed.")
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
        payload["blockers"].append("Snapshot construction did not reach a durable reopen-verification result.")
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        atomic_write(manifest_path, payload)

    print(manifest_path)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
