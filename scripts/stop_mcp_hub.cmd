@echo off
setlocal

cd /d "%~dp0\.."

set "MODE=%~1"

if /I "%MODE%"=="/all" (
  echo Stopping all SolidWorksMcpApp-related processes...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { $items = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { ($_.Name -in @('SolidWorksMcpApp.exe','dotnet.exe')) -and ($_.CommandLine -like '*SolidWorksMcpApp*') }; " ^
    "if (-not $items) { Write-Host 'No matching MCP processes.'; exit 0 }; " ^
    "$items | ForEach-Object { Write-Host ('Stopping PID {0}: {1}' -f $_.ProcessId, $_.CommandLine); Stop-Process -Id $_.ProcessId -Force } } " ^
    "catch { Write-Host 'Command-line process query unavailable; stopping SolidWorksMcpApp.exe only and leaving dotnet.exe untouched.'; Get-Process -Name SolidWorksMcpApp -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('Stopping PID {0}: {1}' -f $_.Id, $_.Path); Stop-Process -Id $_.Id -Force } }"
) else (
  echo Stopping headless MCP Hub processes only...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { $items = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { ($_.Name -in @('SolidWorksMcpApp.exe','dotnet.exe')) -and ($_.CommandLine -like '*SolidWorksMcpApp*') -and ($_.CommandLine -like '*--headless-hub*' -or $_.CommandLine -like '*--hub*') }; " ^
    "if (-not $items) { Write-Host 'No matching headless Hub processes.'; exit 0 }; " ^
    "$items | ForEach-Object { Write-Host ('Stopping PID {0}: {1}' -f $_.ProcessId, $_.CommandLine); Stop-Process -Id $_.ProcessId -Force } } " ^
    "catch { Write-Host 'Command-line process query unavailable; cannot safely identify headless Hub dotnet processes.'; Write-Host 'Run this script from a normal/elevated CMD, or use scripts\stop_mcp_hub.cmd /all if you only need to stop SolidWorksMcpApp.exe processes.' }"
)

echo.
echo Usage:
echo   scripts\stop_mcp_hub.cmd       stops only --headless-hub / --hub processes
echo   scripts\stop_mcp_hub.cmd /all  stops all SolidWorksMcpApp-related processes
