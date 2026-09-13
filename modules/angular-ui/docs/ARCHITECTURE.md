# Architecture

## WHAT

The application is a standalone, lazy-loaded Angular SPA with a small signal-based state layer and typed HTTP clients.

## WHY

It makes feature ownership and security boundaries obvious without introducing NgRx or a large UI framework for a POC of this size.

## HOW

```text
Browser
  |
  v
Angular 21 SPA :4200
  |  functional interceptors: correlation -> error -> auth/refresh
  v
Development proxy /api
  |
  v
Secure API Gateway :8010
  |-- Keycloak :8080
  |-- RAG Ingest :8000
  |-- RAG Search :8001
  |-- RAG Answer :8002
  |-- Online Library :8003 -> MCP :8004 -> Library Agent :8005
```

The app uses no direct browser-to-database, browser-to-Keycloak-admin, browser-to-MCP, or browser-to-internal-service traffic.

## Component boundaries

```text
Feature page (container)
  -> typed reactive form + local signals
  -> typed API service
  -> HttpClient/interceptors
  -> gateway

Shared presentation: status badge, loading/empty/error state, JSON viewer,
diagnostics panel, confirmation dialog, result cards.
```

`ShellComponent` owns navigation, user information, theme selection, and the authenticated router outlet. Features are lazy-loaded using `loadComponent`.

## Important implementation choices

| Decision | Reason | Alternative / trade-off |
| --- | --- | --- |
| Standalone components | Less ceremony and direct imports | NgModules remain useful for legacy libraries |
| Signals for view/shared UI state | Simple synchronous state and derived metrics | RxJS remains used for HTTP, polling, and streams |
| Typed services | Keep HTTP out of components and catch contract changes | Generated OpenAPI client would be suitable when contracts stabilize |
| Functional interceptors | Tree-shakeable, concise `inject()` usage | Class interceptors are valid in older applications |
| Native CSS/semantic HTML | Small dependency surface and accessible baseline | Angular Material can be introduced if product scale needs it |
| Gateway SSE proxy | Maintains token/API-key boundary | Direct service calls would violate the architecture |

## Security extension

The gateway now adds narrowly scoped, protected proxy routes for Graph/combined/debug search, SSE compare, ingestion job status/errors, and Graph RAG settings. They forward the internal API key and user context only server-side. Existing APIs were not changed or removed.

## Interview takeaway

An Angular architecture should separate routes, containers, reusable presentation, cross-cutting HTTP policy, and service contracts. Client authorization improves UX; gateway authorization remains the enforcement point.
