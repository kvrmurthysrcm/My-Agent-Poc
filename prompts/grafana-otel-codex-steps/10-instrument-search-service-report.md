# Step 10 - Instrument Search Service Report

**Status:** Completed successfully, with documented observability limitations  
**Run date:** 2026-10-05  
**Scope:** Applied the validated Answer Service OpenTelemetry image and Deployment pattern to `rag-search-service`, then proved a real Search request reached Tempo. No application code, Kubernetes manifest, Answer Service, Ingest Service, or LGTM configuration was changed.

## Changed files

| File | Change |
| --- | --- |
| `modules/rag-search-service/requirements.txt` | Added `opentelemetry-distro` and `opentelemetry-exporter-otlp`. |
| `modules/rag-search-service/Dockerfile` | Added `opentelemetry-bootstrap -a install` after dependency installation and changed the runtime command to launch Uvicorn through `opentelemetry-instrument`. |
| `prompts/grafana-otel-codex-steps/10-instrument-search-service-report.md` | Created this completion report. |

The uncommitted Answer Dockerfile and requirements changes were inspected as the reference and were not modified.

## Image implementation

The original Search runtime command was:

~~~text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
~~~

The new runtime command is:

~~~text
opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
~~~

The app module, host, and port are unchanged. The source Deployment has no `command` or `args` override, and neither does the live Deployment, so Kubernetes uses this image command.

## Build and image verification

The runtime image built successfully:

~~~text
docker build --target runtime -t rag-search-service:local -f modules\rag-search-service\Dockerfile modules\rag-search-service
~~~

| Item | Value |
| --- | --- |
| Image tag | `rag-search-service:local` |
| Image ID | `sha256:377ea9d6a7234397f3fe89e11b2acca368ff69674434cd032379977cb01844c5` |
| Image size | 88,347,657 bytes |
| Image command | `opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8001` |
| `opentelemetry-instrument` | Present; version `0.66b0` |
| `opentelemetry-bootstrap` | Present and supports `-a install` |
| `pip check` | Passed; no broken requirements |

Verified package versions:

| Package | Version |
| --- | --- |
| `opentelemetry-api` | `1.45.0` |
| `opentelemetry-sdk` | `1.45.0` |
| `opentelemetry-distro` | `0.66b0` |
| `opentelemetry-exporter-otlp` | `1.45.0` |
| `opentelemetry-exporter-otlp-proto-http` | `1.45.0` |
| `opentelemetry-instrumentation` | `0.66b0` |
| FastAPI instrumentation | `0.66b0` |
| HTTPX instrumentation | `0.66b0` |
| SQLAlchemy instrumentation | `0.66b0` |
| Psycopg instrumentation | `0.66b0` |

The build-time bootstrap also installed ASGI, Starlette, DBAPI, logging, OpenAI, urllib, and related compatible instrumentation packages.

## Deployment environment and rollout

The standard deployment script configured only `rag-search-service` in `rag-poc` with these effective values:

| Variable | Value |
| --- | --- |
| `OTEL_SERVICE_NAME` | `rag-search-service` |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=rag-poc,deployment.environment=local` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://host.docker.internal:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_PYTHON_LOG_CORRELATION` | `true` |

The existing Search ConfigMap and Service were unchanged. The rendered Deployment was applied with `rag-search-service:local`, and Kubernetes reported a successful rollout.

| Item | Result |
| --- | --- |
| Namespace | `rag-poc` |
| Deployment image | `rag-search-service:local` |
| New pod | `rag-search-service-559847c458-hmnnd` |
| Pod IP | `10.1.0.19` |
| Ready state | `1/1`, Running |
| Restarts at validation | `0` |
| Safe `GET /health` | HTTP 200, `{"status":"ok","service":"rag-search-service"}` |

Docker Desktop's active built-in Kubernetes node uses `docker://29.5.3`, not the legacy `desktop-control-plane` Kind container named by the older CI script. The locally built image is already visible to this Docker-backed cluster, so no image import was necessary or performed.

## Runtime and collector connectivity validation

Inside the Ready pod:

~~~text
launcher=/usr/local/bin/opentelemetry-instrument
opentelemetry-instrument 0.66b0
~~~

PID 1 is the expected exec'd Python/Uvicorn process. Its actual environment retains auto-instrumentation:

~~~text
PYTHONPATH=/usr/local/lib/python3.13/site-packages/opentelemetry/instrumentation/auto_instrumentation:/app
~~~

Pod-to-collector checks passed:

| Check | Result |
| --- | --- |
| `host.docker.internal` DNS | `192.168.65.254` |
| TCP connection to port `4318` | Passed |
| `GET http://host.docker.internal:4318/` | HTTP 404 Not Found, proving receiver reachability at the non-signal base path |

## Search request and Tempo proof

A real read-only keyword Search request was issued from the deployed Search pod with the unique user agent `Step10-Search-Probe/1.0`:

~~~text
POST http://127.0.0.1:8001/rag/search
{"query":"observability","search_mode":"keyword","top_k":1,"include_chunk_text":false}
~~~

It returned HTTP 200 with one result. After the batch exporter flush, Grafana health was healthy (`Grafana 13.2.2`) and its Tempo datasource returned this trace:

| Evidence | Result |
| --- | --- |
| Tempo trace ID | `55f7b8312ea875d08d48fef742cb928e` |
| Trace retrieval through Grafana Tempo datasource | HTTP 200 |
| Resource `service.name` | `rag-search-service` |
| Resource `service.namespace` | `rag-poc` |
| Resource `deployment.environment` | `local` |
| OpenTelemetry SDK | Python SDK `1.45.0`; auto-instrumentation `0.66b0` |
| Probe span | FastAPI `POST /rag/search`, HTTP 200, with the unique probe user agent |
| Search database spans | Psycopg `select`, `show`, and `WITH` client spans attached to the probe span |

The probe span had three FastAPI response-send children, one request-receive child, and five Psycopg database-client children. This proves the Search process, exporter, OTLP receiver, and Tempo ingestion path work end to end.

## Known limitations and observations

1. **Missing server-root hierarchy:** Tempo reports `rootServiceName: <root span not yet received>`. The probe's FastAPI `POST /rag/search` span is `SPAN_KIND_INTERNAL` and references parent span ID `hMPlY/JysXk=`, which is absent from the retrieved trace. This matches the pre-existing Answer Service behavior documented in Step 09. Kubernetes health probes are also accumulating beneath the same incomplete trace. No custom tracing or middleware change was made in this step.

2. **SQLAlchemy compatibility warning:** the bootstrap-installed SQLAlchemy instrumentor reports that installed `SQLAlchemy 2.1.3` falls outside its supported `<2.1.0` range, so it does not create SQLAlchemy spans. This is non-fatal. The compatible Psycopg instrumentor did emit the five database spans for the real Search request. Pinning or upgrading the incompatible SQLAlchemy instrumentation should be a separate dependency decision, not an unreviewed change to this rollout.

3. **Deferred Loki issue:** the LGTM collector shows `otlp_http/logs` retries with HTTP 503 from Loki (`at least 1 live replicas required`). It did not prevent Tempo trace ingestion or retrieval. This is a log-export environment issue for the planned Step 13 evaluation, not a Search trace-export failure.

4. **Collector scheduler messages:** recurring Tempo `BackendScheduler/Next` `NotFound: no jobs found` warnings remain visible, as in Step 09. Trace search and retrieval both succeeded despite them.

5. **Service log review:** the most recent 1,000 Search pod log lines contained no OpenTelemetry exporter or runtime error match.

## Differences from the Answer Service implementation

| Area | Answer | Search |
| --- | --- | --- |
| Service name | `rag-answer-service` | `rag-search-service` |
| Uvicorn port | `8002` | `8001` |
| Source changes | Same two OTel requirements, bootstrap command, and instrumented runtime command | Same pattern applied |
| Automatic data access instrumentation | No direct SQLAlchemy/Psycopg workload | Bootstrap installed database instrumentation; Psycopg spans export during Search |
| Compatibility observation | No equivalent warning | SQLAlchemy `2.1.3` exceeds the installed SQLAlchemy instrumentor support range, while Psycopg tracing succeeds |
| Trace hierarchy | Missing root documented in Step 09 | Same missing-root pattern observed |

## Validation summary

| Validation | Result |
| --- | --- |
| Requirements and Dockerfile changes | Passed |
| Docker runtime image build | Passed |
| OTel launcher/bootstrap/package checks | Passed |
| `pip check` | Passed |
| Search OTel environment rollout | Passed |
| Search Deployment rollout | Passed |
| Ready pod and health endpoint | Passed |
| PID 1 auto-instrumentation environment | Passed |
| Pod-to-collector DNS, TCP, and HTTP reachability | Passed |
| Real keyword Search request | Passed; HTTP 200 |
| Tempo trace search and retrieval | Passed |
| Search database child spans in Tempo | Passed via Psycopg |
| Complete server-root hierarchy | Needs follow-up; same incomplete-root behavior as Answer |
| Loki log export | Deferred; collector currently reports Loki 503 retries |

## Next decision gate

Step 10 is complete. Approve Step 11 to invoke the normal Answer-to-Search flow and verify that both services appear in one distributed trace with W3C context propagation. No Ingest change has been started.
