# Functional Parity Matrix

Status vocabulary: **IMPLEMENTED** means source code, typed API integration, and unit/build validation exist. **EXTERNAL VALIDATION PENDING** means the local dependency stack was not started during this implementation; the exact validation procedure is stated rather than claiming unperformed runtime verification.

| Existing capability | Existing UI/location | Backend endpoint | Angular route | Angular implementation | Test | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Login/session bootstrap/logout | Gateway `/ui` | `/auth/login`, `/auth/me`, `/auth/logout` | `/login`, shell | AuthService, local token isolation, header logout | Auth service | IMPLEMENTED |
| Registration/options | Gateway `/ui` | `/auth/register/options`, `/auth/register` | `/register` | Typed reactive form + tiers/roles | Build/form | IMPLEMENTED |
| Refresh/expired session | Gateway token support | `/auth/refresh` | Cross-cutting | shared refresh Observable; retry once | interceptor | IMPLEMENTED |
| Role-aware navigation | Gateway `/ui` | `/auth/me` roles | shell | computed navigation + guards | guards | IMPLEMENTED |
| Dark/light theme | Gateway `/ui` | browser storage | shell | ThemeService signal/effect | Build | IMPLEMENTED |
| Books metrics/filter/list/detail | Gateway `/ui` | `/rag/resources` | `/books` | signals, table/detail/diagnostics | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING: load live resources |
| Resource selection/delete | Gateway `/ui` | `/rag/resources/delete` | `/books`, `/admin/resources` | confirmation dialog, force choice | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING: use non-production data |
| Retry/index operations | Gateway `/ui` | `/rag/resources/{id}/retry`, `/index` | `/books`, `/admin/resources` | status-aware actions | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Graph settings | Search Admin UI | secured `/rag/admin/settings/graph-rag` | `/admin/resources` | typed 1–10 form | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Catalog facets/filters/paging/detail | Gateway `/ui` | `/library/catalog/*` | `/catalog` | all gateway-supported filters + detail | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Standard content search | Gateway/Search UI | `/rag/search` | `/search` | lexical/vector/hybrid typed form/results | Search API test | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Graph search | Search UI | secured `/rag/graph/search` | `/search` | graph entities/relations/summaries | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Combined/debug search | Search UI | secured `/rag/search/combined`, `/debug` | `/search` | combined rendering/debug request | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Grounded answer/citations | Gateway/Answer UI | `/rag/answer` | `/answer` | answer state, sources, citation diagnostics | Answer API test | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Non-stream model compare | Gateway `/ui` | `/rag/answer/compare` | `/compare` | side-by-side results | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| SSE model compare | Answer UI | secured `/rag/answer/compare/stream` | `/compare` | POST fetch stream, event reducer, teardown | SSE unit + gateway test | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Upload/multipart/full metadata | Gateway/Ingest UI | `/rag/ingest` | `/ingest` | typed reactive fields, local preview, no fake provider fields | Ingest page | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Job polling/errors | Ingest UI | secured `/rag/ingest/jobs/{id}` | `/ingest` | RxJS timer, terminal/error display | gateway route | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Library agent/guided queries | Gateway/Agent UI | `/library-search/ask` | `/library-search` | guided/free text, dynamic table, diagnostics | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Raw MCP tools | Gateway `/ui` | `/library-tools/tools`, `/call` | `/admin/library-tools` | schema-driven argument controls/JSON | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Trace visibility | Gateway `/ui` | response headers | all API screens | correlation interceptor + diagnostic panel | Build | IMPLEMENTED — EXTERNAL VALIDATION PENDING |
| Central errors/a11y/responsive UX | all UIs | all | all | error classification, states, semantic forms, skip link, dialog | error test/build | IMPLEMENTED |

## Known capability boundaries

- Existing APIs do not expose per-upload embedding provider/model controls, so the UI intentionally does not fabricate them.
- Existing APIs do not expose server-side compare cancellation. The UI supports browser stream cancellation only.
- External end-to-end validation requires the full local Keycloak/PostgreSQL/RAG/MCP/agent stack. Follow [RUNBOOK.md](RUNBOOK.md); every row has an explicit implementation/validation status.
