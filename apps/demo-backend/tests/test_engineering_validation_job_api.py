from pathlib import Path

from fastapi import BackgroundTasks

from demo_backend import main as api
from demo_backend.engineering_validation_jobs import EngineeringValidationJobStore
from demo_backend.models import EngineeringValidationJobCreateRequest
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


def test_api_schedules_independent_validation_without_changing_source(monkeypatch, tmp_path: Path):
    assembly_store = DurableAssemblyJobStore(tmp_path / "assembly-jobs")
    validation_store = EngineeringValidationJobStore(tmp_path / "validation-jobs")
    assembly = tmp_path / "demo.SLDASM"
    evidence = tmp_path / "demo.json"
    assembly.write_bytes(b"demo")
    evidence.write_text("{}", encoding="utf-8")
    source = assembly_store.create(
        {
            "projectId": "project02",
            "validationProfile": "demo",
            "steps": [{"stepId": "step-01", "moduleToken": "A800"}],
        },
        execution_mode="live_cad",
    )
    checkpoint = {
        "stepId": "step-01",
        "moduleToken": "A800",
        "assemblyPath": str(assembly.resolve()),
        "evidencePath": str(evidence.resolve()),
        "committedAt": "2026-10-09T00:00:00Z",
    }
    source.update(
        {
            "status": "succeeded",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "lastCommittedCheckpoint": checkpoint,
            "demoCheckpoint": checkpoint,
        }
    )
    assembly_store.save(source)
    monkeypatch.setattr(api, "_assembly_job_store", lambda workspace, project_id: assembly_store)
    monkeypatch.setattr(
        api, "_engineering_validation_store", lambda workspace, project_id: validation_store
    )

    background = BackgroundTasks()
    response = api.create_engineering_validation_job_api(
        source["jobId"],
        EngineeringValidationJobCreateRequest(
            confirmed=True, idempotencyKey="independent-validation-test"
        ),
        background,
    )

    assert response["executionScheduled"] is True
    assert response["sourceDemoPreserved"] is True
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_project02_engineering_validation
    assert assembly_store.load(source["jobId"])["status"] == "succeeded"
    loaded = api.get_engineering_validation_job_api(
        response["validationJob"]["validationJobId"]
    )
    assert loaded["sourceJobId"] == source["jobId"]
