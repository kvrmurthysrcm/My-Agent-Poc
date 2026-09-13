# SSE Model Comparison Streaming

## WHAT

The Compare page can call `POST /api/rag/answer/compare/stream` and render `search_complete`, `model_started`, `model_result`, `complete`, and `error` events incrementally.

## WHY

Comparison with local models may take minutes. Streaming provides progress and each completed answer rather than making the user wait for every model.

## Flow

```text
Angular typed form
  -> fetch POST + bearer + trace headers
  -> Secure API Gateway authenticated SSE proxy
  -> Answer Service keeps HTTP connection open
  -> text/event-stream frames arrive incrementally
  -> AnswerApiService parses frames into CompareStreamEvent
  -> component signal state updates
  -> cards render model progress/results
```

`EventSource` is intentionally not used: it cannot make the required authenticated POST request with a JSON body. `AnswerApiService` wraps `fetch` + `ReadableStream` in an RxJS `Observable`, so component destruction/unsubscribe aborts the browser request.

## Gateway security

The gateway validates the browser bearer token and role before opening the internal stream. It adds the internal API key and user context only to its server-to-server request. The browser never sees that key.

## Cancellation

The UI exposes **Cancel browser request**. It tears down the reader/connection. The existing Answer API has no documented server-side cancellation endpoint, so it cannot guarantee that model generation stops remotely.

## Test

`answer-api.service.spec.ts` feeds an SSE `ReadableStream` and verifies parsing/completion. Gateway tests verify that the proxy streams content and never forwards browser `Authorization` downstream.

## Interview takeaway

SSE is one long-lived HTTP response with message framing. For POST-authenticated streams, fetch is usually the right browser primitive; wrap it in an Observable for teardown and state integration.
