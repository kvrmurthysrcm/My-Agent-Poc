# Step 11 — Verify Answer -> Search Distributed Trace

Do not add manual tracing first.

Identify which HTTP client Answer uses to call Search and verify its OTel instrumentation.

Invoke the normal Answer flow that calls Search.

In Tempo verify ONE trace contains:
- Answer server span
- outbound HTTP client span
- Search server span

Verify W3C context propagation via `traceparent` and `tracestate` when applicable.

If two traces appear, diagnose client/server instrumentation or propagation and make the smallest fix.

Report TraceId, Answer spans, Search spans, HTTP client span, propagation result.
