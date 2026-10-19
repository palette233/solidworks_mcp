from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.resolved_pair_transaction_chain import (
    ResolvedPairTransactionChainError,
    audit_resolved_pair_transaction_chain,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit(store, token, context, source, output, previous=None):
    output.write_bytes(f"output-{token}".encode())
    evidence = output.with_suffix(".result.json")
    evidence.write_text(
        json.dumps(
            {
                "success": True,
                "sourceAssemblyUnchanged": True,
                "outputClosedAfterVerification": True,
                "outputAssemblySha256": _sha(output),
            }
        ),
        encoding="utf-8",
    )
    plan = {
        "projectId": "project02",
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": _sha(source),
        "contextModuleToken": context,
        "targetModuleToken": token,
        "steps": [{"stepId": f"step-{token}", "moduleToken": token}],
    }
    if previous:
        previous_checkpoint = previous["lastCommittedCheckpoint"]
        plan["seedCheckpoint"] = {
            "seedJobId": previous["jobId"],
            "seedEvidenceSha256": _sha(Path(previous_checkpoint["evidencePath"])),
        }
    job = store.create(plan, execution_mode="independent_context_insert")
    job["status"] = "succeeded"
    job["collisionStatus"] = "not_evaluated"
    job["executionDurationSeconds"] = 1.0
    job["lastCommittedCheckpoint"] = {
        "moduleToken": token,
        "assemblyPath": str(output),
        "evidencePath": str(evidence),
    }
    store.save(job)
    return job


def test_complete_chain_audit_preserves_duplicate_instances(monkeypatch, tmp_path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    base = tmp_path / "base.SLDASM"
    base.write_bytes(b"base")
    first_output = tmp_path / "first.SLDASM"
    first = _commit(store, "A800", "A600", base, first_output)
    second_output = tmp_path / "second.SLDASM"
    second = _commit(store, "T401", "A600", first_output, second_output, first)
    third_output = tmp_path / "third.SLDASM"
    third = _commit(store, "T401", "A200", second_output, third_output, second)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_chain.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_chain._expected_sequence",
        lambda project_id: ["A800", "T401", "T401"],
    )

    result = audit_resolved_pair_transaction_chain(
        tmp_path, "project02", third["jobId"]
    )

    assert result["integrityPassed"] is True
    assert result["assembledInstanceCount"] == 4
    assert result["insertedModuleSequence"] == ["A800", "T401", "T401"]
    assert result["releaseBoundary"]["collisionGate"] == "not_evaluated"


def test_chain_audit_rejects_broken_seed_link(monkeypatch, tmp_path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    base = tmp_path / "base.SLDASM"
    base.write_bytes(b"base")
    output = tmp_path / "output.SLDASM"
    job = _commit(store, "A800", "A600", base, output)
    job["plan"]["seedCheckpoint"] = {
        "seedJobId": "project02-job-does-not-exist"
    }
    store.save(job)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_chain.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    with pytest.raises(ResolvedPairTransactionChainError, match="不存在的作业"):
        audit_resolved_pair_transaction_chain(tmp_path, "project02", job["jobId"])
