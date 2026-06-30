@echo off
setlocal

set TITLE=online-library-tools
set PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo Starting %TITLE% on http://localhost:8004/mcp
echo Press Ctrl+C to stop the service.

pushd "%~dp0..\.."
"%PYTHON_EXE%" -m modules.online_library_mcp.server
popd

endlocal
