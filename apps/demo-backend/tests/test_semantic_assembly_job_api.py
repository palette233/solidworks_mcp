from pathlib import Path

from fastapi import BackgroundTasks

import demo_backend.main as api
from demo_backend.models import (
    SemanticAssemblyJobCreateRequest,
    SemanticAssemblySequencePreviewRequest,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, validated_artifact_step_runner
from demo_backend.semantic_assembly_sequence import (
    load_project02_ordered_assembly_closure,
    preview_project02_ordered_assembly,
)


def _artifact(tmp_path: Path, token: str) -> dict:
    assembly = tmp_path / f"{token}.SLDASM"
    assembly.write_bytes(token.encode())
    evidence = tmp_path / f"{token}.json"
    evidence.write_text("{}\n", encoding="utf-8")
    return {
        "moduleToken": token,
        "success": True,
        "assemblyPath": str(assembly),
        "evidencePath": str(evidence),
    }


def test_job_api_create_query_cancel_and_resume(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    closure = {
        "sequence": ["A600", "A800", "A180"],
        "steps": [_artifact(tmp_path, "A800"), _artifact(tmp_path, "A180")]
    }
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    monkeypatch.setattr(api, "load_project02_ordered_assembly_closure", lambda _: closure)

    background = BackgroundTasks()
    request = SemanticAssemblyJobCreateRequest(
        requirement="项目02：先添加A800，再添加A180",
        idempotencyKey="api-test",
    )
    created = api.create_semantic_assembly_job(request, background)
    assert created["status"] == "queued"
    assert len(background.tasks) == 1

    cancelled = api.cancel_semantic_assembly_job(created["jobId"])
    assert cancelled["cancelRequested"] is True
    result = api._run_validated_assembly_job(tmp_path, "project02", created["jobId"])
    assert result is None
    assert api.get_semantic_assembly_job(created["jobId"])["status"] == "cancelled"

    resumed_tasks = BackgroundTasks()
    resumed = api.resume_semantic_assembly_job(created["jobId"], resumed_tasks)
    assert resumed["status"] == "queued"
    assert len(resumed_tasks.tasks) == 1
    api._run_validated_assembly_job(tmp_path, "project02", created["jobId"])
    final = api.get_semantic_assembly_job(created["jobId"])
    assert final["status"] == "succeeded"
    assert [step["status"] for step in final["steps"]] == ["succeeded", "succeeded"]


def test_job_api_pause_request(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    job = store.create(
        {"steps": [{"stepId": "step-01-a800", "moduleToken": "A800"}]},
        execution_mode="test",
    )
    paused = api.pause_semantic_assembly_job(job["jobId"])
    assert paused["pauseRequested"] is True


def test_job_api_rejects_missing_validated_artifact(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    monkeypatch.setattr(
        api,
        "load_project02_ordered_assembly_closure",
        lambda _: {"sequence": ["A600", "A800", "A180"], "steps": [_artifact(tmp_path, "A800")]},
    )
    request = SemanticAssemblyJobCreateRequest(
        requirement="项目02：先添加A800，再添加A180"
    )
    try:
        api.create_semantic_assembly_job(request, BackgroundTasks())
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "A180" in str(exc.detail)
    else:
        raise AssertionError("missing artifact unexpectedly accepted")


def test_single_step_subsequence_is_accepted(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    monkeypatch.setattr(
        api,
        "load_project02_ordered_assembly_closure",
        lambda _: {"sequence": ["A600", "A800"], "steps": [_artifact(tmp_path, "A800")]},
    )
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(requirement="项目02：添加A800"),
        BackgroundTasks(),
    )
    assert [step["moduleToken"] for step in created["steps"]] == ["A800"]


def test_real_validated_seven_module_artifacts_complete_durable_job(tmp_path: Path):
    workspace = Path(__file__).resolve().parents[3]
    closure = load_project02_ordered_assembly_closure(workspace)
    preview = preview_project02_ordered_assembly(
        "项目02：先添加A800，再添加A180，然后添加A700，接着添加A300，再添加A500，最后添加A100"
    )
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(preview["plan"], execution_mode="validated_artifact_replay")
    result = AssemblyJobExecutor(
        store, validated_artifact_step_runner(closure, workspace)
    ).run(job["jobId"])
    assert result["status"] == "succeeded"
    assert len(result["steps"]) == 6
    assert Path(result["lastCommittedCheckpoint"]["assemblyPath"]).is_file()


def test_validated_replay_rejects_nonprefix_that_would_smuggle_modules(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    closure = {
        "sequence": ["A600", "A800", "A180", "A700", "A300", "A500"],
        "steps": [
            _artifact(tmp_path, token)
            for token in ("A800", "A180", "A700", "A300", "A500")
        ],
    }
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    monkeypatch.setattr(api, "load_project02_ordered_assembly_closure", lambda _: closure)
    request = SemanticAssemblyJobCreateRequest(
        requirement="项目02：先添加A800，再添加A180，然后添加A700，最后添加A500"
    )
    try:
        api.create_semantic_assembly_job(request, BackgroundTasks())
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "夹带未请求模组" in str(exc.detail)
    else:
        raise AssertionError("unsafe non-prefix artifact replay unexpectedly accepted")


def test_live_cad_mode_accepts_valid_nonprefix_and_schedules_serial_runner(monkeypatch, tmp_path: Path):
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    closure = {
        "sequence": ["A600", "A800", "A180", "A700", "A300", "A500"],
        "steps": [
            _artifact(tmp_path, token)
            for token in ("A800", "A180", "A700", "A300", "A500")
        ],
    }
    monkeypatch.setattr(api, "_assembly_job_store", lambda _, project_id="project02": store)
    monkeypatch.setattr(api, "load_project02_ordered_assembly_closure", lambda _: closure)
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            requirement="项目02：先添加A800，再添加A180，然后添加A700，最后添加A500",
            executionMode="live_cad",
        ),
        background,
    )
    assert created["executionMode"] == "live_cad"
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job


def test_pipeline_audit_api_reports_complete_static_chain() -> None:
    result = api.get_semantic_assembly_sequence_pipeline_audit()
    assert result["readyForValidatedArtifactReplay"] is True
    assert result["readyForLiveCadExecution"] is True
    assert result["blockingIssues"] == []


def test_dependency_audit_api_keeps_production_boundary_closed() -> None:
    result = api.get_semantic_assembly_sequence_dependency_audit()
    assert result["staticDemoProfileAccepted"] is True
    assert result["productionProfileAccepted"] is False
    assert result["prototypeDependentModuleCount"] == 7
    assert result["parameterAuthorityAudit"]["productionAcceptedRequirementCount"] == 0


def test_project01_preview_uses_versioned_profile_and_current_static_cad_gate() -> None:
    result = api.preview_semantic_assembly_sequence(
        SemanticAssemblySequencePreviewRequest(
            projectId="project01",
            requirement=(
                "项目01：先添加SS00，再添加FF00，然后添加SM00，接着添加GN00，"
                "再添加BD00，然后添加GJ00，最后添加LM00。"
            ),
        )
    )
    assert result["intent"]["schemaVersion"] == "ordered-assembly-command/v2"
    assert result["plan"]["summary"]["orderValid"] is True
    assert result["plan"]["summary"]["missingImplementationCount"] == 0
    assert result["plan"]["executionBoundary"]["safeToStartCad"] is True


def test_project01_live_cad_accepts_only_released_continuous_prefix(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project01-live-jobs")
    tokens = ["SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"]
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api,
        "build_assembly_release_contract",
        lambda *_: {
            "release": {
                "staticDemoAllowed": True,
                "liveCadAllowed": True,
                "productionBlockers": [],
            }
        },
    )
    monkeypatch.setattr(
        api,
        "_project01_live_adapter_release",
        lambda _: {
            "success": True,
            "liveCadApiMayStartForTokens": tokens,
            "status": "CLOSED",
        },
    )
    monkeypatch.setattr(
        api,
        "_load_project_ordered_assembly_closure",
        lambda *_: {
            "success": True,
            "sequence": ["JJ00", *tokens],
            "steps": [_artifact(tmp_path, token) for token in tokens],
        },
    )

    background = BackgroundTasks()
    accepted = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project01",
            requirement="项目01：先添加SS00，再添加FF00",
            executionMode="live_cad",
        ),
        background,
    )
    assert [step["moduleToken"] for step in accepted["steps"]] == ["SS00", "FF00"]
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job

    try:
        api.create_semantic_assembly_job(
            SemanticAssemblyJobCreateRequest(
                projectId="project01",
                requirement="项目01：先添加SS00，再添加SM00",
                executionMode="live_cad",
            ),
            BackgroundTasks(),
        )
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "连续前缀" in str(exc.detail)
    else:
        raise AssertionError("Project01 non-prefix live CAD request was accepted")


def test_project05_validated_artifact_job_runs_full_real_checkpoint_chain(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project05-jobs")
    tokens = ["A000", "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"]
    closure = {
        "success": True,
        "sequence": tokens,
        "steps": [_artifact(tmp_path, token) for token in tokens],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project05",
            requirement=(
                "项目05：先添加D000，再添加K000，然后添加F000，接着添加M000，"
                "再添加G000，然后添加N000，接着添加P000，最后添加B000。"
            ),
        ),
        background,
    )
    assert created["projectId"] == "project05"
    assert created["jobId"].startswith("project05-job-")
    assert len(background.tasks) == 1
    api._run_validated_assembly_job(tmp_path, "project05", created["jobId"])
    final = store.load(created["jobId"])
    assert final["status"] == "succeeded"
    assert [step["moduleToken"] for step in final["steps"]] == tokens[1:]
    assert final["lastCommittedCheckpoint"]["moduleToken"] == "B000"


def test_project05_live_cad_job_schedules_validated_adapter(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project05-live-jobs")
    closure = {
        "success": True,
        "sequence": ["A000", "D000", "K000"],
        "steps": [_artifact(tmp_path, token) for token in ("A000", "D000", "K000")],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    monkeypatch.setattr(
        api,
        "_project05_live_adapter_release",
        lambda _: {"liveCadApiMayStart": True, "status": "CLOSED"},
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project05",
            executionMode="live_cad",
            requirement="项目05：先添加D000，再添加K000。",
        ),
        background,
    )
    assert created["executionMode"] == "live_cad"
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job


def test_project05_live_cad_job_rejects_when_release_closure_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        api,
        "_project05_live_adapter_release",
        lambda _: {
            "liveCadApiMayStart": False,
            "status": "PROJECT05_LIVE_ADAPTER_CLOSURE_INCOMPLETE",
        },
    )
    try:
        api.create_semantic_assembly_job(
            SemanticAssemblyJobCreateRequest(
                projectId="project05",
                executionMode="live_cad",
                requirement="项目05：先添加D000，再添加K000。",
            ),
            BackgroundTasks(),
        )
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "完整动作链发布门禁" in str(exc.detail)
    else:
        raise AssertionError("unreleased project05 live CAD job unexpectedly accepted")


def test_project03_validated_replay_job_uses_new_step_index(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project03-jobs")
    closure = {
        "success": True,
        "sequence": ["AA00", "AE00", "AD00"],
        "steps": [_artifact(tmp_path, token) for token in ("AE00", "AD00")],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project03",
            requirement="项目03：先添加AE00，再添加AD00。",
        ),
        BackgroundTasks(),
    )
    assert created["projectId"] == "project03"
    assert created["jobId"].startswith("project03-job-")


def test_project03_full_live_cad_schedules_closed_chain(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project03-full-live-jobs")
    tokens = ("AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00")
    closure = {
        "success": True,
        "sequence": ["AA00", *tokens],
        "steps": [_artifact(tmp_path, token) for token in tokens],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    monkeypatch.setattr(
        api,
        "_project03_live_adapter_release",
        lambda _: {
            "success": True,
            "liveCadApiMayStartForTokens": list(tokens),
        },
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project03",
            executionMode="live_cad",
            requirement=(
                "项目03：先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，"
                "再添加AH00，然后添加AJ00，最后添加AB00。"
            ),
        ),
        background,
    )

    assert [step["moduleToken"] for step in created["steps"]] == list(tokens)
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job


def test_project03_ae00_live_cad_schedules_pilot_adapter(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project03-live-jobs")
    closure = {
        "success": True,
        "sequence": ["AA00", "AE00"],
        "steps": [_artifact(tmp_path, "AE00")],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    monkeypatch.setattr(
        api,
        "_project03_live_adapter_release",
        lambda _: {
            "success": True,
            "liveCadApiMayStartForTokens": ["AE00"],
        },
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project03",
            executionMode="live_cad",
            requirement="项目03：添加AE00。",
        ),
        background,
    )
    assert created["executionMode"] == "live_cad"
    assert [step["moduleToken"] for step in created["steps"]] == ["AE00"]
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job


def test_project03_ae00_ad00_live_cad_schedules_closed_prefix(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project03-live-jobs")
    closure = {
        "success": True,
        "sequence": ["AA00", "AE00", "AD00"],
        "steps": [_artifact(tmp_path, token) for token in ("AE00", "AD00")],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    monkeypatch.setattr(
        api,
        "_project03_live_adapter_release",
        lambda _: {
            "success": True,
            "liveCadApiMayStartForTokens": ["AE00", "AD00"],
        },
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project03",
            executionMode="live_cad",
            requirement="项目03：先添加AE00，再添加AD00。",
        ),
        background,
    )
    assert [step["moduleToken"] for step in created["steps"]] == ["AE00", "AD00"]
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job


def test_project03_job_is_rejected_before_cad_when_discrete_state_collides() -> None:
    request = SemanticAssemblyJobCreateRequest(
        projectId="project03",
        executionMode="live_cad",
        requirement=(
            "项目03：先添加AE00，再添加AD00，并验证AD20在20度静态状态。"
        ),
    )
    try:
        api.create_semantic_assembly_job(request, BackgroundTasks())
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "动态工艺硬门禁" in str(exc.detail)
        assert "新增叶级实体干涉" in str(exc.detail)
    else:
        raise AssertionError("colliding Project03 AD20 state unexpectedly scheduled")


def test_project03_job_is_rejected_before_cad_for_unverified_continuous_motion() -> None:
    request = SemanticAssemblyJobCreateRequest(
        projectId="project03",
        executionMode="live_cad",
        requirement=(
            "项目03：先添加AE00，再添加AD00，并将AD20从0度翻转到15度。"
        ),
    )
    try:
        api.create_semantic_assembly_job(request, BackgroundTasks())
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "动态工艺硬门禁" in str(exc.detail)
        assert "连续路径安全" in str(exc.detail)
    else:
        raise AssertionError("unverified continuous Project03 motion unexpectedly scheduled")


def test_release_contract_api_exposes_project03_dynamic_hard_gate() -> None:
    contract = api.get_semantic_assembly_sequence_release_contract("project03")
    assert contract["release"]["staticDemoAllowed"] is True
    assert contract["release"]["liveCadAllowed"] is True
    assert contract["release"]["productionAllowed"] is False
    assert contract["dynamic"]["configured"] is True
    assert contract["dynamic"]["continuousPathVerified"] is False
    assert contract["dynamic"]["firstObservedCollisionBracketDegrees"] == [15.0, 16.0]


def test_job_api_rejects_before_queue_when_unified_release_contract_blocks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api,
        "build_assembly_release_contract",
        lambda *_: {
            "release": {
                "staticDemoAllowed": False,
                "liveCadAllowed": False,
                "productionAllowed": False,
                "productionBlockers": ["测试阻塞"],
            }
        },
    )
    try:
        api.create_semantic_assembly_job(
            SemanticAssemblyJobCreateRequest(
                projectId="project02",
                requirement="项目02：先添加A800。",
            ),
            BackgroundTasks(),
        )
    except api.HTTPException as exc:
        assert exc.status_code == 422
        assert "统一发布契约" in str(exc.detail)
    else:
        raise AssertionError("blocked unified release contract unexpectedly queued a job")


def test_project03_four_step_live_cad_schedules_closed_prefix(
    monkeypatch, tmp_path: Path
) -> None:
    store = DurableAssemblyJobStore(tmp_path / "project03-live-jobs")
    tokens = ("AE00", "AD00", "AI00", "AG00")
    closure = {
        "success": True,
        "sequence": ["AA00", *tokens],
        "steps": [_artifact(tmp_path, token) for token in tokens],
    }
    monkeypatch.setattr(
        api, "_assembly_job_store", lambda _, project_id="project02": store
    )
    monkeypatch.setattr(
        api, "_load_project_ordered_assembly_closure", lambda _, __: closure
    )
    monkeypatch.setattr(
        api,
        "_project03_live_adapter_release",
        lambda _: {
            "success": True,
            "liveCadApiMayStartForTokens": list(tokens),
        },
    )
    background = BackgroundTasks()
    created = api.create_semantic_assembly_job(
        SemanticAssemblyJobCreateRequest(
            projectId="project03",
            executionMode="live_cad",
            requirement="项目03：先添加AE00，再添加AD00，然后添加AI00，接着添加AG00。",
        ),
        background,
    )
    assert [step["moduleToken"] for step in created["steps"]] == list(tokens)
    assert len(background.tasks) == 1
    assert background.tasks[0].func is api._run_live_cad_assembly_job
