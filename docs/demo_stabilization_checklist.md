# Demo Stabilization And Pre-Commit Checklist

Updated: 2026-06-30

## Current Stable Capability

The current demo version has passed this loop:

```text
Reference assembly X_reference_spread
  -> capture layout2d x/y/theta
  -> create a fresh assembly
  -> insert A/B/C
  -> run Common Base
  -> replay Layout2D
  -> recapture and compare
```

Verified result:

```text
A-1 xy_error=0, theta_error=0deg
B-1 xy_error=0, theta_error=0deg
C-1 xy_error=1.11e-16m, theta_error=0deg
```

## Recommended Startup Path

Use direct MCP stdio for backend automation. This avoids the stale named-pipe lifecycle issues seen with the old Hub/proxy path.

PowerShell:

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp
$env:DEMO_MCP_MODE="bridge"
$env:DEMO_MCP_COMMAND="dotnet"
$env:DEMO_MCP_CWD="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
$env:DEMO_FACE_MAPPING_PATH="D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\artifacts\solidworks-mcp\face_mappings.json"
$env:DEMO_MCP_TIMEOUT_SECONDS="420"
python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd D:\zengshuang\workspace\cuhksz\cad\solidworks_mcp\apps\demo-frontend
npm install
npm run dev
```

## Recommended Demo Order

```text
Reset
Initialize
Common Base
Capture Layout
Replay Layout
```

## Pre-Commit Recommendation

Commit:

- `apps/demo-backend/**` source and README.
- `apps/demo-frontend/src/**` source and README.
- `scripts/capture_common_base_layout.py`
- `scripts/apply_captured_common_base_layout.py`
- `scripts/face_mapping_record_probe.py`
- `scripts/face_mapping_verify_select.py`
- MCP tool changes under `vendor/solidworks-mcp/app/SolidWorksMcpApp/**`.
- SolidWorks service/math/selection changes under `vendor/solidworks-mcp/bridge/SolidWorksBridge/**`.
- New or updated tests under `vendor/solidworks-mcp/bridge/SolidWorksBridge.Tests/**`.
- `docs/**`.
- `.gitignore`.

Do not commit:

- `demo/*.SLDASM`
- `demo/*.png`
- `demo/demo_state.json`
- `logs/**`
- `apps/demo-frontend/tsconfig.tsbuildinfo`
- root scratch files: `cad_task.md`, `solve_problem.md`, `git`, `python`

Optional:

- A minimal pair of final layout JSON samples:
  - `demo/x_reference_layout2d_theta.json`
  - `demo/abc_replay_from_x_reference_theta_signfix_layout2d.json`

## Commit Suggestion

Commit locally first. Do not push until the branch has been reviewed.

Suggested message:

```text
Add common-base layout2d theta replay workflow
```

Pre-commit checks:

```powershell
dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release
python -m compileall scripts\capture_common_base_layout.py scripts\apply_captured_common_base_layout.py
```

Note:

- `dotnet test` may currently be blocked by Windows application control policy while loading the test DLL. This is an environment restriction, not an assertion failure in the new math tests.
