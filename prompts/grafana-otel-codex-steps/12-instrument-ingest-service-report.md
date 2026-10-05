# Step 12 - Instrument Ingest Service Report

**Status:** Completed successfully
**Run date:** 2026-10-05
**Scope:** Applied the validated automatic OpenTelemetry pattern to `rag-ingest-service`, deployed it to Docker Desktop Kubernetes, exercised a normal asynchronous ingest request, and retrieved its trace from Tempo. No application request-handling code or Kubernetes source manifest was refactored.

## Changed files

| File | Change |
| --- | --- |
| `modules/rag-ingest-service/requirements.txt` | Added `opentelemetry-distro` and `opentelemetry-exporter-otlp`. |
| `modules/rag-ingest-service/Dockerfile` | Added `opentelemetry-bootstrap -a install` after requirements installation and changed the runtime command to use `opentelemetry-instrument`. |
| `prompts/grafana-otel-codex-steps/12-instrument-ingest-service-report.md` | Created this completion report. |

The existing shared OTel deployment script already contained the corrected Click exclusion from Step 11. It was applied to Ingest without further script changes.

## Image implementation and verification

The original Ingest runtime command was:

~~~text
uvicorn app.main:app --host 0.0.0.0 --port 8000
~~~

The deployed command is:

~~~text
opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
~~~

The application module, interface, and port are unchanged. Kubernetes does not override the image command or arguments. As expected, `opentelemetry-instrument` execs the final Python/Uvicorn process, so PID 1 displays the Python command rather than the launcher wrapper.

| Item | Result |
| --- | --- |
| Build command | `docker build --target runtime -t rag-ingest-service:local -f modules\rag-ingest-service\Dockerfile modules\rag-ingest-service` |
| Image tag | `rag-ingest-service:local` |
| Image ID | `sha256:901f93d12a5e7fb1548030764c74edad86331879e793f0349618fb84494edc91` |
| Image size | `123,014,177` bytes |
| OTel launcher | `opentelemetry-instrument 0.66b0` |
| `pip check` | Passed: `No broken requirements found.` |

Verified installed OTel packages:

| Package | Version |
| --- | --- |
| `opentelemetry-api` | `1.45.0` |
| `opentelemetry-sdk` | `1.45.0` |
| `opentelemetry-distro` | `0.66b0` |
| `opentelemetry-exporter-otlp` | `1.45.0` |
| FastAPI, HTTPX, Psycopg, and SQLAlchemy instrumentors | `0.66b0` |

Build-time bootstrap detected and installed the compatible automatic instrumentation packages, including ASGI/FastAPI, HTTPX, Psycopg, logging, threading, and Click. Click remains installed but is explicitly disabled at runtime because Uvicorn uses a long-lived Click command.

## Deployment and collector connectivity

The shared configuration command was applied as:

~~~text
scripts\configure-otel-k8s.bat rag-ingest-service rag-ingest-service rag-poc
~~~

The rendered Deployment was then applied with `rag-ingest-service:local`. The final deployment and pod state were:

| Item | Result |
| --- | --- |
| Namespace | `rag-poc` |
| Available / updated replicas | `1 / 1` |
| Pod | `rag-ingest-service-557685c57f-djp84` |
| Pod IP | `10.1.0.23` |
| Ready | `true` |
| Restarts | `0` |

Inside the Ready pod, the effective OTel configuration included all nine standard variables. The pod resolved `host.docker.internal` to `192.168.65.254`, opened a TCP connection to port `4318`, and received the expected HTTP `404` from the receiver base path. The latter confirms reachability; OTLP signals use the protocol-specific paths rather than `/`.

## Normal ingest and Tempo proof

A normal multipart request was posted to `POST /rag/ingest` with a minimal tagged `.txt` document and `indexing_mode=NONE`. This exercises upload validation, resource/job creation, text extraction, chunking, database writes, background processing, and original-file cleanup without calling the embedding or Graph RAG providers.

| Item | Result |
| --- | --- |
| User agent | `Step12-Ingest-Probe/1.0` |
| HTTP response | `202 Accepted` |
| Resource ID | `f8dd50f1-0c8c-496f-a0b8-aa9bbdde7327` |
| Job ID | `6c3db994-da3c-4e16-a9d7-a2a4e669a710` |
| Final job state | `COMPLETED` |
| Parser | `plain_text` |
| Chunks | `1` processed / `1` total |
| Embeddings | `0` (expected for `NONE`) |

The request used this valid W3C context for deterministic proof:

~~~text
traceparent: 00-12121212121212121212121212121212-3434343434343434-01
tracestate: acme=step12
~~~

Grafana's Tempo datasource retrieved trace `12121212121212121212121212121212` with HTTP 200. Its resource identifies `service.name=rag-ingest-service`, `service.namespace=rag-poc`, `deployment.environment=local`, Python SDK `1.45.0`, and auto-instrumentation `0.66b0`.

The retrieved trace has 39 unique spans, including 33 Psycopg client spans. Its key hierarchy is:

~~~text
external W3C parent 3434343434343434
  |
  +-- rag-ingest-service  POST /rag/ingest  SERVER, HTTP 202
        span: b93abf264e39b5e1
        tracestate: acme=step12
        |
        +-- BackgroundTask process_job
              parent: b93abf264e39b5e1
~~~

The server span retained the probe user agent and supplied parent exactly. This proves that the Step 11 Click exclusion also prevents a process-lifetime CLI span from interfering with Ingest's incoming W3C context extraction. Psycopg database instrumentation emitted the request and background-job database spans despite the separate SQLAlchemy compatibility warning below.

The pod's recent logs contained no OTel exporter or runtime errors. The only relevant message is the known non-fatal warning that SQLAlchemy `2.1.3` exceeds the bootstrap-installed SQLAlchemy instrumentor's `<2.1.0` support range. It does not block FastAPI, background-task, or Psycopg spans; changing that dependency relationship is outside this focused instrumentation rollout.

The accepted probe is intentionally identifiable by `source_system=otel_step12_probe` and its resource ID above. Its original uploaded file was removed by the configured ingestion cleanup. The Kubernetes profile (`APP_PROFILE=kubernetes`) intentionally gates the local-only delete endpoint, so the completed resource/job metadata and one chunk remain as the normal-ingest verification record rather than bypassing that safety guard.

## Final configuration across all RAG services

All three Deployments are Ready, use local instrumented images, and have the same nine OTel variables. Each service has its own `OTEL_SERVICE_NAME` value.

| Service | Image | `OTEL_SERVICE_NAME` | Status |
| --- | --- | --- | --- |
| Answer | `rag-answer-service:local` | `rag-answer-service` | Ready, 0 restarts |
| Search | `rag-search-service:local` | `rag-search-service` | Ready, 0 restarts |
| Ingest | `rag-ingest-service:local` | `rag-ingest-service` | Ready, 0 restarts |

| Shared variable | Effective value |
| --- | --- |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=rag-poc,deployment.environment=local` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://host.docker.internal:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_PYTHON_LOG_CORRELATION` | `true` |
| `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` | `click` |

The Click exclusion is intentionally shared by all three services. It retains FastAPI, HTTPX, and Psycopg automatic instrumentation while allowing FastAPI to create or extract the correct request-server span.

## Validation summary

| Validation | Result |
| --- | --- |
| Dependency and Docker startup changes | Passed |
| Runtime image build and package verification | Passed |
| `pip check` | Passed |
| Ingest OTel environment rollout | Passed |
| Instrumented image deployment and readiness | Passed |
| Pod-to-collector DNS, TCP, and HTTP reachability | Passed |
| Normal asynchronous ingest request | Passed; HTTP 202 then `COMPLETED` |
| W3C context extraction | Passed; exact trace and parent retrieved from Tempo |
| FastAPI server and background-job spans | Passed |
| Psycopg client spans | Passed; 33 unique spans in the verification trace |
| Exporter/runtime error review | Passed; no matching Ingest pod error |

## Next decision gate

Step 12 is complete. Step 13 can evaluate the OTLP log-export behavior and the previously observed Loki-side retry condition without changing the completed trace instrumentation.
