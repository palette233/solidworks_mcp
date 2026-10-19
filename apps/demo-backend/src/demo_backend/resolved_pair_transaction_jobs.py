"""Durable execution bridge from a committed semantic connection to real CAD mates."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .global_assembly_workbench import (
    load_context,
    load_global_catalog,
)
from .semantic_assembly_jobs import (
    AssemblyJobError,
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
    utc_now,
)


SOURCE_REGISTRY = Path(__file__).with_name("project_profiles") / "resolved_pair_transaction_sources.json"


class ResolvedPairTransactionJobError(AssemblyJobError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_source_registry() -> dict[str, Any]:
    payload = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "resolved-pair-transaction-sources/v1":
        raise ResolvedPairTransactionJobError("真实模组对来源注册表版本不受支持。")
    return payload


def _project_aliases(module: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("projectId") or "").lower(): row
        for row in module.get("projectAliases") or []
        if row.get("projectId") and row.get("moduleToken")
    }


def _registered_path(workspace: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def _load_seed_checkpoint_source(
    workspace: Path,
    project_id: str,
    seed_job_id: str | None,
    required_module_token: str,
) -> tuple[Path, dict[str, Any]]:
    if not seed_job_id:
        raise ResolvedPairTransactionJobError(
            f"独立累计安装需要seedJobId，且其最近检查点必须是{required_module_token}。"
        )
    if not str(seed_job_id).startswith(f"{project_id}-job-"):
        raise ResolvedPairTransactionJobError("续装来源任务与当前项目不一致。")
    store = pair_transaction_job_store(workspace, project_id)
    seed_job = store.load(seed_job_id)
    checkpoint = seed_job.get("lastCommittedCheckpoint") or {}
    if seed_job.get("status") != "succeeded":
        raise ResolvedPairTransactionJobError("续装来源任务不是成功状态。")
    if str(checkpoint.get("moduleToken") or "").upper() != required_module_token.upper():
        raise ResolvedPairTransactionJobError(
            f"续装来源最近检查点必须是{required_module_token}，"
            f"实际为{checkpoint.get('moduleToken')}。"
        )
    source = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
    evidence_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
    if not source.is_file() or not evidence_path.is_file():
        raise ResolvedPairTransactionJobError("续装来源实体或执行证据不存在。")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected_sha = str(evidence.get("outputAssemblySha256") or "")
    if evidence.get("success") is not True or len(expected_sha) != 64:
        raise ResolvedPairTransactionJobError("续装来源证据未确认成功输出摘要。")
    if sha256_file(source) != expected_sha:
        raise ResolvedPairTransactionJobError("续装来源实体摘要与执行证据不一致。")
    return source, {
        "seedJobId": seed_job_id,
        "seedStepId": checkpoint.get("stepId"),
        "seedModuleToken": checkpoint.get("moduleToken"),
        "seedEvidencePath": str(evidence_path),
        "seedEvidenceSha256": sha256_file(evidence_path),
    }


def compile_connection_pair_plan(
    workspace: Path,
    context_id: str,
    connection_id: str,
    *,
    seed_job_id: str | None = None,
) -> dict[str, Any]:
    context = load_context(workspace, context_id)
    catalog = load_global_catalog(workspace)
    connection_matches = [
        row for row in context.get("connections") or []
        if str(row.get("connectionId")) == connection_id
    ]
    if len(connection_matches) != 1:
        raise ResolvedPairTransactionJobError(
            f"连接{connection_id!r}解析到{len(connection_matches)}条，要求唯一。"
        )
    connection = connection_matches[0]
    instances = {str(row["instanceId"]): row for row in context.get("instances") or []}
    definitions = {
        str(row["moduleDefinitionId"]): row
        for row in catalog.get("moduleDefinitions") or []
    }
    try:
        instance_a = instances[str(connection["instanceAId"])]
        instance_b = instances[str(connection["instanceBId"])]
        module_a = definitions[str(instance_a["moduleDefinitionId"])]
        module_b = definitions[str(instance_b["moduleDefinitionId"])]
    except KeyError as exc:
        raise ResolvedPairTransactionJobError(
            f"连接引用的实例或模组定义不存在：{exc}"
        ) from exc

    aliases_a = _project_aliases(module_a)
    aliases_b = _project_aliases(module_b)
    registry = _load_source_registry().get("projects") or {}
    shared = sorted(
        project_id for project_id in set(aliases_a) & set(aliases_b)
        if project_id in registry
    )
    enabled = [project_id for project_id in shared if registry[project_id].get("enabled") is True]
    if len(enabled) != 1:
        raise ResolvedPairTransactionJobError(
            "连接两端必须唯一归属于一个已启用真实事务的项目；"
            f"共同项目={shared}，已启用={enabled}。"
        )
    project_id = enabled[0]
    alias_a = aliases_a[project_id]
    alias_b = aliases_b[project_id]
    token_a = str(alias_a["moduleToken"]).upper()
    token_b = str(alias_b["moduleToken"]).upper()
    base_a = alias_a.get("isBaseModule") is True
    base_b = alias_b.get("isBaseModule") is True
    project_profile = registry[project_id]
    independent_matches: list[tuple[dict[str, Any], bool]] = []
    for row in project_profile.get("independentPairInstallations") or []:
        profile_target = str(row.get("targetModuleToken") or "").upper()
        profile_context = str(row.get("contextModuleToken") or "").upper()
        if profile_target == token_a and profile_context == token_b:
            independent_matches.append((row, True))
        elif profile_target == token_b and profile_context == token_a:
            independent_matches.append((row, False))
    if len(independent_matches) > 1:
        raise ResolvedPairTransactionJobError(
            f"{project_id}的{token_a}/{token_b}独立安装档案不唯一。"
        )
    independent_profile = independent_matches[0][0] if independent_matches else None
    if independent_profile is not None:
        target_is_a = independent_matches[0][1]
        target_token = token_a if target_is_a else token_b
        context_token = token_b if target_is_a else token_a
    else:
        if base_a == base_b:
            raise ResolvedPairTransactionJobError(
                f"连接{connection_id}必须恰有一端是项目基座模组，当前{token_a}/{token_b}不满足；"
                "非基座上下文连接必须先登记唯一的独立安装档案。"
            )
        target_is_a = base_b
        context_token, target_token = (
            (token_a, token_b) if base_a else (token_b, token_a)
        )
    execution_strategy = (
        "independent_context_insert"
        if independent_profile is not None
        else "resolved_source_direct_mate"
    )
    seed_binding: dict[str, Any] | None = None
    if independent_profile is not None and independent_profile.get("sourcePolicy") == "prior_pair_checkpoint":
        source, seed_binding = _load_seed_checkpoint_source(
            workspace,
            project_id,
            seed_job_id,
            str(independent_profile.get("requiredSeedModuleToken") or ""),
        )
    else:
        source = _registered_path(
            workspace,
            (
                independent_profile.get("sourceAssemblyPath")
                if independent_profile is not None
                else project_profile.get("sourceAssemblyPath")
            ),
        )
    if not source.is_file():
        raise ResolvedPairTransactionJobError(f"配合事务来源装配体不存在：{source}")
    if str(connection.get("purpose") or "installation") != "installation":
        raise ResolvedPairTransactionJobError("当前只允许把installation连接编译为真实配合事务。")

    effective_graph: Path | None = None
    if independent_profile is not None:
        effective_graph = _registered_path(
            workspace, independent_profile.get("effectiveMateGraphPath")
        )
        if not effective_graph.is_file():
            raise ResolvedPairTransactionJobError(
                f"独立安装有效配合图不存在：{effective_graph}"
            )

    plan = {
        "schemaVersion": "resolved-pair-transaction-plan/v1",
        "projectId": project_id,
        "contextId": context_id,
        "contextRevision": context["revision"],
        "contextDigest": context["contextDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "connectionId": connection_id,
        "executionStrategy": execution_strategy,
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": sha256_file(source),
        "targetInstanceId": (
            str(instance_a["instanceId"])
            if target_is_a
            else str(instance_b["instanceId"])
        ),
        "contextInstanceId": (
            str(instance_b["instanceId"])
            if target_is_a
            else str(instance_a["instanceId"])
        ),
        "targetModuleToken": target_token,
        "contextModuleToken": context_token,
        "steps": [
            {
                "stepId": f"resolved-pair-{connection_id}",
                "moduleToken": target_token,
            }
        ],
        "stepCount": 1,
        "validationProfile": "demo",
        "validationBoundary": {
            "assemblyGate": (
                "independent_insert_and_cad_save_reopen"
                if independent_profile is not None
                else "mate_preflight_and_cad_save_reopen"
            ),
            "collisionGate": "not_evaluated",
        },
        "safeToCreateDurableJob": True,
        "compiledAt": utc_now(),
    }
    if effective_graph is not None:
        constraint_requirement = str(
            independent_profile.get("constraintRequirement") or "fully_constrained"
        )
        if constraint_requirement not in {
            "fully_constrained",
            "accepted_flexible_or_fully_constrained",
        }:
            raise ResolvedPairTransactionJobError(
                f"不支持的独立安装约束要求：{constraint_requirement}"
            )
        plan["effectiveMateGraphPath"] = str(effective_graph)
        plan["effectiveMateGraphSha256"] = sha256_file(effective_graph)
        plan["constraintRequirement"] = constraint_requirement
        plan["independentInstallationEvidenceBoundary"] = str(
            independent_profile.get("evidenceBoundary") or ""
        )
    if seed_binding is not None:
        plan["seedCheckpoint"] = seed_binding
    digest_source = {key: value for key, value in plan.items() if key != "compiledAt"}
    plan["planDigest"] = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return plan


def pair_transaction_job_store(workspace: Path, project_id: str) -> DurableAssemblyJobStore:
    return DurableAssemblyJobStore(
        workspace / f"demo/semantic_ports/{project_id}_resolved_pair_jobs"
    )


def create_connection_pair_job(
    workspace: Path,
    context_id: str,
    connection_id: str,
    *,
    idempotency_key: str | None = None,
    seed_job_id: str | None = None,
) -> dict[str, Any]:
    plan = compile_connection_pair_plan(
        workspace, context_id, connection_id, seed_job_id=seed_job_id
    )
    store = pair_transaction_job_store(workspace, str(plan["projectId"]))
    execution_mode = (
        "independent_context_insert"
        if plan.get("executionStrategy") == "independent_context_insert"
        else "resolved_pair_direct_mate"
    )
    return store.create(
        plan,
        execution_mode=execution_mode,
        idempotency_key=(
            idempotency_key or f"resolved-pair:{plan['projectId']}:{plan['planDigest']}"
        ),
    )


def _pair_step_runner(workspace: Path, store: DurableAssemblyJobStore):
    def run(job: dict[str, Any], step: dict[str, Any], checkpoint: Path | None) -> dict[str, Any]:
        if checkpoint is not None:
            raise ResolvedPairTransactionJobError("真实原型模组对事务不接受累计装配检查点输入。")
        plan = job["plan"]
        source = Path(plan["sourceAssemblyPath"]).resolve()
        if sha256_file(source) != plan["sourceAssemblySha256"]:
            raise ResolvedPairTransactionJobError("原型装配体摘要在任务创建后发生变化。")
        attempt = int(step.get("attemptCount") or 1)
        attempt_dir = store._dir(str(job["jobId"])) / f"attempt-{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=False)
        target = str(plan["targetModuleToken"])
        context = str(plan["contextModuleToken"])
        output = attempt_dir / f"{job['jobId']}-{target.lower()}-{context.lower()}.SLDASM"
        result = attempt_dir / "cad-transaction.result.json"
        transaction = attempt_dir / "transaction"
        stdout_path = attempt_dir / "stdout.log"
        stderr_path = attempt_dir / "stderr.log"
        strategy = str(plan.get("executionStrategy") or "resolved_source_direct_mate")
        if strategy == "independent_context_insert":
            effective = Path(str(plan.get("effectiveMateGraphPath") or "")).resolve()
            if not effective.is_file() or sha256_file(effective) != plan.get(
                "effectiveMateGraphSha256"
            ):
                raise ResolvedPairTransactionJobError(
                    "独立安装有效配合图不存在或摘要已经变化。"
                )
            command = [
                sys.executable,
                str(workspace / "scripts/run_context_mate_graph_insert.py"),
                "--source", str(source),
                "--effective", str(effective),
                "--target", target,
                "--output", str(output),
                "--expected-source-sha256", str(plan["sourceAssemblySha256"]),
                "--expected-effective-sha256", str(plan["effectiveMateGraphSha256"]),
                "--result", str(result),
                "--direct-stdio",
                "--timeout", "1800",
            ]
        elif strategy == "resolved_source_direct_mate":
            command = [
                sys.executable,
                str(workspace / "scripts/run_resolved_session_pair_transaction.py"),
                "--source", str(source),
                "--target", target,
                "--context", context,
                "--output", str(output),
                "--work-dir", str(transaction),
                "--result", str(result),
                "--direct-stdio",
                "--timeout", "1800",
            ]
        else:
            raise ResolvedPairTransactionJobError(
                f"不支持的真实配合事务策略：{strategy}"
            )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(workspace / "apps/demo-backend/src")
        completed = subprocess.run(
            command,
            cwd=workspace,
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
        if not result.is_file():
            raise ResolvedPairTransactionJobError(
                f"单命令执行器未生成结果证据，退出码={completed.returncode}。"
            )
        evidence = json.loads(result.read_text(encoding="utf-8"))
        if completed.returncode != 0 or evidence.get("success") is not True:
            message = str(
                evidence.get("executionError")
                or f"CAD事务执行失败，退出码={completed.returncode}。"
            )
            if output.is_file():
                return {
                    "accepted": False,
                    "message": message,
                    "assemblyPath": str(output),
                    "evidencePath": str(result),
                }
            raise ResolvedPairTransactionJobError(message)
        if evidence.get("sourceAssemblyUnchanged") is not True:
            raise ResolvedPairTransactionJobError("执行证据未通过源文件不变门禁。")
        if strategy == "resolved_source_direct_mate" and evidence.get("published") is not True:
            raise ResolvedPairTransactionJobError("同会话配合事务没有正式发布。")
        if strategy == "independent_context_insert":
            tool_result = evidence.get("toolResult") or {}
            required = {
                "IndependentComponentInserted": True,
                "Reopened": True,
                "ReopenedMateParametersMatch": True,
                "ComponentSemanticsMatch": True,
                "TargetConstraintStateAccepted": True,
                "MateSolveClean": True,
            }
            if plan.get("constraintRequirement") == "fully_constrained":
                required["TargetFullyConstrained"] = True
            failed = [
                name for name, expected in required.items()
                if tool_result.get(name, tool_result.get(name[0].lower() + name[1:])) is not expected
            ]
            if failed:
                raise ResolvedPairTransactionJobError(
                    "独立安装保存重开证据不完整：" + ", ".join(failed)
                )
        if evidence.get("outputAssemblySha256") != sha256_file(output):
            raise ResolvedPairTransactionJobError("发布实体摘要与执行证据不一致。")
        cad_paths = [str(result), str(stdout_path), str(stderr_path)]
        if strategy == "resolved_source_direct_mate":
            cad_paths.insert(1, str(transaction / "manifest.json"))
        else:
            cad_paths.insert(1, str(plan["effectiveMateGraphPath"]))
        return {
            "accepted": True,
            "message": (
                "独立模组已插入累计上下文并通过保存重开门禁。"
                if strategy == "independent_context_insert"
                else "真实模组对配合事务已通过保存重开门禁。"
            ),
            "assemblyPath": str(output),
            "evidencePath": str(result),
            "cadActionEvidencePaths": cad_paths,
            "validationProfile": "demo",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "validationEvidenceKind": (
                "independent_context_insert_save_reopen"
                if strategy == "independent_context_insert"
                else "resolved_pair_transaction_save_reopen"
            ),
        }
    return run


def run_connection_pair_job(workspace: Path, project_id: str, job_id: str) -> dict[str, Any]:
    store = pair_transaction_job_store(workspace, project_id)
    return AssemblyJobExecutor(store, _pair_step_runner(workspace, store)).run(job_id)
