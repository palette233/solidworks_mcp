#!/usr/bin/env python3
"""Build one bounded leaf-face catalog and optionally merge it into an existing catalog."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from time import perf_counter

from capture_assembly_entity_annotations import McpClient
from create_global_cad_base_wrapper import (
    document_path,
    normalized_document_path,
    restore_open_document_baseline,
)


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.face_endpoint_catalog import merge_face_endpoint_catalogs


DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan faces from one unique leaf component without traversing sibling leaves."
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--leaf", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-catalog", type=Path)
    parser.add_argument("--merged-output", type=Path)
    parser.add_argument("--minimum-face-area", type=float, default=1e-8)
    parser.add_argument("--maximum-face-count", type=int, default=500)
    parser.add_argument("--include-nonplanar", action="store_true")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    return run(args)


def run(args) -> int:
    """Keep scan semantics unchanged; write separate timing even on failure."""
    output = args.output.resolve()
    timing_path = output.with_suffix(".timing.json")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite leaf catalog: {output}")
    if timing_path.exists():
        raise FileExistsError(f"Refusing to overwrite leaf catalog timing: {timing_path}")
    merged_output = args.merged_output.resolve() if args.merged_output else None
    if merged_output and merged_output.exists():
        raise FileExistsError(f"Refusing to overwrite merged catalog: {merged_output}")
    if merged_output in {output, timing_path}:
        raise ValueError("Merged catalog must not alias the leaf catalog or timing file.")
    output.parent.mkdir(parents=True, exist_ok=True)
    clock = perf_counter()
    timing = {
        "schemaVersion": "leaf-face-catalog-timing/v1",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "finishedAtUtc": None,
        "durationSeconds": None,
        "status": "running",
        "success": False,
        "sourceAssemblyPath": str(args.source.resolve()),
        "moduleToken": args.module,
        "leafSelector": args.leaf,
        "outputPath": str(output),
        "sourceSaveRequested": False,
        "phaseDurationsSeconds": {name: None for name in ("connect", "scan", "cleanup", "merge", "clientClose")},
        "phases": {},
    }

    @contextmanager
    def phase(name):
        start = perf_counter()
        row = {"startedAtUtc": datetime.now(timezone.utc).isoformat(), "status": "running"}
        timing["phases"][name] = row
        try:
            yield
            row["status"] = "succeeded"
        except BaseException as exc:
            row.update(status="failed", errorType=type(exc).__name__, error=str(exc))
            raise
        finally:
            row["finishedAtUtc"] = datetime.now(timezone.utc).isoformat()
            row["durationSeconds"] = perf_counter() - start
            timing["phaseDurationsSeconds"][name] = row["durationSeconds"]

    # Exclusive creation reserves the sidecar before starting any MCP process.
    # A terminated process leaves a visible 'running' record, not a false pass.
    with timing_path.open("x", encoding="utf-8") as stream:
        json.dump(timing, stream, ensure_ascii=False, indent=2)
        stream.flush()
        cleanup, client, failure = None, None, None
        try:
            if bool(args.base_catalog) != bool(args.merged_output):
                raise ValueError("--base-catalog and --merged-output must be supplied together.")
            with phase("connect"):
                client = McpClient(
                    args.exe.resolve(), client_name="BuildLeafFaceEndpointCatalog",
                    request_timeout=args.timeout, framing="newline", direct_stdio=True,
                )
                client.__enter__()
                tools = {tool.get("name") for tool in client.list_tools()}
                if "build_leaf_face_endpoint_catalog" not in tools:
                    raise RuntimeError("Published MCP build is missing build_leaf_face_endpoint_catalog")
                client.call_tool("solid_works_connect", {})
                documents = client.call_tool("ListDocuments", {})
                baseline_paths = {
                    normalized_document_path(document_path(row))
                    for row in (documents if isinstance(documents, list) else [])
                    if document_path(row)
                }
            scan_error = None
            try:
                with phase("scan"):
                    result = client.call_tool(
                        "BuildLeafFaceEndpointCatalog",
                        {
                            "sourceAssemblyPath": str(args.source.resolve()),
                            "moduleToken": args.module, "leafSelector": args.leaf,
                            "outputPath": str(output), "planarOnly": not args.include_nonplanar,
                            "minimumFaceArea": args.minimum_face_area,
                            "maximumFaceCount": args.maximum_face_count, "saveJson": True,
                        },
                    )
                    if (not isinstance(result, dict) or result.get("Success") is False
                            or result.get("success") is False or not output.is_file()):
                        raise RuntimeError("Leaf-face catalog scan returned failure or no output artifact")
            except BaseException as exc:
                scan_error = exc
                raise
            finally:
                try:
                    with phase("cleanup"):
                        cleanup = restore_open_document_baseline(client, baseline_paths)
                        if cleanup.get("sessionRestored") is not True:
                            raise RuntimeError("Leaf-face scan did not restore the caller's SolidWorks document baseline: " + str(cleanup))
                except BaseException as exc:
                    timing["cleanupError"] = {"type": type(exc).__name__, "message": str(exc)}
                    if scan_error is None:
                        raise

            merged_count = None
            if args.base_catalog and merged_output:
                with phase("merge"):
                    base = json.loads(args.base_catalog.resolve().read_text(encoding="utf-8-sig"))
                    leaf_catalog = json.loads(output.read_text(encoding="utf-8-sig"))
                    merged = merge_face_endpoint_catalogs(base, leaf_catalog)
                    merged_output.parent.mkdir(parents=True, exist_ok=True)
                    with merged_output.open("x", encoding="utf-8") as merged_stream:
                        json.dump(merged, merged_stream, ensure_ascii=False, indent=2)
                        merged_stream.write("\n")
                    merged_count = merged["EndpointCount"]
            timing.update(status="succeeded", success=True)
        except BaseException as exc:
            failure = exc
            timing.update(status="failed", success=False, errorType=type(exc).__name__, error=str(exc))
            raise
        finally:
            close_error = None
            if client is not None:
                try:
                    with phase("clientClose"):
                        client.__exit__(type(failure) if failure else None, failure, failure.__traceback__ if failure else None)
                except BaseException as exc:
                    close_error = exc
                    timing["clientCloseError"] = {"type": type(exc).__name__, "message": str(exc)}
                    timing.update(status="failed", success=False)
                    if failure is None:
                        timing.update(errorType=type(exc).__name__, error=str(exc))
            timing.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(), durationSeconds=perf_counter()-clock,
                          documentBaselineCleanup=cleanup)
            try:
                stream.seek(0)
                stream.truncate()
                json.dump(timing, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
            except BaseException as exc:
                # An I/O error while recording diagnostics must not mask CAD's
                # original exception. The running sidecar still signals no pass.
                if failure is None and close_error is None:
                    raise
                print(f"Could not finalize timing sidecar: {exc}", file=sys.stderr)
            if failure is None and close_error is not None:
                raise close_error

    print(
        json.dumps(
            {
                "success": True,
                "leafCatalog": str(output),
                "leafEndpointCount": result.get("EndpointCount", result.get("endpointCount")),
                "mergedCatalog": str(merged_output) if merged_output else None,
                "mergedEndpointCount": merged_count,
                "documentBaselineCleanup": cleanup,
                "timingPath": str(timing_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
