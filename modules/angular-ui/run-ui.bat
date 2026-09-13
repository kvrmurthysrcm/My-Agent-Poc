@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Use the project-approved Node installation regardless of the global PATH order.
set "NODE_HOME=D:\common\node-v24.10.0-win-x64"
set "NODE_EXE=%NODE_HOME%\node.exe"
set "NPM_CMD=%NODE_HOME%\npm.cmd"

if not exist "%NODE_EXE%" (
  echo ERROR: Node was not found at "%NODE_EXE%".
  echo Update NODE_HOME in this file to the folder containing node.exe.
  exit /b 1
)

if not exist "%NPM_CMD%" (
  echo ERROR: npm was not found at "%NPM_CMD%".
  echo Reinstall Node.js, or update NODE_HOME in this file.
  exit /b 1
)

set "PATH=%NODE_HOME%;%PATH%"
pushd "%~dp0" || (
  echo ERROR: Could not open the Angular UI folder.
  exit /b 1
)

echo Using Node:
"%NODE_EXE%" --version
if errorlevel 1 goto :failed

rem Angular 21.2 supports Node >=24.0.0; this project intentionally pins Node 24.10.x.
"%NODE_EXE%" -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major === 24 && minor === 10 ? 0 : 1)"
if errorlevel 1 (
  echo ERROR: This UI requires Node 24.10.x.
  popd
  exit /b 1
)

if /I "%~1"=="help" (
  set "RESULT=0"
  goto :help
)
if /I "%~1"=="install" goto :install
if /I "%~1"=="test" goto :test
if /I "%~1"=="build" goto :build
if /I "%~1"=="start" (
  shift
  goto :start
)
if "%~1"=="" goto :start

echo ERROR: Unknown command "%~1".
set "RESULT=1"
goto :help

:start
if not exist "node_modules\" (
  echo node_modules is missing. Installing locked dependencies...
  call "%NPM_CMD%" ci
  if errorlevel 1 goto :failed
)

echo Starting Angular UI at http://localhost:4200 ...
call "%NPM_CMD%" start -- %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :finished

:install
echo Installing locked dependencies...
call "%NPM_CMD%" ci
goto :finished

:test
shift
call "%NPM_CMD%" test -- %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :finished

:build
shift
call "%NPM_CMD%" run build -- %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :finished

:help
echo.
echo Usage:
echo   run-ui.bat                    Start the Angular development server.
echo   run-ui.bat start [ng options] Start with Angular CLI options, for example --port 4300.
echo   run-ui.bat install            Reinstall dependencies from package-lock.json.
echo   run-ui.bat test [ng options]  Run Angular tests.
echo   run-ui.bat build [ng options] Build the production bundle.
popd
exit /b !RESULT!

:failed
set "RESULT=!ERRORLEVEL!"
popd
exit /b !RESULT!

:finished
set "RESULT=!ERRORLEVEL!"
popd
exit /b !RESULT!
