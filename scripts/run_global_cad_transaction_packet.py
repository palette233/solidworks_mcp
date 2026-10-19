from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from demo_backend.global_cad_packet_executor import (  # noqa: E402
    build_global_cad_packet_execution_plan,
    sha256_file,
)
from demo_backend.global_cad_base_context_cache import (  # noqa: E402
    lookup_base_context_cache,
    publish_base_context_cache,
)
from capture_assembly_entity_annotations import McpClient  # noqa: E402
from create_global_cad_base_wrapper import (  # noqa: E402
    DEFAULT_EXE,
    document_path,
    normalized_document_path,
    restore_open_document_baseline,
)


def capture_open_document_baseline(*, timeout: float = 1800.0) -> dict:
    """Capture the caller-owned SolidWorks session before a packet mutates CAD state."""

    with McpClient(
        DEFAULT_EXE,
        "GlobalCadPacketBaseline",
        timeout,
        "newline",
        direct_stdio=True,
    ) as client:
        client.call_tool("solid_works_connect", {})
        documents = client.call_tool("ListDocuments", {})
    rows = documents if isinstance(documents, list) else []
    paths = sorted(
        {
            normalized_document_path(document_path(row))
            for row in rows
            if document_path(row)
        }
    )
    return {"paths": paths, "openDocumentCount": len(paths)}


def restore_packet_document_baseline(
    baseline: dict,
    *,
    timeout: float = 120.0,
) -> dict:
    """Close packet-owned documents while preserving documents open before the run."""

    try:
        with McpClient(
            DEFAULT_EXE,
            "GlobalCadPacketCleanup",
            timeout,
            "newline",
            direct_stdio=True,
        ) as client:
            client.call_tool("solid_works_connect", {})
            result = restore_open_document_baseline(
                client,
                set(baseline.get("paths") or []),
            )
        return {
            "baselineOpenDocumentCount": int(
                baseline.get("openDocumentCount") or 0
            ),
            "closedDocumentPaths": result.get("closedPaths") or [],
            "errors": result.get("errors") or [],
            "sessionRestoredToBaseline": result.get("sessionRestored") is True,
        }
    except Exception as exc:
        return {
            "baselineOpenDocumentCount": int(
                baseline.get("openDocumentCount") or 0
            ),
            "closedDocumentPaths": [],
            "errors": [{"stage": "packet_cleanup", "error": str(exc)}],
            "sessionRestoredToBaseline": False,
        }


def adapter_self_cleanup_result(cad_result: dict, baseline: dict) -> dict | None:
    """Accept explicit adapter cleanup evidence without a second MCP session.

    The insert adapter already closes and reopens the output for verification,
    then restores/cleans the independently opened target source.  Starting a
    second MCP process solely to rediscover the same document state can hang on
    large assemblies.  Reuse the adapter evidence when both invariants are
    explicit; otherwise fall back to the independent baseline restoration.
    """

    tool = cad_result.get("toolResult") or {}
    if not (
        cad_result.get("success") is True
        and cad_result.get("outputClosedAfterVerification") is True
        and cad_result.get("targetSourceSessionClean") is True
        and tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True
    ):
        return None
    return {
        "baselineOpenDocumentCount": int(baseline.get("openDocumentCount") or 0),
        "closedDocumentPaths": [],
        "errors": [],
        "sessionRestoredToBaseline": True,
        "cleanupMode": "adapter_self_cleanup_evidence",
        "evidence": {
            "outputClosedAfterVerification": True,
            "targetSourceSessionClean": True,
            "reopenedMateParametersMatch": True,
        },
    }


def build_adapter_command(
    plan: dict,
    *,
    execution_source: Path,
    execution_source_sha256: str,
    execution_graph: Path,
    execution_graph_sha256: str,
    result_path: Path,
) -> list[str]:
    strategy = plan.get("executionStrategy") or "incremental_component_insert"
    adapter_by_strategy = {
        "incremental_component_insert": "run_context_mate_graph_insert.py",
        "calibrated_static_snapshot_insert": "run_context_mate_graph_insert.py",
        "direct_existing_component_mate_edit": "run_context_direct_mate_edit.py",
        "read_only_existing_relation_verification": "run_context_relation_verify.py",
    }
    adapter = adapter_by_strategy.get(strategy)
    if adapter is None:
        raise RuntimeError(f"不支持的CAD事务执行策略：{strategy}")
    command = [
        sys.executable,
        str(ROOT / "scripts" / adapter),
        "--source",
        str(execution_source),
        "--effective",
        str(execution_graph),
        "--output",
        plan["outputAssemblyPath"],
        "--expected-source-sha256",
        execution_source_sha256,
        "--expected-effective-sha256",
        execution_graph_sha256,
        "--result",
        str(result_path),
        "--direct-stdio",
    ]
    command.extend(["--target", plan["targetModuleToken"]])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or execute one project-independent CAD transaction packet."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("packet_id")
    parser.add_argument("--input-checkpoint", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir
        else ROOT
        / "demo"
        / "global_assembly_contexts"
        / "generic_packet_runs"
        / f"{manifest.get('contextId')}-{args.packet_id}-{stamp}"
    )
    if run_dir.exists():
        raise FileExistsError(f"拒绝复用事务目录：{run_dir}")
    run_dir.mkdir(parents=True)
    output = (
        args.output.resolve()
        if args.output
        else run_dir / f"{manifest.get('contextId')}-{args.packet_id}.SLDASM"
    )
    plan = build_global_cad_packet_execution_plan(
        ROOT,
        manifest,
        args.packet_id,
        output_path=output,
        input_checkpoint=args.input_checkpoint,
    )
    plan_path = run_dir / "execution-plan.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.plan_only:
        print(
            json.dumps(
                {
                    "status": "planned_not_executed",
                    "planPath": str(plan_path),
                    "planDigest": plan["planDigest"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    session_baseline = capture_open_document_baseline()

    result_path = run_dir / "cad-result.json"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    execution_source = Path(plan["sourceAssemblyPath"])
    execution_source_sha256 = plan["sourceAssemblySha256"]
    execution_graph = Path(plan["effectiveMateGraphPath"])
    execution_graph_sha256 = plan["effectiveMateGraphSha256"]
    execution_graph_view = plan.get("effectiveMateGraphExecutionView")
    if execution_graph_view:
        actual_view_digest = hashlib.sha256(
            json.dumps(
                execution_graph_view,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if actual_view_digest != plan.get("effectiveMateGraphExecutionDigest"):
            raise RuntimeError("事务执行图投影摘要不一致。")
        execution_graph = run_dir / "execution-effective-mate-graph.json"
        execution_graph.write_text(
            json.dumps(execution_graph_view, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        execution_graph_sha256 = sha256_file(execution_graph)
    preparation = plan.get("sourcePreparation") or {}
    preparation_result_path = None
    preparation_output_path = None
    preparation_completed = None
    base_wrapper_cache = {"status": "not_applicable"}
    if preparation.get("required") is True:
        if preparation.get("mode") != "wrap_root_module_as_top_level_context":
            raise RuntimeError(f"不支持的源准备方式：{preparation.get('mode')}")
        cache_root_relative = str(preparation.get("cacheRootRelativePath") or "")
        cache_descriptor = preparation.get("cacheDescriptor") or {}
        if not cache_root_relative or not cache_descriptor:
            raise RuntimeError("基座包装计划缺少内容寻址缓存描述。")
        cache_root = (ROOT / cache_root_relative).resolve()
        cache_lookup = lookup_base_context_cache(cache_root, cache_descriptor)
        base_wrapper_cache = {"lookup": cache_lookup, "status": cache_lookup["status"]}
        if cache_lookup.get("status") == "hit":
            preparation_output_path = Path(cache_lookup["assemblyPath"])
            preparation_result_path = Path(cache_lookup["evidencePath"])
            execution_source = preparation_output_path
            execution_source_sha256 = str(cache_lookup["assemblySha256"])
            base_wrapper_cache["executionDecision"] = "reuse_verified_cache"
        else:
            preparation_output_path = run_dir / "base-context-wrapper.SLDASM"
            preparation_result_path = run_dir / "base-context-wrapper.result.json"
            preparation_stdout_path = run_dir / "base-context-wrapper.stdout.log"
            preparation_stderr_path = run_dir / "base-context-wrapper.stderr.log"
            preparation_command = [
                sys.executable,
                str(ROOT / "scripts" / "create_global_cad_base_wrapper.py"),
                "--source",
                plan["sourceAssemblyPath"],
                "--output",
                str(preparation_output_path),
                "--base-token",
                str(preparation["baseContextModuleToken"]),
                "--base-transform-json",
                json.dumps(preparation["baseContextTransform"], separators=(",", ":")),
                "--expected-source-sha256",
                plan["sourceAssemblySha256"],
                "--result",
                str(preparation_result_path),
                "--direct-stdio",
            ]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(BACKEND)
            preparation_completed = subprocess.run(
                preparation_command,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2100,
                check=False,
            )
            preparation_stdout_path.write_text(
                preparation_completed.stdout, encoding="utf-8"
            )
            preparation_stderr_path.write_text(
                preparation_completed.stderr, encoding="utf-8"
            )
            preparation_result = (
                json.loads(preparation_result_path.read_text(encoding="utf-8-sig"))
                if preparation_result_path.is_file()
                else {}
            )
            if (
                preparation_completed.returncode != 0
                or preparation_result.get("success") is not True
                or not preparation_output_path.is_file()
            ):
                session_cleanup = restore_packet_document_baseline(session_baseline)
                envelope = {
                    "schemaVersion": "global-cad-packet-execution/v1",
                    "success": False,
                    "failureStage": "prepare_base_context_wrapper",
                    "planPath": str(plan_path),
                    "planDigest": plan["planDigest"],
                    "packetId": args.packet_id,
                    "packetDigest": plan["packetDigest"],
                    "relationReleaseBinding": plan.get("relationReleaseBinding"),
                    "releaseAuthority": plan.get("releaseAuthority"),
                    "sourceAssemblyUnchanged": (
                        sha256_file(Path(plan["sourceAssemblyPath"]))
                        == plan["sourceAssemblySha256"]
                    ),
                    "baseWrapperResultPath": (
                        str(preparation_result_path)
                        if preparation_result_path.is_file()
                        else None
                    ),
                    "baseWrapperCache": base_wrapper_cache,
                    "outputAssemblyPath": str(output),
                    "returnCode": preparation_completed.returncode,
                    "collisionStatus": "not_evaluated",
                    "sessionCleanup": session_cleanup,
                }
                envelope_path = run_dir / "execution-envelope.json"
                envelope_path.write_text(
                    json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(
                    json.dumps(
                        {**envelope, "envelopePath": str(envelope_path)},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 2
            execution_source = preparation_output_path
            execution_source_sha256 = sha256_file(execution_source)
            base_wrapper_cache["executionDecision"] = "rebuild_wrapper"
            try:
                base_wrapper_cache["publish"] = publish_base_context_cache(
                    cache_root,
                    cache_descriptor,
                    assembly_path=preparation_output_path,
                    evidence_path=preparation_result_path,
                )
            except Exception as exc:  # 缓存是优化，不得掩盖已验证CAD结果。
                base_wrapper_cache["publish"] = {
                    "status": "error",
                    "error": str(exc),
                }

    strategy = plan.get("executionStrategy") or "incremental_component_insert"
    command = build_adapter_command(
        plan,
        execution_source=execution_source,
        execution_source_sha256=execution_source_sha256,
        execution_graph=execution_graph,
        execution_graph_sha256=execution_graph_sha256,
        result_path=result_path,
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BACKEND)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=2100,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    cad_result = (
        json.loads(result_path.read_text(encoding="utf-8-sig"))
        if result_path.is_file()
        else {}
    )
    session_cleanup = adapter_self_cleanup_result(
        cad_result, session_baseline
    ) or restore_packet_document_baseline(session_baseline)
    success = (
        completed.returncode == 0
        and cad_result.get("success") is True
        and output.is_file()
        and sha256_file(Path(plan["sourceAssemblyPath"]))
        == plan["sourceAssemblySha256"]
        and sha256_file(execution_source) == execution_source_sha256
        and session_cleanup["sessionRestoredToBaseline"] is True
        and not session_cleanup["errors"]
    )
    envelope = {
        "schemaVersion": "global-cad-packet-execution/v1",
        "success": success,
        "planPath": str(plan_path),
        "planDigest": plan["planDigest"],
        "packetId": args.packet_id,
        "packetDigest": plan["packetDigest"],
        "relationReleaseBinding": plan.get("relationReleaseBinding"),
        "releaseAuthority": plan.get("releaseAuthority"),
        "operation": plan.get("operation"),
        "executionStrategy": strategy,
        "sourceAssemblyUnchanged": (
            sha256_file(Path(plan["sourceAssemblyPath"]))
            == plan["sourceAssemblySha256"]
        ),
        "sourcePreparation": preparation,
        "baseWrapperAssemblyPath": (
            str(preparation_output_path) if preparation_output_path else None
        ),
        "baseWrapperResultPath": (
            str(preparation_result_path) if preparation_result_path else None
        ),
        "baseWrapperCache": base_wrapper_cache,
        "executionSourceAssemblyPath": str(execution_source),
        "executionSourceUnchanged": sha256_file(execution_source)
        == execution_source_sha256,
        "authoritativeEffectiveMateGraphPath": plan["effectiveMateGraphPath"],
        "authoritativeEffectiveMateGraphSha256": plan["effectiveMateGraphSha256"],
        "executionEffectiveMateGraphPath": str(execution_graph),
        "executionEffectiveMateGraphSha256": execution_graph_sha256,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": sha256_file(output) if output.is_file() else None,
        "cadResultPath": str(result_path) if result_path.is_file() else None,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "returnCode": completed.returncode,
        "collisionStatus": "not_evaluated",
        "sessionCleanup": session_cleanup,
    }
    envelope_path = run_dir / "execution-envelope.json"
    envelope_path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**envelope, "envelopePath": str(envelope_path)}, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
