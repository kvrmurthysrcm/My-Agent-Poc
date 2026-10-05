# Step 01 - OpenTelemetry Readiness Inspection Report

**Status:** Completed successfully  
**Run date:** 2026-10-04  
**Scope:** Read-only inventory and live-state inspection. This report is the only file created, as requested. No application code, dependencies, images, Kubernetes resources, or Docker containers were changed.

## Outcome

The local platform is ready for the staged OpenTelemetry rollout:

- Grafana LGTM is running and healthy, with Grafana on port 3000 and OTLP gRPC/HTTP ports 4317/4318 published.
- The Answer, Search, and Ingest deployments are all Ready in the rag-poc namespace.
- The services cannot emit OpenTelemetry traces yet: no OTEL_* variables are effective in their pods, no OpenTelemetry packages are declared in their dependency files or lock files, and opentelemetry-instrument is absent from every running pod.

The inspection itself succeeded. Instrumentation work should remain blocked until the next planned step is explicitly approved.

## Current runtime state

| Component | State | Evidence |
| --- | --- | --- |
| Grafana LGTM | Ready | grafana/otel-lgtm:latest is Up and healthy; ports 3000, 4317, and 4318 are published on the host. |
| rag-answer-service | Ready | 1/1 available; running image rag-answer-service:46-61072fb. |
| rag-search-service | Ready | 1/1 available; running image rag-search-service:46-61072fb. |
| rag-ingest-service | Ready | 1/1 available; running image rag-ingest-service:46-61072fb. |
| OpenTelemetry environment | Not configured | Effective OTEL_* environment check returned no values from all three pods. |
| Instrumentation executable | Not installed | command -v opentelemetry-instrument returned no path from all three pods. |

All three live Deployments have no Kubernetes command or args override. Their image CMD is therefore the effective startup path.

## Service inventory

| Service | Docker CMD | Primary libraries and integrations | Existing custom correlation |
| --- | --- | --- | --- |
| Answer | python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 | FastAPI, Uvicorn, HTTPX; calls Search and Ollama | Custom FastAPI middleware plus outbound traceparent, X-Trace-Id, X-Span-Id, and X-Request-ID headers. |
| Search | python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 | FastAPI, Uvicorn, HTTPX, SQLAlchemy, psycopg, pgvector; calls Ingest for admin actions and Ollama | Same custom middleware/header model as Answer. |
| Ingest | uvicorn app.main:app --host 0.0.0.0 --port 8000 | FastAPI, Uvicorn, HTTPX, SQLAlchemy, psycopg, pgvector, background-task worker; optional unimplemented RQ/Redis adapter | Custom FastAPI middleware and correlation logging; no active outbound service client helper. |

Each service runs Python 3.13 in a python:3.13-slim image. The Dockerfiles install requirements.txt; pyproject.toml and uv.lock are also present for each service.

## Existing correlation implementation

The three services already use app/trace_context.py and log custom trace_id, span_id, and request_id fields.

- Answer and Search have identical trace-context implementations.
- They parse W3C traceparent version 00, preserve its trace ID, create a custom span ID, and emit traceparent plus X-Trace-Id/X-Span-Id response headers.
- Answer explicitly forwards those custom headers to Search through HTTPX.
- Search similarly forwards them when calling Ingest admin endpoints.
- Ingest uses the same inbound/log correlation pattern but does not provide the outbound helper.

This is useful existing business/request correlation, but it is not OpenTelemetry tracing and does not create Tempo spans.

## Kubernetes and delivery inventory

- Source manifests are under k8s/rag-answer-service, k8s/rag-search-service, and k8s/rag-ingest-service.
- Each Deployment imports a service-specific ConfigMap and declares namespace rag-poc.
- No Helm charts, Kustomize files, Docker Compose files, or existing runtime OTel configuration were found.
- The checked-in Deployment image field is the __IMAGE__ placeholder; the live image tag is supplied during delivery.
- The primary CI/CD path is Jenkinsfile -> scripts/ci/build-test-deploy.sh -> scripts/ci/service-worker.sh:
  1. Build the test image and run container tests.
  2. Build the runtime image.
  3. Render __IMAGE__ in the Deployment manifest.
  4. Apply ConfigMap, Service, and Deployment; wait for rollout.
- scripts/ci/detect-changes.sh selects a service when its module or k8s directory changes. A standalone change to scripts/configure-otel-k8s.bat would not trigger a service deployment by itself.

## Existing OTel script

prompts/grafana-otel-codex-steps/configure-otel-k8s.bat already contains the desired OTLP HTTP endpoint and environment-variable set. It is a newly staged plan artifact, not the runtime script path specified by the execution plan.

The next planned step should create or review scripts/configure-otel-k8s.bat without changing the plan copy. Before it is used:

- Set its default namespace to rag-poc, or always pass rag-poc explicitly. Its current default is default, where these deployments do not exist.
- Preserve host.docker.internal:4318; localhost:4318 would point to the pod, not Grafana LGTM.
- Keep its deployment-scoped behavior so only the approved service restarts.

## Files expected to change in later approved steps

| Planned change | Files |
| --- | --- |
| Configure deployment environment variables | scripts/configure-otel-k8s.bat; live Deployment only when Step 03 is approved. |
| Add Answer OpenTelemetry dependencies | At minimum modules/rag-answer-service/requirements.txt, which is the Docker build input. Keep modules/rag-answer-service/pyproject.toml and uv.lock synchronized if they remain supported dependency sources. |
| Instrument Answer startup | modules/rag-answer-service/Dockerfile. The current Deployment has no command/args override, so no manifest command change is currently needed. |
| Repeat only after Answer validation | Equivalent Search and Ingest dependency and Dockerfile files, in Steps 10 and 12. |

For Answer, the expected instrumentation set is the OpenTelemetry distribution, OTLP HTTP exporter, and FastAPI/Uvicorn/HTTPX instrumentations. Search and Ingest will later additionally need SQLAlchemy instrumentation. Exact package versions and any package-lock update should be decided in the corresponding approved dependency step.

## Risks and inconsistencies

1. **Manual versus OpenTelemetry propagation:** the current middleware writes its own traceparent header while OpenTelemetry HTTPX/FastAPI instrumentation will extract and inject W3C context. Do not remove or rewrite the custom middleware during the first Answer rollout. Verify in the distributed-trace step that automatic instrumentation has not created competing parent relationships or overwritten the expected header.
2. **Logging correlation:** each application calls logging.basicConfig with force=True and a formatter containing only the custom fields. OTEL_PYTHON_LOG_CORRELATION=true may inject OTel record fields, but it will not automatically make this formatter display them. Keep the business trace_id distinct from OTel TraceId and defer logging-format decisions to Step 13.
3. **Namespace mismatch:** the proposed batch script defaults to default while the active deployments are in rag-poc.
4. **Dependency-source drift:** requirements.txt, pyproject.toml, and uv.lock all exist. Updating only the Docker input would leave developer tooling metadata inconsistent.
5. **Potential unrelated test-image issue:** every RAG Dockerfile test stage installs httpx2>=0.1.0. That package name appears nonstandard and may cause a later test-image build failure. It was not changed or built during this inspection.
6. **Stale observability containers:** local-alloy, local-grafana, and local-loki are stopped. Use grafana-lgtm for this rollout. Its recent logs show normal backend work alongside occasional Tempo scheduler no-jobs-found messages; the container health check remains healthy, so this is a warning to monitor rather than a current blocker.

## Validation performed

| Validation | Result |
| --- | --- |
| Repository inventory for Dockerfiles, dependencies, manifests, scripts, Helm/Kustomize/Docker Compose files | Passed; no Helm, Kustomize, Compose, or pre-existing runtime OTel configuration found. |
| Search of all three service dependency manifests and uv.lock files for OpenTelemetry/OTEL | Passed; no matches found. |
| Inspection of service startup commands and live Deployment command/args | Passed; image CMD is effective for all three services. |
| Inspection of custom trace/correlation source | Passed; custom W3C-style headers and log context are present. |
| Docker Desktop / Grafana LGTM state | Passed; Grafana LGTM is healthy and exposes the planned ports. |
| Kubernetes context, Deployments, Pods, and Services | Passed; Docker Desktop context and rag-poc workloads are healthy. |
| Effective pod OTEL_* variables | Passed; none are set. |
| Effective opentelemetry-instrument executable check | Passed; executable is absent from all three pods. |

## Test-run details

No unit tests, Docker builds, image rebuilds, deployments, rollouts, or requests that generate application traffic were run. Step 01 explicitly prohibits changing files, rebuilding images, or deploying; avoiding those actions preserves the intended baseline. The validation above was limited to read-only source, Docker, and Kubernetes inspection.

## Proposed execution order

1. Approve Step 02: create/review scripts/configure-otel-k8s.bat with the rag-poc namespace correction.
2. Approve Step 03: apply the OTEL environment only to rag-answer-service and verify the post-restart environment.
3. Approve Steps 04-06: add Answer dependencies, build-only verification, then change the effective Answer startup command.
4. Approve Steps 07-09: deploy Answer, prove pod-to-LGTM connectivity, and confirm the first Tempo trace.
5. Proceed to Search only after Answer tracing is stable; verify one Answer-to-Search TraceId before Ingest.
6. Instrument Ingest, then evaluate log export/correlation, metrics, dashboards, and alerts.

## Decision gate

Step 01 is complete. Do not start Step 02 until explicit approval is given.
