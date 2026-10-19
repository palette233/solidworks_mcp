"""Integrity audit for a cumulative resolved-pair CAD transaction chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .resolved_pair_transaction_jobs import (
    ResolvedPairTransactionJobError,
    _load_source_registry,
    pair_transaction_job_store,
    sha256_file,
)
from .semantic_assembly_jobs import AssemblyJobError, utc_now


class ResolvedPairTransactionChainError(ResolvedPairTransactionJobError):
    pass


def _expected_sequence(project_id: str) -> list[str]:
    project = (_load_source_registry().get("projects") or {}).get(project_id) or {}
    return [
        str(row.get("targetModuleToken") or "").upper()
        for row in project.get("independentPairInstallations") or []
    ]


def audit_resolved_pair_transaction_chain(
    workspace: Path,
    project_id: str,
    terminal_job_id: str,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    store = pair_transaction_job_store(workspace, project_id)
    reverse_jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_id: str | None = terminal_job_id
    while current_id:
        if current_id in seen:
            raise ResolvedPairTransactionChainError("累计事务链包含循环seedJobId。")
        seen.add(current_id)
        try:
            job = store.load(current_id)
        except AssemblyJobError as exc:
            raise ResolvedPairTransactionChainError(
                f"累计事务链引用了不存在的作业：{current_id}。"
            ) from exc
        if job.get("projectId") != project_id:
            raise ResolvedPairTransactionChainError("累计事务链跨越了不同项目。")
        reverse_jobs.append(job)
        current_id = str(
            ((job.get("plan") or {}).get("seedCheckpoint") or {}).get("seedJobId")
            or ""
        ) or None

    jobs = list(reversed(reverse_jobs))
    expected = _expected_sequence(project_id)
    observed: list[str] = []
    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for index, job in enumerate(jobs, start=1):
        plan = job.get("plan") or {}
        checkpoint = job.get("lastCommittedCheckpoint") or {}
        token = str(checkpoint.get("moduleToken") or "").upper()
        if job.get("status") != "succeeded" or not checkpoint or not token:
            raise ResolvedPairTransactionChainError(
                f"作业{job.get('jobId')}没有成功提交检查点。"
            )
        assembly_path = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
        evidence_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
        if not assembly_path.is_file() or not evidence_path.is_file():
            raise ResolvedPairTransactionChainError(
                f"作业{job.get('jobId')}的实体或证据文件不存在。"
            )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        output_sha = sha256_file(assembly_path)
        if evidence.get("success") is not True or evidence.get(
            "outputAssemblySha256"
        ) != output_sha:
            raise ResolvedPairTransactionChainError(
                f"作业{job.get('jobId')}的输出摘要未通过。"
            )
        if evidence.get("sourceAssemblyUnchanged") is not True or evidence.get(
            "outputClosedAfterVerification"
        ) is not True:
            raise ResolvedPairTransactionChainError(
                f"作业{job.get('jobId')}缺少源文件不变或关闭输出证据。"
            )
        source_path = Path(str(plan.get("sourceAssemblyPath") or "")).resolve()
        if not source_path.is_file() or sha256_file(source_path) != plan.get(
            "sourceAssemblySha256"
        ):
            raise ResolvedPairTransactionChainError(
                f"作业{job.get('jobId')}的输入实体摘要未通过。"
            )
        seed = plan.get("seedCheckpoint") or {}
        if previous is None:
            if seed:
                raise ResolvedPairTransactionChainError("累计事务链首作业不应再引用种子。")
        else:
            previous_checkpoint = previous.get("lastCommittedCheckpoint") or {}
            if seed.get("seedJobId") != previous.get("jobId"):
                raise ResolvedPairTransactionChainError(
                    f"作业{job.get('jobId')}没有直接引用前一检查点。"
                )
            if source_path != Path(
                str(previous_checkpoint.get("assemblyPath") or "")
            ).resolve():
                raise ResolvedPairTransactionChainError(
                    f"作业{job.get('jobId')}的输入不是前一作业输出。"
                )
            previous_evidence = Path(
                str(previous_checkpoint.get("evidencePath") or "")
            ).resolve()
            if seed.get("seedEvidenceSha256") != sha256_file(previous_evidence):
                raise ResolvedPairTransactionChainError(
                    f"作业{job.get('jobId')}的种子证据摘要不一致。"
                )
        observed.append(token)
        rows.append(
            {
                "order": index,
                "jobId": job.get("jobId"),
                "moduleToken": token,
                "contextModuleToken": plan.get("contextModuleToken"),
                "assemblyPath": str(assembly_path),
                "assemblySha256": output_sha,
                "evidencePath": str(evidence_path),
                "executionDurationSeconds": job.get("executionDurationSeconds"),
                "collisionStatus": job.get("collisionStatus"),
            }
        )
        previous = job

    sequence_matches = observed == expected
    if require_complete and not sequence_matches:
        raise ResolvedPairTransactionChainError(
            f"累计事务链不完整：期望{expected}，实际{observed}。"
        )
    base_token = str((jobs[0].get("plan") or {}).get("contextModuleToken") or "")
    return {
        "schemaVersion": "resolved-pair-transaction-chain-audit/v1",
        "generatedAt": utc_now(),
        "projectId": project_id,
        "terminalJobId": terminal_job_id,
        "baseModuleToken": base_token,
        "insertedModuleSequence": observed,
        "expectedInsertedModuleSequence": expected,
        "sequenceMatchesRegistry": sequence_matches,
        "jobCount": len(jobs),
        "assembledInstanceCount": len(jobs) + 1,
        "integrityPassed": True,
        "jobs": rows,
        "releaseBoundary": {
            "staticAssemblyChainClosed": sequence_matches,
            "saveReopenEvidenceComplete": True,
            "collisionGate": "not_evaluated",
            "productionReady": False,
            "reason": (
                "静态累计装配及保存重开证据闭环；实体干涉、动态行程、"
                "光学工艺和维护可达性不在本轮放行范围。"
            ),
        },
    }
