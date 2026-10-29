#!/usr/bin/env python3
"""Run one checkpoint-safe context insert with timestamped evidence."""

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
from create_global_cad_base_wrapper import (
    document_path,
    normalized_document_path,
    restore_open_document_baseline,
)


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


def project_target_context_graph(graph: dict, target_module_token: str) -> dict:
    """Keep only the target and modules directly used by its driving mates."""

    module_key = "Modules" if "Modules" in graph else "modules"
    mate_key = "Mates" if "Mates" in graph else "mates"
    target = target_module_token.strip().upper()
    projected_mates = []
    execution_tokens = {target}
    for mate in graph.get(mate_key) or []:
        tokens = {
            str(value).strip().upper()
            for value in mate.get("ModuleTokens") or mate.get("moduleTokens") or []
            if str(value).strip()
        }
        suppressed = bool(mate.get("IsSuppressed", mate.get("isSuppressed", False)))
        if target in tokens and not suppressed:
            projected_mates.append(mate)
            execution_tokens.update(tokens)
    if not projected_mates:
        raise ValueError(f"No active driving mates found for target {target!r}.")
    projected_modules = [
        module
        for module in graph.get(module_key) or []
        if str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        in execution_tokens
    ]
    observed_tokens = {
        str(module.get("ModuleToken") or module.get("moduleToken") or "")
        .strip()
        .upper()
        for module in projected_modules
    }
    if observed_tokens != execution_tokens:
        raise ValueError(
            "Target execution projection is missing module records: "
            + ", ".join(sorted(execution_tokens - observed_tokens))
        )
    projected = json.loads(json.dumps(graph))
    projected[module_key] = projected_modules
    projected[mate_key] = projected_mates
    if "ModuleCount" in projected:
        projected["ModuleCount"] = len(projected_modules)
    if "moduleCount" in projected:
        projected["moduleCount"] = len(projected_modules)
    if "InterModuleMateCount" in projected:
        projected["InterModuleMateCount"] = len(projected_mates)
    if "interModuleMateCount" in projected:
        projected["interModuleMateCount"] = len(projected_mates)
    projected["CheckpointExecutionProjection"] = {
        "targetModuleToken": target,
        "moduleTokens": sorted(execution_tokens),
        "mateNames": sorted(
            str(mate.get("MateName") or mate.get("mateName") or "")
            for mate in projected_mates
        ),
        "reason": (
            "Only the target and its direct driving context are retained so "
            "unrelated prototype modules are not required in a cumulative checkpoint."
        ),
    }
    return projected


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
    parser.add_argument("--project-target-context", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    effective = args.effective.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".context-insert.result.json")).resolve()
    executable = args.exe.resolve()
    for path in (source, effective, executable):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() or result.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result}")
    source_sha = sha256_file(source)
    effective_sha = sha256_file(effective)
    if source_sha != args.expected_source_sha256:
        raise ValueError("Source assembly SHA-256 changed after preview confirmation.")
    if args.expected_effective_sha256 and effective_sha != args.expected_effective_sha256:
        raise ValueError("Effective graph SHA-256 changed after preview confirmation.")

    execution_effective = effective
    execution_effective_sha = effective_sha
    if args.project_target_context:
        graph = json.loads(effective.read_text(encoding="utf-8-sig"))
        projected = project_target_context_graph(graph, args.target)
        output.parent.mkdir(parents=True, exist_ok=True)
        execution_effective = output.with_suffix(".execution-graph.json")
        if execution_effective.exists():
            raise FileExistsError(f"Refusing to overwrite: {execution_effective}")
        execution_effective.write_text(
            json.dumps(projected, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        execution_effective_sha = sha256_file(execution_effective)

    started_at = utc_now()
    started = time.perf_counter()
    print(
        json.dumps(
            {
                "event": "context-insert-start",
                "source": str(source),
                "output": str(output),
                "target": args.target,
                "startedAtUtc": started_at,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    with McpClient(
        executable,
        "CheckpointSelectedFaceContextInsert",
        args.timeout,
        "newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        before_documents = client.call_tool("ListDocuments", {})
        before_paths = {
            normalized_document_path(document_path(item))
            for item in (before_documents or [])
            if isinstance(item, dict) and document_path(item)
        }
        tool_result = client.call_tool(
            "InsertComponentInAssemblyContextFromMateGraph",
            {
                "sourceAssemblyPath": str(source),
                "effectiveMateGraphPath": str(execution_effective),
                "outputAssemblyPath": str(output),
                "targetModuleToken": args.target,
            },
        )
        output_closed = False
        close_error = None
        try:
            client.call_tool_text("CloseDocument", {"path": str(output)})
            output_closed = True
        except Exception as exc:
            close_error = str(exc)
        target_source_path = str(pick(tool_result, "TargetModuleSourcePath", ""))
        target_source_was_already_open = bool(
            target_source_path
            and normalized_document_path(target_source_path) in before_paths
        )
        target_source_closed_after_verification = False
        target_source_close_error = None
        if target_source_path and not target_source_was_already_open:
            try:
                client.call_tool_text("CloseDocument", {"path": target_source_path})
                target_source_closed_after_verification = True
            except Exception as exc:
                target_source_close_error = str(exc)
        target_source_session_clean = (
            target_source_was_already_open or target_source_closed_after_verification
        )
        document_cleanup = restore_open_document_baseline(client, before_paths)
        target_source_session_clean = bool(
            target_source_session_clean and document_cleanup.get("sessionRestored") is True
        )
    duration = time.perf_counter() - started
    source_sha_after = sha256_file(source)
    success = (
        bool(pick(tool_result, "Success", False))
        and output.is_file()
        and source_sha_after == source_sha
        and output_closed
        and target_source_session_clean
    )
    envelope = {
        "schemaVersion": "checkpoint-selected-face-context-insert-run/v1",
        "success": success,
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now(),
        "durationSeconds": duration,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256Before": source_sha,
        "sourceAssemblySha256After": source_sha_after,
        "sourceAssemblyUnchanged": source_sha_after == source_sha,
        "effectiveGraphPath": str(effective),
        "effectiveGraphSha256": effective_sha,
        "executionEffectiveGraphPath": str(execution_effective),
        "executionEffectiveGraphSha256": execution_effective_sha,
        "targetContextProjected": bool(args.project_target_context),
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if output.is_file() else None,
        "targetModuleToken": args.target,
        "outputClosedAfterVerification": output_closed,
        "closeError": close_error,
        "targetSourceWasAlreadyOpen": target_source_was_already_open,
        "targetSourceClosedAfterVerification": target_source_closed_after_verification,
        "targetSourceSessionClean": target_source_session_clean,
        "targetSourceCloseError": target_source_close_error,
        "documentBaselineCleanup": document_cleanup,
        "toolResult": tool_result,
    }
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "event": "context-insert-finish",
                "success": success,
                "durationSeconds": duration,
                "createdMateCount": pick(tool_result, "CreatedMateCount"),
                "parametersMatch": pick(tool_result, "ReopenedMateParametersMatch"),
                "targetCaseAnchored": pick(tool_result, "TargetCaseAnchored"),
                "caseAnchorPoseMatch": pick(tool_result, "CaseAnchorPoseMatch"),
                "targetConstraintStateAccepted": pick(
                    tool_result, "TargetConstraintStateAccepted"
                ),
                "mateSolveClean": pick(tool_result, "MateSolveClean"),
                "sourceAssemblyUnchanged": source_sha_after == source_sha,
                "outputClosedAfterVerification": output_closed,
                "targetSourceClosedAfterVerification": target_source_closed_after_verification,
                "targetSourceSessionClean": target_source_session_clean,
                "result": str(result),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
