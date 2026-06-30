# Demo Backend

FastAPI backend for the SolidWorks common-base layout demo.

It provides the HTTP boundary between the frontend and the SolidWorks MCP tool layer. The current stable path uses direct MCP stdio:

```text
McpToolRunner -> dotnet SolidWorksMcpApp.dll --stdio-direct -> SolidWorks COM
```

## Run

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
$env:DEMO_MCP_MODE="bridge"
$env:DEMO_MCP_COMMAND="dotnet"
$env:DEMO_MCP_CWD="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
$env:DEMO_FACE_MAPPING_PATH="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json"
$env:DEMO_MCP_TIMEOUT_SECONDS="420"
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Health Check

```powershell
curl.exe http://127.0.0.1:8000/api/health
```

Expected configuration:

- `mcpMode`: `bridge`
- `mcpCommand`: `dotnet`
- `mcpCwd`: the Release `win-x64` folder containing `SolidWorksMcpApp.dll`
- default MCP args are inferred as `SolidWorksMcpApp.dll --stdio-direct`

## Main Endpoints

```text
GET  /api/health
GET  /api/demo/state
PUT  /api/demo/state
POST /api/demo/reset
POST /api/demo/initialize-common-base
POST /api/demo/finalize-common-base
POST /api/demo/capture-common-base-layout
POST /api/demo/apply-captured-layout
POST /api/demo/arrange
GET  /api/demo/screenshot
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

This file is intentionally ignored by git because it is local runtime state.
