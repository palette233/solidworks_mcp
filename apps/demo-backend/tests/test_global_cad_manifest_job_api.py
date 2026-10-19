from pathlib import Path

from fastapi import BackgroundTasks

from demo_backend import main
from demo_backend.models import (
    GlobalCadManifestJobCreateRequest,
    GlobalCadManifestJobStartRequest,
    GlobalIndependentCadJobCreateRequest,
    GlobalNaturalLanguageManifestJobRequest,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json"
)


def test_natural_language_manifest_request_preserves_release_binding():
    request = GlobalNaturalLanguageManifestJobRequest(
        contextId="release-bound-natural-language-test",
        requirements=["建立固定安装环境", "安装扫描模组"],
        releaseManifestPath="demo/releases/example/release-manifest.json",
        autoOrderByReleasedDependencies=True,
    )

    payload = request.model_dump(by_alias=True, exclude_none=True)

    assert payload["releaseManifestPath"] == (
        "demo/releases/example/release-manifest.json"
    )
    assert "catalogPath" not in payload
    assert payload["autoOrderByReleasedDependencies"] is True


def test_manifest_job_api_create_status_and_schedule(tmp_path, monkeypatch):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(main, "_global_manifest_job_store", lambda workspace: store)
    monkeypatch.setattr(main, "bind_conversation_job", lambda *args: None)
    created = main.create_global_cad_manifest_job_api(
        GlobalCadManifestJobCreateRequest(
            manifestPath=str(MANIFEST),
            packetLimit=2,
            idempotencyKey="api-create-status",
        )
    )
    assert created["status"] == "queued"
    assert created["progress"]["totalSteps"] == 2
    assert created["collisionStatus"] == "not_evaluated"

    loaded = main.get_global_cad_manifest_job_api(created["jobId"])
    assert loaded["jobId"] == created["jobId"]
    assert loaded["events"][0]["eventType"] == "job-created"

    tasks = BackgroundTasks()
    scheduled = main.start_global_cad_manifest_job_api(
        created["jobId"],
        GlobalCadManifestJobStartRequest(timeoutSeconds=120),
        tasks,
    )
    assert scheduled["status"] == "queued"
    assert len(tasks.tasks) == 1
    persisted = store.load(created["jobId"])
    assert persisted["startRequestedAt"] is not None

    duplicate_tasks = BackgroundTasks()
    main.start_global_cad_manifest_job_api(
        created["jobId"],
        GlobalCadManifestJobStartRequest(timeoutSeconds=120),
        duplicate_tasks,
    )
    assert len(duplicate_tasks.tasks) == 0


def test_manifest_job_api_pause_and_resume_schedule(tmp_path, monkeypatch):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(main, "_global_manifest_job_store", lambda workspace: store)
    created = main.create_global_cad_manifest_job_api(
        GlobalCadManifestJobCreateRequest(
            manifestPath=str(MANIFEST),
            packetLimit=1,
            idempotencyKey="api-pause-resume",
        )
    )
    paused_job = store.load(created["jobId"])
    paused_job["status"] = "paused"
    paused_job["assemblyStatus"] = "paused"
    paused_job["pauseRequested"] = True
    store.save(paused_job)

    tasks = BackgroundTasks()
    resumed = main.resume_global_cad_manifest_job_api(
        created["jobId"],
        GlobalCadManifestJobStartRequest(timeoutSeconds=120),
        tasks,
    )
    assert resumed["status"] == "queued"
    assert resumed["pauseRequested"] is False
    assert len(tasks.tasks) == 1


def test_release_bound_context_prepares_independent_job_without_starting_cad(
    tmp_path, monkeypatch
):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(main, "_global_manifest_job_store", lambda workspace: store)
    monkeypatch.setattr(main, "bind_conversation_job", lambda *args: None)

    result = main.prepare_global_independent_cad_job_api(
        "project02-release-a800-a180-v2",
        GlobalIndependentCadJobCreateRequest(
            confirmed=True,
            packetLimit=2,
            idempotencyKey="independent-a800-a180",
        ),
    )

    assert result["preparedOnly"] is True
    assert result["executionStarted"] is False
    assert result["solidWorksStarted"] is False
    assert result["assemblyMode"] == "mate_driven_port_assembly"
    assert result["portable"] is True
    assert result["manifest"]["planningMode"] == (
        "project_independent_semantic_graph"
    )
    assert result["manifest"]["packetCount"] == 2
    assert Path(result["transactionDagPath"]).is_file()
    assert result["job"]["status"] == "queued"
    assert result["job"]["startRequestedAt"] is None
    assert result["job"]["progress"]["totalSteps"] == 2
    assert store.load(result["job"]["jobId"])["executionMode"] == (
        "generic_cad_manifest"
    )
    assert store.load(result["job"]["jobId"])["plan"]["contextRevision"] == 3
    assert store.load(result["job"]["jobId"])["plan"]["commandAudit"][
        "status"
    ] == "complete"


def test_manifest_job_routes_are_exposed_in_openapi():
    paths = main.app.openapi()["paths"]
    assert "/api/demo/global-cad-manifest-jobs" in paths
    assert "/api/demo/global-cad-manifest-jobs/compile-natural-language" in paths
    assert "/api/demo/global-cad-manifest-jobs/{job_id}" in paths
    assert "/api/demo/global-cad-manifest-jobs/{job_id}/start" in paths
    assert "/api/demo/global-cad-manifest-jobs/{job_id}/pause" in paths
    assert "/api/demo/global-cad-manifest-jobs/{job_id}/resume" in paths
    assert (
        "/api/demo/global-assembly-contexts/{context_id}/independent-cad-jobs"
        in paths
    )
