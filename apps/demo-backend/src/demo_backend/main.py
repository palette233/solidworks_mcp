from __future__ import annotations

from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query
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
)
from .mate_face_workbench import (
    MateFaceWorkbenchError,
    build_face_mate_patch_preview,
    finalize_face_mate_patch_application,
    load_face_endpoint_workbench,
    prepare_face_mate_patch_application,
)
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
