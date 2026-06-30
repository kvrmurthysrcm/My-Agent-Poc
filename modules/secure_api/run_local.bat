@echo off
setlocal

set PORT=8010
set APP_MODULE=app.main:app
set TITLE=secure-api-gateway
set PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo Starting %TITLE% on http://localhost:%PORT%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList '-m uvicorn %APP_MODULE% --reload --port %PORT%' -WorkingDirectory '%~dp0' -PassThru; Write-Host 'Service PID:' $p.Id; Write-Host 'Stop command: taskkill /PID' $p.Id '/F'"

endlocal
