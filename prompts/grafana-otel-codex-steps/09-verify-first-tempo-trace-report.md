# Step 09 - Verify First Tempo Trace Report

**Status:** Completed with a diagnosed trace-hierarchy issue  
**Run date:** 2026-10-05  
**Scope:** Generated safe Answer Service traffic, verified OTLP export into Tempo through Grafana's Tempo datasource, and inspected the exported span hierarchy. No application, image, Kubernetes, or LGTM configuration was changed.

## Safe endpoint and HTTP result

The existing safe endpoint was `GET /health`. Its implementation returns static service status and does not call Search, Ollama, or the RAG answer flow.

Five requests were issued from inside the deployed Answer pod to avoid exposing a ClusterIP-only service externally:

~~~text
GET http://127.0.0.1:8002/health
~~~

All five returned:

~~~json
{"status":"ok","service":"rag-answer-service"}
~~~

with HTTP `200`.

## Tempo visibility and export proof

Grafana's local health API responded successfully (`Grafana 13.2.2`), and its provisioned Tempo datasource was identified as UID `tempo`.

The following read-only Tempo search through Grafana returned a trace for the Answer Service:

~~~text
GET /api/datasources/proxy/uid/tempo/api/search?tags=service.name=rag-answer-service&limit=20
~~~

| Evidence | Result |
| --- | --- |
| Trace ID returned by Tempo | `7cfd2c5eed369cfd0691089c7c20d2a1` |
| Tempo trace retrieval | HTTP `200` |
| Resource `service.name` | `rag-answer-service` |
| Resource `service.namespace` | `rag-poc` |
| Resource `deployment.environment` | `local` |
| OpenTelemetry SDK | Python SDK `1.45.0`; auto-instrumentation `0.66b0` |
| Manual Step 09 probe spans found | 5, identified by `Python-urllib/3.13` user agent |
| Manual probe status values | All `200` |

This is direct proof that Answer Service spans were exported and are visible to Tempo through the same datasource Grafana Explore uses.

## Spans observed

The five explicit probe requests produced five FastAPI-instrumented `GET /health` spans:

~~~text
scope: opentelemetry.instrumentation.fastapi
name: GET /health
kind: SPAN_KIND_INTERNAL
http.user_agent: Python-urllib/3.13
http.status_code: 200
~~~

Each of those spans had three direct FastAPI response child spans, for 15 total direct children:

~~~text
GET /health http send
scope: opentelemetry.instrumentation.fastapi
kind: SPAN_KIND_INTERNAL
~~~

The trace also contains the auto-instrumented Answer startup HTTPX client span for Ollama (`GET http://host.docker.internal:11434/api/tags`, HTTP 200). No Search or answer-generation child span was expected in this step because only `/health` was invoked and Search is not yet instrumented.

## Diagnosed hierarchy issue

Although the spans export successfully, the Tempo search result reports:

~~~text
rootServiceName: <root span not yet received>
~~~

The five manual health spans all reference the same parent span ID, `Uj/bfI6gCtU=`, but that parent span is not included in the retrieved trace. No `SPAN_KIND_SERVER` root span was found for the requests; the observed FastAPI request spans are `SPAN_KIND_INTERNAL`.

At the time of inspection, this single trace contained 437 `GET /health` spans and 1,311 `GET /health http send` spans, largely from Kubernetes probes. This means the health traffic is being appended beneath the same unresolved parent rather than appearing as clean, independent server-root traces.

This does **not** block Step 09's export proof, but it makes the Answer trace hierarchy incomplete and should be investigated before relying on root-service topology or distributed-trace relationships. The existing custom `app.trace_context` middleware also writes independently generated log `trace_id` values, which do not match Tempo's trace ID for these probes; that is a future log-correlation concern. No source change was made because this step is validation/diagnosis only.

## Exporter and collector log review

| Check | Result |
| --- | --- |
| Answer pod logs, latest 3,000 lines | No OpenTelemetry exporter or runtime error match found |
| LGTM OTLP receiver/rejection errors | None found in the reviewed 10-minute log window |
| LGTM Tempo scheduler messages | Recurring `BackendScheduler/Next` `NotFound: no jobs found` warnings/errors observed |
| Impact of scheduler messages on this test | They did not prevent trace search or trace retrieval; they are retained as an environmental observation |

Tempo's collector log also recorded the successful trace search with `status_code=200`.

## Grafana Explore UI limitation

The prescribed Explore UI could not be opened because this environment exposed no browser surface; attempting to create the local in-app browser returned `Browser is not available: iab`. The validation therefore used Grafana's own local Tempo datasource proxy, which is the read-only backend used by Explore. No login, browser setting, or external service was changed.

## Validation and test-run details

| Validation | Result |
| --- | --- |
| Safe `GET /health` endpoint selection | Passed |
| Five in-pod HTTP requests | Passed; all HTTP 200 |
| Answer pod log review for exporter/runtime errors | Passed; no matching errors |
| Tempo search for `service.name=rag-answer-service` | Passed; trace returned |
| Direct trace retrieval | Passed; HTTP 200 with Answer resource and probe spans |
| Child-span inspection | Passed; 15 response children for the five probes |
| Complete server-root hierarchy | Needs follow-up; root span absent/unresolved parent |
| Grafana Explore UI interaction | Blocked by unavailable browser surface; datasource API verification completed instead |

## Next decision gate

Step 09 is complete: Answer span export and Tempo visibility are proven, and the missing-root hierarchy issue is documented without changing the service. Approve Step 10 to instrument Search using the validated deployment pattern; no subsequent step has been started.
