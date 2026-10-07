# Grafana Loki LogQL Templates

Use these queries in Grafana **Explore** with the **Loki** data source. Select
the **Code** option, paste a query into the editor, choose the time range, and
run it. Start with a narrow time range and a service selector to keep searches
fast.

The examples use the resource fields documented for this project, including
`service_name`, `service_namespace`, `deployment_environment`, `otelTraceID`,
`otelSpanID`, `trace_id`, `span_id`, and `request_id`.

## Basic service searches

All logs from the answer service:

```logql
{service_name="rag-answer-service"} | json | path != "/health"
```

All logs from any RAG service in the local namespace:

```logql
{service_namespace="rag-poc", deployment_environment="local"} | json | path != "/health"
```

Search several services at once:

```logql
{service_name=~"rag-(answer|search|ingest)-service"} | json | path != "/health"
```

Search for a phrase in the log message:

```logql
{service_name="rag-answer-service"} | json | path != "/health" |= "timeout"
```

Case-insensitive search using a regular expression:

```logql
{service_name="rag-answer-service"} | json | path != "/health" |~ `(?i)error|exception|failed`
```

Exclude Kubernetes probe requests to the `/health` endpoint using the parsed
`path` field:

```logql
{service_name="rag-answer-service"} | json | path != "/health"
```

If the log is key-value rather than JSON, use:

JSON logs:

```logql
{service_name="rag-answer-service"} | json | path != "/health"
```

Key-value logs:

```logql
{service_name="rag-answer-service"} | logfmt | path != "/health"
```

Some access logs use `request`, `url`, or `http_route` instead of `path`:

```logql
{service_name="rag-answer-service"} | json | request != "/health" | url != "/health" | http_route != "/health"
```

If the route is still only part of the raw message, use this exact endpoint
filter for common access-log formats:

```logql
{service_name="rag-answer-service"} !~ `(?i)(?:GET|POST|HEAD|OPTIONS)\s+/health(?:\?|\s|$)`
```

The `{service_name="..."}` portion filters stream labels. The `!~` portion
filters the raw log body; it does not inspect fields that have not yet been
parsed. In Explore, expand one `/health` result and check whether the route is
under **Labels**, **Detected fields**, or only the log message. Use a label
selector for a label, `json`/`logfmt` for a detected field, and a raw `!~`
filter for text in the message.

## Remove duplicate request-completion lines

The services can produce two records for one HTTP request:

- `request_completed` is emitted by the application's trace-context middleware
  in `app/trace_context.py`. It includes application correlation fields and
  request duration.
- `200 OK` is the Uvicorn access log for the same response. It is emitted by
  the web server and reports the HTTP status.

They are different loggers, so both records are exported to Loki. To hide the
middleware completion record in Grafana while retaining the Uvicorn access
log, add a line filter for the exact event name:

```logql
{service_name="rag-answer-service"} != "request_completed" | json | path != "/health"
```

For all RAG services:

```logql
{service_name=~"rag-(answer|search|ingest)-service"} != "request_completed" | json | path != "/health"
```

This changes only the search results; it does not stop the application from
emitting the event. To stop generating the event entirely, the middleware
logging call must be removed, lowered to a different log level, or disabled by
application logging configuration. Keep it when request duration and
application-level correlation are useful for diagnostics.

## Trace and request correlation

Find all logs for a known OpenTelemetry trace ID. Replace the placeholder with
the value copied from a log line or Tempo:

```logql
{service_name=~"rag-.*-service"} | json | path != "/health" |= "YOUR_OTEL_TRACE_ID"
```

Find logs for a known OpenTelemetry span ID:

```logql
{service_name=~"rag-.*-service"} | json | path != "/health" |= "YOUR_OTEL_SPAN_ID"
```

Find logs for an application request ID:

```logql
{service_name=~"rag-.*-service"} | json | path != "/health" |= "YOUR_REQUEST_ID"
```

If the log is parsed as key-value data, use a field filter instead:

```logql
{service_name="rag-answer-service"} | json | path != "/health" | otelTraceID="YOUR_OTEL_TRACE_ID"
```

The JSON form is the recommended query for the current records because the
working route field is `path`. Use the field name and parser shown in Grafana's
expanded log line if a different format is displayed.

When searching a longer period, older records may contain non-JSON or malformed
JSON lines. Loki marks those records with `__error__="JSONParserErr"`. Add
`| __error__=""` after the JSON parser when you want to ignore parser failures:

```logql
{service_name=~"rag-.*-service"} | json | __error__="" | path != "/health"
```

## Errors and warnings

Show error-level messages when the level is available as a parsed field:

```logql
{service_name=~"rag-.*-service"} | logfmt | level=~"(?i)error|critical"
```

Show warnings and errors using text matching, which also works with the
project's standard Python log format:

```logql
{service_name=~"rag-.*-service"} |~ `(?i)\bWARNING\b|\bERROR\b|\bCRITICAL\b`
```

Find common application failures:

```logql
{service_name=~"rag-.*-service"} |~ `(?i)timeout|connection refused|unavailable|failed`
```

## Service-specific examples

Answer service failures:

```logql
{service_name="rag-answer-service"} | json | path != "/health" |~ `(?i)llm|ollama|search|context|answer`
```

Search service failures:

```logql
{service_name="rag-search-service"} | json | path != "/health" |~ `(?i)embedding|database|search|ollama|timeout`
```

Ingest service failures:

```logql
{service_name="rag-ingest-service"} | json | path != "/health" |~ `(?i)document|embedding|ingest|database|failed`
```

## Useful aggregations

Count matching error lines by service over the selected Grafana time range:

The examples below use a fixed five-minute range because Explore Code mode may
not expand dashboard-only variables such as `$__interval` and
`$__rate_interval`. Change `[5m]` to `[1m]`, `[15m]`, or another valid Loki
duration as needed.

Use Loki/Go-style duration units:

| Unit | Meaning | Example |
| --- | --- | --- |
| `ns` | Nanoseconds | `500ns` |
| `us` or `µs` | Microseconds | `250us` |
| `ms` | Milliseconds | `500ms` |
| `s` | Seconds | `30s` |
| `m` | Minutes | `15m` |
| `h` | Hours | `2h` |

Durations can be combined, for example `1h30m` or `24h`. Use `24h` instead of
`1d`; `1d` is not accepted by some Loki parsers and Grafana/Loki versions.

```logql
sum by (service_name) (
  count_over_time({service_name=~"rag-.*-service"} | json | __error__="" | path != "/health" |~ `(?i)error|exception|failed` [5m])
)
```

Count log volume by service:

```logql
sum by (service_name) (
  count_over_time({service_name=~"rag-.*-service"} | json | __error__="" | path != "/health" [5m])
)
```

Show the rate of matching errors per second:

```logql
sum by (service_name) (
  rate({service_name=~"rag-.*-service"} | json | __error__="" | path != "/health" |~ `(?i)error|exception|failed` [5m])
)
```

## Query tips

- Use label selectors first, for example `{service_name="rag-search-service"}`.
  They reduce the amount of data Loki must scan.
- `|=` performs a literal substring search. `|~` performs a regular-expression
  search.
- `logfmt` parses `key=value` log content. Use `json` instead if the expanded
  log line is JSON: `{...} | json | level="ERROR"`.
- `otelTraceID` and `otelSpanID` are the OpenTelemetry correlation fields.
  The older `trace_id`, `span_id`, and `request_id` fields may also be useful,
  but they are not always the same identifiers.
- If a selector returns no data, inspect one log line in Grafana and check
  **Labels** and **Detected fields**. A value shown as a detected field must
  be parsed with `logfmt` or `json` rather than placed in the `{...}` label
  selector.
