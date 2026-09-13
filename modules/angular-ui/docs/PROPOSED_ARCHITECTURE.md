# Proposed Angular Architecture (Pre-Implementation)

## Status

This began as the Step 2 architecture proposal. The Angular 21.2.22 implementation is now scaffolded and the gateway capability gap was resolved through approved, additive, role-protected proxy routes. See `ARCHITECTURE.md` and `IMPLEMENTATION_REPORT.md` for final state.

## Target runtime

```text
Browser
  -> Angular 21 SPA :4200
       -> functional interceptors
       -> typed API services
  -> development proxy /api
  -> Secure API Gateway :8010
  -> Keycloak and internal RAG/library services
```

Only gateway-relative URLs will be used by normal Angular features. No internal API key, Keycloak admin credential, database connection, or direct downstream base URL will be shipped to the browser.

## Proposed source decomposition

```text
src/app/
  core/
    auth/                 session store, token storage, auth API
    guards/               authGuard, roleGuard
    interceptors/         auth/refresh, correlation, error handling
    http/                 API error model and response utilities
    models/               cross-feature DTOs
    config/               typed runtime/environment configuration
  shared/
    components/           status badge, empty/loading/error, JSON viewer,
                          confirmation dialog, result/source cards
    directives/           focus/accessibility utilities only if justified
    pipes/                byte/date/display formatting
    utils/                trace IDs and form/DTO helpers
  layout/
    shell/                authenticated router outlet
    header/               user, roles, theme, logout
    navigation/           capability-aware links
    theme/                persisted theme signal/service
  features/
    auth/                 login and registration
    books/                dashboard, metrics, list and detail
    catalog/              facets, filters, paging and details
    search/               standard/graph/combined forms and results
    answer/               grounded answer and sources
    compare/              non-streaming + streaming state abstraction
    ingest/               full metadata/upload and job polling
    admin/                resource actions and Graph settings
    library-search/       guided NLQ and diagnostics
    library-tools/        schema-driven tool forms and JSON output
```

## Routes

Authenticated features live under a lazy shell route. Each feature is loaded with `loadComponent` or a small feature routes file. Guards run before feature code is downloaded where possible.

```text
/login
/register
/(authenticated shell)
  /books
  /catalog
  /search
  /answer
  /compare
  /library-search
  /ingest
  /admin/resources
  /admin/library-tools
```

## State boundaries

- Component-only interaction state: writable signals.
- Derived display/authorization state: computed signals.
- Shared session, theme, and feature caches: injectable signal stores/facades.
- One-shot HTTP and polling/stream lifecycles: RxJS.
- No NgRx: current scale does not justify actions/reducers/effects/global normalized state.

```text
Page component
  -> feature facade (signals)
       -> typed API service (Observable)
            -> HttpClient
                 -> gateway
```

## HTTP pipeline

1. API service creates a typed request using a relative `/api` URL.
2. Correlation interceptor creates `traceparent`, `X-Trace-Id`, and `X-Span-Id`.
3. Auth interceptor attaches the access token only to configured gateway URLs.
4. On 401, one coordinated refresh request is shared so concurrent failures do not cause a refresh storm.
5. Successful refresh updates isolated token storage and retries eligible requests once.
6. Refresh failure clears session and navigates to login.
7. Error interceptor converts HTTP/network/timeout failures to a typed `AppHttpError` while preserving server diagnostics.

Multipart requests are not assigned a manual `Content-Type`; the browser supplies the boundary.

## Authentication decisions

- Reproduce local-storage persistence for parity, isolated behind `TokenStorage`/`AuthService`.
- Bootstrap with `/auth/me` before opening authenticated routes.
- Decode token expiry only as a client scheduling hint; never treat client decoding as validation.
- The current user response is the source of UI roles.
- Backend role enforcement remains the security boundary.
- Document a production move to a secure, HttpOnly, SameSite cookie/BFF session design.

## UI and accessibility

- Semantic HTML and project-owned CSS; no Angular Material dependency is proposed.
- Responsive header/navigation, grids, cards, and horizontally scrollable data tables.
- Visible focus, skip link, correctly associated labels/descriptions, live status regions, and keyboard-operable dialogs.
- Reusable loading, empty, error, status, source, diagnostics, and confirmation components.
- Light/dark design tokens using CSS custom properties and a persisted theme signal.
- OnPush change detection on application components.

## Testing proposal

- Angular 21's generated stable test tooling, confirmed when the exact CLI version is selected.
- Service tests with the Angular HTTP testing provider.
- Auth refresh-concurrency and URL-scoping tests.
- Guard role matrix tests.
- Reactive-form validation tests.
- Streaming parser/reducer and teardown tests.
- Container tests for loading/error/empty/success behavior.
- Production build and strict TypeScript compilation as delivery gates.

## Open architecture decision

The intended design requires gateway access to SSE compare, graph/combined/debug search, ingest job status/errors, and Graph RAG settings. The recommended solution is a small set of additive gateway proxy routes. Until the user approves that limited backend change—or explicitly approves direct internal-service calls—those Angular capabilities cannot be both functional and compliant with the target architecture.
