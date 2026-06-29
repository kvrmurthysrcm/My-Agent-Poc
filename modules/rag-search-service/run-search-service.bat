@echo off
setlocal

cd /d "%~dp0"

set "LOG_DIR=D:\tmp"
set "LOG_FILE=%LOG_DIR%\rag_search_service.combined.log"
set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%VENV_PY%" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Installing dependencies...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    )
)

echo Starting rag-search-service on http://127.0.0.1:8001
echo Writing logs to %LOG_FILE%
echo Tail logs with:
echo   powershell -NoProfile -Command "Get-Content -Wait -Tail 100 '%LOG_FILE%'"
echo.
echo Press Ctrl+C to stop the service.
echo ============================================================ > "%LOG_FILE%"
echo rag-search-service started at %DATE% %TIME% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

set "PYTHONUNBUFFERED=1"
"%VENV_PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001 >> "%LOG_FILE%" 2>&1

endlocal
