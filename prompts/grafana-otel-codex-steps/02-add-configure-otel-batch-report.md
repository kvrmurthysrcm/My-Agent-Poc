# Step 02 - Kubernetes OTel Configuration Script Report

**Status:** Completed successfully  
**Run date:** 2026-10-04  
**Scope:** Added only the required runtime batch script. This report was also created at the user's request. No Python, Dockerfile, requirements, Kubernetes YAML, image, container, or live Kubernetes resource was changed.

## Result

Added [scripts/configure-otel-k8s.bat](/D:/py-workspace/My-Agent-Poc/scripts/configure-otel-k8s.bat).

The script:

- Accepts configure-otel-k8s.bat <deployment> <otel-service-name> [namespace].
- Defaults the optional namespace to default, exactly as required by Step 02.
- Uses the Docker Desktop pod-to-host endpoint http://host.docker.internal:4318.
- Sets all required OTEL_* variables through kubectl set env.
- Verifies kubectl and the target Deployment before making a change.
- Waits up to 120 seconds for rollout completion and returns a clear error on failure.
- Prints the Deployment's configured OTEL_* values.
- Does not select Pods using app=<deployment>, so it does not assume the app label equals the Deployment name.

## Important use note

The live RAG Deployments inspected in Step 01 reside in namespace rag-poc. The required default remains default, so the approved Step 03 invocation must pass rag-poc explicitly:

~~~text
scripts\configure-otel-k8s.bat rag-answer-service rag-answer-service rag-poc
~~~

The script was intentionally not executed in Step 02, because kubectl set env would change the Deployment and trigger a rollout.

## Final script

~~~bat
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

if "%NAMESPACE%"=="" set "NAMESPACE=default"

echo.
echo ============================================================
echo Configuring OpenTelemetry
echo ============================================================
echo Kubernetes deployment : %DEPLOYMENT%
echo Kubernetes namespace  : %NAMESPACE%
echo OTel service.name     : %OTEL_SERVICE_NAME%
echo OTLP endpoint         : %OTLP_ENDPOINT%
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
    OTEL_PYTHON_LOG_CORRELATION="true"
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
~~~

## Diff

The script is a new 106-line file; therefore every line in the final script above is an addition. The read-only Git diff was:

~~~diff
diff --git a/scripts/configure-otel-k8s.bat b/scripts/configure-otel-k8s.bat
new file mode 100644
index 0000000..89f2917
--- /dev/null
+++ b/scripts/configure-otel-k8s.bat
@@ -0,0 +1,106 @@
+[all 106 lines shown in the Final script section]
~~~

## Validation performed

| Validation | Result |
| --- | --- |
| Required usage contract is present | Passed |
| Default namespace is default | Passed |
| OTLP endpoint is host.docker.internal:4318 | Passed |
| All eight required OTEL_* settings are present | Passed |
| kubectl presence and Deployment existence checks are present | Passed |
| kubectl set env and rollout status are present with explicit error paths | Passed |
| OTEL_* verification output is present | Passed |
| No app label selector assumes a Deployment name | Passed |
| New-file diff whitespace check | Passed; Git only noted normal LF-to-CRLF normalization on a Windows checkout. |

## Test-run details

No batch execution, unit tests, Docker builds, image rebuilds, deployments, or rollouts were run. This is intentional: Step 02 requires a script implementation and explicitly says not to run it yet.

## Next decision gate

Step 02 is complete. Approve Step 03 to apply this script only to rag-answer-service in namespace rag-poc and validate the resulting Deployment environment.
