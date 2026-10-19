#!/usr/bin/env python3
"""Export, compile, and execute one real module-pair mate transaction atomically."""

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
for search in (ROOT / "scripts", ROOT / "apps/demo-backend/src"):
    if str(search) not in sys.path:
        sys.path.insert(0, str(search))

from build_pair_multi_mate_transaction import build_pair_transaction
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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pick(payload: dict, pascal: str, default=None):
    return payload.get(pascal, payload.get(pascal[0].lower() + pascal[1:], default))


def run_pipeline(args: argparse.Namespace, client_factory=McpClient) -> dict:
    source = args.source.resolve()
    output = args.output.resolve()
    result_path = (args.result or output.with_suffix(".resolved-session.result.json")).resolve()
    work_dir = args.work_dir.resolve()
    executable = args.exe.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if source.suffix.lower() != ".sldasm" or output.suffix.lower() != ".sldasm":
        raise ValueError("source and output must be .SLDASM files")
    if args.target.strip().upper() == args.context.strip().upper():
        raise ValueError("target and context must be different module tokens")
    guarded = [output, result_path]
    if any(path.exists() for path in guarded):
        raise FileExistsError("Refusing to overwrite output or result evidence.")

    artifacts = {
        "sourceGraph": work_dir / "source-graph.json",
        "sourceSubset": work_dir / "source-subset.json",
        "patch": work_dir / "patch.json",
        "effectiveGraph": work_dir / "effective-graph.json",
        "preflight": work_dir / "preflight.json",
        "manifest": work_dir / "manifest.json",
    }
    existing = [path for path in artifacts.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite transaction artifacts: {existing}")
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    source_sha_before = sha256_file(source)
    staging = output.with_name(f".{output.stem}.staging-{uuid.uuid4().hex[:12]}{output.suffix}")
    started_at = utc_now()
    started = time.perf_counter()
    phase_started = started
    phase_durations: dict[str, float] = {}
    stage = "export_graph"
    graph: dict = {}
    preflight: dict = {}
    tool_result: dict = {}
    execution_error: str | None = None

    def finish_phase(name: str) -> None:
        nonlocal phase_started
        now = time.perf_counter()
        phase_durations[name] = now - phase_started
        phase_started = now

    print(json.dumps({
        "event": "resolved-session-pair-transaction-start",
        "source": str(source),
        "target": args.target.upper(),
        "context": args.context.upper(),
        "output": str(output),
        "startedAtUtc": started_at,
    }, ensure_ascii=False), flush=True)

    try:
        with client_factory(
            executable,
            "ResolvedSessionPairTransaction",
            args.timeout,
            "newline" if args.direct_stdio else "content-length",
            direct_stdio=args.direct_stdio,
        ) as client:
            graph = client.call_tool(
                "ExportModuleMateGraph",
                {
                    "sourceAssemblyPath": str(source),
                    "moduleTokens": [args.target.upper(), args.context.upper()],
                    "outputPath": str(artifacts["sourceGraph"]),
                    "saveJson": True,
                },
            )
            finish_phase("export-graph-and-resolve-endpoints")

            stage = "compile_transaction"
            subset, patch, effective, preflight = build_pair_transaction(
                graph,
                target_module_token=args.target,
                context_module_token=args.context,
            )
            for key, payload in (
                ("sourceSubset", subset),
                ("patch", patch),
                ("effectiveGraph", effective),
                ("preflight", preflight),
            ):
                write_json(artifacts[key], payload)
            manifest = {
                "schemaVersion": "resolved-session-pair-transaction/v1",
                "status": "ready_for_same_session_cad_execution",
                "sourceAssemblyPath": str(source),
                "sourceAssemblySha256": source_sha_before,
                "targetModuleToken": args.target.upper(),
                "contextModuleToken": args.context.upper(),
                "mateCount": len(effective.get("Mates") or []),
                "artifacts": {
                    key: {"path": str(path), "sha256": sha256_file(path)}
                    for key, path in artifacts.items()
                    if key != "manifest"
                },
            }
            write_json(artifacts["manifest"], manifest)
            finish_phase("compile-and-preflight-transaction")

            stage = "cad_execution"
            try:
                tool_result = client.call_tool(
                    "RemateComponentInAssemblyContextFromMateGraph",
                    {
                        "sourceAssemblyPath": str(source),
                        "effectiveMateGraphPath": str(artifacts["effectiveGraph"]),
                        "outputAssemblyPath": str(staging),
                        "targetModuleToken": args.target.upper(),
                        "preserveResolvedSourceSession": True,
                    },
                )
            finally:
                if staging.exists():
                    try:
                        client.call_tool_text("CloseDocument", {"path": str(staging)})
                    except Exception:
                        pass
            finish_phase("same-session-cad-execution")
    except Exception as exc:
        execution_error = f"{stage}: {exc}"
        finish_phase(f"failed-{stage}")

    try:
        source_sha_after = sha256_file(source)
    except OSError:
        source_sha_after = None
    source_unchanged = source_sha_after == source_sha_before
    success = (
        execution_error is None
        and preflight.get("publishAllowed") is True
        and bool(pick(tool_result, "Success", False))
        and pick(tool_result, "ExecutionMode") == "direct_existing_component_mate_edit"
        and pick(tool_result, "TargetComponentReinserted", True) is False
        and pick(tool_result, "TargetComponentExplicitlyDisplaced", True) is False
        and staging.is_file()
        and source_unchanged
    )
    published = False
    failed_artifact = None
    if success:
        staging.replace(output)
        published = True
    elif staging.exists():
        failed_dir = output.parent / "_failed_transactions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_artifact = failed_dir / f"{output.stem}-{uuid.uuid4().hex[:12]}{output.suffix}"
        staging.replace(failed_artifact)

    phase_durations["total"] = time.perf_counter() - started
    envelope = {
        "schemaVersion": "resolved-session-pair-transaction-run/v1",
        "success": success,
        "published": published,
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now(),
        "phaseDurationsSeconds": phase_durations,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256Before": source_sha_before,
        "sourceAssemblySha256After": source_sha_after,
        "sourceAssemblyUnchanged": source_unchanged,
        "targetModuleToken": args.target.upper(),
        "contextModuleToken": args.context.upper(),
        "workDirectory": str(work_dir),
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if published else None,
        "failedArtifactPath": str(failed_artifact) if failed_artifact else None,
        "executionError": execution_error,
        "preflight": preflight,
        "toolResult": tool_result,
        "collisionStatus": "not_evaluated",
    }
    write_json(result_path, envelope)
    print(json.dumps({
        "event": "resolved-session-pair-transaction-finish",
        "success": success,
        "published": published,
        "durationSeconds": phase_durations["total"],
        "output": str(output),
        "result": str(result_path),
        "executionError": execution_error,
    }, ensure_ascii=False), flush=True)
    return envelope


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--direct-stdio", action="store_true")
    return parser.parse_args()


def main() -> int:
    result = run_pipeline(parse_args())
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
