#!/usr/bin/env python3
"""Measure an existing semantic relation without changing assembly mates."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import shutil


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
    args = parser.parse_args()

    source = args.source.resolve()
    effective = args.effective.resolve()
    output = args.output.resolve()
    result = (args.result or output.with_suffix(".relation-verify.result.json")).resolve()
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

    graph = json.loads(effective.read_text(encoding="utf-8-sig"))
    audit = graph.get("SemanticAssemblyPlanAudit") or {}
    relations = audit.get("ValidationRelations") or audit.get("validationRelations") or []
    if not relations:
        raise ValueError("Read-only relation verification requires ValidationRelations.")
    patch = graph.get("PatchAudit") or {}
    if list(patch.get("operations") or patch.get("Operations") or []):
        raise ValueError("Read-only relation verification refuses mutating PatchAudit operations.")
    if list(graph.get("Mates") or graph.get("mates") or []):
        raise ValueError("Read-only relation verification refuses active driving mates.")

    started_at = utc_now()
    started = time.perf_counter()
    tool_result: dict = {}
    execution_error = None
    with McpClient(
        executable,
        "ContextRelationVerify",
        args.timeout,
        "newline",
        direct_stdio=args.direct_stdio,
    ) as client:
        try:
            tool_result = client.call_tool(
                "VerifyRelationsInAssemblyContextFromMateGraph",
                {
                    "sourceAssemblyPath": str(source),
                    "effectiveMateGraphPath": str(effective),
                    "targetModuleToken": args.target,
                    "preserveResolvedSourceSession": False,
                },
            )
        except Exception as exc:
            execution_error = str(exc)

    validation_results = list(pick(tool_result, "ValidationResults", []) or [])
    duration = time.perf_counter() - started
    source_sha_after = sha256_file(source)
    direct_mode = (
        pick(tool_result, "ExecutionMode")
        == "read_only_existing_relation_verification"
    )
    no_mate_mutation = direct_mode
    success = bool(
        execution_error is None
        and pick(tool_result, "Success", False)
        and direct_mode
        and no_mate_mutation
        and len(validation_results) == len(relations)
        and all(bool(pick(row, "Passed", False)) for row in validation_results)
        and source_sha_after == source_sha
    )
    published = False
    if success:
        shutil.copy2(source, output)
        published = True

    envelope = {
        "schemaVersion": "context-relation-verify-run/v3",
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
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if published else None,
        "published": published,
        "failedArtifactPath": None,
        "executionError": execution_error,
        "targetModuleToken": args.target,
        "noMateMutation": no_mate_mutation,
        "checkpointPublicationMode": (
            "filesystem_copy_of_verified_source" if published else None
        ),
        "validationResults": validation_results,
        "toolResult": tool_result,
    }
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "event": "context-relation-verify-finish",
        "success": success,
        "published": published,
        "durationSeconds": duration,
        "validationRelationCount": len(relations),
        "passedCount": sum(bool(pick(row, "Passed", False)) for row in validation_results),
        "noMateMutation": no_mate_mutation,
        "sourceAssemblyUnchanged": source_sha_after == source_sha,
        "result": str(result),
        "executionError": execution_error,
    }, ensure_ascii=False), flush=True)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
