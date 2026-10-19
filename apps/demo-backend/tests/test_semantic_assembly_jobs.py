from __future__ import annotations

from pathlib import Path

from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    AssemblyJobError,
    DurableAssemblyJobStore,
    validated_artifact_step_runner,
)


def plan(tokens: list[str]):
    return {
        "steps": [
            {"stepId": f"step-{index:02d}-{token.lower()}", "moduleToken": token}
            for index, token in enumerate(tokens, start=1)
        ]
    }


def runner(tmp_path: Path, fail: str | None = None):
    def execute(job, step, previous):
        token = step["moduleToken"]
        output = tmp_path / f"{job['jobId']}-{token}.SLDASM"
        output.write_bytes(token.encode())
        if token == fail:
            return {"accepted": False, "assemblyPath": str(output), "message": "hard gate"}
        return {"accepted": True, "assemblyPath": str(output), "evidencePath": f"{token}.json"}

    return execute


def test_success_commits_every_checkpoint(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")
    result = AssemblyJobExecutor(store, runner(tmp_path)).run(job["jobId"])

    assert result["status"] == "succeeded"
    assert [item["status"] for item in result["steps"]] == ["succeeded", "succeeded"]
    assert result["lastCommittedCheckpoint"]["moduleToken"] == "A180"
    assert result["executionDurationSeconds"] >= 0
    assert result["steps"][0]["attempts"][0]["durationSeconds"] >= 0
    assert result["assemblyStatus"] == "assembled"
    assert result["collisionStatus"] == "not_evaluated"
    assert result["demoCheckpoint"]["moduleToken"] == "A180"


def test_failure_rolls_back_to_last_committed_checkpoint(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")
    result = AssemblyJobExecutor(store, runner(tmp_path, fail="A180")).run(job["jobId"])

    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "succeeded"
    assert result["steps"][1]["status"] == "failed"
    assert result["rollback"]["checkpoint"]["moduleToken"] == "A800"
    assert Path(result["rollback"]["quarantinedArtifactPath"]).is_file()
    assert not (tmp_path / f"{job['jobId']}-A180.SLDASM").exists()


def test_failed_read_only_validation_preserves_assembled_checkpoint_status(
    tmp_path: Path,
):
    relation_plan = {
        "steps": [
            {"stepId": "install-a500", "moduleToken": "A500", "operation": "INSERT_AND_CONNECT"},
            {"stepId": "verify-spacing", "moduleToken": "A500", "operation": "VERIFY_RELATION"},
        ]
    }
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(relation_plan, execution_mode="test")

    def execute(job_row, step, previous):
        output = tmp_path / f"{step['stepId']}.SLDASM"
        output.write_bytes(step["stepId"].encode())
        if step["stepId"] == "verify-spacing":
            return {
                "accepted": False,
                "assemblyPath": str(output),
                "message": "50 mm spacing validation failed",
            }
        return {"accepted": True, "assemblyPath": str(output)}

    result = AssemblyJobExecutor(store, execute).run(job["jobId"])
    assert result["status"] == "failed"
    assert result["assemblyStatus"] == "assembled"
    assert result["validationStatus"] == "failed"
    assert result["lastCommittedCheckpoint"]["stepId"] == "install-a500"
    assert result["rollback"]["checkpoint"]["stepId"] == "install-a500"


def test_rejected_step_without_output_preserves_hard_gate_reason(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800"]), execution_mode="test")

    def rejected(job_row, step, previous):
        return {
            "accepted": False,
            "assemblyPath": str(tmp_path / "not-created.SLDASM"),
            "message": "base context evidence mismatch",
        }

    result = AssemblyJobExecutor(store, rejected).run(job["jobId"])
    assert result["status"] == "failed"
    assert result["error"] == "base context evidence mismatch"


def test_cancel_before_next_step_preserves_checkpoint(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")

    def cancelling(job_row, step, previous):
        output = tmp_path / f"{step['moduleToken']}.SLDASM"
        output.write_bytes(b"ok")
        if step["moduleToken"] == "A800":
            store.request_cancel(job_row["jobId"])
        return {"accepted": True, "assemblyPath": str(output)}

    result = AssemblyJobExecutor(store, cancelling).run(job["jobId"])
    assert result["status"] == "cancelled"
    assert result["steps"][0]["status"] == "succeeded"
    assert result["steps"][1]["status"] == "cancelled"
    assert (store.root / job["jobId"] / "evidence-manifest.json").is_file()


def test_resume_retries_only_failed_tail(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")
    failed = AssemblyJobExecutor(store, runner(tmp_path, fail="A180")).run(job["jobId"])
    assert failed["status"] == "failed"

    store.prepare_resume(job["jobId"])
    result = AssemblyJobExecutor(store, runner(tmp_path)).run(job["jobId"])
    assert result["status"] == "succeeded"
    assert result["steps"][0]["attemptCount"] == 1
    assert result["steps"][1]["attemptCount"] == 2


def test_pause_between_steps_and_resume_from_checkpoint(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")

    def pausing(job_row, step, previous):
        output = tmp_path / f"{step['moduleToken']}.SLDASM"
        output.write_bytes(b"ok")
        if step["moduleToken"] == "A800":
            store.request_pause(job_row["jobId"])
        return {"accepted": True, "assemblyPath": str(output)}

    paused = AssemblyJobExecutor(store, pausing).run(job["jobId"])
    assert paused["status"] == "paused"
    assert paused["steps"][0]["status"] == "succeeded"
    assert paused["steps"][1]["status"] == "pending"
    assert paused["lastCommittedCheckpoint"]["moduleToken"] == "A800"
    assert (store.root / job["jobId"] / "evidence-manifest.json").is_file()

    store.prepare_resume(job["jobId"])
    result = AssemblyJobExecutor(store, runner(tmp_path)).run(job["jobId"])
    assert result["status"] == "succeeded"
    assert result["steps"][0]["attemptCount"] == 1
    assert result["steps"][1]["attemptCount"] == 1


def test_idempotency_returns_existing_job(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    first = store.create(plan(["A800", "A180"]), execution_mode="test")
    repeated = store.create(plan(["A800", "A180"]), execution_mode="test")
    assert repeated["jobId"] == first["jobId"]


def test_job_identity_and_schema_follow_plan_project(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    project05_plan = {**plan(["D000", "K000"]), "projectId": "project05"}
    job = store.create(project05_plan, execution_mode="validated_artifact_replay")
    assert job["schemaVersion"] == "ordered-assembly-job/v2"
    assert job["projectId"] == "project05"
    assert job["jobId"].startswith("project05-job-")


def test_validated_artifact_runner_requires_real_stage_evidence(tmp_path: Path):
    assembly = tmp_path / "D000.SLDASM"
    assembly.write_bytes(b"cad")
    closure = {
        "steps": [
            {
                "moduleToken": "D000",
                "success": True,
                "assemblyPath": str(assembly),
                "evidencePath": str(tmp_path / "missing-stage-result.json"),
            }
        ]
    }
    step_runner = validated_artifact_step_runner(closure, tmp_path)
    try:
        step_runner({}, {"moduleToken": "D000"}, None)
    except AssemblyJobError as exc:
        assert "Validated evidence does not exist" in str(exc)
    else:
        raise AssertionError("artifact replay unexpectedly accepted missing evidence")


def test_verified_checkpoint_seed_starts_single_tail_step_from_prior_cad(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A100"]), execution_mode="test")
    assembly = tmp_path / "step05.SLDASM"
    evidence = tmp_path / "step05.json"
    assembly.write_bytes(b"step05")
    evidence.write_text("{}", encoding="utf-8")
    seeded = store.seed_verified_checkpoint(
        job["jobId"],
        step_id="step-05-a500",
        module_token="A500",
        assembly_path=assembly,
        evidence_path=evidence,
    )
    assert seeded["lastCommittedCheckpoint"]["externalVerifiedSeed"] is True

    observed = {}

    def capture_previous(job_row, step, previous):
        observed["previous"] = previous
        output = tmp_path / "step06.SLDASM"
        output.write_bytes(b"step06")
        return {"accepted": True, "assemblyPath": str(output)}

    result = AssemblyJobExecutor(store, capture_previous).run(job["jobId"])
    assert result["status"] == "succeeded"
    assert observed["previous"] == assembly.resolve()


def test_verified_checkpoint_seed_requires_real_evidence(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A100"]), execution_mode="test")
    assembly = tmp_path / "step05.SLDASM"
    assembly.write_bytes(b"step05")
    try:
        store.seed_verified_checkpoint(
            job["jobId"],
            step_id="step-05-a500",
            module_token="A500",
            assembly_path=assembly,
            evidence_path=tmp_path / "missing.json",
        )
    except AssemblyJobError as exc:
        assert "Seed evidence does not exist" in str(exc)
    else:
        raise AssertionError("missing seed evidence unexpectedly accepted")


def test_nonterminal_job_cannot_resume(tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800", "A180"]), execution_mode="test")
    try:
        store.prepare_resume(job["jobId"])
    except AssemblyJobError as exc:
        assert "not resumable" in str(exc)
    else:
        raise AssertionError("queued job unexpectedly resumed")


def test_locked_uncommitted_artifact_is_copied_with_quarantine_metadata(
    monkeypatch, tmp_path: Path
):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan(["A800"]), execution_mode="test")
    artifact = tmp_path / "locked.SLDASM"
    artifact.write_bytes(b"locked")

    def locked_move(*args, **kwargs):
        raise PermissionError("SolidWorks holds the file")

    monkeypatch.setattr("demo_backend.semantic_assembly_jobs.shutil.move", locked_move)
    rejected = store.quarantine_artifact(job["jobId"], "step-01-a800", artifact)
    assert rejected is not None and rejected.is_file()
    assert artifact.is_file()
    metadata = rejected.with_suffix(rejected.suffix + ".quarantine.json")
    assert metadata.is_file()
    assert "copied-because-source-locked" in metadata.read_text(encoding="utf-8")
