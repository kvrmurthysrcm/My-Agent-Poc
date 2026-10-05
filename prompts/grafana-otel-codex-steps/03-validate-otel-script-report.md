# Step 03 - OTel Script Validation Report

**Status:** Completed successfully  
**Run date:** 2026-10-04  
**Scope:** Applied the approved OpenTelemetry environment configuration only to the live rag-answer-service Deployment in rag-poc. This report is the only file created for this step. No application code, Dockerfile, dependency, image, Kubernetes manifest, or non-Answer Deployment was changed.

## Target identified

The read-only Deployment inventory confirmed the approved target:

| Field | Value |
| --- | --- |
| Deployment | rag-answer-service |
| Namespace | rag-poc |
| Image before and after rollout | rag-answer-service:46-61072fb |
| State before change | 1/1 Ready |
| State after change | 1/1 Ready |

The optional namespace argument was supplied explicitly because the Step 02 script's required fallback is default, while the live target is in rag-poc.

## Command executed

~~~text
cmd.exe /d /c "scripts\configure-otel-k8s.bat rag-answer-service rag-answer-service rag-poc"
~~~

The script exited with code 0 and reported:

1. The target Deployment exists.
2. The Deployment environment was updated.
3. One old replica terminated during the rollout.
4. The replacement rollout completed successfully.
5. All required OTEL_* values were listed from the Deployment.

## Rollout and Pod verification

The new Answer pod is:

| Pod | Ready | Status | Restarts | Image |
| --- | --- | --- | --- | --- |
| rag-answer-service-5bc7794555-whkxn | 1/1 | Running | 0 | rag-answer-service:46-61072fb |

Final read-only rollout verification returned:

~~~text
deployment "rag-answer-service" successfully rolled out
~~~

## Effective pod environment

The replacement pod was inspected directly. All eight required values are present:

| Variable | Effective value |
| --- | --- |
| OTEL_SERVICE_NAME | rag-answer-service |
| OTEL_RESOURCE_ATTRIBUTES | service.namespace=rag-poc,deployment.environment=local |
| OTEL_EXPORTER_OTLP_ENDPOINT | http://host.docker.internal:4318 |
| OTEL_EXPORTER_OTLP_PROTOCOL | http/protobuf |
| OTEL_TRACES_EXPORTER | otlp |
| OTEL_METRICS_EXPORTER | otlp |
| OTEL_LOGS_EXPORTER | otlp |
| OTEL_PYTHON_LOG_CORRELATION | true |

## Validation commands and results

| Command | Result |
| --- | --- |
| kubectl get deployments -A -o wide | Passed; rag-answer-service was identified in rag-poc. |
| scripts/configure-otel-k8s.bat rag-answer-service rag-answer-service rag-poc | Passed; exit code 0 and all variables applied. |
| kubectl get pods -n rag-poc -o wide | Passed; one new Answer pod is Running and 1/1 Ready. |
| kubectl exec new Answer pod -- env filter for OTEL_* | Passed; all eight expected values are effective in the container. |
| kubectl get deployment rag-answer-service -n rag-poc -o wide | Passed; 1/1 ready, up-to-date, and available. |
| kubectl rollout status deployment/rag-answer-service -n rag-poc --timeout=30s | Passed. |

## Test-run details

No unit tests, Docker builds, image rebuilds, application-code changes, or Tempo trace checks were run. Step 03 is an environment-only validation step. Kubernetes readiness and the pod's effective environment are the applicable validations for this step.

## Warnings and expected limitations

1. The Answer image remains unchanged and was previously verified not to contain opentelemetry-instrument or the required Python OpenTelemetry packages. These variables alone do not produce traces.
2. The current process still starts directly through Uvicorn rather than opentelemetry-instrument. No traces in Tempo at this point are expected and are acceptable under the plan.
3. Only rag-answer-service changed. Search and Ingest remain untouched.

## Next decision gate

Step 03 is complete. Approve Step 04 to add OpenTelemetry dependencies to the Answer image only.
