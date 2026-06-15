from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .adapters.llm_client import LlmClient
from .adapters.mcp_client import McpClient
from .config import Settings, get_settings
from .face_mappings import FaceMappingStore
from .models import ApplyLayoutRequest, DemoState, OperationResult
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
    return DemoService(store, face_mappings, llm, mcp)


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
    }


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
def get_screenshot() -> FileResponse:
    path = Path(__file__).resolve().parents[4] / "demo" / "arrange_result_frontend.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot has not been generated yet.")
    return FileResponse(path, media_type="image/png")
