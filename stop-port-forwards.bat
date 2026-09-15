@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM Stop Kubernetes port-forwards for My-Agent-Poc
REM
REM Secure API is intentionally stopped FIRST.
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "PID_DIR=%SCRIPT_DIR%.port-forward-pids"

echo.
echo ============================================================
echo STOPPING KUBERNETES PORT FORWARDS
echo ============================================================
echo.

call :stop_forward "secure-api"
call :stop_forward "rag-ingest-service"
call :stop_forward "rag-search-service"
call :stop_forward "rag-answer-service"
call :stop_forward "online-library"
call :stop_forward "online-library-mcp"
call :stop_forward "online-library-agent"
call :stop_forward "weather-agent"
call :stop_forward "weather-ai-agent"
call :stop_forward "angular-ui"

echo.
echo ============================================================
echo PORT-FORWARD STOP COMPLETE
echo ============================================================
echo.
echo Verification - remaining kubectl port-forward processes:
powershell -NoProfile -Command ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^kubectl(\.exe)?$' -and $_.CommandLine -match 'port-forward' }; if ($p) { $p | Select-Object ProcessId,CommandLine | Format-Table -AutoSize } else { Write-Host 'No kubectl port-forward processes found.' }"

echo.
echo Script completed. Exiting automatically.
exit /b 0


:stop_forward
set "SERVICE=%~1"
set "PID_FILE=%PID_DIR%\%SERVICE%.pid"

echo ------------------------------------------------------------
echo Service: %SERVICE%
echo ------------------------------------------------------------

if not exist "%PID_FILE%" (
    echo No PID file found. Nothing to stop.
    echo.
    exit /b 0
)

set /p PID=<"%PID_FILE%"

echo Command:
echo   taskkill /PID !PID! /T /F
taskkill /PID !PID! /T /F >nul 2>&1

if errorlevel 1 (
    echo Process !PID! was not running or could not be found.
) else (
    echo STOPPED: %SERVICE%  PID=!PID!
)

del /q "%PID_FILE%" >nul 2>&1
echo.
exit /b 0
