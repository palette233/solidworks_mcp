#!/usr/bin/env python3
"""Apply a mate-graph patch directly to existing components in a copied context."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "apps/demo-backend/src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from capture_assembly_entity_annotations import McpClient
from demo_backend.mate_transaction_preflight import preflight_direct_mate_transaction


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--effective", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-effective-sha256")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument("--require-closed-dof", action="store_true")
    parser.add_argument("--require-multiple-operations", action="store_true")
    parser.add_argument(
        "--preserve-resolved-source-session",
        action="store_true",
        help=(
            "Require the source assembly to already be active/resolved in SolidWorks, "
            "then Save As the staging output before editing instead of reopening a copied file."
        ),
    )
    parser.add_argument(
        "--prepare-resolved-source-session",
        action="store_true",
        help=(
            "Open the source and resolve all lightweight components in this MCP session "
            "before executing. This implies --preserve-resolved-source-session."
        ),
    )
    parser.add_argument(
        "--displace-target-before-remate",
        action="store_true",
        help=(
            "After suppressing replaced source mates, move the target to a "
            "deterministic non-source pose before rebuilding the requested mates."
        ),
    )
    args = parser.parse_args()

    source = args.source.resolve()
    effective = args.effective.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".direct-mate-edit.result.json")).resolve()
    executable = args.exe.resolve()
    for path in (source, effective, executable):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() or result.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result}")
    source_hash_verified_before = True
    try:
        source_sha = sha256_file(source)
    except OSError:
        if not args.preserve_resolved_source_session:
            raise
        # SolidWorks can hold an exclusive read lock while the source remains
        # active/resolved.  The caller's digest must have been captured before
        # opening it; publication still requires a readable matching digest after
        # Save As switches the active document to the staging path.
        source_sha = args.expected_source_sha256.lower()
        source_hash_verified_before = False
    effective_sha = sha256_file(effective)
    if source_sha != args.expected_source_sha256:
        raise ValueError("Source assembly SHA-256 changed after preview confirmation.")
    if args.expected_effective_sha256 and effective_sha != args.expected_effective_sha256:
        raise ValueError("Effective graph SHA-256 changed after preview confirmation.")

    effective_payload = json.loads(effective.read_text(encoding="utf-8"))
    preflight = preflight_direct_mate_transaction(
        effective_payload,
        args.target,
        require_closed_dof=args.require_closed_dof,
        require_multiple_operations=args.require_multiple_operations,
        reject_redundant_mutations=True,
    )
    if not preflight["publishAllowed"]:
        raise ValueError(
            "Direct mate transaction preflight blocked CAD execution: "
            + json.dumps(preflight["blockers"], ensure_ascii=False)
        )

    staging = output.with_name(
        f".{output.stem}.staging-{uuid.uuid4().hex[:12]}{output.suffix}"
    )
    started_at = utc_now()
    started = time.perf_counter()
    print(json.dumps({
        "event": "context-direct-mate-edit-start",
        "source": str(source),
        "output": str(output),
        "staging": str(staging),
        "target": args.target,
        "startedAtUtc": started_at,
    }, ensure_ascii=False), flush=True)
    tool_result: dict = {}
    session_preparation: dict = {}
    execution_error: str | None = None
    with McpClient(
        executable,
        "ContextDirectMateEdit",
        args.timeout,
        "newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        try:
            if args.prepare_resolved_source_session:
                prepare_started = time.perf_counter()
                opened = client.call_tool("open_document", {"path": str(source)})
                resolved = client.call_tool(
                    "resolve_all_lightweight_components",
                    {"warnIfNotResolved": False, "rebuild": True},
                )
                session_preparation = {
                    "requested": True,
                    "opened": opened,
                    "resolved": resolved,
                    "durationSeconds": time.perf_counter() - prepare_started,
                }
            tool_result = client.call_tool(
                "RemateComponentInAssemblyContextFromMateGraph",
                {
                    "sourceAssemblyPath": str(source),
                    "effectiveMateGraphPath": str(effective),
                    "outputAssemblyPath": str(staging),
                    "targetModuleToken": args.target,
                    "preserveResolvedSourceSession": (
                        args.preserve_resolved_source_session
                        or args.prepare_resolved_source_session
                    ),
                    "forceInitialDisplacement": args.displace_target_before_remate,
                },
            )
        except Exception as exc:
            execution_error = str(exc)
        finally:
            if staging.exists():
                try:
                    client.call_tool_text("CloseDocument", {"path": str(staging)})
                except Exception:
                    pass
    duration = time.perf_counter() - started
    try:
        source_sha_after = sha256_file(source)
    except OSError:
        source_sha_after = None
    source_unchanged = source_sha_after == source_sha
    direct_mode = pick(tool_result, "ExecutionMode") == "direct_existing_component_mate_edit"
    success = (
        execution_error is None
        and bool(pick(tool_result, "Success", False))
        and direct_mode
        and staging.is_file()
        and source_unchanged
        and pick(tool_result, "TargetComponentReinserted", True) is False
        and bool(pick(tool_result, "TargetComponentExplicitlyDisplaced", False))
        is bool(args.displace_target_before_remate)
    )
    published = False
    if success:
        staging.replace(output)
        published = True
    failed_artifact = None
    if not success and staging.exists():
        failed_dir = output.parent / "_failed_transactions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_artifact = failed_dir / f"{output.stem}-{uuid.uuid4().hex[:12]}{output.suffix}"
        staging.replace(failed_artifact)
    envelope = {
        "schemaVersion": "context-direct-mate-edit-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now(),
        "durationSeconds": duration,
        "preflight": preflight,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256Before": source_sha,
        "sourceAssemblySha256After": source_sha_after,
        "sourceHashVerifiedBeforeExecution": source_hash_verified_before,
        "sourceAssemblyUnchanged": source_unchanged,
        "effectiveGraphPath": str(effective),
        "effectiveGraphSha256": effective_sha,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if published else None,
        "published": published,
        "failedArtifactPath": str(failed_artifact) if failed_artifact else None,
        "executionError": execution_error,
        "targetModuleToken": args.target,
        "preserveResolvedSourceSession": (
            args.preserve_resolved_source_session
            or args.prepare_resolved_source_session
        ),
        "displaceTargetBeforeRemate": args.displace_target_before_remate,
        "sessionPreparation": session_preparation,
        "toolResult": tool_result,
    }
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "event": "context-direct-mate-edit-finish",
        "success": success,
        "published": published,
        "durationSeconds": duration,
        "executionMode": pick(tool_result, "ExecutionMode"),
        "preservedSourceMateNames": pick(tool_result, "PreservedSourceMateNames"),
        "createdOrReplacedMateNames": pick(tool_result, "CreatedOrReplacedMateNames"),
        "removedOrReplacedSourceMateNames": pick(tool_result, "RemovedOrReplacedSourceMateNames"),
        "parametersMatch": pick(tool_result, "ReopenedMateParametersMatch"),
        "targetFullyConstrained": pick(tool_result, "TargetFullyConstrained"),
        "sourceAssemblyUnchanged": source_unchanged,
        "result": str(result),
        "executionError": execution_error,
    }, ensure_ascii=False), flush=True)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
