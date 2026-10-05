@echo off
setlocal EnableExtensions

REM ============================================================
REM configure-otel-k8s.bat
REM Configure OpenTelemetry environment variables on a Kubernetes
REM Deployment running in Docker Desktop Kubernetes.
REM
REM Usage:
REM   configure-otel-k8s.bat <deployment> <otel-service-name> [namespace]
REM
REM Examples:
REM   configure-otel-k8s.bat rag-answer-service rag-answer-service rag-poc
REM   configure-otel-k8s.bat rag-search-service rag-search-service rag-poc
REM   configure-otel-k8s.bat rag-ingest-service rag-ingest-service rag-poc
REM ============================================================

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "DEPLOYMENT=%~1"
set "OTEL_SERVICE_NAME=%~2"
set "NAMESPACE=%~3"
set "OTLP_ENDPOINT=http://host.docker.internal:4318"
set "OTEL_RESOURCE_ATTRIBUTES=service.namespace=rag-poc,deployment.environment=local"
set "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=click"

if "%NAMESPACE%"=="" set "NAMESPACE=default"

echo.
echo ============================================================
echo Configuring OpenTelemetry
echo ============================================================
echo Kubernetes deployment : %DEPLOYMENT%
echo Kubernetes namespace  : %NAMESPACE%
echo OTel service.name     : %OTEL_SERVICE_NAME%
echo OTLP endpoint         : %OTLP_ENDPOINT%
echo Disabled instrumentation: %OTEL_PYTHON_DISABLED_INSTRUMENTATIONS%
echo.

where kubectl >nul 2>&1
if errorlevel 1 (
    echo ERROR: kubectl was not found in PATH.
    exit /b 1
)

echo Checking deployment...
kubectl get deployment "%DEPLOYMENT%" -n "%NAMESPACE%" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Deployment "%DEPLOYMENT%" was not found in namespace "%NAMESPACE%".
    echo.
    echo Available deployments:
    kubectl get deployments -n "%NAMESPACE%"
    exit /b 1
)

echo Applying OpenTelemetry environment variables...
kubectl set env "deployment/%DEPLOYMENT%" -n "%NAMESPACE%" ^
    OTEL_SERVICE_NAME="%OTEL_SERVICE_NAME%" ^
    OTEL_RESOURCE_ATTRIBUTES="%OTEL_RESOURCE_ATTRIBUTES%" ^
    OTEL_EXPORTER_OTLP_ENDPOINT="%OTLP_ENDPOINT%" ^
    OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf" ^
    OTEL_TRACES_EXPORTER="otlp" ^
    OTEL_METRICS_EXPORTER="otlp" ^
    OTEL_LOGS_EXPORTER="otlp" ^
    OTEL_PYTHON_LOG_CORRELATION="true" ^
    OTEL_PYTHON_DISABLED_INSTRUMENTATIONS="%OTEL_PYTHON_DISABLED_INSTRUMENTATIONS%"
if errorlevel 1 (
    echo ERROR: kubectl set env failed.
    exit /b 1
)

echo.
echo Waiting for Kubernetes rollout...
kubectl rollout status "deployment/%DEPLOYMENT%" -n "%NAMESPACE%" --timeout=120s
if errorlevel 1 (
    echo ERROR: Rollout did not complete successfully.
    echo Check:
    echo   kubectl get pods -n %NAMESPACE%
    echo   kubectl describe deployment %DEPLOYMENT% -n %NAMESPACE%
    exit /b 1
)

echo.
echo Current OTel environment variables on the deployment:
kubectl set env "deployment/%DEPLOYMENT%" -n "%NAMESPACE%" --list | findstr /I /C:"OTEL_"
if errorlevel 1 (
    echo ERROR: Unable to confirm OTEL_* variables on the deployment.
    exit /b 1
)

echo.
echo OpenTelemetry environment configuration completed.
echo.
echo IMPORTANT:
echo The container image must also contain the OpenTelemetry Python packages,
echo and the Python process must be started through opentelemetry-instrument.
echo.
exit /b 0

:usage
echo.
echo Usage:
echo   %~nx0 ^<deployment^> ^<otel-service-name^> [namespace]
echo.
echo Example:
echo   %~nx0 rag-answer-service rag-answer-service rag-poc
echo.
exit /b 2
