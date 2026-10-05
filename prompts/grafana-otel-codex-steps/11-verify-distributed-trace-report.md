# Step 11 - Verify Distributed Trace Report

**Status:** Completed successfully  
**Run date:** 2026-10-05  
**Scope:** Verified the normal Answer-to-Search flow, diagnosed an initial split-trace condition, applied the smallest automatic-instrumentation configuration fix, and proved both root creation and W3C distributed propagation in Tempo. No manual spans were added and no application request-handling code was changed.

## Answer-to-Search implementation inspected

`rag-answer-service` uses `httpx.Client` in `app.services.search_client.RagSearchClient` to call:

~~~text
POST http://rag-search-service:8001/rag/search
~~~

The deployed Answer pod contains:

| Item | Result |
| --- | --- |
| `httpx` | `0.28.1` |
| `opentelemetry-instrumentation-httpx` | `0.66b0` |
| `opentelemetry-instrumentation-fastapi` | `0.66b0` |
| Launcher | `opentelemetry-instrument 0.66b0` |
| PID 1 auto-instrumentation path | Present in `PYTHONPATH` |

Both deployed services were Ready before validation and used their Step 10 / Step 07 instrumented local images.

## Initial split-trace diagnosis

The first normal Answer request deliberately used an unmatched keyword query, so it invoked Search but returned `insufficient_context` without generating an LLM response. It returned HTTP 200.

Before the fix, Tempo showed separate service traces:

| Service | Trace ID |
| --- | --- |
| Answer | `7cfd2c5eed369cfd0691089c7c20d2a1` |
| Search | `55f7b8312ea875d08d48fef742cb928e` |

The Answer HTTPX client span was correctly a child of the Answer request span and used the Answer trace ID. Search application logs also recorded the Answer trace ID for the incoming request, proving the W3C `traceparent` header reached Search. However, Search's FastAPI span stayed attached to a process-lifetime parent from its own trace and was marked `SPAN_KIND_INTERNAL` instead of extracting the incoming W3C context.

The bootstrap-installed Click instrumentor was the cause. Uvicorn runs as a long-lived Click command; Click instrumentation left that CLI command span active for the process lifetime. The OpenTelemetry ASGI middleware creates an `INTERNAL` span whenever another span is already current, rather than extracting the inbound carrier as a `SERVER` span.

An isolated, auto-removed Search container reproduced the issue. With default bootstrap instrumentation, an explicit W3C `traceparent` was ignored and the request became an internal child of the long-lived parent. With only `click` disabled:

- the startup Ollama HTTPX span was a root span;
- an incoming `traceparent` produced a `SPAN_KIND_SERVER` span;
- its trace ID and parent span ID matched the supplied W3C values.

## Applied fix

The standard OTel configuration now sets:

~~~text
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=click
~~~

This disables only the unwanted Click CLI instrumentation. FastAPI, HTTPX, Psycopg, and the other required automatic instrumentation remain enabled.

The updated standard script was applied sequentially to only:

- `rag-search-service`
- `rag-answer-service`

Both Kubernetes rollouts completed successfully. The final Ready pods were:

| Service | Pod | IP | Restarts |
| --- | --- | --- | --- |
| Answer | `rag-answer-service-84db77d956-4lf2j` | `10.1.0.21` | `0` |
| Search | `rag-search-service-8598c57f5f-kfh7p` | `10.1.0.20` | `0` |

Both actual PID 1 environments contain `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=click` and the automatic-instrumentation `PYTHONPATH` entry.

## No-parent distributed trace proof

A normal Answer request without an incoming `traceparent` was sent with the unique user agent `Step11-No-Parent-Probe/1.0`:

~~~text
POST http://127.0.0.1:8002/rag/answer
{"query":"codexstep11noparentmzkqv","search_mode":"keyword","top_k":1,"context_top_k":1,"include_sources":false}
~~~

It returned HTTP 200, `insufficient_context`, zero Search results, and zero context sources. Tempo returned one trace:

~~~text
a1c39341dd68e6ac8da3a97fc038908
~~~

Tempo identifies `rag-answer-service` / `POST /rag/answer` as its root. Its verified hierarchy is:

~~~text
rag-answer-service  POST /rag/answer  SERVER
  span: sfaySH7+AwM=
    |
    +-- rag-answer-service  HTTPX POST  CLIENT
          span: lQBy63eOrAk=
          parent: sfaySH7+AwM=
            |
            +-- rag-search-service  POST /rag/search  SERVER
                  span: IMfJ3ous70M=
                  parent: lQBy63eOrAk=
~~~

All three spans have HTTP status 200. This is the expected Answer server -> HTTP client -> Search server topology in one trace.

## W3C propagation proof

A second normal Answer request carried this valid W3C context:

~~~text
traceparent: 00-a1b2c3d4e5f60718293a4b5c6d7e8f90-0123456789abcdef-01
tracestate: acme=step11
~~~

The request returned HTTP 200 with `insufficient_context`, and Tempo retrieved the exact requested trace ID:

~~~text
a1b2c3d4e5f60718293a4b5c6d7e8f90
~~~

| Span | Kind | Parent | `tracestate` |
| --- | --- | --- | --- |
| Answer `POST /rag/answer` | `SERVER` | Supplied external parent (`0123456789abcdef`) | `acme=step11` |
| Answer HTTPX `POST` | `CLIENT` | Answer server span | `acme=step11` |
| Search `POST /rag/search` | `SERVER` | Answer HTTPX client span | `acme=step11` |

The trace reports `<root span not yet received>` only because its supplied external parent is not exported by this local lab. The service-to-service span chain itself is complete and correctly propagated.

## Changed files

| File | Change |
| --- | --- |
| `scripts/configure-otel-k8s.bat` | Added the standard `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=click` Deployment environment variable. |
| `prompts/grafana-otel-codex-steps/configure-otel-k8s.bat` | Kept the reference script aligned with the active script. |
| `prompts/grafana-otel-codex-steps/execution-details.md` | Documented the new setting and its Uvicorn/Click rationale. |
| `prompts/grafana-otel-codex-steps/11-verify-distributed-trace-report.md` | Created this report. |

No Answer or Search application code, Dockerfile, dependency declaration, Kubernetes manifest, or Ingest resource was changed in this step.

## Remaining observations

1. Search still logs the previously documented non-fatal SQLAlchemy compatibility warning. Its Psycopg instrumentation remains active and exported Search database spans in Step 10.
2. The LGTM collector's Loki log-export retries remain a Step 13 concern; they did not block trace creation, propagation, search, or retrieval.
3. The pre-fix process-lifetime traces remain stored in Tempo as historical diagnostic evidence. New requests after the Click exclusion create normal per-request traces.

## Validation summary

| Validation | Result |
| --- | --- |
| Live Answer HTTPX instrumentation | Passed |
| Initial split-trace diagnosis | Completed |
| Isolated Click-disable proof | Passed |
| Search Click-exclusion rollout | Passed |
| Answer Click-exclusion rollout | Passed |
| Final pod readiness | Passed |
| No-parent Answer-to-Search trace | Passed |
| Answer server root span | Passed |
| Answer HTTPX client span | Passed |
| Search server span | Passed |
| Parent-child linkage across services | Passed |
| W3C `traceparent` propagation | Passed |
| W3C `tracestate` propagation | Passed |

## Next decision gate

Step 11 is complete. Approve Step 12 to apply the now-corrected OTel pattern to `rag-ingest-service`. No Ingest change has been started.
