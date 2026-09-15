@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "NS=rag-poc"
set "PID_DIR=%TEMP%\my-agent-poc-port-forwards"
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

echo Starting cumulative Kubernetes port forwards...
call :startForward secure-api 8010 8010
call :startForward rag-ingest-service 8000 8000
call :startForward rag-search-service 8001 8001
call :startForward rag-answer-service 8002 8002
call :startForward online-library 8003 8003
call :startForward online-library-mcp 8004 8004
call :startForward online-library-agent 8005 8005
call :startForward weather-agent 8006 8006
call :startForward weather-ai-agent 8007 8007
call :startForward angular-ui 4200 8080

echo.
echo Port forwards requested.
echo Secure API:      http://localhost:8010
echo Ingest:          http://localhost:8000
echo Search:          http://localhost:8001
echo Answer:          http://localhost:8002
echo Online Library:  http://localhost:8003
echo Library MCP:     http://localhost:8004/mcp
echo Library Agent:   http://localhost:8005
echo Weather Agent:   http://localhost:8006
echo Weather AI:      http://localhost:8007
echo Angular UI:      http://localhost:4200
exit /b 0

:startForward
set "SVC=%~1"
set "LOCAL=%~2"
set "REMOTE=%~3"
kubectl -n "%NS%" get service "%SVC%" >nul 2>&1
if errorlevel 1 (
  echo SKIP: service/%SVC% is not deployed.
  exit /b 0
)
for /f %%P in ('powershell -NoProfile -Command "$p=Start-Process -FilePath kubectl -ArgumentList @('-n','%NS%','port-forward','service/%SVC%','%LOCAL%:%REMOTE%') -WindowStyle Hidden -PassThru; $p.Id"') do set "PF_PID=%%P"
echo %PF_PID%>"%PID_DIR%\%SVC%.pid"
echo STARTED: %SVC% localhost:%LOCAL% -^> %REMOTE% ^(PID %PF_PID%^)
exit /b 0
