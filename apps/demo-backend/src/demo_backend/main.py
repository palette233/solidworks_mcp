from __future__ import annotations

from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .adapters.llm_client import LlmClient
from .adapters.mcp_client import McpClient
from .config import Settings, get_settings
from .face_mappings import FaceMappingStore
from .models import (
    ApplyLayoutRequest,
    CaptureProjectLayoutRequest,
    DemoState,
    DiscoverComponentsRequest,
    LayoutJsonInfo,
    McpHealthResult,
    OperationResult,
    ApplyCapturedLayoutRequest,
    RecordSelectedFaceRequest,
    SelectLayoutJsonRequest,
    SyncDiscoveredComponentsRequest,
    UploadLayoutJsonRequest,
)
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


@app.get("/api/demo/mcp-health", response_model=McpHealthResult)
async def demo_mcp_health(service: DemoService = Depends(get_service)) -> McpHealthResult:
    return await service.mcp_health()


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
