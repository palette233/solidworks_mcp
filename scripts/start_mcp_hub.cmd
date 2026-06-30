@echo off
setlocal

cd /d "%~dp0\.."

set "MCP_CWD=%CD%\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64"
set "MCP_DLL=%MCP_CWD%\SolidWorksMcpApp.dll"
set "DEMO_FACE_MAPPING_PATH=%CD%\artifacts\solidworks-mcp\face_mappings.json"

if not exist "%MCP_DLL%" (
  echo SolidWorksMcpApp.dll was not found:
  echo   %MCP_DLL%
  echo Run dotnet build vendor\solidworks-mcp\app\SolidWorksMcpApp\SolidWorksMcpApp.csproj -c Release first.
  exit /b 1
)

echo Starting MCP headless hub...
echo   DLL:  %MCP_DLL%
echo   CWD:  %MCP_CWD%
echo   DEMO_FACE_MAPPING_PATH=%DEMO_FACE_MAPPING_PATH%
echo.

if /I "%~1"=="/dry-run" (
  echo Dry run only. Command that would be started:
  echo   start "SolidWorks MCP Hub" /D "%MCP_CWD%" cmd /k "set ""DEMO_FACE_MAPPING_PATH=%DEMO_FACE_MAPPING_PATH%"" && dotnet ""%MCP_DLL%"" --headless-hub"
  exit /b 0
)

start "SolidWorks MCP Hub" /D "%MCP_CWD%" cmd /k "set ""DEMO_FACE_MAPPING_PATH=%DEMO_FACE_MAPPING_PATH%"" && dotnet ""%MCP_DLL%"" --headless-hub"

echo Started a new MCP Hub window. Keep that window open while testing Hub/proxy mode.
echo Use scripts\check_mcp_hub.cmd to verify process and pipe status.
