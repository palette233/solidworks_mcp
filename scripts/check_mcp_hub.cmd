@echo off
setlocal

cd /d "%~dp0\.."

set "MCP_DLL=%CD%\vendor\solidworks-mcp\app\SolidWorksMcpApp\bin\Release\net8.0-windows\win-x64\SolidWorksMcpApp.dll"
set "PIPE_NAME=SolidWorksMcpHub"

echo MCP Hub check
echo   DLL:  %MCP_DLL%
echo   Pipe: \\.\pipe\%PIPE_NAME%
echo.

if exist "%MCP_DLL%" (
  echo DLL status: found
) else (
  echo DLL status: missing
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $items = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { ($_.Name -in @('SolidWorksMcpApp.exe','dotnet.exe')) -and ($_.CommandLine -like '*SolidWorksMcpApp*') }; " ^
  "if (-not $items) { Write-Host 'MCP process status: none'; } else { Write-Host 'MCP process status:'; $items | Select-Object ProcessId,Name,CommandLine | Format-List; } } " ^
  "catch { Write-Host 'MCP process status: command-line query unavailable.'; Write-Host ('Reason: ' + $_.Exception.Message); $fallback = Get-Process -Name SolidWorksMcpApp,dotnet -ErrorAction SilentlyContinue; if ($fallback) { $fallback | Select-Object Id,ProcessName,Path | Format-List; } else { Write-Host 'No SolidWorksMcpApp/dotnet processes visible through Get-Process.'; } } " ^
  "$pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', '%PIPE_NAME%', [System.IO.Pipes.PipeDirection]::InOut); try { $pipe.Connect(200); Write-Host 'Pipe status: connectable'; } catch { Write-Host 'Pipe status: not connectable'; } finally { $pipe.Dispose(); }"

echo.
echo Note:
echo   Backend automation normally uses --stdio-direct and does not require a long-lived Hub.
echo   Use start_mcp_hub.cmd only when you explicitly want to test Hub/proxy mode.
