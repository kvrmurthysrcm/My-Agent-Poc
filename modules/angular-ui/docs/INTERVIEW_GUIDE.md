# Java + Angular Architect Interview Guide

## Project capability discussion points

| Capability | Angular concept | Why this design | Alternatives/trade-offs | Architect discussion |
| --- | --- | --- | --- | --- |
| Auth/session | service, signal, interceptor | One source for identity/tokens/refresh | OIDC SDK or BFF cookie | Separate browser UX policy from gateway authorization. |
| RBAC routes | guards + computed navigation | Prevent dead-end navigation and hide unavailable workflows | Per-component checks only | UI RBAC is not a security boundary. |
| API access | typed services + HttpClient | Keeps DTOs/endpoints out of views | Generated OpenAPI client | Version contracts and test mapping. |
| Correlation | functional interceptor | Every gateway request has trace context | Service-local headers | Cross-cutting policy belongs in pipeline middleware. |
| Search | reactive forms + signals | Rich input and derived result view | Template-driven forms | Match backend query schema, do not invent filters. |
| Grounded answer | container/presentation | Separates request lifecycle from answer/sources | one giant page | Evidence/citation UX is a product and trust concern. |
| Comparison SSE | Observable + fetch stream | POST authentication and teardown | EventSource, WebSocket | Streaming protocol choice follows server contract and auth needs. |
| Ingestion | multipart service + polling | Native boundary handling and job lifecycle | direct service URL | Gateway mediates internal key and authorization. |
| Admin operations | confirmations + role guard | Destructive actions need explicit UX | hidden buttons only | Add audit/soft delete in production. |
| Library tools | schema-driven dynamic forms | Tools evolve without one custom page each | hand-built tool forms | Validate schema and cap complex types. |

## Questions and concise answers

### 1. Angular fundamentals

1. **What is Angular?** A TypeScript application framework with a compiler, dependency injection, templates, routing, forms, and HTTP tooling for maintainable client applications.
2. **What is an SPA?** A browser application that swaps views/client state without full document navigation; server APIs remain separately deployed.
3. **What does the Angular compiler do?** It compiles templates and decorators into efficient JavaScript instructions and reports template type errors early.
4. **Why use TypeScript?** Static types make refactors, API contracts, tooling, and large-team maintenance safer; types erase at runtime.

### 2. Components and templates

5. **What makes a standalone component different?** It declares the directives, pipes, and components it imports directly instead of relying on an NgModule declaration.
6. **Interpolation vs property binding?** Interpolation renders a string in template content; property binding writes a target DOM/component property.
7. **Why avoid direct `innerHTML`?** It risks XSS and bypasses Angular’s declarative view/state model; render untrusted data through bindings.
8. **When would you use a directive rather than a component?** Use a directive to add behavior to an existing host; use a component when it owns a view/template.

### 3. Signals

9. **What is a signal?** A synchronous reactive value read by calling it and changed via `set`/`update`.
10. **What is `computed`?** A cached derived signal that re-evaluates when its tracked dependencies change.
11. **What is an `effect` appropriate for?** Side effects such as persistence, analytics, or DOM integration—not computing another state value.
12. **Why use signals for the books dashboard?** Filters, selection, metrics, and loading state are local synchronous UI state with clear derivations.

### 4. RxJS

13. **What is an Observable?** A lazy sequence of zero or more values over time that can complete, error, and be unsubscribed.
14. **Signals vs Observables?** Signals represent current state for a view; Observables represent asynchronous/time-based work such as HTTP, polling, and SSE.
15. **Why use `switchMap` for polling?** It switches to the newest inner request and avoids processing obsolete previous work.
16. **How do you prevent refresh storms?** Store one in-flight refresh Observable and share/replay it to all requests that receive 401 concurrently.

### 5. Dependency injection

17. **What is Angular DI?** An injector creates and supplies dependencies based on provider configuration instead of classes constructing collaborators themselves.
18. **Why use `inject()`?** It works in functional guards/interceptors and field initialization while keeping dependencies explicit.
19. **Root provider vs component provider?** Root produces an application singleton; component provider creates a scoped instance for that subtree.

### 6. HTTP

20. **Why centralize HttpClient calls in services?** It preserves typed contracts, makes testing simple, and prevents component duplication.
21. **How do HTTP interceptors work?** They wrap a request chain, can clone requests, call the next handler, transform responses, retry, or normalize errors.
22. **Why not set multipart Content-Type manually?** The browser must add the generated multipart boundary; manual headers commonly break upload parsing.
23. **How do you handle 502 from a gateway?** Show a dependency/gateway-friendly message, retain safe diagnostics, and avoid exposing internal details.

### 7. Routing and guards

24. **What is lazy loading?** Loading a route’s JavaScript only on navigation, which reduces initial bundle cost.
25. **What does a guard return?** `true`, `false`, a `UrlTree`, or an async equivalent to allow, cancel, or redirect navigation.
26. **Why is a role guard not security?** A caller can alter client code or call the API directly; the gateway must authorize the request too.
27. **How would you split a monolithic Angular app?** Identify domain routes, establish contracts/shared libraries, lazy load bounded features, and migrate incrementally.

### 8. Forms

28. **Why reactive forms for ingestion/search?** Their typed model, validators, dynamic controls, and deterministic testability suit enterprise forms.
29. **Client validation vs server validation?** Client validation improves feedback; server validation is authoritative because clients are untrusted.
30. **How do dynamic tool forms remain safe?** Interpret a constrained JSON schema, type-convert values, validate locally, and let the gateway/tool validate again.

### 9. State management

31. **When is NgRx justified?** When many cross-feature workflows need explicit event history, effects, normalized cache, devtools, and a team can sustain the ceremony.
32. **Why no NgRx here?** Shared state is limited to session/theme and each feature owns its own short-lived screen state.
33. **How do you avoid stale derived state?** Use computed state rather than storing independently updated copies of a filtered list or metric.

### 10. Performance and change detection

34. **What is OnPush?** A strategy that narrows change checking to signal updates, input changes, events, and explicit marks rather than broad checks.
35. **How do `@for` track expressions help?** Stable identity lets Angular update only changed list rows instead of recreating them.
36. **What would you optimize first?** Measure actual route, render, network, and backend latency; then choose code splitting, caching, pagination, or rendering changes.

### 11. Security

37. **Where should SPA tokens be stored?** A BFF with HttpOnly/Secure/SameSite cookies is usually preferable; local storage is a POC compromise with XSS risk.
38. **How should token refresh work?** Retry only eligible requests once after a single-flight refresh; clear session on refresh failure.
39. **Why must internal API keys stay off the browser?** Browser code, storage, and network traffic are inspectable; a gateway should hold service credentials.
40. **How do you mitigate XSS?** CSP, framework bindings, output encoding, dependency hygiene, avoiding unsafe DOM APIs, and short/non-script-readable sessions.

### 12. Testing

41. **What should HttpClient tests verify?** URL, method, DTO body/query, headers/interceptor policy, success mapping, and important failure paths.
42. **What is the value of component tests?** They validate template/rendered interaction, validation, accessibility state, and local orchestration without a browser stack.
43. **What belongs in E2E tests?** Critical journeys across real auth, gateway, permissions, upload, polling, and streamed answers in an isolated environment.

### 13. Architecture

44. **How would you structure a large Angular enterprise app?** Core cross-cutting concerns, shared UI/utilities, domain feature libraries, lazy routes, contract libraries, and clear ownership boundaries.
45. **How would you version API contracts?** Publish OpenAPI/schema versions, generate or validate clients, maintain compatibility policy, and test consumer/provider behavior.
46. **How do you handle observability in an SPA?** Propagate correlation IDs, log safe client errors, capture route/performance telemetry, and join it with gateway traces.
47. **What is a BFF?** A backend tailored to frontend needs that owns sessions, aggregation, and secret-bearing service calls, reducing browser trust responsibilities.

### 14. Java/Spring + Angular integration

48. **How does an Angular SPA integrate with Spring Boot?** Through versioned HTTPS JSON/multipart/SSE APIs, CORS/session/token policy, and shared contract tests—not direct database access.
49. **How would you stream events from Spring Boot?** Use SSE (`SseEmitter`/reactive stream) or WebSocket when bidirectional messaging is needed; proxy through the security boundary.
50. **How would you coordinate validation?** Put business validation in Spring/server DTOs, mirror high-value constraints in Angular reactive forms, and map structured errors consistently.

## Scenario answers

- **Signals vs RxJS:** signals for current UI state; RxJS for cancellation, streams, operators, SSE, polling, and HTTP composition.
- **Prevent memory leaks:** prefer `AsyncPipe`/signals, use `takeUntilDestroyed`, unsubscribe timer/SSE streams, and abort fetch readers on destroy.
- **Improve performance:** profile first; apply route splitting, OnPush, stable list tracking, pagination, debouncing, cache strategy, and backend query tuning.
- **Authentication token storage:** articulate the threat model and recommend a BFF cookie session over JavaScript-readable refresh tokens.

## Architect takeaway

Answer in terms of boundaries and trade-offs: the SPA is an untrusted presentation client, Spring/gateway owns security and business rules, and contracts/observability/testing make the integration operable.
