@echo off
setlocal

cd /d "%~dp0\.."

set "DEMO_MCP_MODE=bridge"
set "DEMO_MCP_COMMAND=dotnet"
set "DEMO_MCP_CWD=%CD%\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
set "DEMO_FACE_MAPPING_PATH=%CD%\artifacts\solidworks-mcp\face_mappings.json"
set "DEMO_MCP_TIMEOUT_SECONDS=420"

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

python -m uvicorn demo_backend.main:app --app-dir apps/demo-backend/src --host 127.0.0.1 --port 8000
