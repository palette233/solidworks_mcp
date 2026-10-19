from __future__ import annotations

from pathlib import Path
import hashlib
import json
import threading

from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .adapters.llm_client import LlmClient
from .adapters.mcp_client import McpClient
from .config import Settings, get_settings
from .face_mappings import FaceMappingStore
from .layout_preview import (
    LayoutPreviewError,
    approve_case_preview,
    load_case_preview,
    load_case_verification_plan,
    solve_case_preview,
)
from .project02_ablation import load_dependency_ablation_bundle
from .models import (
    ApplyLayoutRequest,
    CaptureProjectLayoutRequest,
    DemoState,
    GenerateConstraintLayoutRequest,
    DiscoverComponentsRequest,
    LayoutJsonInfo,
    McpHealthResult,
    OperationResult,
    ApplyCapturedLayoutRequest,
    RecordSelectedFaceRequest,
    ProjectModuleConfirmationRequest,
    ProjectRequirementRequest,
    SelectLayoutJsonRequest,
    SyncDiscoveredComponentsRequest,
    UploadLayoutJsonRequest,
    HighlightFaceEndpointRequest,
    FaceMatePatchApplyRequest,
    FaceMatePatchPreviewRequest,
    SemanticConnectionApplyRequest,
    SemanticConnectionPreviewRequest,
    SemanticAssemblyIntentPreviewRequest,
    SemanticAssemblySequencePreviewRequest,
    SemanticAssemblyJobCreateRequest,
    GlobalAssemblyContextCreateRequest,
    GlobalCatalogMigrationPreviewRequest,
    GlobalCatalogMigrationCommitRequest,
    GlobalPortableReleaseCommitRequest,
    GlobalRelationEditPreviewRequest,
    GlobalRelationEditApplyRequest,
    GlobalModuleSelectionReadinessRequest,
    CrossProjectModuleSubstitutionPreviewRequest,
    GlobalRelationIntentPreviewRequest,
    GlobalRelationDrivingPreflightRequest,
    GlobalAssemblyCommandPreviewRequest,
    GlobalAssemblyCommandApplyRequest,
    GlobalAssemblyCommandUndoRequest,
    GlobalAssemblyCommandSequenceRequest,
    GlobalCadManifestJobCreateRequest,
    GlobalCadManifestJobStartRequest,
    GlobalIndependentCadJobCreateRequest,
    GlobalNaturalLanguageManifestJobRequest,
    GlobalProjectAdapterJobCreateRequest,
    GlobalProjectAdapterJobStartRequest,
    ResolvedPairTransactionJobCreateRequest,
    ResolvedPairTransactionJobStartRequest,
    EngineeringValidationJobCreateRequest,
    TemporarySemanticPortCaptureRequest,
    TemporaryConnectionPreviewRequest,
    CheckpointMateGraphExportRequest,
    CheckpointTemporaryMateCompileRequest,
    DirectMateExecutionBindRequest,
    HistoricalCheckpointPreviewRequest,
    HistoricalCheckpointImportRequest,
    ToolCallPlan,
)
from .mate_face_workbench import (
    MateFaceWorkbenchError,
    build_face_mate_patch_preview,
    finalize_face_mate_patch_application,
    load_face_endpoint_workbench,
    prepare_face_mate_patch_application,
)
from .semantic_port_workbench import (
    SemanticPortWorkbenchError,
    finalize_semantic_connection_application,
    load_semantic_port_workbench,
    prepare_semantic_connection_application,
    preview_semantic_connection,
    preview_semantic_assembly_intent,
)
from .semantic_assembly_sequence import (
    SemanticAssemblySequenceError,
    load_project02_ordered_assembly_closure,
    preview_project02_ordered_assembly,
    run_project02_validated_demo,
)
from .ordered_assembly_planner import (
    OrderedAssemblyPlannerError,
    preview_ordered_assembly,
)
from .project_assembly_profile import load_project_assembly_profile
from .semantic_assembly_jobs import (
    AssemblyJobError,
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
    utc_now,
    validated_artifact_step_runner,
)
from .global_project_adapter_plan import (
    build_checkpoint_continuation_plan,
    build_direct_edit_checkpoint_continuation_plan,
    create_seeded_durable_job,
)
from .resolved_pair_transaction_jobs import (
    ResolvedPairTransactionJobError,
    compile_connection_pair_plan,
    create_connection_pair_job,
    pair_transaction_job_store,
    run_connection_pair_job,
    sha256_file as resolved_pair_sha256_file,
)
from .semantic_assembly_cad_runner import live_cad_step_runner
from .project05_semantic_assembly_cad_runner import project05_live_cad_step_runner
from .project03_semantic_assembly_cad_runner import project03_live_cad_step_runner
from .project01_semantic_assembly_cad_runner import project01_live_cad_step_runner
from .semantic_assembly_collision_gate import (
    canonical_pair as collision_pair,
    live_pair_local_collision_hard_gate,
    module_token as collision_module_token,
)
from .global_assembly_workbench import (
    GlobalAssemblyWorkbenchError,
    apply_command as apply_global_assembly_command,
    apply_command_sequence as apply_global_assembly_command_sequence,
    undo_latest_command as undo_latest_global_assembly_command,
    create_context as create_global_assembly_context,
    load_context as load_global_assembly_context,
    load_global_catalog,
    load_module_port_coverage,
    assess_module_selection,
    preview_command as preview_global_assembly_command,
    search_modules as search_global_modules,
    compile_execution_manifest as compile_global_assembly_execution_manifest,
    compile_project_adapter_plan as compile_global_project_adapter_plan,
    compile_transaction_dag as compile_global_assembly_transaction_dag,
    compile_cad_transaction_manifest as compile_global_cad_transaction_manifest,
    context_path as global_context_path,
    preview_catalog_migration,
    commit_catalog_migration,
    preview_portable_release_upgrade,
    commit_portable_release_upgrade,
    preview_relation_edit,
    apply_relation_edit,
    describe_released_relation_catalog,
    load_released_relation_catalog,
    preview_released_relation_intent,
    preflight_released_driving_relation,
)
from .global_cad_manifest_orchestrator import (
    GlobalCadManifestOrchestrationError,
    build_manifest_job_plan,
    manifest_cad_step_runner,
    manifest_job_status_view,
    run_manifest_job,
    validate_seed_evidence,
    write_manifest_job_artifacts,
)
from .global_natural_language_manifest import (
    GlobalNaturalLanguageManifestError,
    compile_natural_language_manifest_job,
)
from .global_relation_semantics import (
    build_relation_capability_matrix,
)
from .cross_project_module_substitution import (
    CrossProjectModuleSubstitutionError,
    build_module_role_overlay,
    compile_substitution_preview,
)
from .assembly_pipeline_audit import audit_project02_assembly_pipeline
from .assembly_release_contract import build_assembly_release_contract
from .engineering_validation_jobs import (
    EngineeringValidationJobStore,
    run_engineering_validation_job,
)
from .assembly_conversation import (
    AssemblyConversationError,
    bind_direct_mate_execution,
    bind_job as bind_conversation_job,
    conversation_snapshot,
    find_direct_mate_execution,
)
from .temporary_semantic_ports import (
    TemporarySemanticPortError,
    load_temporary_ports,
    parse_active_assembly_path,
    parse_captured_endpoint,
    preview_temporary_connection,
    register_captured_face,
    registry_path as temporary_port_registry_path,
    endpoint_catalog_path as temporary_endpoint_catalog_path,
)
from .checkpoint_mate_graph_adapter import (
    CheckpointMateGraphAdapterError,
    build_checkpoint_graph_export_spec,
    compile_temporary_connection_for_checkpoint,
    finalize_checkpoint_graph_export,
    load_checkpoint_graph_binding,
)
from .historical_checkpoint_import import (
    HistoricalCheckpointImportError,
    build_historical_checkpoint_import_assessment,
    commit_historical_checkpoint_import,
    infer_component_inventory_path,
)
from .prototype_dependency_audit import audit_project_profile_dependencies
from .project02_requirements import confirm_project02_modules, recommend_project02_modules
from .project_migration import (
    load_project01_migration_readiness,
    load_project03_migration_readiness,
)
from .project05_migration import load_project05_migration_readiness
from .services.demo_service import DemoService
from .state_store import DemoStateStore


def create_service(settings: Settings) -> DemoService:
    store = DemoStateStore(settings.resolved_state_path, settings.resolved_asset_dir)
    face_mappings = FaceMappingStore(settings.resolved_face_mapping_path)
    llm = LlmClient(settings.llm_mode)
    mcp = McpClient(
        mode=settings.mcp_mode,
        command=settings.mcp_command,
        args=settings.mcp_args,
        cwd=settings.resolved_mcp_cwd,
        pipe_name=settings.mcp_pipe_name,
        timeout_seconds=settings.mcp_timeout_seconds,
    )
    return DemoService(
        store,
        face_mappings,
        llm,
        mcp,
        replay_xy_tolerance_meters=settings.replay_xy_tolerance_meters,
        replay_theta_tolerance_degrees=settings.replay_theta_tolerance_degrees,
        initialize_batch_size=settings.initialize_batch_size,
        target_assembly_path=settings.resolved_target_assembly_path,
    )


def get_service(settings: Settings = Depends(get_settings)) -> DemoService:
    return create_service(settings)


app = FastAPI(title="SolidWorks Demo Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_live_cad_job_lock = threading.Lock()


def _global_manifest_job_store(workspace: Path) -> DurableAssemblyJobStore:
    return DurableAssemblyJobStore(
        workspace / "demo" / "global_assembly_contexts" / "manifest_jobs"
    )


def _workspace_file(workspace: Path, value: str, *, label: str) -> Path:
    candidate = Path(value)
    result = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        result.relative_to(workspace.resolve())
    except ValueError as exc:
        raise GlobalCadManifestOrchestrationError(f"{label}必须位于当前工作区内。") from exc
    return result


def _run_global_manifest_job(
    workspace: Path,
    job_id: str,
    *,
    timeout_seconds: int,
    pause_after_packet: str | None,
    fail_before_packet: str | None,
) -> None:
    """Serialize live SolidWorks work while leaving status reads non-blocking."""

    store = _global_manifest_job_store(workspace)
    runner = manifest_cad_step_runner(
        workspace,
        store,
        timeout_seconds=timeout_seconds,
        pause_after_packet=pause_after_packet,
        fail_before_packet=fail_before_packet,
    )
    with _live_cad_job_lock:
        run_manifest_job(store, job_id, runner)


def _normalize_job_project_id(project_id: str) -> str:
    value = str(project_id or "").strip().lower()
    if value.isdigit():
        value = f"project{value.zfill(2)}"
    if not value.startswith("project") or not value.replace("-", "").replace("_", "").isalnum():
        raise AssemblyJobError(f"非法作业项目编号：{project_id!r}")
    return value


def _project_id_from_job_id(job_id: str) -> str:
    prefix, separator, _ = str(job_id or "").partition("-job-")
    if not separator:
        raise AssemblyJobError(f"无法从作业编号识别项目：{job_id}")
    return _normalize_job_project_id(prefix)


def _assembly_job_store(
    workspace: Path, project_id: str = "project02"
) -> DurableAssemblyJobStore:
    project_id = _normalize_job_project_id(project_id)
    return DurableAssemblyJobStore(
        workspace / f"demo/semantic_ports/{project_id}_ordered_jobs"
    )


def _engineering_validation_store(
    workspace: Path, project_id: str
) -> EngineeringValidationJobStore:
    return EngineeringValidationJobStore(
        _assembly_job_store(workspace, project_id).root / "_engineering_validations"
    )


def _project_id_from_engineering_validation_job_id(validation_job_id: str) -> str:
    prefix, separator, _ = str(validation_job_id or "").partition(
        "-engineering-validation-"
    )
    if not separator:
        raise AssemblyJobError(
            f"无法从工程验证任务编号识别项目：{validation_job_id}"
        )
    return _normalize_job_project_id(prefix)


def _load_project_ordered_assembly_closure(
    workspace: Path, project_id: str
) -> dict:
    project_id = _normalize_job_project_id(project_id)
    if project_id == "project02":
        return load_project02_ordered_assembly_closure(workspace)
    profile = load_project_assembly_profile(project_id)
    relative_path = str((profile.get("artifacts") or {}).get("orderedClosure") or "")
    if not relative_path:
        raise AssemblyJobError(f"{project_id}未配置有序装配闭包。")
    path = (workspace / relative_path).resolve()
    if not path.is_file():
        raise AssemblyJobError(f"{project_id}有序装配闭包不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("success") is not True:
        raise AssemblyJobError(f"{project_id}有序装配闭包尚未通过：{path}")
    return payload


def _run_validated_assembly_job(
    workspace: Path, project_id: str, job_id: str
) -> None:
    project_id = _normalize_job_project_id(project_id)
    store = _assembly_job_store(workspace, project_id)
    closure = _load_project_ordered_assembly_closure(workspace, project_id)
    executor = AssemblyJobExecutor(
        store,
        validated_artifact_step_runner(closure, workspace),
    )
    executor.run(job_id)


def _baseline_map_from_cache(cache_path: Path) -> dict[tuple[str, str], Path]:
    if not cache_path.is_file():
        return {}
    import json

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], Path] = {}
    for row in payload.get("entries") or []:
        baseline = row.get("baselinePath")
        sources = row.get("sources") or []
        if baseline and len(sources) == 2:
            first_name = str(sources[0]["componentName"])
            second_name = str(sources[1]["componentName"])
            baseline_path = Path(str(baseline))
            result[collision_pair(first_name, second_name)] = baseline_path
            first_token = collision_module_token(first_name)
            second_token = collision_module_token(second_name)
            if first_token and second_token:
                token_pair = collision_pair(first_token, second_token)
                existing = result.get(token_pair)
                if existing is None or existing == baseline_path:
                    result[token_pair] = baseline_path
    return result


def _project05_live_adapter_release(workspace: Path) -> dict:
    path = workspace / (
        "demo/semantic_ports/project05_live_adapter_jobs/"
        "project05_live_adapter_closure.json"
    )
    if not path.is_file():
        return {
            "liveCadApiMayStart": False,
            "status": "PROJECT05_LIVE_ADAPTER_CLOSURE_MISSING",
            "path": str(path),
        }
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["path"] = str(path)
    return payload


def _project03_live_adapter_release(workspace: Path) -> dict:
    path = workspace / (
        "demo/semantic_ports/project03_live_adapter_full_jobs/"
        "project03_full_live_adapter_closure.json"
    )
    if not path.is_file():
        return {
            "success": False,
            "liveCadApiMayStartForTokens": [],
            "status": "PROJECT03_FULL_LIVE_ADAPTER_CLOSURE_MISSING",
            "path": str(path),
        }
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["path"] = str(path)
    return payload


def _project01_live_adapter_release(workspace: Path) -> dict:
    path = workspace / (
        "demo/semantic_ports/project01_live_adapter_full_jobs/"
        "project01_full_live_adapter_closure.json"
    )
    if not path.is_file():
        return {
            "success": False,
            "liveCadApiMayStartForTokens": [],
            "status": "PROJECT01_FULL_LIVE_ADAPTER_CLOSURE_MISSING",
            "path": str(path),
        }
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["path"] = str(path)
    return payload


def _project01_static_baselines(workspace: Path) -> dict[tuple[str, str], Path]:
    """Return Project01 prototype pairs accepted under a no-new-interference policy."""
    baseline_root = workspace / (
        "demo/semantic_ports/project01_LM00_ZZ00_static_context_v1/"
        "prototype_brep_baseline"
    )
    gj00_jj00_root = workspace / (
        "demo/semantic_ports/project01_live_adapter_full_jobs/"
        "prototype_baseline_gj00_jj00_v1"
    )
    return {
        collision_pair("GN00", "LM00"): baseline_root
        / "FL9C24N074AA00.001_leaf_details_FL9C24N074GN00_FL9C24N074ZZ00.json",
        collision_pair("JJ00", "LM00"): baseline_root
        / "FL9C24N074AA00.001_leaf_details_FL9C24N074JJ00_FL9C24N074LM00.json",
        collision_pair("GJ00", "JJ00"): gj00_jj00_root
        / "FL9C24N074AA00.001_leaf_details_FL9C24N074GJ00_FL9C24N074JJ00.json",
    }


def _run_live_cad_assembly_job(
    workspace: Path, project_id: str, job_id: str
) -> None:
    project_id = _normalize_job_project_id(project_id)
    if project_id not in {"project01", "project02", "project03", "project05"}:
        raise AssemblyJobError(
            f"{project_id}尚未实现现场CAD逐步动作适配器；只能使用已验证工件回放。"
        )
    with _live_cad_job_lock:
        store = _assembly_job_store(workspace, project_id)
        job = store.load(job_id)
        required_order = [
            str(step.get("moduleToken")) for step in job.get("steps") or []
        ]
        required_tokens = set(required_order)
        if project_id == "project01":
            release = _project01_live_adapter_release(workspace)
            released_prefix = [
                str(token)
                for token in release.get("liveCadApiMayStartForTokens") or []
            ]
            if (
                release.get("success") is not True
                or not required_order
                or required_order != released_prefix[: len(required_order)]
            ):
                raise AssemblyJobError(
                    "项目01现场CAD只允许已完成单一持久化作业闭环的"
                    "SS00→FF00→SM00→GN00→BD00→GJ00→LM00连续前缀。"
                )
            cache_path = workspace / (
                "demo/semantic_ports/project01_live_adapter_full_jobs/"
                "pair_brep_cache_manifest_v1.json"
            )
            runtime = workspace / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
            baselines = _project01_static_baselines(workspace)
            missing_baselines = [path for path in baselines.values() if not path.is_file()]
            if missing_baselines:
                raise AssemblyJobError(
                    "项目01原型碰撞基线不存在："
                    + "、".join(str(path) for path in missing_baselines)
                )
            gate = live_pair_local_collision_hard_gate(
                store=store,
                workspace=workspace,
                executable=runtime,
                cache_manifest_path=cache_path,
                accepted_baselines=baselines,
                step_member_tokens={
                    "SS00": {"SS00"},
                    "FF00": {"FF00"},
                    "SM00": {"SM00"},
                    "GN00": {"GN00"},
                    "BD00": {"BD00"},
                    "GJ00": {"GJ00"},
                    "LM00": {"LM00", "ZZ00"},
                },
                accepted_contact_token_pairs={
                    collision_pair("JJ00", "SS00"),
                    collision_pair("JJ00", "FF00"),
                },
            )
            runner = project01_live_cad_step_runner(
                store=store,
                workspace=workspace,
                executable=runtime,
                hard_gate=gate,
            )
            AssemblyJobExecutor(store, runner).run(job_id)
            return
        if project_id == "project03":
            release = _project03_live_adapter_release(workspace)
            released_prefix = [
                str(token)
                for token in release.get("liveCadApiMayStartForTokens") or []
            ]
            if (
                release.get("success") is not True
                or not required_order
                or required_order != released_prefix[: len(required_order)]
            ):
                raise AssemblyJobError(
                    "项目03现场CAD只允许已完成单一持久化作业闭环的"
                    "AE00→AD00→AI00→AG00→AH00→AJ00→AB00连续前缀。"
                )
            cache_path = workspace / (
                "demo/semantic_ports/project03_live_adapter_four_step_jobs/"
                "pair_brep_cache_manifest_v3.json"
            )
            runtime = workspace / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
            gate = live_pair_local_collision_hard_gate(
                store=store,
                workspace=workspace,
                executable=runtime,
                cache_manifest_path=cache_path,
                accepted_baselines=_baseline_map_from_cache(cache_path),
                step_member_tokens={
                    "AE00": {"AE00"},
                    "AD00": {"AD00"},
                    "AI00": {"AI00"},
                    "AG00": {"AG00"},
                    "AH00": {"AH00"},
                    "AJ00": {"AJ00"},
                    "AB00": {"AB00", "AC00"},
                },
                accepted_contact_token_pairs={
                    collision_pair("AA00", "AE00"),
                    collision_pair("AA00", "AD00"),
                    collision_pair("AA00", "AI00"),
                    collision_pair("AA00", "AG00"),
                    collision_pair("AA00", "AH00"),
                    collision_pair("AA00", "AJ00"),
                },
            )
            runner = project03_live_cad_step_runner(
                store=store,
                workspace=workspace,
                executable=runtime,
                hard_gate=gate,
            )
            AssemblyJobExecutor(store, runner).run(job_id)
            return
        if project_id == "project05":
            closure = _load_project_ordered_assembly_closure(workspace, project_id)
            cache_path = workspace / (
                "demo/semantic_ports/project05_ordered_jobs/"
                "pair_brep_cache_manifest_v3.json"
            )
            runtime = workspace / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
            step_members = {
                token: {token}
                for token in ("D000", "K000", "F000", "M000", "G000", "N000", "P000")
            }
            step_members["B000"] = {"B000", "Z000"}
            contacts = {
                tuple(sorted((frame, module)))
                for frame in ("A000", "E000")
                for module in (
                    "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000", "Z000"
                )
            }
            contacts.add(tuple(sorted(("B000", "Z000"))))
            gate = live_pair_local_collision_hard_gate(
                store=store,
                workspace=workspace,
                executable=runtime,
                cache_manifest_path=cache_path,
                accepted_baselines=_baseline_map_from_cache(cache_path),
                step_member_tokens=step_members,
                accepted_contact_token_pairs=contacts,
            )
            runner = project05_live_cad_step_runner(
                store=store,
                closure=closure,
                workspace=workspace,
                executable=runtime,
                hard_gate=gate,
            )
            AssemblyJobExecutor(store, runner).run(job_id)
            return
        closure = load_project02_ordered_assembly_closure(workspace)
        cache_path = workspace / (
            "demo/semantic_ports/project02_full_machine_increment_v1/"
            "pair_brep_cache_manifest_v3.json"
        )
        runtime = workspace / "demo/runtime/project02_full_machine_20260930_v2/SolidWorksMcpApp.exe"
        gate = live_pair_local_collision_hard_gate(
            store=store,
            workspace=workspace,
            executable=runtime,
            cache_manifest_path=cache_path,
            accepted_baselines=_baseline_map_from_cache(cache_path),
        )
        runner = live_cad_step_runner(
            store=store,
            closure=closure,
            workspace=workspace,
            executable=runtime,
            hard_gate=gate,
            required_tokens=required_tokens,
        )
        AssemblyJobExecutor(store, runner).run(job_id)


def _run_scheduled_global_adapter_job(
    workspace: Path, project_id: str, job_id: str
) -> None:
    """Fail closed when runner initialization fails before the executor starts."""
    try:
        _run_live_cad_assembly_job(workspace, project_id, job_id)
    except Exception as exc:
        store = _assembly_job_store(workspace, project_id)
        job = store.load(job_id)
        if job.get("status") in {"queued", "running"}:
            job["status"] = "failed"
            job["completedAt"] = utc_now()
            job["error"] = f"CAD runner启动前失败：{exc}"
            job["rollback"] = {
                "mode": "restore-last-committed-checkpoint",
                "checkpoint": job.get("lastCommittedCheckpoint"),
                "uncommittedOutputAccepted": False,
                "quarantinedArtifactPath": None,
            }
            store.save(job)
            store.append_event(
                job_id,
                "job-start-failed",
                error=str(exc),
                checkpoint=job.get("lastCommittedCheckpoint"),
            )
            from .assembly_evidence_manifest import write_job_evidence_manifest

            write_job_evidence_manifest(job, store._dir(job_id))


def _run_scheduled_resolved_pair_job(
    workspace: Path, project_id: str, job_id: str
) -> None:
    """Run one real pair transaction serially and fail closed before CAD startup."""
    try:
        with _live_cad_job_lock:
            run_connection_pair_job(workspace, project_id, job_id)
    except Exception as exc:
        store = pair_transaction_job_store(workspace, project_id)
        job = store.load(job_id)
        if job.get("status") in {"queued", "running"}:
            job["status"] = "failed"
            job["assemblyStatus"] = "failed"
            job["completedAt"] = utc_now()
            job["error"] = f"真实配合对事务启动失败：{exc}"
            job["rollback"] = {
                "mode": "reject-unpublished-pair-transaction",
                "checkpoint": job.get("lastCommittedCheckpoint"),
                "uncommittedOutputAccepted": False,
            }
            store.save(job)
            store.append_event(job_id, "job-start-failed", error=str(exc))
            from .assembly_evidence_manifest import write_job_evidence_manifest

            write_job_evidence_manifest(job, store._dir(job_id))


def _run_project02_engineering_validation(
    workspace: Path, validation_job_id: str
) -> None:
    """Run full static validation against one immutable Project02 Demo checkpoint."""

    with _live_cad_job_lock:
        project_id = "project02"
        assembly_store = _assembly_job_store(workspace, project_id)
        validation_store = _engineering_validation_store(workspace, project_id)
        cache_path = workspace / (
            "demo/semantic_ports/project02_full_machine_increment_v1/"
            "pair_brep_cache_manifest_v3.json"
        )
        runtime = workspace / (
            "demo/runtime/project02_full_machine_20260930_v2/SolidWorksMcpApp.exe"
        )
        gate = live_pair_local_collision_hard_gate(
            store=assembly_store,
            workspace=workspace,
            executable=runtime,
            cache_manifest_path=cache_path,
            accepted_baselines=_baseline_map_from_cache(cache_path),
            step_member_tokens={
                "FULL": {
                    "A600",
                    "A800",
                    "A180",
                    "A700",
                    "A300",
                    "A500",
                    "A100",
                    "A200",
                    "T401",
                }
            },
        )
        run_engineering_validation_job(
            validation_store=validation_store,
            assembly_store=assembly_store,
            validation_job_id=validation_job_id,
            hard_gate=gate,
        )


def _validate_current_global_adapter_job(
    workspace: Path,
    context_id: str,
    context: dict,
    project_id: str,
    store: DurableAssemblyJobStore,
    job: dict,
    expected_step_count: int,
) -> None:
    """Revalidate a queued or resumable job against the current graph and seed."""

    plan = job.get("plan") or {}
    if plan.get("contextId") != context_id or plan.get("contextDigest") != context["contextDigest"]:
        raise AssemblyJobError("任务并非由当前上下文及修订创建。")
    if job.get("executionMode") != "live_cad":
        raise AssemblyJobError("全局项目适配任务必须使用live_cad执行模式。")
    if len(job.get("steps") or []) != expected_step_count:
        raise AssemblyJobError("任务步骤数与二次确认值不一致。")
    current_plan = compile_global_project_adapter_plan(
        workspace,
        context_id,
        assembly_mode=str(plan.get("assemblyMode") or "mate_driven_port_assembly"),
    )
    scope = plan.get("executionScope") or {}
    start_index = int(scope.get("startStepIndex") or 0)
    current_slice = [
        (str(step["stepId"]), str(step["moduleToken"]))
        for step in (current_plan.get("steps") or [])[
            start_index : start_index + expected_step_count
        ]
    ]
    queued_steps = [
        (str(step["stepId"]), str(step["moduleToken"]))
        for step in job.get("steps") or []
    ]
    if current_plan.get("safeToCreateDurableJob") is not True or queued_steps != current_slice:
        raise AssemblyJobError("当前项目适配计划与任务步骤范围不一致。")
    seed = plan.get("seedCheckpoint") or {}
    for field in ("assemblyPath", "evidencePath"):
        if not Path(str(seed.get(field) or "")).is_file():
            raise AssemblyJobError(f"任务检查点{field}已经不存在。")
    seed_job_id = str(scope.get("seedJobId") or "")
    if seed_job_id:
        seed_job = store.load(seed_job_id)
        seed_checkpoint = seed_job.get("lastCommittedCheckpoint") or {}
        if seed_job.get("status") != "succeeded":
            raise AssemblyJobError("续跑来源任务不再处于成功状态。")
        for field in ("stepId", "moduleToken", "assemblyPath", "evidencePath"):
            if str(seed_checkpoint.get(field) or "") != str(seed.get(field) or ""):
                raise AssemblyJobError("续跑来源任务的最后检查点已经变化。")
    release = build_assembly_release_contract(workspace, project_id)
    if release["release"]["liveCadAllowed"] is not True:
        raise AssemblyJobError(f"{project_id}统一发布契约已撤销现场CAD许可。")


def _validate_current_resolved_pair_job(
    workspace: Path,
    context_id: str,
    connection_id: str,
    job: dict,
    expected_context_digest: str,
    expected_plan_digest: str,
) -> None:
    """Bind execution to the reviewed connection, graph revision, plan and source file."""
    plan = job.get("plan") or {}
    expected_mode = (
        "independent_context_insert"
        if plan.get("executionStrategy") == "independent_context_insert"
        else "resolved_pair_direct_mate"
    )
    if job.get("executionMode") != expected_mode:
        raise ResolvedPairTransactionJobError(
            "任务执行模式与当前语义连接的CAD策略不一致。"
        )
    if plan.get("contextId") != context_id or plan.get("connectionId") != connection_id:
        raise ResolvedPairTransactionJobError("任务与当前上下文连接不一致。")
    if plan.get("contextDigest") != expected_context_digest:
        raise ResolvedPairTransactionJobError("任务绑定的上下文摘要与确认值不一致。")
    if plan.get("planDigest") != expected_plan_digest:
        raise ResolvedPairTransactionJobError("任务计划摘要与确认值不一致。")
    seed_checkpoint = plan.get("seedCheckpoint") or {}
    current = compile_connection_pair_plan(
        workspace,
        context_id,
        connection_id,
        seed_job_id=(str(seed_checkpoint.get("seedJobId") or "") or None),
    )
    if current.get("contextDigest") != expected_context_digest:
        raise ResolvedPairTransactionJobError("上下文已变化，请重新创建并确认任务。")
    if current.get("planDigest") != expected_plan_digest:
        raise ResolvedPairTransactionJobError("连接、模组映射或源文件已变化，请重新创建任务。")
    source = Path(str(plan.get("sourceAssemblyPath") or ""))
    if not source.is_file() or resolved_pair_sha256_file(source) != plan.get("sourceAssemblySha256"):
        raise ResolvedPairTransactionJobError("任务绑定的原型装配体不存在或摘要已经变化。")
    if plan.get("executionStrategy") == "independent_context_insert":
        effective = Path(str(plan.get("effectiveMateGraphPath") or ""))
        if not effective.is_file() or resolved_pair_sha256_file(effective) != plan.get(
            "effectiveMateGraphSha256"
        ):
            raise ResolvedPairTransactionJobError(
                "任务绑定的独立安装有效配合图不存在或摘要已经变化。"
            )
    if len(job.get("steps") or []) != 1:
        raise ResolvedPairTransactionJobError("真实配合对事务必须恰好包含一个原子步骤。")


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "statePath": str(settings.resolved_state_path),
        "assetDir": str(settings.resolved_asset_dir),
        "faceMappingPath": str(settings.resolved_face_mapping_path),
        "mcpMode": settings.mcp_mode,
        "llmMode": settings.llm_mode,
        "mcpCommand": settings.mcp_command,
        "mcpCwd": str(settings.resolved_mcp_cwd) if settings.resolved_mcp_cwd else None,
        "mcpPipeName": settings.mcp_pipe_name,
        "initializeBatchSize": settings.initialize_batch_size,
        "targetAssemblyPath": str(settings.resolved_target_assembly_path),
    }


@app.post("/api/demo/cases/{case_id}/solve-preview")
def solve_layout_case_preview(case_id: str, profile: str = "calibrated") -> dict:
    """Run an offline, source-independent layout solve and return display-ready geometry."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return solve_case_preview(workspace, case_id, profile=profile)
    except (LayoutPreviewError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/cases/{case_id}/recommend-modules")
def recommend_case_modules(case_id: str, request: ProjectRequirementRequest) -> dict:
    """Convert a project02 natural-language requirement into an auditable module recommendation."""
    if case_id != "project02":
        raise HTTPException(status_code=404, detail=f"Module recommendation is not implemented for '{case_id}'.")
    workspace = Path(__file__).resolve().parents[4]
    try:
        return recommend_project02_modules(request.requirement, workspace=workspace, persist=True)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/cases/{case_id}/confirm-modules")
def confirm_case_modules(case_id: str, request: ProjectModuleConfirmationRequest) -> dict:
    """Validate the user's module selection and gate entry into the fixed project02 layout case."""
    if case_id != "project02":
        raise HTTPException(status_code=404, detail=f"Module confirmation is not implemented for '{case_id}'.")
    workspace = Path(__file__).resolve().parents[4]
    try:
        recommendation = recommend_project02_modules(request.requirement, persist=False)
        return confirm_project02_modules(
            recommendation,
            request.selected_module_codes,
            workspace=workspace,
            persist=True,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/cases/{case_id}/approve-preview")
def approve_layout_case_preview(
    case_id: str,
    payload: dict = Body(default_factory=dict),
) -> dict:
    """Confirm a displayed Top-K candidate before any SolidWorks/B-rep work starts."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        solution_rank = int(payload.get("solutionRank", 0))
        reviewer_note = payload.get("reviewerNote")
        return approve_case_preview(
            workspace,
            case_id,
            solution_rank,
            reviewer_note=str(reviewer_note) if reviewer_note else None,
        )
    except (LayoutPreviewError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/cases/{case_id}/verification-plan")
def get_layout_case_verification_plan(case_id: str) -> dict:
    """Return the latest visual/CAD verification state without re-solving."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_case_verification_plan(workspace, case_id)
    except (LayoutPreviewError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/demo/cases/{case_id}/preview")
def get_layout_case_preview(case_id: str) -> dict:
    """Return the last persisted preview without launching a new solve."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_case_preview(workspace, case_id)
    except (LayoutPreviewError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/demo/cases/project02/dependency-ablation")
def get_project02_dependency_ablation() -> dict:
    """Return read-only B/C no-v42 candidates without changing the selected preview."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_dependency_ablation_bundle(workspace)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/demo/cases/{case_id}/migration-readiness")
def get_case_migration_readiness(case_id: str) -> dict:
    """Expose cross-case parameter/evidence readiness without starting SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if case_id == "project01":
            return load_project01_migration_readiness(workspace)
        if case_id == "project03":
            return load_project03_migration_readiness(workspace)
        if case_id == "project05":
            return load_project05_migration_readiness(workspace)
        raise HTTPException(status_code=404, detail=f"Migration readiness is not implemented for '{case_id}'.")
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/mcp-health", response_model=McpHealthResult)
async def demo_mcp_health(service: DemoService = Depends(get_service)) -> McpHealthResult:
    return await service.mcp_health()


@app.get("/api/demo/mate-face-catalog")
def get_mate_face_catalog(
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_face_endpoint_workbench(workspace, catalog_path)
    except (MateFaceWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/mate-face-catalog/highlight", response_model=OperationResult)
async def highlight_mate_face_endpoint(
    request: HighlightFaceEndpointRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.highlight_face_endpoint(request)


@app.post("/api/demo/mate-face-catalog/patch-preview")
def preview_mate_face_patch(request: FaceMatePatchPreviewRequest) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return build_face_mate_patch_preview(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (MateFaceWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/mate-face-catalog/apply")
async def apply_mate_face_patch(
    request: FaceMatePatchApplyRequest,
    service: DemoService = Depends(get_service),
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        prepared = prepare_face_mate_patch_application(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
        operation = await service.rebuild_effective_mate_graph(
            Path(prepared["effectiveGraphPath"]),
            Path(prepared["outputAssemblyPath"]),
        )
        return finalize_face_mate_patch_application(
            prepared,
            operation.model_dump(by_alias=True),
        )
    except (MateFaceWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/semantic-port-catalog")
def get_semantic_port_catalog(
    semantic_catalog_path: str | None = Query(default=None, alias="semanticCatalogPath"),
    endpoint_catalog_path: str | None = Query(default=None, alias="endpointCatalogPath"),
    source_graph_path: str | None = Query(default=None, alias="sourceGraphPath"),
    request_path: str | None = Query(default=None, alias="requestPath"),
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_semantic_port_workbench(
            workspace,
            semantic_catalog_path,
            endpoint_catalog_path,
            source_graph_path,
            request_path,
        )
    except (SemanticPortWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-module-catalog")
def get_global_module_catalog(
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
) -> dict:
    """Return the cross-project module definitions and semantic-port evidence."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_global_catalog(workspace, catalog_path)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-module-catalog/search")
def search_global_module_catalog(
    query: str = Query(default="", alias="q"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search all registered module definitions; project codes are aliases, not boundaries."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return search_global_modules(workspace, query, limit=limit)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-module-port-coverage")
def get_global_module_port_coverage(
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
) -> dict:
    """Return module/port/template coverage without starting SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_module_port_coverage(workspace, catalog_path)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-module-port-coverage/selection-readiness")
def assess_global_module_selection_readiness_api(
    request: GlobalModuleSelectionReadinessRequest,
) -> dict:
    """Assess whether selected modules form one CAD-plannable semantic subgraph."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return assess_module_selection(
            workspace, request.model_dump(by_alias=True, exclude_none=True)
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-module-catalog/cross-project-substitutions/preview")
def preview_cross_project_module_substitution_api(
    request: CrossProjectModuleSubstitutionPreviewRequest,
) -> dict:
    """Compile one same-role cross-project replacement without starting SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    payload = request.model_dump(by_alias=True, exclude_none=True)
    try:
        catalog = load_global_catalog(workspace, payload.get("catalogPath"))
        overlay = build_module_role_overlay(catalog)
        return compile_substitution_preview(
            catalog,
            overlay,
            source_module=payload["sourceModule"],
            replaced_module=payload["replacedModule"],
            requirement=payload["requirement"],
        )
    except (
        CrossProjectModuleSubstitutionError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-relation-capabilities")
def get_global_relation_capabilities(
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
) -> dict:
    """Describe relation kinds, standalone support and DOF evidence."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if catalog_path:
            return build_relation_capability_matrix(
                load_global_catalog(workspace, catalog_path)
            )
        catalog, release = load_released_relation_catalog(workspace)
        matrix = build_relation_capability_matrix(catalog)
        matrix["catalogRelease"] = {
            "releaseId": release["releaseId"],
            "releaseDigest": release["releaseDigest"],
            "scope": release["scope"],
        }
        matrix["matrixDigest"] = hashlib.sha256(
            json.dumps(
                {key: value for key, value in matrix.items() if key != "matrixDigest"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return matrix
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-relation-intents/preview")
def preview_global_relation_intent(
    request: GlobalRelationIntentPreviewRequest,
) -> dict:
    """Parse relation semantics and select only released relation templates."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_released_relation_intent(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-relation-release")
def get_global_relation_release() -> dict:
    """Return the immutable relation release selected by the default API."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return describe_released_relation_catalog(workspace)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-relation-driving/preflight")
def preflight_global_relation_driving(
    request: GlobalRelationDrivingPreflightRequest,
) -> dict:
    """Classify one proposed driving relation before any SolidWorks mutation."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preflight_released_driving_relation(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts")
def create_global_assembly_context_api(request: GlobalAssemblyContextCreateRequest) -> dict:
    """Create a versioned assembly graph context without opening SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return create_global_assembly_context(
            workspace, request.model_dump(by_alias=True, exclude_none=True)
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-module-catalog/migrations/preview")
def preview_global_module_catalog_migration_api(
    request: GlobalCatalogMigrationPreviewRequest,
) -> dict:
    """Assess old contexts against a candidate catalog without changing either file."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_catalog_migration(
            workspace, request.model_dump(by_alias=True, exclude_none=True)
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-module-catalog/migrations/commit")
def commit_global_module_catalog_migration_api(
    request: GlobalCatalogMigrationCommitRequest,
) -> dict:
    """Create a new rebound context after explicit digest-confirmed approval."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return commit_catalog_migration(
            workspace, request.model_dump(by_alias=True, exclude_none=True)
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/relation-edits/preview")
def preview_global_relation_edit_api(
    context_id: str, request: GlobalRelationEditPreviewRequest
) -> dict:
    """Preview add/replace/delete of a relation between existing module instances."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_relation_edit(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/relation-edits/apply")
def apply_global_relation_edit_api(
    context_id: str, request: GlobalRelationEditApplyRequest
) -> dict:
    """Commit a digest-confirmed relation edit without opening SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return apply_relation_edit(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-cad-manifest-jobs")
def create_global_cad_manifest_job_api(
    request: GlobalCadManifestJobCreateRequest,
) -> dict:
    """Create a durable generic-CAD job without starting SolidWorks."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        manifest_path = _workspace_file(
            workspace, request.manifest_path, label="CAD事务清单"
        )
        plan = build_manifest_job_plan(
            workspace,
            manifest_path,
            start_order=request.start_order,
            packet_limit=request.packet_limit,
        )
        store = _global_manifest_job_store(workspace)
        job = store.create(
            plan,
            execution_mode="generic_cad_manifest",
            idempotency_key=request.idempotency_key,
        )
        if plan.get("requiresSeedCheckpoint") and not job.get("lastCommittedCheckpoint"):
            if not request.seed_assembly_path or not request.seed_evidence_path:
                raise GlobalCadManifestOrchestrationError(
                    "非首包任务必须同时提供seedAssemblyPath和seedEvidencePath。"
                )
            seed_assembly = _workspace_file(
                workspace, request.seed_assembly_path, label="种子装配体"
            )
            seed_evidence = _workspace_file(
                workspace, request.seed_evidence_path, label="种子执行证据"
            )
            seed = validate_seed_evidence(
                plan, seed_assembly, seed_evidence
            )
            job = store.seed_verified_checkpoint(
                job["jobId"],
                step_id=seed["packetId"],
                module_token=seed["moduleToken"],
                assembly_path=seed_assembly,
                evidence_path=seed_evidence,
            )
            job["initialCommittedCheckpoint"].update(seed)
            job["lastCommittedCheckpoint"].update(seed)
            job["demoCheckpoint"].update(seed)
            store.save(job)
        write_manifest_job_artifacts(store, job["jobId"])
        return manifest_job_status_view(store, job["jobId"])
    except (
        AssemblyJobError,
        GlobalCadManifestOrchestrationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/independent-cad-jobs"
)
def prepare_global_independent_cad_job_api(
    context_id: str,
    request: GlobalIndependentCadJobCreateRequest,
) -> dict:
    """Compile a release-bound semantic graph into a queued generic CAD job."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise GlobalCadManifestOrchestrationError(
                "必须显式confirmed=true才能创建独立装配任务。"
            )
        manifest = compile_global_cad_transaction_manifest(workspace, context_id)
        if manifest.get("status") != "ready_for_generic_executor_implementation":
            codes = sorted(
                {
                    str(row.get("code") or "UNKNOWN_BLOCKER")
                    for row in manifest.get("blockers") or []
                }
            )
            raise GlobalCadManifestOrchestrationError(
                "语义端口＋配合图尚不能独立驱动当前装配："
                + "、".join(codes)
            )
        context_file = global_context_path(workspace, context_id)
        transaction_dag = compile_global_assembly_transaction_dag(
            workspace, context_id
        )
        dag_path = context_file.with_suffix(".transaction-dag.json")
        dag_temporary = dag_path.with_suffix(dag_path.suffix + ".tmp")
        dag_temporary.write_text(
            json.dumps(transaction_dag, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        dag_temporary.replace(dag_path)
        manifest_path = context_file.with_suffix(
            ".cad-transaction-manifest.json"
        )
        temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(manifest_path)
        plan = build_manifest_job_plan(
            workspace,
            manifest_path,
            start_order=1,
            packet_limit=request.packet_limit,
        )
        store = _global_manifest_job_store(workspace)
        job = store.create(
            plan,
            execution_mode="generic_cad_manifest",
            idempotency_key=request.idempotency_key,
        )
        context = load_global_assembly_context(workspace, context_id)
        bind_conversation_job(
            global_context_path(workspace, context_id), context, job
        )
        write_manifest_job_artifacts(store, job["jobId"])
        return {
            "success": True,
            "preparedOnly": True,
            "executionStarted": False,
            "solidWorksStarted": False,
            "assemblyMode": "mate_driven_port_assembly",
            "portable": True,
            "manifestPath": str(manifest_path),
            "transactionDagPath": str(dag_path),
            "manifest": manifest,
            "job": manifest_job_status_view(store, job["jobId"]),
        }
    except (
        AssemblyJobError,
        GlobalCadManifestOrchestrationError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-cad-manifest-jobs")
def list_global_cad_manifest_jobs_api() -> dict:
    workspace = Path(__file__).resolve().parents[4]
    store = _global_manifest_job_store(workspace)
    jobs = []
    for path in sorted(
        store.root.glob("*/job.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        try:
            jobs.append(
                manifest_job_status_view(store, path.parent.name, include_events=False)
            )
        except (AssemblyJobError, GlobalCadManifestOrchestrationError, OSError):
            continue
    return {"success": True, "jobCount": len(jobs), "jobs": jobs}


@app.post("/api/demo/global-cad-manifest-jobs/compile-natural-language")
def compile_global_natural_language_manifest_job_api(
    request: GlobalNaturalLanguageManifestJobRequest,
) -> dict:
    """Compile an ordered NL context into a queued job; never start CAD here."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_natural_language_manifest_job(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
            store=_global_manifest_job_store(workspace),
        )
    except (
        AssemblyJobError,
        GlobalNaturalLanguageManifestError,
        GlobalAssemblyWorkbenchError,
        GlobalCadManifestOrchestrationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-cad-manifest-jobs/{job_id}")
def get_global_cad_manifest_job_api(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return manifest_job_status_view(
            _global_manifest_job_store(workspace), job_id
        )
    except (AssemblyJobError, GlobalCadManifestOrchestrationError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/global-cad-manifest-jobs/{job_id}/start")
def start_global_cad_manifest_job_api(
    job_id: str,
    request: GlobalCadManifestJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        store = _global_manifest_job_store(workspace)
        _, scheduled = store.request_start(job_id)
        if scheduled:
            background_tasks.add_task(
                _run_global_manifest_job,
                workspace,
                job_id,
                timeout_seconds=request.timeout_seconds,
                pause_after_packet=request.pause_after_packet,
                fail_before_packet=request.inject_failure_before_packet,
            )
        return manifest_job_status_view(store, job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-cad-manifest-jobs/{job_id}/pause")
def pause_global_cad_manifest_job_api(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        store = _global_manifest_job_store(workspace)
        store.request_pause(job_id)
        return manifest_job_status_view(store, job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/global-cad-manifest-jobs/{job_id}/resume")
def resume_global_cad_manifest_job_api(
    job_id: str,
    request: GlobalCadManifestJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        store = _global_manifest_job_store(workspace)
        store.prepare_resume(job_id)
        store.request_start(job_id)
        background_tasks.add_task(
            _run_global_manifest_job,
            workspace,
            job_id,
            timeout_seconds=request.timeout_seconds,
            pause_after_packet=request.pause_after_packet,
            fail_before_packet=request.inject_failure_before_packet,
        )
        return manifest_job_status_view(store, job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}")
def get_global_assembly_context_api(context_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return load_global_assembly_context(workspace, context_id)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/api/demo/global-assembly-contexts/{context_id}/portable-release-recommendation"
)
def preview_global_portable_release_upgrade_api(context_id: str) -> dict:
    """Recommend a portable release; never mutate the source context."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_portable_release_upgrade(workspace, context_id)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/portable-release-upgrades"
)
def commit_global_portable_release_upgrade_api(
    context_id: str, request: GlobalPortableReleaseCommitRequest
) -> dict:
    """Create a new release-bound context after explicit confirmation."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return commit_portable_release_upgrade(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/conversation")
def get_global_assembly_conversation_api(context_id: str) -> dict:
    """Recover natural-language turns, CAD jobs and the latest Demo checkpoint."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)

        def load_job(job_id: str) -> dict:
            try:
                return _assembly_job_store(
                    workspace, _project_id_from_job_id(job_id)
                ).load(job_id)
            except (AssemblyJobError, OSError, ValueError):
                # Project-independent semantic-graph jobs live in the global
                # manifest store even when their traceable job id retains a
                # project prefix.  Conversation refresh must therefore fall
                # back to that store instead of losing task state on reload.
                return _global_manifest_job_store(workspace).load(job_id)

        return conversation_snapshot(
            global_context_path(workspace, context_id), context, load_job
        )
    except (
        AssemblyConversationError,
        AssemblyJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/direct-mate-executions/bind"
)
def bind_direct_mate_execution_api(
    context_id: str, request: DirectMateExecutionBindRequest
) -> dict:
    """Promote a verified direct mate-edit result to the physical continuation seed."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise AssemblyConversationError("必须显式confirmed=true才能推进CAD检查点。")
        execution_path = Path(request.execution_path)
        execution_path = (
            execution_path.resolve()
            if execution_path.is_absolute()
            else (workspace / execution_path).resolve()
        )
        try:
            execution_path.relative_to(workspace.resolve())
        except ValueError as exc:
            raise AssemblyConversationError("直接配合执行证据必须位于工作区内。") from exc
        execution = json.loads(execution_path.read_text(encoding="utf-8-sig"))
        context = load_global_assembly_context(workspace, context_id)
        context_file = global_context_path(workspace, context_id)
        bind_direct_mate_execution(
            context_file,
            context,
            execution,
            execution_path=execution_path,
        )
        return conversation_snapshot(context_file, context)
    except (
        AssemblyConversationError,
        GlobalAssemblyWorkbenchError,
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/temporary-ports")
def get_temporary_semantic_ports_api(context_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        path = global_context_path(workspace, context_id)
        registry = load_temporary_ports(path, context)
        return {
            "success": True,
            "contextId": context_id,
            "ports": registry["ports"],
            "registryPath": str(temporary_port_registry_path(path)),
            "endpointCatalogPath": str(temporary_endpoint_catalog_path(path)),
        }
    except (
        TemporarySemanticPortError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/temporary-ports/capture-selected-face")
async def capture_temporary_semantic_port_api(
    context_id: str,
    request: TemporarySemanticPortCaptureRequest,
    service: DemoService = Depends(get_service),
) -> dict:
    """Capture the currently selected SolidWorks face; never creates a mate."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        result = await service.mcp.run_plan(
            [
                ToolCallPlan(tool="get_active_document", arguments={}),
                ToolCallPlan(
                    tool="capture_selected_face_endpoint",
                    arguments={"moduleToken": request.module_token},
                )
            ]
        )
        captured = parse_captured_endpoint(
            result.model_dump(by_alias=True, exclude_none=True)
        )
        source_assembly_path = parse_active_assembly_path(
            result.model_dump(by_alias=True, exclude_none=True)
        )
        return register_captured_face(
            global_context_path(workspace, context_id),
            context,
            captured,
            instance_id=request.instance_id,
            module_token=request.module_token,
            display_name=request.display_name,
            interface_type=request.interface_type,
            role=request.role,
            aliases=request.aliases,
            source_assembly_path=source_assembly_path,
        )
    except (
        TemporarySemanticPortError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/temporary-connections/preview")
def preview_temporary_semantic_connection_api(
    context_id: str, request: TemporaryConnectionPreviewRequest
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        return preview_temporary_connection(
            global_context_path(workspace, context_id),
            context,
            request.requirement,
            port_ids=request.port_ids or None,
        )
    except (
        TemporarySemanticPortError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _historical_inventory_path(
    workspace: Path, job: dict, requested_path: str | None
) -> Path:
    candidate = (
        Path(requested_path).resolve()
        if requested_path
        else infer_component_inventory_path(job)
    )
    if candidate is None:
        raise HistoricalCheckpointImportError(
            "无法从历史任务推断顶层组件清单，请显式提供componentInventoryPath。"
        )
    try:
        candidate.resolve().relative_to(workspace.resolve())
    except ValueError as exc:
        raise HistoricalCheckpointImportError("组件清单必须位于当前工作区内。") from exc
    return candidate.resolve()


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/historical-checkpoints/preview"
)
def preview_historical_checkpoint_import_api(
    context_id: str, request: HistoricalCheckpointPreviewRequest
) -> dict:
    """Attest a successful pre-ledger job without changing its files or the ledger."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        project_id = _project_id_from_job_id(request.job_id)
        job = _assembly_job_store(workspace, project_id).load(request.job_id)
        inventory = _historical_inventory_path(
            workspace, job, request.component_inventory_path
        )
        return build_historical_checkpoint_import_assessment(
            context, load_global_catalog(workspace), job, inventory
        )
    except (
        AssemblyJobError,
        HistoricalCheckpointImportError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/historical-checkpoints/import"
)
def import_historical_checkpoint_api(
    context_id: str, request: HistoricalCheckpointImportRequest
) -> dict:
    """Bind an attested historical checkpoint to the current turn ledger only."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        if context.get("contextDigest") != request.expected_context_digest:
            raise HistoricalCheckpointImportError(
                "上下文摘要已变化，请重新执行历史检查点评估。"
            )
        project_id = _project_id_from_job_id(request.job_id)
        store = _assembly_job_store(workspace, project_id)
        job = store.load(request.job_id)
        inventory = _historical_inventory_path(
            workspace, job, request.component_inventory_path
        )
        assessment = build_historical_checkpoint_import_assessment(
            context, load_global_catalog(workspace), job, inventory
        )
        imported = commit_historical_checkpoint_import(
            global_context_path(workspace, context_id),
            context,
            job,
            assessment,
            expected_assessment_digest=request.assessment_digest,
            confirmed=request.confirmed,
        )
        imported["conversation"] = conversation_snapshot(
            global_context_path(workspace, context_id), context, store.load
        )
        return imported
    except (
        AssemblyConversationError,
        AssemblyJobError,
        HistoricalCheckpointImportError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/checkpoint-mate-graph/export"
)
async def export_checkpoint_mate_graph_api(
    context_id: str,
    request: CheckpointMateGraphExportRequest,
    service: DemoService = Depends(get_service),
) -> dict:
    """Plan or execute a read-only mate-graph export for the latest Demo checkpoint."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        context_file = global_context_path(workspace, context_id)

        def load_job(job_id: str) -> dict:
            return _assembly_job_store(
                workspace, _project_id_from_job_id(job_id)
            ).load(job_id)

        conversation = conversation_snapshot(context_file, context, load_job)
        catalog = load_global_catalog(workspace)
        spec = build_checkpoint_graph_export_spec(
            workspace,
            context_file,
            context,
            catalog,
            conversation,
            expected_demo_job_id=request.expected_demo_job_id,
        )
        binding_file = Path(spec["bindingPath"])
        if binding_file.is_file():
            binding = load_checkpoint_graph_binding(spec)
            return {
                "success": True,
                "status": "cached_bound_graph",
                "executionStarted": False,
                "solidWorksAssemblyModified": False,
                "spec": spec,
                "binding": binding,
                "bindingPath": str(binding_file),
            }
        if request.confirmed is not True:
            return {
                "success": True,
                "status": "confirmation_required",
                "executionStarted": False,
                "solidWorksStarted": False,
                "spec": spec,
            }
        if Path(spec["outputGraphPath"]).exists():
            raise CheckpointMateGraphAdapterError(
                "发现没有有效绑定清单的同名配合图；为避免误用旧图，已拒绝覆盖。"
            )
        result = await service.mcp.run_plan(
            [
                ToolCallPlan(
                    tool=spec["toolCall"]["tool"],
                    arguments=spec["toolCall"]["arguments"],
                )
            ]
        )
        finalized = finalize_checkpoint_graph_export(spec, result.status)
        return {
            **finalized,
            "executionStarted": True,
            "solidWorksAssemblyModified": False,
            "spec": spec,
        }
    except (
        AssemblyConversationError,
        AssemblyJobError,
        CheckpointMateGraphAdapterError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/checkpoint-mate-graph/compile-temporary-connection"
)
def compile_checkpoint_temporary_connection_api(
    context_id: str, request: CheckpointTemporaryMateCompileRequest
) -> dict:
    """Compile a selected-face mate into a target-local graph; never edits CAD."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        context = load_global_assembly_context(workspace, context_id)
        context_file = global_context_path(workspace, context_id)

        def load_job(job_id: str) -> dict:
            return _assembly_job_store(
                workspace, _project_id_from_job_id(job_id)
            ).load(job_id)

        conversation = conversation_snapshot(context_file, context, load_job)
        spec = build_checkpoint_graph_export_spec(
            workspace,
            context_file,
            context,
            load_global_catalog(workspace),
            conversation,
        )
        binding = load_checkpoint_graph_binding(spec)
        if binding.get("bindingDigest") != request.expected_binding_digest:
            raise CheckpointMateGraphAdapterError(
                "检查点配合图绑定摘要已变化，请重新导出或刷新页面。"
            )
        endpoint_path = temporary_endpoint_catalog_path(context_file)
        if not endpoint_path.is_file():
            raise CheckpointMateGraphAdapterError("当前上下文没有临时面端点目录。")
        endpoint_catalog = json.loads(endpoint_path.read_text(encoding="utf-8-sig"))
        return compile_temporary_connection_for_checkpoint(
            context,
            binding,
            request.temporary_preview,
            endpoint_catalog,
            target_module_token=request.target_module_token,
            output_dir=Path(spec["outputGraphPath"]).parent / "compiled",
        )
    except (
        AssemblyConversationError,
        AssemblyJobError,
        CheckpointMateGraphAdapterError,
        GlobalAssemblyWorkbenchError,
        json.JSONDecodeError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/commands/preview")
def preview_global_assembly_command_api(
    context_id: str, request: GlobalAssemblyCommandPreviewRequest
) -> dict:
    """Resolve a natural-language add command into an auditable graph-patch preview."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_global_assembly_command(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/commands/apply")
def apply_global_assembly_command_api(
    context_id: str, request: GlobalAssemblyCommandApplyRequest
) -> dict:
    """Commit a confirmed graph patch. CAD execution and collision assessment remain separate."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return apply_global_assembly_command(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/commands/undo-latest")
def undo_latest_global_assembly_command_api(
    context_id: str, request: GlobalAssemblyCommandUndoRequest
) -> dict:
    """Restore the previous graph revision when the latest turn has no CAD evidence."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return undo_latest_global_assembly_command(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/commands/apply-sequence")
def apply_global_assembly_command_sequence_api(
    context_id: str, request: GlobalAssemblyCommandSequenceRequest
) -> dict:
    """Atomically compile and commit an ordered natural-language command sequence."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return apply_global_assembly_command_sequence(
            workspace,
            context_id,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/execution-manifest")
def get_global_assembly_execution_manifest_api(context_id: str) -> dict:
    """Compile committed global connections back into existing project-adapter requests."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_global_assembly_execution_manifest(workspace, context_id)
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/project-adapter-plan")
def get_global_project_adapter_plan_api(
    context_id: str,
    assembly_mode: str = Query(
        default="mate_driven_port_assembly", alias="assemblyMode"
    ),
) -> dict:
    """Bind the global graph to a safe cumulative project runner plan; do not run CAD."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_global_project_adapter_plan(
            workspace,
            context_id,
            assembly_mode=assembly_mode,
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/transaction-dag")
def get_global_assembly_transaction_dag_api(
    context_id: str,
    base_instance_id: str | None = Query(default=None, alias="baseInstanceId"),
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
    positioning_standard_id: str | None = Query(
        default=None, alias="positioningStandardId"
    ),
) -> dict:
    """Compile a project-independent semantic transaction DAG; do not run CAD."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_global_assembly_transaction_dag(
            workspace,
            context_id,
            base_instance_id=(
                base_instance_id if isinstance(base_instance_id, str) else None
            ),
            positioning_standard_id=(
                positioning_standard_id
                if isinstance(positioning_standard_id, str)
                else None
            ),
            catalog_path=(catalog_path if isinstance(catalog_path, str) else None),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/global-assembly-contexts/{context_id}/cad-transaction-manifest")
def get_global_cad_transaction_manifest_api(
    context_id: str,
    base_instance_id: str | None = Query(default=None, alias="baseInstanceId"),
    catalog_path: str | None = Query(default=None, alias="catalogPath"),
    positioning_standard_id: str | None = Query(
        default=None, alias="positioningStandardId"
    ),
) -> dict:
    """Compile endpoint-complete generic CAD packets; do not run SolidWorks."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_global_cad_transaction_manifest(
            workspace,
            context_id,
            base_instance_id=(
                base_instance_id if isinstance(base_instance_id, str) else None
            ),
            positioning_standard_id=(
                positioning_standard_id
                if isinstance(positioning_standard_id, str)
                else None
            ),
            catalog_path=(catalog_path if isinstance(catalog_path, str) else None),
        )
    except (GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/api/demo/global-assembly-contexts/{context_id}/connections/{connection_id}/resolved-pair-plan"
)
def get_resolved_pair_transaction_plan_api(
    context_id: str,
    connection_id: str,
    seed_job_id: str | None = Query(default=None, alias="seedJobId"),
) -> dict:
    """Compile one committed semantic connection into a reviewed real-CAD pair plan."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return compile_connection_pair_plan(
            workspace, context_id, connection_id, seed_job_id=seed_job_id
        )
    except (
        ResolvedPairTransactionJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/connections/{connection_id}/resolved-pair-jobs"
)
def prepare_resolved_pair_transaction_job(
    context_id: str,
    connection_id: str,
    request: ResolvedPairTransactionJobCreateRequest,
) -> dict:
    """Persist a reviewed pair job without starting SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise ResolvedPairTransactionJobError(
                "必须显式confirmed=true才能创建真实配合对任务。"
            )
        job = create_connection_pair_job(
            workspace,
            context_id,
            connection_id,
            idempotency_key=request.idempotency_key,
            seed_job_id=request.seed_job_id,
        )
        return {
            "success": True,
            "preparedOnly": True,
            "executionStarted": False,
            "solidWorksStarted": False,
            "message": "任务已持久化；必须再次确认上下文与计划摘要后才能启动CAD。",
            "job": job,
        }
    except (
        ResolvedPairTransactionJobError,
        AssemblyJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/connections/{connection_id}/"
    "resolved-pair-jobs/{job_id}/start"
)
def start_resolved_pair_transaction_job(
    context_id: str,
    connection_id: str,
    job_id: str,
    request: ResolvedPairTransactionJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Schedule one digest-bound pair transaction after explicit confirmation."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise ResolvedPairTransactionJobError(
                "必须显式confirmed=true才能启动真实CAD事务。"
            )
        project_id = _project_id_from_job_id(job_id)
        store = pair_transaction_job_store(workspace, project_id)
        job = store.load(job_id)
        _validate_current_resolved_pair_job(
            workspace,
            context_id,
            connection_id,
            job,
            request.expected_context_digest,
            request.expected_plan_digest,
        )
        job, scheduled = store.request_start(job_id)
        if scheduled:
            background_tasks.add_task(
                _run_scheduled_resolved_pair_job,
                workspace,
                project_id,
                job_id,
            )
        return {
            "success": True,
            "executionScheduled": scheduled,
            "solidWorksStartedInRequest": False,
            "message": (
                "已提交后台真实CAD事务。"
                if scheduled
                else "该任务已经提交过启动请求，本次未重复调度。"
            ),
            "job": job,
        }
    except (
        ResolvedPairTransactionJobError,
        AssemblyJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/connections/{connection_id}/"
    "resolved-pair-jobs/{job_id}/resume"
)
def resume_resolved_pair_transaction_job(
    context_id: str,
    connection_id: str,
    job_id: str,
    request: ResolvedPairTransactionJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Retry a failed pair transaction while preserving every prior attempt."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise ResolvedPairTransactionJobError(
                "必须显式confirmed=true才能恢复真实CAD事务。"
            )
        project_id = _project_id_from_job_id(job_id)
        store = pair_transaction_job_store(workspace, project_id)
        job = store.load(job_id)
        if job.get("status") not in {"paused", "failed", "cancelled"}:
            raise ResolvedPairTransactionJobError(
                f"任务当前状态{job.get('status')}不可恢复。"
            )
        _validate_current_resolved_pair_job(
            workspace,
            context_id,
            connection_id,
            job,
            request.expected_context_digest,
            request.expected_plan_digest,
        )
        store.prepare_resume(job_id)
        job, scheduled = store.request_start(job_id)
        if scheduled:
            background_tasks.add_task(
                _run_scheduled_resolved_pair_job,
                workspace,
                project_id,
                job_id,
            )
        return {
            "success": True,
            "executionScheduled": scheduled,
            "solidWorksStartedInRequest": False,
            "message": "已保留旧尝试并提交新的真实CAD事务。",
            "job": job,
        }
    except (
        ResolvedPairTransactionJobError,
        AssemblyJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/resolved-pair-jobs/{job_id}")
def get_resolved_pair_transaction_job(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_job_id(job_id)
        return pair_transaction_job_store(workspace, project_id).load(job_id)
    except (AssemblyJobError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/global-assembly-contexts/{context_id}/project-adapter-jobs")
def prepare_global_project_adapter_job(
    context_id: str,
    request: GlobalProjectAdapterJobCreateRequest,
) -> dict:
    """Create and seed a queued job, but never start SolidWorks in this request."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise AssemblyJobError("必须显式confirmed=true才能创建排队任务。")
        plan = compile_global_project_adapter_plan(
            workspace,
            context_id,
            assembly_mode=request.assembly_mode,
        )
        if plan.get("safeToCreateDurableJob") is not True:
            raise AssemblyJobError("项目适配计划未通过，禁止创建排队任务。")
        project_id = _normalize_job_project_id(str(plan["projectId"]))
        release = build_assembly_release_contract(workspace, project_id)
        if release["release"]["liveCadAllowed"] is not True:
            raise AssemblyJobError(f"{project_id}尚未获准建立现场CAD任务。")
        full_step_count = len(plan.get("steps") or [])
        step_limit = request.step_limit or full_step_count
        store = _assembly_job_store(workspace, project_id)
        if request.seed_job_id and request.seed_edit_id:
            raise AssemblyJobError("seedJobId与seedEditId只能指定一个。")
        if request.seed_edit_id:
            context = load_global_assembly_context(workspace, context_id)
            context_file = global_context_path(workspace, context_id)
            direct_edit = find_direct_mate_execution(
                context_file, context, request.seed_edit_id
            )
            source_job_id = str(direct_edit.get("sourceJobId") or "")
            if not source_job_id:
                raise AssemblyJobError("直接配合实体检查点缺少来源任务编号。")
            seed_project_id = _project_id_from_job_id(source_job_id)
            if seed_project_id != project_id:
                raise AssemblyJobError("直接配合实体检查点与当前项目不一致。")
            plan = build_direct_edit_checkpoint_continuation_plan(
                plan,
                store.load(source_job_id),
                direct_edit,
                step_limit=step_limit,
            )
        elif request.seed_job_id:
            seed_project_id = _project_id_from_job_id(request.seed_job_id)
            if seed_project_id != project_id:
                raise AssemblyJobError("续跑来源任务与当前项目不一致。")
            plan = build_checkpoint_continuation_plan(
                plan,
                store.load(request.seed_job_id),
                step_limit=step_limit,
            )
        else:
            if step_limit > full_step_count:
                raise AssemblyJobError(
                    f"stepLimit={step_limit}超过计划步骤数{full_step_count}。"
                )
            plan = {
                **plan,
                "steps": list(plan["steps"][:step_limit]),
                "stepCount": step_limit,
                "executionScope": {
                    "kind": "full_chain" if step_limit == full_step_count else "validated_prefix",
                    "requestedStepCount": step_limit,
                    "fullStepCount": full_step_count,
                    "startStepIndex": 0,
                    "moduleTokens": [
                        str(step["moduleToken"]) for step in plan["steps"][:step_limit]
                    ],
                },
            }
        plan = {
            **plan,
            "validationProfile": request.validation_profile,
            "validationBoundary": {
                "assemblyGate": "cad_save_reopen",
                "collisionGate": (
                    "synchronous_hard_gate"
                    if request.validation_profile == "engineering"
                    else "not_evaluated"
                ),
            },
        }
        job = create_seeded_durable_job(
            store,
            plan,
            execution_mode="live_cad",
            idempotency_key=request.idempotency_key,
        )
        context = load_global_assembly_context(workspace, context_id)
        bind_conversation_job(
            global_context_path(workspace, context_id), context, job
        )
        return {
            "success": True,
            "preparedOnly": True,
            "executionStarted": False,
            "solidWorksStarted": False,
            "validationProfile": request.validation_profile,
            "message": (
                "续跑任务和上一成功检查点已建立；必须另行调用启动接口才会执行CAD。"
                if request.seed_job_id or request.seed_edit_id
                else "排队任务和基座检查点已建立；必须另行调用恢复/启动接口才会执行CAD。"
            ),
            "executionScope": plan["executionScope"],
            "job": job,
        }
    except (
        AssemblyConversationError,
        AssemblyJobError,
        GlobalAssemblyWorkbenchError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/project-adapter-jobs/{job_id}/start"
)
def start_global_project_adapter_job(
    context_id: str,
    job_id: str,
    request: GlobalProjectAdapterJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Explicitly schedule a prepared job after a second digest-bound confirmation."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise AssemblyJobError("必须显式confirmed=true才能启动CAD任务。")
        context = load_global_assembly_context(workspace, context_id)
        if context["contextDigest"] != request.expected_context_digest:
            raise AssemblyJobError("上下文摘要已变化，请重新检查计划并创建新任务。")
        project_id = _project_id_from_job_id(job_id)
        store = _assembly_job_store(workspace, project_id)
        job = store.load(job_id)
        _validate_current_global_adapter_job(
            workspace,
            context_id,
            context,
            project_id,
            store,
            job,
            request.expected_step_count,
        )
        job, scheduled = store.request_start(job_id)
        if scheduled:
            background_tasks.add_task(
                _run_scheduled_global_adapter_job,
                workspace,
                project_id,
                job_id,
            )
        return {
            "success": True,
            "executionScheduled": scheduled,
            "solidWorksStartedInRequest": False,
            "message": (
                "已提交后台CAD执行请求。"
                if scheduled
                else "该任务已提交过启动请求，本次未重复调度。"
            ),
            "job": job,
        }
    except (AssemblyJobError, GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/global-assembly-contexts/{context_id}/project-adapter-jobs/{job_id}/resume"
)
def resume_global_project_adapter_job(
    context_id: str,
    job_id: str,
    request: GlobalProjectAdapterJobStartRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Resume from the last checkpoint after revalidating the bound global plan."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise AssemblyJobError("必须显式confirmed=true才能恢复CAD任务。")
        context = load_global_assembly_context(workspace, context_id)
        if context["contextDigest"] != request.expected_context_digest:
            raise AssemblyJobError("上下文摘要已变化，请重新检查计划并创建新任务。")
        project_id = _project_id_from_job_id(job_id)
        store = _assembly_job_store(workspace, project_id)
        job = store.load(job_id)
        if job.get("status") not in {"paused", "failed", "cancelled"}:
            raise AssemblyJobError(f"任务当前状态{job.get('status')}不可恢复。")
        _validate_current_global_adapter_job(
            workspace,
            context_id,
            context,
            project_id,
            store,
            job,
            request.expected_step_count,
        )
        store.prepare_resume(job_id)
        job, scheduled = store.request_start(job_id)
        if scheduled:
            background_tasks.add_task(
                _run_scheduled_global_adapter_job,
                workspace,
                project_id,
                job_id,
            )
        return {
            "success": True,
            "executionScheduled": scheduled,
            "solidWorksStartedInRequest": False,
            "message": "已从最后有效检查点提交后台恢复请求。",
            "job": job,
        }
    except (AssemblyJobError, GlobalAssemblyWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/demo/semantic-assembly-sequence/jobs/{job_id}/engineering-validation"
)
def create_engineering_validation_job_api(
    job_id: str,
    request: EngineeringValidationJobCreateRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Validate an immutable Demo checkpoint without rebuilding the assembly."""

    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.confirmed is not True:
            raise AssemblyJobError("必须显式confirmed=true才能启动独立工程验证。")
        project_id = _project_id_from_job_id(job_id)
        if project_id != "project02":
            raise AssemblyJobError("独立工程验证作业当前只完成项目02闭环。")
        assembly_store = _assembly_job_store(workspace, project_id)
        source_job = assembly_store.load(job_id)
        validation_store = _engineering_validation_store(workspace, project_id)
        validation = validation_store.create(
            source_job,
            idempotency_key=request.idempotency_key,
        )
        scheduled = False
        if validation.get("status") == "queued" and not validation.get("startRequestedAt"):
            validation["startRequestedAt"] = utc_now()
            validation_store.save(validation)
            validation_store.append_event(
                str(validation["validationJobId"]),
                "engineering-validation-start-requested",
            )
            background_tasks.add_task(
                _run_project02_engineering_validation,
                workspace,
                str(validation["validationJobId"]),
            )
            scheduled = True
        return {
            "success": True,
            "executionScheduled": scheduled,
            "sourceDemoPreserved": True,
            "message": (
                "独立工程验证已排队；Demo装配体不会被重建、移动或隔离。"
                if scheduled
                else "该工程验证任务已存在，本次未重复调度。"
            ),
            "validationJob": validation,
        }
    except (AssemblyJobError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/engineering-validation-jobs/{validation_job_id}")
def get_engineering_validation_job_api(validation_job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_engineering_validation_job_id(validation_job_id)
        return _engineering_validation_store(workspace, project_id).load(
            validation_job_id
        )
    except AssemblyJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/semantic-port-catalog/connection-preview")
def preview_semantic_port_connection(request: SemanticConnectionPreviewRequest) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_semantic_connection(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (SemanticPortWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/semantic-port-catalog/intent-preview")
def preview_semantic_port_intent(request: SemanticAssemblyIntentPreviewRequest) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        return preview_semantic_assembly_intent(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
    except (SemanticPortWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/preview")
def preview_semantic_assembly_sequence(
    request: SemanticAssemblySequencePreviewRequest,
) -> dict:
    """Compile a controlled multi-module command without starting SolidWorks."""
    try:
        if request.project_id.strip().lower() != "project02":
            return preview_ordered_assembly(request.project_id, request.requirement)
        return preview_project02_ordered_assembly(request.requirement)
    except (
        OrderedAssemblyPlannerError,
        SemanticAssemblySequenceError,
        ValueError,
        TypeError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/semantic-assembly-sequence/closure")
def get_semantic_assembly_sequence_closure() -> dict:
    """Return the latest durable CAD/B-rep closure without starting SolidWorks."""
    workspace = Path(__file__).resolve().parents[4]
    return load_project02_ordered_assembly_closure(workspace)


@app.get("/api/demo/semantic-assembly-sequence/pipeline-audit")
def get_semantic_assembly_sequence_pipeline_audit() -> dict:
    """Return read-only static/live preflight evidence for the complete chain."""
    workspace = Path(__file__).resolve().parents[4]
    return audit_project02_assembly_pipeline(workspace)


@app.get("/api/demo/semantic-assembly-sequence/dependency-audit")
def get_semantic_assembly_sequence_dependency_audit() -> dict:
    """Expose which parameters are CAD-measured, prototype-inferred, or authoritative."""
    return audit_project_profile_dependencies("project02")


@app.get("/api/demo/semantic-assembly-sequence/release-contract")
def get_semantic_assembly_sequence_release_contract(
    project_id: str = Query(default="project03", alias="projectId"),
) -> dict:
    """Return the unified static/live/dynamic/production release decision."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        return build_assembly_release_contract(
            workspace,
            _normalize_job_project_id(project_id),
        )
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/run-validated-demo")
def run_semantic_assembly_sequence_validated_demo(
    request: SemanticAssemblySequencePreviewRequest,
) -> dict:
    """Bind the full natural-language order to the latest validated CAD artifacts."""
    workspace = Path(__file__).resolve().parents[4]
    try:
        if request.project_id.strip().lower() != "project02":
            raise SemanticAssemblySequenceError(
                "项目01/03当前只开放计划预演，尚未形成可回放的完整CAD闭包。"
            )
        return run_project02_validated_demo(workspace, request.requirement)
    except (SemanticAssemblySequenceError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/jobs")
def create_semantic_assembly_job(
    request: SemanticAssemblyJobCreateRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Create a durable, idempotent ordered-assembly job.

    ``validated_artifact_replay`` reuses accepted checkpoints. ``live_cad``
    serializes SolidWorks work and commits a step only after save/reopen plus
    the pair-local AABB/cache/conditional-B-rep hard gate.
    """
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _normalize_job_project_id(request.project_id)
        if project_id not in {"project01", "project02", "project03", "project05"}:
            raise SemanticAssemblySequenceError(
                f"{project_id}尚未形成可回放的逐步CAD证据链，禁止启动作业。"
            )
        release_contract = build_assembly_release_contract(workspace, project_id)
        if request.execution_mode == "validated_artifact_replay":
            if release_contract["release"]["staticDemoAllowed"] is not True:
                raise SemanticAssemblySequenceError(
                    f"{project_id}统一发布契约尚未放行静态证据回放。"
                )
        elif release_contract["release"]["liveCadAllowed"] is not True:
            raise SemanticAssemblySequenceError(
                f"{project_id}统一发布契约尚未放行现场CAD作业："
                + "；".join(release_contract["release"]["productionBlockers"][:2])
            )
        if project_id == "project01" and request.execution_mode == "live_cad":
            live_release = _project01_live_adapter_release(workspace)
            if live_release.get("success") is not True:
                raise SemanticAssemblySequenceError(
                    "项目01现场CAD适配器尚未通过完整动作链发布门禁："
                    + str(live_release.get("status") or "UNKNOWN")
                )
        if project_id == "project05" and request.execution_mode == "live_cad":
            live_release = _project05_live_adapter_release(workspace)
            if live_release.get("liveCadApiMayStart") is not True:
                raise SemanticAssemblySequenceError(
                    "项目05现场CAD适配器尚未通过完整动作链发布门禁："
                    + str(live_release.get("status") or "UNKNOWN")
                )
        preview = (
            preview_project02_ordered_assembly(request.requirement)
            if project_id == "project02"
            else preview_ordered_assembly(project_id, request.requirement)
        )
        plan = preview["plan"]
        if not plan["summary"]["orderValid"]:
            raise SemanticAssemblySequenceError("装配顺序依赖未通过。")
        dynamic_gate = plan.get("dynamicProcessGate")
        if (
            isinstance(dynamic_gate, dict)
            and dynamic_gate.get("requested") is True
            and dynamic_gate.get("accepted") is not True
        ):
            raise SemanticAssemblySequenceError(
                "动态工艺硬门禁拒绝本次作业："
                + str(dynamic_gate.get("message") or dynamic_gate.get("status"))
            )
        closure = _load_project_ordered_assembly_closure(workspace, project_id)
        available = {
            str(item.get("moduleToken"))
            for item in closure.get("steps") or []
            if item.get("success") is True
        }
        requested = [str(item["moduleToken"]) for item in plan["steps"]]
        if project_id == "project01" and request.execution_mode == "live_cad":
            live_release = _project01_live_adapter_release(workspace)
            allowed = [
                str(token)
                for token in live_release.get("liveCadApiMayStartForTokens") or []
            ]
            if not requested or requested != allowed[: len(requested)]:
                raise SemanticAssemblySequenceError(
                    "项目01现场CAD只允许已完成单一持久化作业闭环的"
                    "SS00→FF00→SM00→GN00→BD00→GJ00→LM00连续前缀。"
                )
        if project_id == "project03" and request.execution_mode == "live_cad":
            live_release = _project03_live_adapter_release(workspace)
            allowed = [str(token) for token in live_release.get("liveCadApiMayStartForTokens") or []]
            if (
                live_release.get("success") is not True
                or not requested
                or requested != allowed[: len(requested)]
            ):
                raise SemanticAssemblySequenceError(
                    "项目03现场CAD只允许已完成单一持久化作业闭环的"
                    "AE00→AD00→AI00→AG00→AH00→AJ00→AB00连续前缀。"
                )
        base_module = str(load_project_assembly_profile(project_id)["baseModule"])
        validated_sequence = [
            str(token)
            for token in closure.get("sequence") or []
            if str(token) != base_module
        ]
        if request.execution_mode == "validated_artifact_replay" and requested != validated_sequence[: len(requested)]:
            raise SemanticAssemblySequenceError(
                "已验证产物回放只允许闭包顺序的连续前缀；任意合法子序列必须使用现场CAD执行器，"
                "以免累计产物夹带未请求模组。"
            )
        missing = [token for token in requested if token not in available]
        if missing:
            raise SemanticAssemblySequenceError(
                "缺少可执行的逐步CAD证据：" + "、".join(missing)
            )
        store = _assembly_job_store(workspace, project_id)
        job = store.create(
            plan,
            execution_mode=request.execution_mode,
            idempotency_key=request.idempotency_key,
        )
        if job["status"] == "queued":
            task = (
                _run_live_cad_assembly_job
                if request.execution_mode == "live_cad"
                else _run_validated_assembly_job
            )
            background_tasks.add_task(task, workspace, project_id, job["jobId"])
        return job
    except (AssemblyJobError, SemanticAssemblySequenceError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/semantic-assembly-sequence/jobs/{job_id}")
def get_semantic_assembly_job(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_job_id(job_id)
        return _assembly_job_store(workspace, project_id).load(job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/jobs/{job_id}/cancel")
def cancel_semantic_assembly_job(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_job_id(job_id)
        return _assembly_job_store(workspace, project_id).request_cancel(job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/jobs/{job_id}/pause")
def pause_semantic_assembly_job(job_id: str) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_job_id(job_id)
        return _assembly_job_store(workspace, project_id).request_pause(job_id)
    except AssemblyJobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/demo/semantic-assembly-sequence/jobs/{job_id}/resume")
def resume_semantic_assembly_job(job_id: str, background_tasks: BackgroundTasks) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        project_id = _project_id_from_job_id(job_id)
        store = _assembly_job_store(workspace, project_id)
        job = store.prepare_resume(job_id)
        task = (
            _run_live_cad_assembly_job
            if job.get("executionMode") == "live_cad"
            else _run_validated_assembly_job
        )
        background_tasks.add_task(task, workspace, project_id, job_id)
        return job
    except AssemblyJobError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/demo/semantic-port-catalog/apply")
async def apply_semantic_port_connection(
    request: SemanticConnectionApplyRequest,
    service: DemoService = Depends(get_service),
) -> dict:
    workspace = Path(__file__).resolve().parents[4]
    try:
        prepared = prepare_semantic_connection_application(
            workspace,
            request.model_dump(by_alias=True, exclude_none=True),
        )
        if prepared["executionMode"] == "context_incremental":
            operation = await service.insert_component_in_assembly_context(
                Path(prepared["sourceAssemblyPath"]),
                Path(prepared["effectiveGraphPath"]),
                Path(prepared["outputAssemblyPath"]),
                str(prepared["targetModuleToken"]),
            )
        else:
            operation = await service.rebuild_effective_mate_graph(
                Path(prepared["effectiveGraphPath"]),
                Path(prepared["outputAssemblyPath"]),
            )
        return finalize_semantic_connection_application(
            prepared,
            operation.model_dump(by_alias=True),
        )
    except (SemanticPortWorkbenchError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/demo/state", response_model=DemoState)
def get_demo_state(service: DemoService = Depends(get_service)) -> DemoState:
    return service.get_state()


@app.put("/api/demo/state", response_model=DemoState)
def put_demo_state(state: DemoState, service: DemoService = Depends(get_service)) -> DemoState:
    return service.save_state(state)


@app.post("/api/demo/reset", response_model=DemoState)
def reset_demo_state(service: DemoService = Depends(get_service)) -> DemoState:
    return service.reset_state()


@app.post("/api/demo/import", response_model=OperationResult)
async def import_components(service: DemoService = Depends(get_service)) -> OperationResult:
    return await service.import_components()


@app.post("/api/demo/align-bottom", response_model=OperationResult)
async def align_bottom(service: DemoService = Depends(get_service)) -> OperationResult:
    return await service.align_bottom()


@app.post("/api/demo/initialize-common-base", response_model=OperationResult)
async def initialize_common_base(
    request: ApplyLayoutRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.initialize_common_base(request)


@app.post("/api/demo/finalize-common-base", response_model=OperationResult)
async def finalize_common_base(service: DemoService = Depends(get_service)) -> OperationResult:
    return await service.finalize_common_base()


@app.post("/api/demo/capture-common-base-layout", response_model=OperationResult)
async def capture_common_base_layout(service: DemoService = Depends(get_service)) -> OperationResult:
    return await service.capture_common_base_layout()


@app.post("/api/demo/discover-components", response_model=OperationResult)
async def discover_components(
    request: DiscoverComponentsRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.discover_components(request)


@app.post("/api/demo/sync-discovered-components", response_model=OperationResult)
def sync_discovered_components(
    request: SyncDiscoveredComponentsRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return service.sync_discovered_components(request)


@app.post("/api/demo/capture-project-layout", response_model=OperationResult)
async def capture_project_layout(
    request: CaptureProjectLayoutRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.capture_project_layout(request)


@app.post("/api/demo/generate-constraint-layout", response_model=OperationResult)
async def generate_constraint_layout(
    request: GenerateConstraintLayoutRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.generate_constraint_layout(request)


@app.get("/api/demo/layout-json-files", response_model=list[LayoutJsonInfo])
def list_layout_json_files(service: DemoService = Depends(get_service)) -> list[LayoutJsonInfo]:
    return service.list_layout_json_files()


@app.post("/api/demo/select-layout-json", response_model=OperationResult)
def select_layout_json(
    request: SelectLayoutJsonRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return service.select_layout_json(request)


@app.post("/api/demo/upload-layout-json", response_model=OperationResult)
def upload_layout_json(
    request: UploadLayoutJsonRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return service.upload_layout_json(request)


@app.post("/api/demo/verify-face-mappings", response_model=OperationResult)
async def verify_face_mappings(service: DemoService = Depends(get_service)) -> OperationResult:
    return await service.verify_face_mappings()


@app.post("/api/demo/record-selected-face", response_model=OperationResult)
async def record_selected_face(
    request: RecordSelectedFaceRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.record_selected_face(request)


@app.post("/api/demo/apply-captured-layout", response_model=OperationResult)
async def apply_captured_layout(
    request: ApplyCapturedLayoutRequest | None = Body(default=None),
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.apply_captured_layout(request)


@app.post("/api/demo/apply-layout", response_model=OperationResult)
async def apply_layout(
    request: ApplyLayoutRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.apply_layout(request)


@app.post("/api/demo/arrange", response_model=OperationResult)
async def arrange(
    request: ApplyLayoutRequest,
    service: DemoService = Depends(get_service),
) -> OperationResult:
    return await service.arrange(request)


@app.get("/api/demo/screenshot")
def get_screenshot(service: DemoService = Depends(get_service)) -> FileResponse:
    state = service.get_state()
    last_run = state.last_run if isinstance(state.last_run, dict) else {}
    screenshot_path = last_run.get("screenshotPath")
    path = Path(screenshot_path) if isinstance(screenshot_path, str) and screenshot_path else None
    if path is None:
        path = Path(__file__).resolve().parents[4] / "demo" / "arrange_result_frontend.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot has not been generated yet.")
    return FileResponse(path, media_type="image/png")
