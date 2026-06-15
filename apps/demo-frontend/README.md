# SolidWorks Demo Frontend

React/Vite frontend for editing A/B/C target coordinates and triggering the backend `/api/demo/arrange` workflow.

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
