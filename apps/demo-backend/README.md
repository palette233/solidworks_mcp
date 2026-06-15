# Demo Backend

FastAPI backend skeleton for the SolidWorks layout demo.

It provides a stable HTTP boundary between the future frontend, the LLM orchestration layer, and the SolidWorks MCP tool layer.

## Run

```powershell
cd apps/demo-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn demo_backend.main:app --reload --host 127.0.0.1 --port 8010
```

Open:

```text
http://127.0.0.1:8010/docs
```

## Current Status

This is a skeleton. It persists demo state and returns explicit execution plans, but the MCP and LLM adapters are placeholders.

The next implementation step is to replace `McpClient.apply_layout()` with real calls to the SolidWorks MCP server.

## Main Endpoints

```text
GET  /api/health
GET  /api/demo/state
PUT  /api/demo/state
POST /api/demo/reset
POST /api/demo/import
POST /api/demo/align-bottom
POST /api/demo/apply-layout
```

## Default State

By default, the backend uses:

```text
demo/testdata/A.SLDASM
demo/testdata/B.SLDASM
demo/testdata/C.SLDASM
```

Runtime state is written to:

```text
demo/demo_state.json
```
