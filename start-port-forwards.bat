@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM Start Kubernetes port-forwards for My-Agent-Poc
REM Namespace: rag-poc
REM
REM Secure API is intentionally started FIRST.
REM ============================================================

set "NAMESPACE=rag-poc"
set "SCRIPT_DIR=%~dp0"
set "PID_DIR=%SCRIPT_DIR%.port-forward-pids"
set "LOG_DIR=%SCRIPT_DIR%.port-forward-logs"

if not exist "%PID_DIR%" mkdir "%PID_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ============================================================
echo STARTING KUBERNETES PORT FORWARDS
echo Namespace: %NAMESPACE%
echo ============================================================
echo.

call :start_forward "secure-api" 8003 8003
call :start_forward "rag-ingest-service" 8000 8000
call :start_forward "rag-search-service" 8001 8001
call :start_forward "rag-answer-service" 8002 8002

echo.
echo ============================================================
echo PORT-FORWARD START REQUESTS COMPLETE
echo ============================================================
echo.
echo Expected local URLs:
echo   Secure API:          http://localhost:8003
echo   RAG Ingest Service:  http://localhost:8000
echo   RAG Search Service:  http://localhost:8001
echo   RAG Answer Service:  http://localhost:8002
echo.
echo Verification:
echo   kubectl -n %NAMESPACE% get svc
kubectl -n "%NAMESPACE%" get svc
echo.
echo PID files:
dir /b "%PID_DIR%" 2>nul
echo.
echo Logs:
echo   %LOG_DIR%
echo.
echo Script completed. Port-forward processes continue in background.
exit /b 0


:start_forward
set "SERVICE=%~1"
set "LOCAL_PORT=%~2"
set "REMOTE_PORT=%~3"
set "PID_FILE=%PID_DIR%\%SERVICE%.pid"
set "LOG_FILE=%LOG_DIR%\%SERVICE%.log"
set "ERR_FILE=%LOG_DIR%\%SERVICE%.err.log"

echo ------------------------------------------------------------
echo Service: %SERVICE%
echo Command:
echo   kubectl -n %NAMESPACE% port-forward service/%SERVICE% %LOCAL_PORT%:%REMOTE_PORT%
echo ------------------------------------------------------------

REM Verify service exists before starting.
kubectl -n "%NAMESPACE%" get service "%SERVICE%" >nul 2>&1
if errorlevel 1 (
    echo WARNING: service/%SERVICE% does not currently exist in namespace %NAMESPACE%.
    echo          Skipping this port-forward for now.
    echo.
    exit /b 0
)

REM If a prior PID file exists and process is still alive, do not start duplicate.
if exist "%PID_FILE%" (
    set /p OLD_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !OLD_PID!" 2>nul | findstr /R /C:"[ ]!OLD_PID![ ]" >nul
    if not errorlevel 1 (
        echo Already running with PID !OLD_PID!. Skipping duplicate.
        echo.
        exit /b 0
    )
    del /q "%PID_FILE%" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath 'kubectl.exe' -ArgumentList @('-n','%NAMESPACE%','port-forward','service/%SERVICE%','%LOCAL_PORT%:%REMOTE_PORT%') -WindowStyle Hidden -RedirectStandardOutput '%LOG_FILE%' -RedirectStandardError '%ERR_FILE%' -PassThru; Set-Content -Path '%PID_FILE%' -Value $p.Id"

if errorlevel 1 (
    echo ERROR: Failed to start port-forward for %SERVICE%.
    echo.
    exit /b 0
)

timeout /t 2 /nobreak >nul

if exist "%PID_FILE%" (
    set /p NEW_PID=<"%PID_FILE%"
    tasklist /FI "PID eq !NEW_PID!" 2>nul | findstr /R /C:"[ ]!NEW_PID![ ]" >nul
    if not errorlevel 1 (
        echo STARTED: %SERVICE% on localhost:%LOCAL_PORT%  PID=!NEW_PID!
    ) else (
        echo WARNING: %SERVICE% process exited immediately.
        echo          Check:
        echo          %ERR_FILE%
    )
)
echo.
exit /b 0
