# Trace ID Implementation

## Purpose

The local POC now propagates one trace ID across UI initiated actions and downstream service calls. This lets you search logs for one user action across the wrapper, RAG services, and Online Library services.

## Headers

The implementation uses the W3C Trace Context header as the primary propagation format:

```text
traceparent: 00-<trace_id>-<span_id>-01
```

It also sends simple debug headers:

```text
X-Trace-Id: <trace_id>
X-Span-Id: <span_id>
X-Parent-Span-Id: <parent_span_id>
X-Request-ID: <request_id>
```

`trace_id` is 32 lowercase hex characters. `span_id` is 16 lowercase hex characters.

## Flow

For browser actions, the UI creates a new trace ID in `gateway.html` before calling `secure_api`.

```text
secure_api UI
  -> secure_api wrapper
  -> rag-search-service / rag-answer-service / rag-ingest-service
  -> downstream RAG service calls
```

Library Search follows this path:

```text
secure_api UI
  -> secure_api wrapper
  -> online_library_agent
  -> online_library_mcp
  -> online_library
```

The wrapper and FastAPI services also create a trace ID when a request arrives without trace headers. This covers curl, Postman, and direct service calls.

## Services Updated

Trace middleware and trace-aware logging were added to:

```text
modules/secure_api
modules/rag-search-service
modules/rag-answer-service
modules/rag-ingest-service
modules/online_library_agent
modules/online_library
```

Trace forwarding was added to:

```text
secure_api DownstreamClient
secure_api LibrarySearchClient
secure_api LibraryToolsClient
rag-answer-service RagSearchClient
rag-search-service admin calls to rag-ingest-service
online_library_agent MCP and Ollama calls
online_library_mcp Online Library API client
```

## Logs

The updated log format includes:

```text
trace_id=<trace_id> span_id=<span_id> request_id=<request_id>
```

Example:

```text
2026-06-30 16:20:00 INFO app.trace_context trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=00f067aa0ba902b7 request_id=... request_completed
```

Search by `trace_id` across all service log files.

## Error Responses

Wrapper error responses include `trace_id`:

```json
{
  "error": {
    "code": "downstream_request_failed",
    "message": "Downstream service request failed.",
    "request_id": "b3c8d8d8-0a9c-498b-a2a1-7d5d50dce5f1",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "details": {
      "service": "rag-answer",
      "error_type": "timeout"
    }
  }
}
```

## Curl Validation

Create a token first:

```bash
curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"raguser\",\"password\":\"raguser123\"}"
```

Call a wrapper endpoint with a known trace:

```bash
curl -i -X POST "http://localhost:8010/rag/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access-token>" \
  -H "traceparent: 00-11111111111111111111111111111111-2222222222222222-01" \
  -H "X-Trace-Id: 11111111111111111111111111111111" \
  -d "{\"query\":\"Ashtavakra\",\"search_mode\":\"keyword\",\"top_k\":5,\"filters\":{},\"include_metadata\":true}"
```

Expected response headers include:

```text
traceparent: 00-11111111111111111111111111111111-<secure-api-span>-01
X-Trace-Id: 11111111111111111111111111111111
X-Span-Id: <secure-api-span>
```

Then search logs for:

```text
11111111111111111111111111111111
```

## Postman Validation

Add these headers to any request:

```text
traceparent: 00-11111111111111111111111111111111-2222222222222222-01
X-Trace-Id: 11111111111111111111111111111111
```

If the request fails, copy `error.trace_id` from the response and search all service logs for that value.

## Current Limitation

Background ingestion workers do not yet resume the original request trace after the HTTP request returns. The current `rag_ingestion_jobs` table does not have a `trace_id` column or metadata JSON field.

For full async trace continuity, add one of these in a follow-up migration:

```text
rag_ingestion_jobs.trace_id
rag_ingestion_jobs.parent_span_id
```

or:

```text
rag_ingestion_jobs.metadata_json
```

Then set worker ContextVars before processing each job.
