@echo off
setlocal

cd /d "%~dp0\.."

set "DEMO_MCP_MODE=bridge"
set "DEMO_MCP_COMMAND=dotnet"
set "DEMO_MCP_CWD=%CD%\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
set "DEMO_FACE_MAPPING_PATH=%CD%\artifacts\solidworks-mcp\face_mappings.json"
set "DEMO_MCP_TIMEOUT_SECONDS=420"
set "DEMO_INITIALIZE_BATCH_SIZE=4"
if "%DEMO_TARGET_ASSEMBLY_PATH%"=="" set "DEMO_TARGET_ASSEMBLY_PATH=%CD%\demo\ABC_arrange_demo.SLDASM"
set "DEMO_REPLAY_XY_TOLERANCE_METERS=0.000001"
set "DEMO_REPLAY_THETA_TOLERANCE_DEGREES=0.0001"

if not exist "%DEMO_MCP_CWD%\SolidWorksMcpApp.dll" (
  echo SolidWorksMcpApp.dll was not found:
  echo   %DEMO_MCP_CWD%\SolidWorksMcpApp.dll
  echo Run dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release first.
  exit /b 1
)

echo Starting demo backend...
echo   DEMO_MCP_MODE=%DEMO_MCP_MODE%
echo   DEMO_MCP_COMMAND=%DEMO_MCP_COMMAND%
echo   DEMO_MCP_CWD=%DEMO_MCP_CWD%
echo   DEMO_FACE_MAPPING_PATH=%DEMO_FACE_MAPPING_PATH%
echo   DEMO_MCP_TIMEOUT_SECONDS=%DEMO_MCP_TIMEOUT_SECONDS%
echo   DEMO_INITIALIZE_BATCH_SIZE=%DEMO_INITIALIZE_BATCH_SIZE%
echo   DEMO_TARGET_ASSEMBLY_PATH=%DEMO_TARGET_ASSEMBLY_PATH%
echo   DEMO_REPLAY_XY_TOLERANCE_METERS=%DEMO_REPLAY_XY_TOLERANCE_METERS%
echo   DEMO_REPLAY_THETA_TOLERANCE_DEGREES=%DEMO_REPLAY_THETA_TOLERANCE_DEGREES%

python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
