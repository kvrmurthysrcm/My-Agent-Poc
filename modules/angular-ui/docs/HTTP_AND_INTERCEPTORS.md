# HTTP and Interceptors

## Request pipeline

```text
typed API service
  -> correlation interceptor (traceparent, trace/span IDs)
  -> error interceptor (normalizes failures)
  -> auth interceptor (gateway-only bearer, refresh/retry)
  -> HttpClient -> /api -> proxy -> gateway
```

The ordering is intentional: the auth interceptor sees a native `401` before the outer error interceptor converts it to `AppHttpError`.

## Typed services

`AuthService`, `ResourceApiService`, `AdminApiService`, `CatalogApiService`, `SearchApiService`, `AnswerApiService`, `IngestApiService`, `LibraryAgentApiService`, `LibraryToolsApiService`, and `HealthApiService` are the only normal HTTP callers.

## Error model

`AppHttpError` distinguishes validation (400/422), unauthenticated (401), unauthorized (403), not found, conflict, server/gateway, network, timeout, and unknown errors. It preserves safe server diagnostics for the expandable developer panel.

## Observability

Each gateway request gets W3C `traceparent`, `X-Trace-Id`, and `X-Span-Id`. Returned `X-Request-ID` and trace headers are surfaced only when actually returned by the gateway. The UI never invents server correlation IDs.

## Interview takeaway

Interceptors are the right place for cross-cutting concerns—not endpoint business behavior. Keep services typed and let multipart bodies retain browser-generated boundaries.
