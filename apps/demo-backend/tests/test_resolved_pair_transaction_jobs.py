from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import BackgroundTasks, HTTPException
import pytest

from demo_backend import main as main_api
from demo_backend.models import (
    ResolvedPairTransactionJobCreateRequest,
    ResolvedPairTransactionJobStartRequest,
)
from demo_backend.resolved_pair_transaction_jobs import (
    ResolvedPairTransactionJobError,
    _pair_step_runner,
    compile_connection_pair_plan,
    create_connection_pair_job,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


WORKSPACE = Path(__file__).resolve().parents[3]
CONTEXT_INSERT_SCRIPT = WORKSPACE / "scripts/run_context_mate_graph_insert.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(source: Path) -> dict:
    return {
        "schemaVersion": "resolved-pair-transaction-plan/v1",
        "projectId": "project05",
        "contextId": "test-context",
        "contextDigest": "a" * 64,
        "connectionId": "connection-001",
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": _sha256(source),
        "targetModuleToken": "D000",
        "contextModuleToken": "A000",
        "steps": [{"stepId": "resolved-pair-connection-001", "moduleToken": "D000"}],
        "stepCount": 1,
        "validationProfile": "demo",
        "validationBoundary": {
            "assemblyGate": "mate_preflight_and_cad_save_reopen",
            "collisionGate": "not_evaluated",
        },
    }


def test_project05_committed_connection_compiles_to_unique_real_pair():
    plan = compile_connection_pair_plan(
        WORKSPACE, "project05-full-static-graph-v1", "connection-001"
    )

    assert plan["projectId"] == "project05"
    assert plan["targetModuleToken"] == "D000"
    assert plan["contextModuleToken"] == "A000"
    assert plan["stepCount"] == 1
    assert len(plan["planDigest"]) == 64
    assert plan["validationBoundary"]["collisionGate"] == "not_evaluated"


def test_project02_a600_a800_compiles_to_independent_incremental_insert():
    plan = compile_connection_pair_plan(
        WORKSPACE, "project02-full-static-graph-v1", "connection-001"
    )

    assert plan["projectId"] == "project02"
    assert plan["targetModuleToken"] == "A800"
    assert plan["contextModuleToken"] == "A600"
    assert plan["executionStrategy"] == "independent_context_insert"
    assert Path(plan["sourceAssemblyPath"]).name == "step00_A600_base_V3.SLDASM"
    assert Path(plan["effectiveMateGraphPath"]).name == "assembly_plan_effective.json"
    assert len(plan["effectiveMateGraphSha256"]) == 64
    assert plan["constraintRequirement"] == "fully_constrained"
    assert plan["validationBoundary"]["collisionGate"] == "not_evaluated"


def test_project02_a180_requires_attested_a800_seed(monkeypatch, tmp_path):
    seed_output = tmp_path / "a600-plus-a800.SLDASM"
    seed_output.write_bytes(b"attested-a600-plus-a800")
    seed_evidence = tmp_path / "a800.result.json"
    seed_evidence.write_text(
        json.dumps(
            {
                "success": True,
                "outputAssemblySha256": _sha256(seed_output),
            }
        ),
        encoding="utf-8",
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    seed_plan = {
        **_plan(seed_output),
        "projectId": "project02",
        "targetModuleToken": "A800",
        "contextModuleToken": "A600",
        "steps": [
            {
                "stepId": "resolved-pair-connection-001",
                "moduleToken": "A800",
            }
        ],
    }
    seed_job = store.create(seed_plan, execution_mode="independent_context_insert")
    seed_job["status"] = "succeeded"
    seed_job["lastCommittedCheckpoint"] = {
        "stepId": "resolved-pair-connection-001",
        "moduleToken": "A800",
        "assemblyPath": str(seed_output),
        "evidencePath": str(seed_evidence),
    }
    store.save(seed_job)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    plan = compile_connection_pair_plan(
        WORKSPACE,
        "project02-full-static-graph-v1",
        "connection-002",
        seed_job_id=seed_job["jobId"],
    )

    assert plan["targetModuleToken"] == "A180"
    assert plan["contextModuleToken"] == "A600"
    assert plan["executionStrategy"] == "independent_context_insert"
    assert Path(plan["sourceAssemblyPath"]) == seed_output
    assert plan["seedCheckpoint"]["seedJobId"] == seed_job["jobId"]
    assert plan["seedCheckpoint"]["seedModuleToken"] == "A800"
    assert len(plan["seedCheckpoint"]["seedEvidenceSha256"]) == 64


def test_project02_a180_fails_closed_without_a800_seed():
    with pytest.raises(ResolvedPairTransactionJobError, match="seedJobId"):
        compile_connection_pair_plan(
            WORKSPACE, "project02-full-static-graph-v1", "connection-002"
        )


def test_project02_a700_compiles_with_flexible_constraint_policy(
    monkeypatch, tmp_path
):
    seed_output = tmp_path / "a600-a800-a180.SLDASM"
    seed_output.write_bytes(b"attested-three-module-checkpoint")
    seed_evidence = tmp_path / "a180.result.json"
    seed_evidence.write_text(
        json.dumps(
            {"success": True, "outputAssemblySha256": _sha256(seed_output)}
        ),
        encoding="utf-8",
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    seed_plan = {
        **_plan(seed_output),
        "projectId": "project02",
        "targetModuleToken": "A180",
        "contextModuleToken": "A600",
        "steps": [
            {
                "stepId": "resolved-pair-connection-002",
                "moduleToken": "A180",
            }
        ],
    }
    seed_job = store.create(seed_plan, execution_mode="independent_context_insert")
    seed_job["status"] = "succeeded"
    seed_job["lastCommittedCheckpoint"] = {
        "stepId": "resolved-pair-connection-002",
        "moduleToken": "A180",
        "assemblyPath": str(seed_output),
        "evidencePath": str(seed_evidence),
    }
    store.save(seed_job)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    plan = compile_connection_pair_plan(
        WORKSPACE,
        "project02-full-static-graph-v1",
        "connection-003",
        seed_job_id=seed_job["jobId"],
    )

    assert plan["targetModuleToken"] == "A700"
    assert plan["seedCheckpoint"]["seedModuleToken"] == "A180"
    assert plan["constraintRequirement"] == (
        "accepted_flexible_or_fully_constrained"
    )
    assert Path(plan["effectiveMateGraphPath"]).parent.name == "A700"


def test_project02_a200_requires_attested_a100_seed(monkeypatch, tmp_path):
    seed_output = tmp_path / "seven-module-checkpoint.SLDASM"
    seed_output.write_bytes(b"attested-through-a100")
    seed_evidence = tmp_path / "a100.result.json"
    seed_evidence.write_text(
        json.dumps(
            {"success": True, "outputAssemblySha256": _sha256(seed_output)}
        ),
        encoding="utf-8",
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    seed_plan = {
        **_plan(seed_output),
        "projectId": "project02",
        "targetModuleToken": "A100",
        "contextModuleToken": "A600",
        "steps": [
            {
                "stepId": "resolved-pair-connection-006",
                "moduleToken": "A100",
            }
        ],
    }
    seed_job = store.create(seed_plan, execution_mode="independent_context_insert")
    seed_job["status"] = "succeeded"
    seed_job["lastCommittedCheckpoint"] = {
        "stepId": "resolved-pair-connection-006",
        "moduleToken": "A100",
        "assemblyPath": str(seed_output),
        "evidencePath": str(seed_evidence),
    }
    store.save(seed_job)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    plan = compile_connection_pair_plan(
        WORKSPACE,
        "project02-full-static-graph-v1",
        "connection-007",
        seed_job_id=seed_job["jobId"],
    )

    assert plan["targetModuleToken"] == "A200"
    assert plan["contextModuleToken"] == "A600"
    assert plan["seedCheckpoint"]["seedModuleToken"] == "A100"
    assert plan["constraintRequirement"] == "fully_constrained"
    assert Path(plan["effectiveMateGraphPath"]).name == (
        "a200_increment_effective.json"
    )
    assert "working distance" in plan["independentInstallationEvidenceBoundary"]


def test_project02_second_t401_uses_registered_non_base_context(monkeypatch, tmp_path):
    seed_output = tmp_path / "through-first-t401.SLDASM"
    seed_output.write_bytes(b"attested-through-first-t401")
    seed_evidence = tmp_path / "t401-1.result.json"
    seed_evidence.write_text(
        json.dumps(
            {"success": True, "outputAssemblySha256": _sha256(seed_output)}
        ),
        encoding="utf-8",
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    seed_plan = {
        **_plan(seed_output),
        "projectId": "project02",
        "targetModuleToken": "T401",
        "contextModuleToken": "A600",
        "steps": [
            {
                "stepId": "resolved-pair-connection-008",
                "moduleToken": "T401",
            }
        ],
    }
    seed_job = store.create(seed_plan, execution_mode="independent_context_insert")
    seed_job["status"] = "succeeded"
    seed_job["lastCommittedCheckpoint"] = {
        "stepId": "resolved-pair-connection-008",
        "moduleToken": "T401",
        "assemblyPath": str(seed_output),
        "evidencePath": str(seed_evidence),
    }
    store.save(seed_job)
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    plan = compile_connection_pair_plan(
        WORKSPACE,
        "project02-full-static-graph-v1",
        "connection-009",
        seed_job_id=seed_job["jobId"],
    )

    assert plan["targetModuleToken"] == "T401"
    assert plan["contextModuleToken"] == "A200"
    assert plan["targetInstanceId"] == "t401aa-07388-0-002"
    assert plan["contextInstanceId"] == "fl9a24d062a200-001-1-001"
    assert plan["seedCheckpoint"]["seedModuleToken"] == "T401"
    assert Path(plan["effectiveMateGraphPath"]).name == (
        "t401-2_increment_effective.json"
    )


def test_context_insert_script_closes_verified_output(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "run_context_mate_graph_insert_test", CONTEXT_INSERT_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source.SLDASM"
    effective = tmp_path / "effective.json"
    output = tmp_path / "output.SLDASM"
    result = tmp_path / "result.json"
    executable = tmp_path / "mcp.exe"
    target_source = tmp_path / "target.SLDASM"
    source.write_bytes(b"immutable-source")
    effective.write_text("{}\n", encoding="utf-8")
    executable.write_bytes(b"exe")
    target_source.write_bytes(b"target-source")
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def call_tool(self, name, payload):
            calls.append((name, payload))
            if name == "ListDocuments":
                return []
            output.write_bytes(b"verified-output")
            return {
                "Success": True,
                "IndependentComponentInserted": True,
                "Reopened": True,
                "ReopenedMateParametersMatch": True,
                "ComponentSemanticsMatch": True,
                "TargetConstraintStateAccepted": True,
                "TargetFullyConstrained": True,
                "MateSolveClean": True,
                "TargetModuleSourcePath": str(target_source),
            }

        def call_tool_text(self, name, payload):
            calls.append((name, payload))
            return "closed"

    monkeypatch.setattr(module, "McpClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            str(CONTEXT_INSERT_SCRIPT),
            "--source",
            str(source),
            "--effective",
            str(effective),
            "--output",
            str(output),
            "--target",
            "A800",
            "--expected-source-sha256",
            _sha256(source),
            "--expected-effective-sha256",
            _sha256(effective),
            "--result",
            str(result),
            "--exe",
            str(executable),
        ],
    )

    assert module.main() == 0
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["outputClosedAfterVerification"] is True
    assert any(name == "CloseDocument" for name, _ in calls)


def test_default_pair_job_idempotency_ignores_compile_timestamp(monkeypatch, tmp_path):
    source = tmp_path / "prototype.SLDASM"
    source.write_bytes(b"source-assembly")
    plans = iter(
        [
            {**_plan(source), "compiledAt": "first", "planDigest": "b" * 64},
            {**_plan(source), "compiledAt": "second", "planDigest": "b" * 64},
        ]
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.compile_connection_pair_plan",
        lambda workspace, context_id, connection_id, seed_job_id=None: next(plans),
    )
    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.pair_transaction_job_store",
        lambda workspace, project_id: store,
    )

    first = create_connection_pair_job(tmp_path, "ctx", "connection-001")
    second = create_connection_pair_job(tmp_path, "ctx", "connection-001")

    assert first["jobId"] == second["jobId"]


def test_pair_job_commits_only_published_source_unchanged_output(monkeypatch, tmp_path):
    source = tmp_path / "prototype.SLDASM"
    source.write_bytes(b"source-assembly")
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(_plan(source), execution_mode="resolved_pair_direct_mate")

    def fake_run(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        work = Path(command[command.index("--work-dir") + 1])
        output.write_bytes(b"published-output")
        work.mkdir(parents=True)
        (work / "manifest.json").write_text("{}\n", encoding="utf-8")
        result.write_text(
            json.dumps(
                {
                    "success": True,
                    "published": True,
                    "sourceAssemblyUnchanged": True,
                    "outputAssemblySha256": _sha256(output),
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.subprocess.run", fake_run
    )
    result = AssemblyJobExecutor(store, _pair_step_runner(tmp_path, store)).run(
        job["jobId"]
    )

    assert result["status"] == "succeeded"
    assert result["collisionStatus"] == "not_evaluated"
    checkpoint = result["lastCommittedCheckpoint"]
    assert Path(checkpoint["assemblyPath"]).read_bytes() == b"published-output"
    assert Path(checkpoint["evidencePath"]).is_file()
    assert source.read_bytes() == b"source-assembly"
    assert (store._dir(job["jobId"]) / "attempt-01" / "stdout.log").is_file()


def test_independent_pair_job_inserts_fresh_component_and_commits_reopen_evidence(
    monkeypatch, tmp_path
):
    source = tmp_path / "base.SLDASM"
    source.write_bytes(b"a600-only-base")
    effective = tmp_path / "effective.json"
    effective.write_text("{}\n", encoding="utf-8")
    independent_plan = {
        **_plan(source),
        "projectId": "project02",
        "targetModuleToken": "A800",
        "contextModuleToken": "A600",
        "executionStrategy": "independent_context_insert",
        "constraintRequirement": "fully_constrained",
        "effectiveMateGraphPath": str(effective),
        "effectiveMateGraphSha256": _sha256(effective),
        "steps": [
            {"stepId": "resolved-pair-connection-001", "moduleToken": "A800"}
        ],
    }
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(independent_plan, execution_mode="independent_context_insert")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"a600-plus-fresh-a800")
        result.write_text(
            json.dumps(
                {
                    "success": True,
                    "sourceAssemblyUnchanged": True,
                    "outputAssemblySha256": _sha256(output),
                    "toolResult": {
                        "IndependentComponentInserted": True,
                        "Reopened": True,
                        "ReopenedMateParametersMatch": True,
                        "ComponentSemanticsMatch": True,
                        "TargetConstraintStateAccepted": True,
                        "TargetFullyConstrained": True,
                        "MateSolveClean": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.subprocess.run", fake_run
    )
    result = AssemblyJobExecutor(store, _pair_step_runner(tmp_path, store)).run(
        job["jobId"]
    )

    assert result["status"] == "succeeded"
    assert result["lastCommittedCheckpoint"]["validationEvidenceKind"] == (
        "independent_context_insert_save_reopen"
    )
    assert commands and commands[0][1].endswith("run_context_mate_graph_insert.py")
    assert source.read_bytes() == b"a600-only-base"


def test_flexible_independent_pair_accepts_clean_solidworks_constraint_state(
    monkeypatch, tmp_path
):
    source = tmp_path / "three-module.SLDASM"
    source.write_bytes(b"a600-a800-a180")
    effective = tmp_path / "a700-effective.json"
    effective.write_text("{}\n", encoding="utf-8")
    plan = {
        **_plan(source),
        "projectId": "project02",
        "targetModuleToken": "A700",
        "contextModuleToken": "A600",
        "executionStrategy": "independent_context_insert",
        "constraintRequirement": "accepted_flexible_or_fully_constrained",
        "effectiveMateGraphPath": str(effective),
        "effectiveMateGraphSha256": _sha256(effective),
        "steps": [
            {"stepId": "resolved-pair-connection-003", "moduleToken": "A700"}
        ],
    }
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="independent_context_insert")

    def fake_run(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.write_bytes(b"four-module-flexible-output")
        result.write_text(
            json.dumps(
                {
                    "success": True,
                    "sourceAssemblyUnchanged": True,
                    "outputAssemblySha256": _sha256(output),
                    "toolResult": {
                        "IndependentComponentInserted": True,
                        "Reopened": True,
                        "ReopenedMateParametersMatch": True,
                        "ComponentSemanticsMatch": True,
                        "TargetConstraintStateAccepted": True,
                        "TargetFullyConstrained": False,
                        "MateSolveClean": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.subprocess.run", fake_run
    )
    result = AssemblyJobExecutor(store, _pair_step_runner(tmp_path, store)).run(
        job["jobId"]
    )

    assert result["status"] == "succeeded"
    assert result["lastCommittedCheckpoint"]["moduleToken"] == "A700"


def test_pair_job_fails_closed_when_transaction_evidence_rejects_publish(
    monkeypatch, tmp_path
):
    source = tmp_path / "prototype.SLDASM"
    source.write_bytes(b"source-assembly")
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(_plan(source), execution_mode="resolved_pair_direct_mate")

    def fake_run(command, **kwargs):
        result = Path(command[command.index("--result") + 1])
        result.write_text(
            json.dumps(
                {
                    "success": False,
                    "published": False,
                    "sourceAssemblyUnchanged": True,
                    "executionError": "save/reopen rejected",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=1, stdout="", stderr="failed")

    monkeypatch.setattr(
        "demo_backend.resolved_pair_transaction_jobs.subprocess.run", fake_run
    )
    result = AssemblyJobExecutor(store, _pair_step_runner(tmp_path, store)).run(
        job["jobId"]
    )

    assert result["status"] == "failed"
    assert result["lastCommittedCheckpoint"] is None
    assert result["rollback"]["uncommittedOutputAccepted"] is False
    assert "save/reopen rejected" in result["error"]
    assert source.read_bytes() == b"source-assembly"


def test_api_requires_two_digest_bound_confirmations_before_scheduling(
    monkeypatch, tmp_path
):
    source = tmp_path / "prototype.SLDASM"
    source.write_bytes(b"source-assembly")
    plan = {
        **_plan(source),
        "planDigest": "b" * 64,
    }
    store = DurableAssemblyJobStore(tmp_path / "jobs")

    def create_job(
        workspace,
        context_id,
        connection_id,
        *,
        idempotency_key=None,
        seed_job_id=None,
    ):
        return store.create(
            plan,
            execution_mode="resolved_pair_direct_mate",
            idempotency_key=idempotency_key,
        )

    monkeypatch.setattr(main_api, "create_connection_pair_job", create_job)
    monkeypatch.setattr(
        main_api, "pair_transaction_job_store", lambda workspace, project_id: store
    )
    monkeypatch.setattr(
        main_api,
        "compile_connection_pair_plan",
        lambda workspace, context_id, connection_id, seed_job_id=None: plan,
    )

    with pytest.raises(HTTPException):
        main_api.prepare_resolved_pair_transaction_job(
            "test-context",
            "connection-001",
            ResolvedPairTransactionJobCreateRequest(confirmed=False),
        )

    prepared = main_api.prepare_resolved_pair_transaction_job(
        "test-context",
        "connection-001",
        ResolvedPairTransactionJobCreateRequest(
            confirmed=True, idempotencyKey="pair-api-test"
        ),
    )
    assert prepared["preparedOnly"] is True
    assert prepared["executionStarted"] is False
    assert prepared["job"]["status"] == "queued"

    background = BackgroundTasks()
    started = main_api.start_resolved_pair_transaction_job(
        "test-context",
        "connection-001",
        prepared["job"]["jobId"],
        ResolvedPairTransactionJobStartRequest(
            confirmed=True,
            expectedContextDigest="a" * 64,
            expectedPlanDigest="b" * 64,
        ),
        background,
    )
    assert started["executionScheduled"] is True
    assert started["solidWorksStartedInRequest"] is False
    assert len(background.tasks) == 1


def test_api_rejects_changed_plan_before_cad_schedule(monkeypatch, tmp_path):
    source = tmp_path / "prototype.SLDASM"
    source.write_bytes(b"source-assembly")
    stored_plan = {**_plan(source), "planDigest": "b" * 64}
    changed_plan = {**stored_plan, "planDigest": "c" * 64}
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(stored_plan, execution_mode="resolved_pair_direct_mate")
    monkeypatch.setattr(
        main_api, "pair_transaction_job_store", lambda workspace, project_id: store
    )
    monkeypatch.setattr(
        main_api,
        "compile_connection_pair_plan",
        lambda workspace, context_id, connection_id, seed_job_id=None: changed_plan,
    )

    background = BackgroundTasks()
    with pytest.raises(HTTPException) as captured:
        main_api.start_resolved_pair_transaction_job(
            "test-context",
            "connection-001",
            job["jobId"],
            ResolvedPairTransactionJobStartRequest(
                confirmed=True,
                expectedContextDigest="a" * 64,
                expectedPlanDigest="b" * 64,
            ),
            background,
        )
    assert "已变化" in str(captured.value.detail)
    assert len(background.tasks) == 0
