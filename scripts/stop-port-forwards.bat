@echo off
setlocal EnableExtensions
set "PID_DIR=%TEMP%\my-agent-poc-port-forwards"
if not exist "%PID_DIR%" (
  echo No saved port-forward processes found.
  exit /b 0
)
for %%F in ("%PID_DIR%\*.pid") do (
  if exist "%%~fF" (
    set /p PID=<"%%~fF"
    call :stopPid "%%~nF" "%%~fF"
  )
)
echo Port-forward cleanup complete.
exit /b 0

:stopPid
set "NAME=%~1"
set "FILE=%~2"
set /p PID=<"%FILE%"
if defined PID taskkill /PID %PID% /F >nul 2>&1
del /q "%FILE%" >nul 2>&1
echo STOPPED: %NAME%
exit /b 0
