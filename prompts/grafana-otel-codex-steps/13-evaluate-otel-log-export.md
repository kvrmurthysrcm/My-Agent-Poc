# Step 13 — Evaluate OTel Log Export

Tracing is already working. Do not immediately rewrite logging.

Inspect:
- current Python logging config
- existing application trace_id/correlation ID
- handlers/formatters
- effect of OTEL_PYTHON_LOG_CORRELATION=true
- whether logs already reach Loki

Treat these as distinct:
- app.trace_id = existing business/request correlation ID
- OTel TraceId = distributed trace
- OTel SpanId = current span

Determine whether zero-code logging is sufficient. If not, propose the smallest explicit LoggerProvider + OTLPLogExporter change.

Show current behavior, missing pieces, and proposed changes before implementation.
