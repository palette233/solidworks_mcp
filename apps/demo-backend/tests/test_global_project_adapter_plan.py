from pathlib import Path
import hashlib

import pytest
from fastapi import BackgroundTasks, HTTPException

from demo_backend import main as main_api
from demo_backend.global_assembly_workbench import (
    compile_cad_transaction_manifest,
    compile_project_adapter_plan,
)
from demo_backend.global_project_adapter_plan import (
    build_checkpoint_continuation_plan,
    build_direct_edit_checkpoint_continuation_plan,
    create_seeded_durable_job,
)
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobError,
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)
from demo_backend.semantic_assembly_cad_runner import build_live_cad_step_specs
from demo_backend.semantic_assembly_sequence import load_project02_ordered_assembly_closure
from demo_backend.models import (
    GlobalProjectAdapterJobCreateRequest,
    GlobalProjectAdapterJobStartRequest,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_project05_global_context_binds_to_seeded_eight_step_durable_plan(tmp_path):
    plan = compile_project_adapter_plan(
        WORKSPACE,
        "project05-full-static-graph-v1",
        assembly_mode="prototype_pose_dependency",
    )

    assert plan["status"] == "ready_for_durable_job"
    assert plan["safeToCreateDurableJob"] is True
    assert plan["projectId"] == "project05"
    assert plan["contextRevision"] > 0
    assert plan["sequenceAssessment"]["kind"] == "exact"
    assert [row["moduleToken"] for row in plan["steps"]] == [
        "D000",
        "K000",
        "F000",
        "M000",
        "G000",
        "N000",
        "P000",
        "B000",
    ]
    assert plan["steps"][0]["sourceCheckpointPolicy"] == "verified_external_seed"
    assert all(
        row["sourceCheckpointPolicy"] == "previous_committed_step"
        for row in plan["steps"][1:]
    )
    assert Path(plan["seedCheckpoint"]["assemblyPath"]).is_file()
    assert Path(plan["seedCheckpoint"]["evidencePath"]).is_file()
    assert plan["executionBoundary"]["solidWorksExecuted"] is False
    assert plan["executionBoundary"]["collisionGateExecuted"] is False

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = create_seeded_durable_job(
        store,
        plan,
        idempotency_key="project05-global-adapter-test",
    )
    assert job["status"] == "queued"
    assert len(job["steps"]) == 8
    assert job["lastCommittedCheckpoint"]["moduleToken"] == "A000"
    assert job["lastCommittedCheckpoint"]["externalVerifiedSeed"] is True

    repeated = create_seeded_durable_job(
        store,
        plan,
        idempotency_key="project05-global-adapter-test",
    )
    assert repeated["jobId"] == job["jobId"]


def test_project02_partial_chain_is_blocked_before_solidworks_or_job_creation(tmp_path):
    plan = compile_project_adapter_plan(WORKSPACE, "project02-a200-t401-evidence-v1")

    assert plan["status"] == "blocked"
    assert plan["safeToCreateDurableJob"] is False
    assert plan["sequenceAssessment"]["kind"] == "sequence_mismatch"
    assert plan["sequenceAssessment"]["missingPredecessors"] == [
        "A800",
        "A180",
        "A700",
        "A300",
        "A500",
        "A100",
    ]
    assert any(row["code"] == "SEQUENCE_NOT_VALIDATED_PREFIX" for row in plan["blockers"])
    assert plan["executionBoundary"]["solidWorksExecuted"] is False

    with pytest.raises(AssemblyJobError, match="禁止创建执行任务"):
        create_seeded_durable_job(DurableAssemblyJobStore(tmp_path / "jobs"), plan)


def test_project02_complete_chain_groups_two_t401_instances_for_existing_runner(tmp_path):
    default_plan = compile_project_adapter_plan(
        WORKSPACE, "project02-full-static-graph-v1"
    )
    assert default_plan["assemblyMode"] == "mate_driven_port_assembly"
    assert default_plan["safeToCreateDurableJob"] is False
    assert default_plan["poseDependencyAudit"]["prototypePoseRequiredCount"] >= 2
    assert any(
        row["code"] == "PROTOTYPE_POSE_DEPENDENCY_NOT_ALLOWED"
        for row in default_plan["blockers"]
    )

    plan = compile_project_adapter_plan(
        WORKSPACE,
        "project02-full-static-graph-v1",
        assembly_mode="prototype_pose_dependency",
    )

    assert plan["status"] == "ready_for_durable_job"
    assert plan["sequenceAssessment"]["kind"] == "exact"
    assert plan["runnerBinding"]["groupedInstanceTokens"] == ["T401"]
    assert [row["moduleToken"] for row in plan["steps"]] == [
        "A800",
        "A180",
        "A700",
        "A300",
        "A500",
        "A100",
        "A200",
        "T401",
    ]
    assert plan["steps"][-1]["groupedInstanceCount"] == 2
    assert len(plan["steps"][-1]["targetInstanceIds"]) == 2
    assert len(plan["steps"][-1]["semanticConnectionRequests"]) == 2

    job = create_seeded_durable_job(
        DurableAssemblyJobStore(tmp_path / "jobs"),
        plan,
        idempotency_key="project02-full-global-adapter-test",
    )
    assert len(job["steps"]) == 8
    assert job["lastCommittedCheckpoint"]["moduleToken"] == "A600"

    closure = load_project02_ordered_assembly_closure(WORKSPACE)
    base, specs = build_live_cad_step_specs(
        closure,
        required_tokens={row["moduleToken"] for row in plan["steps"]},
    )
    assert base == Path(plan["seedCheckpoint"]["assemblyPath"])
    assert set(specs) == {row["moduleToken"] for row in plan["steps"]}
    assert len(specs["T401"]) == 2
    assert len(specs["A100"]) == 2


def test_project02_portable_a800_a180_release_uses_generic_manifest_path():
    """The independent route must not fall back to the fixed-sequence adapter."""

    context_id = "project02-release-a800-a180-v2"
    legacy_adapter = compile_project_adapter_plan(WORKSPACE, context_id)
    assert legacy_adapter["safeToCreateDurableJob"] is False
    assert legacy_adapter["poseDependencyAudit"]["mateDrivenReadyCount"] == 2
    assert legacy_adapter["poseDependencyAudit"]["prototypePoseRequiredCount"] == 0

    manifest = compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["planningMode"] == "project_independent_semantic_graph"
    assert manifest["packetCount"] == 2
    assert manifest["relationReleaseBinding"]["releaseId"] == (
        "relation-v30-project02-a800-a180-portable-driving-20261011"
    )
    assert all(
        packet["executionStrategy"] == "incremental_component_insert"
        for packet in manifest["packets"]
    )


def test_global_adapter_seeded_job_pause_resume_and_failure_rollback(tmp_path):
    plan = compile_project_adapter_plan(
        WORKSPACE,
        "project05-full-static-graph-v1",
        assembly_mode="prototype_pose_dependency",
    )

    pause_store = DurableAssemblyJobStore(tmp_path / "pause-jobs")
    paused_job = create_seeded_durable_job(
        pause_store,
        plan,
        idempotency_key="pause-resume",
    )
    observed_previous: list[Path | None] = []

    def pausing_runner(job, step, previous):
        observed_previous.append(previous)
        output = tmp_path / f"pause-{step['stepId']}-{step['attemptCount']}.SLDASM"
        evidence = output.with_suffix(".json")
        output.write_bytes(step["moduleToken"].encode())
        evidence.write_text("{}", encoding="utf-8")
        if step["moduleToken"] == "D000":
            pause_store.request_pause(job["jobId"])
        return {"accepted": True, "assemblyPath": str(output), "evidencePath": str(evidence)}

    paused = AssemblyJobExecutor(pause_store, pausing_runner).run(paused_job["jobId"])
    assert paused["status"] == "paused"
    assert paused["steps"][0]["status"] == "succeeded"
    assert paused["steps"][1]["status"] == "pending"
    assert observed_previous[0] == Path(plan["seedCheckpoint"]["assemblyPath"])

    def success_runner(job, step, previous):
        output = tmp_path / f"resume-{step['stepId']}-{step['attemptCount']}.SLDASM"
        evidence = output.with_suffix(".json")
        output.write_bytes(step["moduleToken"].encode())
        evidence.write_text("{}", encoding="utf-8")
        return {"accepted": True, "assemblyPath": str(output), "evidencePath": str(evidence)}

    pause_store.prepare_resume(paused_job["jobId"])
    resumed = AssemblyJobExecutor(pause_store, success_runner).run(paused_job["jobId"])
    assert resumed["status"] == "succeeded"
    assert resumed["steps"][0]["attemptCount"] == 1
    assert all(step["status"] == "succeeded" for step in resumed["steps"])

    failure_store = DurableAssemblyJobStore(tmp_path / "failure-jobs")
    failed_job = create_seeded_durable_job(
        failure_store,
        plan,
        idempotency_key="failure-rollback",
    )

    def failing_runner(job, step, previous):
        output = tmp_path / f"fail-{step['stepId']}-{step['attemptCount']}.SLDASM"
        output.write_bytes(step["moduleToken"].encode())
        return {
            "accepted": step["moduleToken"] != "K000",
            "assemblyPath": str(output),
            "message": "simulated hard gate",
        }

    failed = AssemblyJobExecutor(failure_store, failing_runner).run(failed_job["jobId"])
    assert failed["status"] == "failed"
    assert failed["rollback"]["checkpoint"]["moduleToken"] == "D000"
    assert failed["rollback"]["uncommittedOutputAccepted"] is False
    assert Path(failed["rollback"]["quarantinedArtifactPath"]).is_file()

    failure_store.prepare_resume(failed_job["jobId"])
    recovered = AssemblyJobExecutor(failure_store, success_runner).run(failed_job["jobId"])
    assert recovered["status"] == "succeeded"
    assert recovered["steps"][0]["attemptCount"] == 1
    assert recovered["steps"][1]["attemptCount"] == 2


def test_succeeded_job_checkpoint_creates_next_step_only_continuation(
    monkeypatch, tmp_path
):
    store = DurableAssemblyJobStore(tmp_path / "continuation-jobs")
    monkeypatch.setattr(main_api, "_assembly_job_store", lambda workspace, project_id: store)
    bound_jobs = []
    monkeypatch.setattr(
        main_api,
        "bind_conversation_job",
        lambda context_path, context, job: bound_jobs.append(job["jobId"]),
    )

    first = main_api.prepare_global_project_adapter_job(
        "project05-full-static-graph-v1",
        GlobalProjectAdapterJobCreateRequest(
            confirmed=True,
            idempotencyKey="continuation-first",
            stepLimit=1,
            assemblyMode="prototype_pose_dependency",
        ),
    )["job"]

    def runner(job, step, previous):
        output = tmp_path / f"{step['moduleToken']}.SLDASM"
        evidence = tmp_path / f"{step['moduleToken']}.json"
        output.write_bytes(step["moduleToken"].encode())
        evidence.write_text("{}", encoding="utf-8")
        return {"accepted": True, "assemblyPath": str(output), "evidencePath": str(evidence)}

    succeeded = AssemblyJobExecutor(store, runner).run(first["jobId"])
    assert succeeded["status"] == "succeeded"
    assert succeeded["lastCommittedCheckpoint"]["moduleToken"] == "D000"

    full_plan = compile_project_adapter_plan(
        WORKSPACE,
        "project05-full-static-graph-v1",
        assembly_mode="prototype_pose_dependency",
    )
    direct = build_checkpoint_continuation_plan(full_plan, succeeded, step_limit=1)
    assert [step["moduleToken"] for step in direct["steps"]] == ["K000"]
    assert direct["steps"][0]["sourceCheckpointPolicy"] == "verified_external_seed"
    assert direct["executionScope"]["startStepIndex"] == 1

    prepared = main_api.prepare_global_project_adapter_job(
        "project05-full-static-graph-v1",
        GlobalProjectAdapterJobCreateRequest(
            confirmed=True,
            idempotencyKey="continuation-second",
            stepLimit=1,
            seedJobId=first["jobId"],
            assemblyMode="prototype_pose_dependency",
        ),
    )
    assert prepared["executionScope"]["kind"] == "validated_continuation"
    assert prepared["executionScope"]["moduleTokens"] == ["K000"]
    assert prepared["job"]["lastCommittedCheckpoint"]["moduleToken"] == "D000"
    assert prepared["job"]["steps"][0]["moduleToken"] == "K000"
    assert bound_jobs == [first["jobId"], prepared["job"]["jobId"]]

    background = BackgroundTasks()
    started = main_api.start_global_project_adapter_job(
        "project05-full-static-graph-v1",
        prepared["job"]["jobId"],
        GlobalProjectAdapterJobStartRequest(
            confirmed=True,
            expectedContextDigest=prepared["job"]["plan"]["contextDigest"],
            expectedStepCount=1,
        ),
        background,
    )
    assert started["executionScheduled"] is True
    assert len(background.tasks) == 1


def test_direct_mate_edit_checkpoint_can_seed_next_project_step(tmp_path):
    store = DurableAssemblyJobStore(tmp_path / "direct-edit-continuation-jobs")
    full_plan = compile_project_adapter_plan(
        WORKSPACE,
        "project05-full-static-graph-v1",
        assembly_mode="prototype_pose_dependency",
    )
    first_plan = {
        **full_plan,
        "steps": full_plan["steps"][:1],
        "stepCount": 1,
        "executionScope": {
            "kind": "validated_prefix",
            "requestedStepCount": 1,
            "fullStepCount": len(full_plan["steps"]),
            "startStepIndex": 0,
            "moduleTokens": ["D000"],
        },
    }
    first = create_seeded_durable_job(store, first_plan, idempotency_key="direct-seed")

    def runner(job, step, previous):
        output = tmp_path / "D000.SLDASM"
        evidence = tmp_path / "D000.json"
        output.write_bytes(b"D000")
        evidence.write_text("{}", encoding="utf-8")
        return {"accepted": True, "assemblyPath": str(output), "evidencePath": str(evidence)}

    succeeded = AssemblyJobExecutor(store, runner).run(first["jobId"])
    edited = tmp_path / "D000-edited.SLDASM"
    edit_evidence = tmp_path / "D000-edit-result.json"
    edited.write_bytes(b"D000 plus direct mate edit")
    edit_evidence.write_text('{"success":true}', encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    direct_edit = {
        "editId": "direct-mate-unit",
        "status": "succeeded",
        "sourceJobId": succeeded["jobId"],
        "assemblyPath": str(edited),
        "assemblySha256": digest(edited),
        "executionEvidencePath": str(edit_evidence),
        "executionEvidenceSha256": digest(edit_evidence),
    }

    continuation = build_direct_edit_checkpoint_continuation_plan(
        full_plan, succeeded, direct_edit, step_limit=1
    )
    prepared = create_seeded_durable_job(
        store, continuation, idempotency_key="after-direct-edit"
    )

    assert continuation["executionScope"]["kind"] == (
        "validated_direct_edit_continuation"
    )
    assert continuation["executionScope"]["seedEditId"] == "direct-mate-unit"
    assert continuation["steps"][0]["moduleToken"] == "K000"
    assert continuation["seedCheckpoint"]["assemblyPath"] == str(edited.resolve())
    assert prepared["lastCommittedCheckpoint"]["assemblyPath"] == str(edited.resolve())


def test_prepare_job_api_requires_confirmation_and_never_starts_execution(
    monkeypatch, tmp_path
):
    store = DurableAssemblyJobStore(tmp_path / "api-jobs")
    monkeypatch.setattr(main_api, "_assembly_job_store", lambda workspace, project_id: store)
    bound_jobs = []
    monkeypatch.setattr(
        main_api,
        "bind_conversation_job",
        lambda context_path, context, job: bound_jobs.append(job["jobId"]),
    )

    with pytest.raises(HTTPException, match="confirmed=true"):
        main_api.prepare_global_project_adapter_job(
            "project05-full-static-graph-v1",
            GlobalProjectAdapterJobCreateRequest(confirmed=False),
        )

    result = main_api.prepare_global_project_adapter_job(
        "project05-full-static-graph-v1",
        GlobalProjectAdapterJobCreateRequest(
            confirmed=True,
            idempotencyKey="api-prepare-only",
            stepLimit=1,
            assemblyMode="prototype_pose_dependency",
        ),
    )
    assert result["preparedOnly"] is True
    assert result["executionStarted"] is False
    assert result["solidWorksStarted"] is False
    assert result["validationProfile"] == "demo"
    assert result["job"]["status"] == "queued"
    assert result["job"]["validationProfile"] == "demo"
    assert result["job"]["assemblyStatus"] == "seeded"
    assert result["job"]["collisionStatus"] == "not_evaluated"
    assert result["job"]["lastCommittedCheckpoint"]["moduleToken"] == "A000"
    assert all(step["status"] == "pending" for step in result["job"]["steps"])
    assert len(result["job"]["steps"]) == 1
    assert result["executionScope"]["kind"] == "validated_prefix"
    assert result["executionScope"]["moduleTokens"] == ["D000"]

    engineering = main_api.prepare_global_project_adapter_job(
        "project05-full-static-graph-v1",
        GlobalProjectAdapterJobCreateRequest(
            confirmed=True,
            idempotencyKey="api-prepare-engineering",
            stepLimit=1,
            validationProfile="engineering",
            assemblyMode="prototype_pose_dependency",
        ),
    )
    assert engineering["validationProfile"] == "engineering"
    assert engineering["job"]["plan"]["validationBoundary"]["collisionGate"] == (
        "synchronous_hard_gate"
    )
    assert bound_jobs == [result["job"]["jobId"], engineering["job"]["jobId"]]

    background = BackgroundTasks()
    with pytest.raises(HTTPException, match="上下文摘要已变化"):
        main_api.start_global_project_adapter_job(
            "project05-full-static-graph-v1",
            result["job"]["jobId"],
            GlobalProjectAdapterJobStartRequest(
                confirmed=True,
                expectedContextDigest="0" * 64,
                expectedStepCount=1,
            ),
            background,
        )
    assert len(background.tasks) == 0

    context_digest = result["job"]["plan"]["contextDigest"]
    started = main_api.start_global_project_adapter_job(
        "project05-full-static-graph-v1",
        result["job"]["jobId"],
        GlobalProjectAdapterJobStartRequest(
            confirmed=True,
            expectedContextDigest=context_digest,
            expectedStepCount=1,
        ),
        background,
    )
    assert started["executionScheduled"] is True
    assert started["solidWorksStartedInRequest"] is False
    assert started["job"]["startRequestedAt"]
    assert len(background.tasks) == 1

    repeated = main_api.start_global_project_adapter_job(
        "project05-full-static-graph-v1",
        result["job"]["jobId"],
        GlobalProjectAdapterJobStartRequest(
            confirmed=True,
            expectedContextDigest=context_digest,
            expectedStepCount=1,
        ),
        background,
    )
    assert repeated["executionScheduled"] is False
    assert len(background.tasks) == 1

    monkeypatch.setattr(
        main_api,
        "_run_live_cad_assembly_job",
        lambda workspace, project_id, job_id: (_ for _ in ()).throw(
            AssemblyJobError("simulated runner initialization failure")
        ),
    )
    main_api._run_scheduled_global_adapter_job(
        WORKSPACE,
        "project05",
        result["job"]["jobId"],
    )
    failed_to_start = store.load(result["job"]["jobId"])
    assert failed_to_start["status"] == "failed"
    assert "启动前失败" in failed_to_start["error"]
    assert failed_to_start["rollback"]["checkpoint"]["moduleToken"] == "A000"
    assert (store.root / result["job"]["jobId"] / "evidence-manifest.json").is_file()

    resume_background = BackgroundTasks()
    with pytest.raises(HTTPException, match="上下文摘要已变化"):
        main_api.resume_global_project_adapter_job(
            "project05-full-static-graph-v1",
            result["job"]["jobId"],
            GlobalProjectAdapterJobStartRequest(
                confirmed=True,
                expectedContextDigest="f" * 64,
                expectedStepCount=1,
            ),
            resume_background,
        )
    assert len(resume_background.tasks) == 0

    resumed = main_api.resume_global_project_adapter_job(
        "project05-full-static-graph-v1",
        result["job"]["jobId"],
        GlobalProjectAdapterJobStartRequest(
            confirmed=True,
            expectedContextDigest=context_digest,
            expectedStepCount=1,
        ),
        resume_background,
    )
    assert resumed["executionScheduled"] is True
    assert resumed["solidWorksStartedInRequest"] is False
    assert resumed["job"]["status"] == "queued"
    assert resumed["job"]["startRequestedAt"]
    assert resumed["job"]["steps"][0]["status"] == "pending"
    assert resumed["job"]["lastCommittedCheckpoint"]["moduleToken"] == "A000"
    assert len(resume_background.tasks) == 1
