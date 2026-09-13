# Existing UI Functionality Inventory

## Purpose and analysis boundary

This document records the browser functionality that exists before the Angular implementation. The primary parity source is `modules/secure_api/app/ui/gateway.html`. Standalone development UIs in the ingest, search, answer, and library-agent services are recorded separately because they expose capabilities that are not currently routed through the Secure API Gateway.

Analysis date: 2026-09-02.

## Current UI architecture

The existing main UI is one server-served HTML file containing CSS, markup, and vanilla JavaScript. It is served by the Secure API Gateway at `/` and `/ui`. Its state is held in one JavaScript object and browser storage. It uses `fetch`, relative gateway URLs, `FormData`, native confirmation dialogs, and hand-written DOM rendering.

```text
Browser gateway.html
  -> relative /auth, /rag, /library, and /library-* URLs
  -> Secure API Gateway :8010
  -> authenticated downstream calls
```

The browser creates W3C-compatible trace and span IDs for every request. Protected requests include a bearer access token. The browser never receives the gateway's internal downstream API key.

## Authentication and session functionality

| Capability | Existing behavior | State/error behavior |
| --- | --- | --- |
| Login | Username/password form calls `POST /auth/login`. | Displays signing-in and error messages; stores returned tokens. |
| Registration options | Opening registration calls `GET /auth/register/options`. | Populates subscription tiers and displays automatically assigned roles; falls back visually to FREE if the request returns no tiers. |
| Registration | Full name, email, username, password, and tier call `POST /auth/register`. | HTML minimum lengths are 3 for username and 8 for password; success returns to login. |
| Session bootstrap | A stored access token is checked with `GET /auth/me`. | Invalid/expired token clears both tokens and returns to login. |
| Token storage | Access and refresh tokens use `localStorage` keys `secure_api_access_token` and `secure_api_refresh_token`. | Persists across reloads; has the documented XSS risk of local storage. |
| Refresh token | The refresh token is retained. | The existing UI does **not** call `/auth/refresh` automatically or manually. |
| Current user | `/auth/me` provides subject, username, email/name, roles, and issuer. | Header displays preferred username or subject. |
| Role display | Header shows a coarse `admin` or `user` pill. | It does not list every role even though the user DTO contains them. |
| Logout | Best-effort `POST /auth/logout` with the refresh token, then local state/storage cleanup. | Local logout completes even if the network call fails. |
| Unauthorized/expired session | Bootstrap failure returns to login. | There is no centralized runtime 401 refresh/retry flow. |

## Application shell

- Sticky responsive header with product title and welcome text.
- Navigation: Books, Search, Answer, Compare, Library, Library Search, plus admin-only Ingest and Library Tools.
- Admin detection uses `rag_admin` or `system_admin`.
- Global success/error message region.
- Refresh button reloads Books regardless of the current view.
- Dark/light toggle persists `secure_api_theme` in `localStorage`.
- Responsive layouts collapse to one column under 900 px.
- Navigation is in-page DOM switching; URLs, deep links, browser back navigation, guards, and lazy loading do not exist.

## Books dashboard

### Summary and filtering

- Automatically loads after a valid session and whenever Books navigation is selected.
- Prevents duplicate simultaneous refreshes and disables both refresh buttons while loading.
- Four metrics: total, ready/completed, queued/processing, and failed.
- Client-side free-text filtering across title, author, category, ingestion status, latest job status, and tags.
- Visible-row count and explicit empty state.

### Resource table

The table shows:

- Title and resource ID.
- Author, category, and tag badges.
- Effective status and RAG enabled/disabled state.
- Chunk and embedding counts.
- Job count and latest job status/progress information.
- Admin selection checkbox and action column.

The resource response also supports latest job ID/indexing mode, processed/embedded chunk counts, Graph RAG entity/relationship counts, latest error information, file metadata, creation time, and arbitrary metadata. Angular should expose these in a detail view even where the compact legacy row does not display every value.

### Administrative actions

- Select individual resources or toggle all visible resources.
- Bulk delete with a native confirmation dialog. The existing UI sends `force: true`.
- Retry button only for an effective `FAILED` status.
- Create Standard embeddings (`STANDARD`).
- Create Graph index (`GRAPH`).
- Index buttons are disabled while the resource is queued/processing.
- Every mutation refreshes the resource list.

## Content search

### Existing gateway screen

- Required query.
- Search mode: `hybrid`, `vector`, or `keyword` (labelled lexical in some documentation).
- Top K.
- Optional resource ID.
- Comma-separated tags.
- Always requests metadata.
- Loading, error JSON, no-results, and ranked-results states.
- Result cards show rank, title, overall score, chunk index, and snippet.

### Additional response data available from the routed endpoint

The response may include normalized/original query, intent, spelling normalization, embedding provider/model, page range, section/heading path, vector score, keyword score, chunk text, metadata, per-result debug information, and observability. These are candidates for a collapsible diagnostics/detail view.

### Search capabilities not reachable through the gateway

The Search Service has direct endpoints for Graph search, combined standard/graph search, debug search, and Graph RAG runtime settings. The gateway currently proxies only `POST /rag/search`. See the API mapping and open decisions.

## Grounded answer

- Required question.
- Answer mode: concise, detailed, or quote-backed.
- Top K (1–50) and context Top K (1–20).
- Include-sources true/false.
- Uses hybrid search in the existing screen.
- Slow-local-model loading message.
- Error JSON display.
- Displays answer status, answer text, and raw source JSON.

The routed response can additionally expose provider/model, citation verification, cited ranks, source counts, search counts, raw search/prompt when enabled, and observability. Angular should render these as typed fields and diagnostics.

## Model comparison

### Existing gateway screen

- One required question.
- Comma-separated local model names.
- Answer mode and Top K/context Top K.
- Always includes sources and uses hybrid search.
- Sends a non-streaming request to `POST /rag/answer/compare`.
- Shows each model/provider, answer status/text, source count, and mode side by side.
- Displays shared sources as JSON.

### SSE capability gap

The Answer Service has `POST /rag/answer/compare/stream`, producing `search_complete`, `model_started`, `model_result`, and `complete` events. The Secure API Gateway has no matching streaming proxy route. The existing gateway UI therefore does not use SSE. Browser `EventSource` also cannot issue the required authenticated POST request; Angular needs a fetch/ReadableStream abstraction once a gateway streaming endpoint exists.

## Ingestion

### Existing gateway screen

- Admin-only navigation and gateway role check (`rag_ingest_user` or `rag_admin` on the API; current UI visibility is narrower and requires admin).
- Required file input; guidance lists PDF, TXT, DOCX, and EPUB.
- Optional title and author.
- Comma-separated tags.
- Indexing mode: NONE, STANDARD, GRAPH, or BOTH; NONE is the UI default.
- Sends multipart `file` plus JSON-string `metadata`.
- Metadata includes title/filename fallback, author, DOCUMENT resource type, `secure_api_ui` source system, tags, and mode.
- Renders the complete accepted/error response as JSON and refreshes Books on acceptance.

### Standalone ingest UI and API capabilities

The direct Ingest UI also exposes category, language, business domain, description, source system, custom metadata JSON, semantic/intelligent chunking strategy, chunk size, chunk overlap, metadata preview, and job polling. The ingestion schema additionally supports genre, publisher, publication date, ISBN, page count, created-from-file date, and custom metadata.

The Secure API Gateway can forward all metadata fields in the initial multipart request, but it does not currently proxy job-status/error endpoints or Graph RAG runtime settings. Provider/model selection is service configuration rather than an ingest-request field.

## Structured Library Catalog

### Existing screen filters

- General search across catalog metadata.
- Author, tag, and genre filters with values loaded from facets.
- Subscription tier from facets.
- Sort: title, newest added, newest published, oldest published.
- Limit 1–100.
- Status is fixed to ACTIVE by the legacy UI.
- Search/reset and previous/next offset pagination.

### Routed filters not currently shown

The gateway endpoint additionally accepts category, publisher, language, status, `published_from`, and `published_to`. Angular requirements explicitly request these, so the new catalog form should expose them.

### Results and details

- Results display title, publisher, authors, genre/category, up to three tag badges, tier, and admin-only ingestion/status data.
- First result is selected automatically.
- Clicking a row loads full detail.
- Detail shows description, all authors/tags, genre/category, language, tier, ISBN, page count, and publication date.
- Admin detail adds resource ID, status, ingestion status, RAG-enabled state, file name, and file size.
- Loading, error, initial, empty, summary, and pagination states are present.

## Natural-language Library Search

- Available to every authenticated user.
- Required free-text question, limit 1–100, and non-negative offset.
- Guided buttons populate questions for Books, Authors, Approvals, and Bookshelf.
- Always asks for the raw tool result.
- Displays the selected tool, formatted answer, original question, dynamic row/resource table, tool arguments, and debug data.
- Supports errors as structured JSON.

The agent response diagnostics can include selection mode, fallback use, LLM provider/model, Ollama and MCP configuration, temperatures/token settings, and timings.

## Raw Library Tools

- Admin-only navigation and backend authorization (`rag_admin` or `system_admin`).
- Loads discoverable MCP tools from the gateway.
- Displays tool name and description; auto-selects the first tool.
- Existing form only generates `limit` and `offset` arguments, except `list_available_tables`, which receives no arguments.
- Calls a selected tool and renders the complete structured result as formatted JSON.

The MCP catalog contains business tools with richer typed schemas as well as raw table tools. Angular should generate controls from each returned input schema or implement typed forms per known tool, rather than limiting every tool to `limit`/`offset`.

## Tracing and diagnostics

- Every request receives a new 32-hex-character trace ID and 16-hex-character span ID.
- Sends `traceparent: 00-<trace-id>-<span-id>-01`, `X-Trace-Id`, and `X-Span-Id`.
- The gateway adds/request-propagates `X-Request-ID` and downstream identity context.
- The legacy UI does not surface returned correlation headers.
- Angular should retain client trace generation and expose only real request/response correlation data in a diagnostics panel.

## Existing error and accessibility behavior

### Present

- Native required/min/max validation for primary controls.
- Human-readable login, registration, catalog, tools, and global messages.
- Raw JSON for many backend failures.
- Semantic forms, labels, buttons, headings, tables, and native inputs.
- Responsive layout and disabled loading/action buttons.
- HTML escaping before dynamic values enter `innerHTML`.

### Missing or inconsistent

- No central classification of 400/401/403/404/409/422/500/network/timeout failures.
- No automatic refresh-token coordination.
- No focus management, live regions, skip link, route announcements, or accessible custom confirmation dialog.
- Most async actions lack cancellation.
- No URL-addressable views or unsaved-form navigation warning.
- No automated frontend tests.

## Standalone browser UIs

| Service | URL | Additional purpose |
| --- | --- | --- |
| RAG Ingest | `:8000/ui` | Full metadata/chunk controls, metadata preview, and ingestion job polling. |
| RAG Search | `:8001/ui/search` | Direct content search. |
| RAG Search Admin | `:8001/ui/admin/resources` | Resource inspection/filtering and development cleanup. |
| RAG Answer | `:8002/ui/answer` | Direct answer and comparison testing. |
| Online Library Agent | `:8005/ask` | Guided and open-ended NLQ with developer diagnostics. |

These direct pages are development tools and do not share the complete gateway authorization boundary.

## Functional scope conclusion

The Angular application can reproduce the current gateway UI using existing gateway routes. Full satisfaction of the expanded prompt—SSE comparison, graph/combined/debug search, job polling/errors, and Graph RAG runtime settings—requires corresponding Secure API Gateway proxy routes or an explicit exception allowing the browser to call internal services directly. Direct calls are not recommended because they bypass the intended security and internal-credential boundary.
