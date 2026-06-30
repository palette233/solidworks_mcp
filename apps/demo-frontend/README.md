# SolidWorks Demo Frontend

React/Vite frontend for the SolidWorks common-base layout demo.

The current demo flow supports:

- initialize a target assembly with A/B/C;
- finalize common-base mates;
- capture layout2d from a reference assembly;
- choose or upload captured layout JSON;
- display each component's layout2d x/y/theta;
- verify bottom-face mappings in batch;
- replay captured layout2d position and in-plane theta.

The 2D block center represents the SolidWorks bottom-face center:

- screen right maps to the layout frame +X direction;
- screen up maps to the layout frame +Y direction;
- replay layout can also restore `thetaDegrees/thetaAxis` captured from Transform2.

## Run

Start the backend first:

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
$env:DEMO_MCP_MODE="bridge"
$env:DEMO_MCP_COMMAND="dotnet"
$env:DEMO_MCP_CWD="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
$env:DEMO_FACE_MAPPING_PATH="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json"
$env:DEMO_MCP_TIMEOUT_SECONDS="420"
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --reload --host 127.0.0.1 --port 8000
```

Then start the frontend:

```powershell
cd apps/demo-frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Demo Order

For the current stable demo, use this order:

```text
Reset
Initialize
Common Base
Verify Faces
Capture Layout
Replay Layout
```

`Capture Layout` writes the current common-base layout to JSON. `Replay Layout` applies a captured JSON layout to the initialized assembly.

## cmd

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
set DEMO_MCP_MODE=bridge
set DEMO_MCP_COMMAND=dotnet
set DEMO_MCP_CWD=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64
set DEMO_FACE_MAPPING_PATH=D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json
set DEMO_MCP_TIMEOUT_SECONDS=420
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --reload --host 127.0.0.1 --port 8000
```

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
npm run dev
```
