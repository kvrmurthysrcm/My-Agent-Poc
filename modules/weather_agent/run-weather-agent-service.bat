@echo off
setlocal

set "PORT=8006"
set "APP_MODULE=modules.weather_agent.api:app"
set "TITLE=weather-agent"
set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Starting %TITLE% on http://localhost:%PORT%
echo Press Ctrl+C to stop the service.

pushd "%~dp0..\.."
"%PYTHON_EXE%" -m uvicorn %APP_MODULE% --reload --host 127.0.0.1 --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"
popd

endlocal & exit /b %EXIT_CODE%
