@echo off
setlocal

set PORT=8010
set APP_MODULE=app.main:app
set TITLE=secure-api-gateway
set PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo Starting %TITLE% on http://localhost:%PORT%
echo Press Ctrl+C to stop the service.

pushd "%~dp0"
"%PYTHON_EXE%" -m uvicorn %APP_MODULE% --reload --port %PORT%
popd

endlocal
