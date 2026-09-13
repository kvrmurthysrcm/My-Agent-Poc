# Testing Strategy

Angular 21's generated Vitest/jsdom unit-test builder is used. Tests favor observable behavior over coverage-only assertions.

| Area | Test |
| --- | --- |
| Root bootstrapping | `app.spec.ts` |
| Auth service | login token persistence, `/auth/me`, role state |
| Auth interceptor | gateway-only bearer attachment |
| Guards | anonymous redirect and role matrix |
| Typed search/answer services | endpoint, method, request DTO |
| SSE parser | fetched `ReadableStream` event parsing and completion |
| Major pages | Books metrics, Catalog facets/detail, Ingestion file-required validation |
| Error normalization | validation and authorization classification |
| Gateway proxies | 21 pytest checks including Graph, jobs, settings, SSE |

Run:

```powershell
npm test -- --watch=false
cd ..\secure_api
..\..\.venv\Scripts\python.exe -m pytest tests/test_rag_gateway_routes.py -q -p no:cacheprovider
```

Recommended next tests: component interaction tests for catalog paging, resource deletion confirmation, router navigation, and full end-to-end tests against a disposable Keycloak/PostgreSQL/service stack.
