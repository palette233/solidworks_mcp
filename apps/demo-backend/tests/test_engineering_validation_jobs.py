from pathlib import Path

from demo_backend.engineering_validation_jobs import (
    EngineeringValidationJobStore,
    run_engineering_validation_job,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


def source_job(assembly_store: DurableAssemblyJobStore, tmp_path: Path) -> dict:
    assembly = tmp_path / "demo.SLDASM"
    evidence = tmp_path / "demo.json"
    assembly.write_bytes(b"immutable-demo")
    evidence.write_text("{}", encoding="utf-8")
    job = assembly_store.create(
        {
            "projectId": "project02",
            "validationProfile": "demo",
            "steps": [{"stepId": "step-01-a800", "moduleToken": "A800"}],
        },
        execution_mode="live_cad",
    )
    job["status"] = "succeeded"
    job["assemblyStatus"] = "assembled"
    checkpoint = {
        "stepId": "step-01-a800",
        "moduleToken": "A800",
        "assemblyPath": str(assembly.resolve()),
        "evidencePath": str(evidence.resolve()),
        "committedAt": "2026-10-09T00:00:00Z",
        "collisionStatus": "not_evaluated",
    }
    job["lastCommittedCheckpoint"] = checkpoint
    job["demoCheckpoint"] = checkpoint
    assembly_store.save(job)
    return job


def test_independent_validation_passes_without_rebuilding_demo(tmp_path: Path):
    assembly_store = DurableAssemblyJobStore(tmp_path / "assembly-jobs")
    validation_store = EngineeringValidationJobStore(tmp_path / "validation-jobs")
    source = source_job(assembly_store, tmp_path)
    evidence = tmp_path / "brep.json"
    evidence.write_text("{}", encoding="utf-8")
    before = Path(source["demoCheckpoint"]["assemblyPath"]).read_bytes()

    validation = validation_store.create(source)
    result = run_engineering_validation_job(
        validation_store=validation_store,
        assembly_store=assembly_store,
        validation_job_id=validation["validationJobId"],
        hard_gate=lambda *args: {"accepted": True, "evidencePath": str(evidence)},
    )

    refreshed = assembly_store.load(source["jobId"])
    assert result["status"] == "succeeded"
    assert result["collisionStatus"] == "passed"
    assert refreshed["status"] == "succeeded"
    assert refreshed["assemblyStatus"] == "assembled"
    assert refreshed["demoCheckpoint"] == source["demoCheckpoint"]
    assert refreshed["engineeringCheckpoint"]["sourceValidationJobId"] == (
        validation["validationJobId"]
    )
    assert Path(source["demoCheckpoint"]["assemblyPath"]).read_bytes() == before


def test_rejected_validation_preserves_demo_checkpoint(tmp_path: Path):
    assembly_store = DurableAssemblyJobStore(tmp_path / "assembly-jobs")
    validation_store = EngineeringValidationJobStore(tmp_path / "validation-jobs")
    source = source_job(assembly_store, tmp_path)
    evidence = tmp_path / "collision.json"
    evidence.write_text("{}", encoding="utf-8")

    validation = validation_store.create(source)
    result = run_engineering_validation_job(
        validation_store=validation_store,
        assembly_store=assembly_store,
        validation_job_id=validation["validationJobId"],
        hard_gate=lambda *args: {
            "accepted": False,
            "evidencePath": str(evidence),
            "message": "collision",
        },
    )

    refreshed = assembly_store.load(source["jobId"])
    assert result["status"] == "rejected"
    assert refreshed["status"] == "succeeded"
    assert refreshed["assemblyStatus"] == "assembled"
    assert refreshed["collisionStatus"] == "rejected"
    assert refreshed["demoCheckpoint"] == source["demoCheckpoint"]
    assert refreshed["engineeringCheckpoint"] is None
    assert Path(source["demoCheckpoint"]["assemblyPath"]).is_file()


def test_changed_demo_bytes_fail_before_gate(tmp_path: Path):
    assembly_store = DurableAssemblyJobStore(tmp_path / "assembly-jobs")
    validation_store = EngineeringValidationJobStore(tmp_path / "validation-jobs")
    source = source_job(assembly_store, tmp_path)
    validation = validation_store.create(source)
    Path(source["demoCheckpoint"]["assemblyPath"]).write_bytes(b"changed")
    called = False

    def forbidden_gate(*args):
        nonlocal called
        called = True
        return {"accepted": True}

    result = run_engineering_validation_job(
        validation_store=validation_store,
        assembly_store=assembly_store,
        validation_job_id=validation["validationJobId"],
        hard_gate=forbidden_gate,
    )

    assert result["status"] == "failed"
    assert result["collisionStatus"] == "not_evaluated"
    assert called is False
    assert assembly_store.load(source["jobId"])["collisionStatus"] == "not_evaluated"


def test_validation_creation_is_idempotent_for_same_checkpoint(tmp_path: Path):
    assembly_store = DurableAssemblyJobStore(tmp_path / "assembly-jobs")
    validation_store = EngineeringValidationJobStore(tmp_path / "validation-jobs")
    source = source_job(assembly_store, tmp_path)
    first = validation_store.create(source)
    repeated = validation_store.create(source)
    assert repeated["validationJobId"] == first["validationJobId"]
