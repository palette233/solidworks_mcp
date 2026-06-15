# SolidWorks Demo Frontend

React/Vite frontend for dragging A/B/C blocks in a 2D layout and triggering the backend `/api/demo/arrange` workflow.

The block center represents the SolidWorks bottom-face center:

- Screen right = SolidWorks +X
- Screen up = SolidWorks +Y
- Z is still editable in the coordinate table

## Run

Start the backend first:

```powershell
$env:DEMO_MCP_MODE='bridge'
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

## cmd

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
set DEMO_MCP_MODE=bridge
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --reload --host 127.0.0.1 --port 8000
```

```cmd
cd /d D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
npm run dev
```
