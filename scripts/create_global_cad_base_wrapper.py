#!/usr/bin/env python3
"""Wrap one root module in a new parent assembly for generic cumulative CAD insertion."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient


DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/"
    "net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pick(payload: dict, pascal: str, default=None):
    return payload.get(pascal, payload.get(pascal[0].lower() + pascal[1:], default))


def document_path(row: dict) -> str:
    return str(row.get("Path", row.get("path", ""))).strip()


def normalized_document_path(value: str) -> str:
    return str(Path(value).resolve()).casefold() if value else ""


def restore_open_document_baseline(
    client: McpClient,
    baseline_paths: set[str],
    *,
    settle_timeout_seconds: float = 5.0,
    quiet_period_seconds: float = 0.75,
    poll_seconds: float = 0.25,
) -> dict:
    """Close only documents opened by this action and wait for COM to settle.

    SolidWorks can reopen a dependency shortly after the parent assembly has
    closed.  A single ListDocuments snapshot therefore produces false-clean
    evidence.  Require the original baseline to remain stable for a bounded
    quiet period while never touching documents that were already open.
    """

    closed_paths: list[str] = []
    errors: list[dict[str, str]] = []
    error_keys: set[tuple[str, str]] = set()
    deadline = time.monotonic() + max(settle_timeout_seconds, 0.0)
    stable_since: float | None = None
    final_paths: set[str] = set()
    while True:
        open_documents = client.call_tool("ListDocuments", {})
        open_rows = open_documents if isinstance(open_documents, list) else []
        new_rows = [
            row
            for row in open_rows
            if document_path(row)
            and normalized_document_path(document_path(row)) not in baseline_paths
        ]
        for row in sorted(
            new_rows,
            key=lambda item: int(item.get("Type", item.get("type", 0))),
            reverse=True,
        ):
            path = document_path(row)
            try:
                client.call_tool_text("CloseDocument", {"path": path})
                if path not in closed_paths:
                    closed_paths.append(path)
            except Exception as exc:
                key = (path, str(exc))
                if key not in error_keys:
                    errors.append({"path": path, "error": str(exc)})
                    error_keys.add(key)
        final_documents = client.call_tool("ListDocuments", {})
        final_rows = final_documents if isinstance(final_documents, list) else []
        final_paths = {
            normalized_document_path(document_path(row))
            for row in final_rows
            if document_path(row)
        }
        now = time.monotonic()
        if final_paths == baseline_paths:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= max(quiet_period_seconds, 0.0):
                break
        else:
            stable_since = None
        if now >= deadline:
            break
        time.sleep(max(poll_seconds, 0.01))
    return {
        "closedPaths": closed_paths,
        "errors": errors,
        "sessionRestored": final_paths == baseline_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-token", required=True)
    parser.add_argument("--base-transform-json", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--direct-stdio", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".base-wrapper.result.json")).resolve()
    executable = args.exe.resolve()
    for path in (source, executable):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() or result.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result}")
    source_sha = sha256_file(source)
    if source_sha != args.expected_source_sha256:
        raise ValueError("Root module SHA-256 changed after transaction planning.")
    try:
        base_transform = [float(value) for value in json.loads(args.base_transform_json)]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("--base-transform-json must be a JSON array of numbers.") from exc
    if len(base_transform) != 16:
        raise ValueError("--base-transform-json must contain 16 Transform2 values.")

    output.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started = time.perf_counter()
    with McpClient(
        executable,
        "GlobalCadBaseWrapper",
        args.timeout,
        "newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        client.call_tool("solid_works_connect", {})
        baseline_documents = client.call_tool("ListDocuments", {})
        baseline_rows = baseline_documents if isinstance(baseline_documents, list) else []
        baseline_paths = {
            normalized_document_path(document_path(row))
            for row in baseline_rows
            if document_path(row)
        }
        cleanup_closed_paths: list[str] = []
        cleanup_errors: list[dict[str, str]] = []
        session_restored = False
        try:
            tool_result = client.call_tool(
                "initialize_common_base_assembly",
                {
                    "components": [
                        {
                            "filePath": str(source),
                            "componentName": f"{args.base_token.upper()}-BASE-1",
                            "x": 0.0,
                            "y": 0.0,
                            "z": 0.0,
                            "bottomFaceName": "ROOT_CONTEXT_WRAPPER",
                        }
                    ],
                    "outputAssemblyPath": str(output),
                    "screenshotPath": None,
                    "includeScreenshotBase64Data": False,
                },
            )
            components = client.call_tool("list_components", {})
            rows = components if isinstance(components, list) else []
            matching_paths = [
                row
                for row in rows
                if Path(document_path(row)).resolve() == source
            ]
            if len(rows) != 1 or len(matching_paths) != 1:
                raise RuntimeError("Root context wrapper did not contain exactly one source module.")
            component_name = str(
                matching_paths[0].get("Name", matching_paths[0].get("name", ""))
            )
            transform_result = client.call_tool(
                "set_component_transform",
                {
                    "componentName": component_name,
                    "transform": base_transform,
                    "rebuild": True,
                },
            )
            client.call_tool("force_rebuild_active_document", {"topOnly": False})
            client.call_tool("save_document", {"path": str(output)})
            client.call_tool_text("CloseDocument", {"path": str(output)})
            client.call_tool("open_document", {"path": str(output)})
            reopened_components = client.call_tool("list_components", {})
            reopened_poses = client.call_tool(
                "list_component_poses", {"topLevelOnly": True}
            )
            output_closed = False
            close_error = None
            try:
                client.call_tool_text("CloseDocument", {"path": str(output)})
                output_closed = True
            except Exception as exc:
                close_error = str(exc)
        finally:
            cleanup = restore_open_document_baseline(client, baseline_paths)
            cleanup_closed_paths = cleanup["closedPaths"]
            cleanup_errors = cleanup["errors"]
            session_restored = cleanup["sessionRestored"]

    source_sha_after = sha256_file(source)
    reopened_rows = reopened_components if isinstance(reopened_components, list) else []
    pose_rows = reopened_poses if isinstance(reopened_poses, list) else []
    pose = next(
        (
            row
            for row in pose_rows
            if str(row.get("Name", row.get("name", ""))) == component_name
        ),
        None,
    )
    expected_pose_values = [
        *base_transform[0:3],
        *base_transform[3:6],
        *base_transform[6:9],
        *base_transform[9:12],
    ]
    actual_pose_values = (
        [
            *pose.get("XAxis", pose.get("xAxis", [])),
            *pose.get("YAxis", pose.get("yAxis", [])),
            *pose.get("ZAxis", pose.get("zAxis", [])),
            *pose.get("Translation", pose.get("translation", [])),
        ]
        if pose
        else []
    )
    pose_maximum_error = (
        max(
            abs(float(actual) - expected)
            for actual, expected in zip(
                actual_pose_values, expected_pose_values, strict=True
            )
        )
        if len(actual_pose_values) == len(expected_pose_values)
        else None
    )
    success = (
        bool(pick(tool_result, "Success", False))
        and output.is_file()
        and source_sha_after == source_sha
        and output_closed
        and session_restored
        and not cleanup_errors
        and len(reopened_rows) == 1
        and pose_maximum_error is not None
        and pose_maximum_error <= 1e-9
    )
    envelope = {
        "schemaVersion": "global-cad-base-wrapper-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now(),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "baseContextModuleToken": args.base_token.upper(),
        "baseContextTransform": base_transform,
        "sourceModulePath": str(source),
        "sourceModuleSha256Before": source_sha,
        "sourceModuleSha256After": source_sha_after,
        "sourceModuleUnchanged": source_sha_after == source_sha,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if output.is_file() else None,
        "topLevelComponentCount": len(reopened_rows),
        "topLevelComponents": reopened_rows,
        "sourcePathMatchCount": len(matching_paths),
        "reopenedPose": pose,
        "poseMaximumElementError": pose_maximum_error,
        "transformResult": transform_result,
        "outputClosedAfterVerification": output_closed,
        "closeError": close_error,
        "sessionRestoredToBaseline": session_restored,
        "baselineOpenDocumentCount": len(baseline_rows),
        "cleanupClosedDocumentPaths": cleanup_closed_paths,
        "cleanupErrors": cleanup_errors,
        "toolResult": tool_result,
        "collisionStatus": "not_evaluated",
    }
    result.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
