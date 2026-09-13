# API Endpoint Mapping

## Conventions

- Angular uses relative `/api/...` URLs in development.
- `proxy.conf.json` is expected to strip or forward the prefix to the Secure API Gateway at `http://localhost:8010`.
- `Authenticated` means any valid JWT; role-specific requirements are listed explicitly.
- DTO names below describe the planned Angular interfaces. Backend types are from the current Pydantic models where present.
- The gateway accepts untyped dictionaries for several proxy routes, but Angular should type them to the downstream contract.

## Gateway endpoints usable by Angular

| Existing function | Gateway endpoint | Method | Request -> response | Required role | Planned Angular route / service |
| --- | --- | --- | --- | --- | --- |
| Login | `/auth/login` | POST | `LoginRequest` -> `TokenResponse` | Public | `/login`; `AuthApiService` |
| Registration choices | `/auth/register/options` | GET | none -> `RegistrationOptionsResponse` | Public | `/register`; `AuthApiService` |
| Register | `/auth/register` | POST | `RegistrationRequest` -> `RegistrationResponse` | Public | `/register`; `AuthApiService` |
| Refresh access token | `/auth/refresh` | POST | `RefreshRequest` -> `TokenResponse` | Refresh token | Cross-cutting; `AuthApiService` + auth interceptor |
| Logout | `/auth/logout` | POST | `LogoutRequest` -> `LogoutResponse` | Refresh token | Shell; `AuthApiService` |
| Current user/session check | `/auth/me` | GET | none -> `CurrentUser` | Authenticated | Shell/bootstrap; `AuthApiService` |
| Resource dashboard | `/rag/resources` | GET | none -> `AdminResourceListResponse` | Authenticated | `/books`; `ResourceApiService` |
| Delete selected resources | `/rag/resources/delete` | POST | `AdminDeleteResourcesRequest` -> `AdminDeleteResourcesResponse` | `rag_admin` or `system_admin` | `/admin/resources`; `AdminApiService` |
| Retry failed resource | `/rag/resources/{id}/retry` | POST | empty -> `AdminRetryResourceResponse` | `rag_admin` or `system_admin` | `/admin/resources`; `AdminApiService` |
| Index existing chunks | `/rag/resources/{id}/index` | POST | `AdminIndexResourceRequest` -> `AdminIndexResourceResponse` | `rag_admin` or `system_admin` | `/admin/resources`; `AdminApiService` |
| Upload/ingest | `/rag/ingest` | POST multipart | `file` + serialized `IngestMetadata` -> `IngestAcceptedResponse` | `rag_ingest_user` or `rag_admin` | `/ingest`; `IngestApiService` |
| Standard content search | `/rag/search` | POST | `SearchRequest` -> `SearchResponse` | `rag_search_user`, `rag_user`, or `rag_admin` | `/search`; `SearchApiService` |
| Grounded answer | `/rag/answer` | POST | `AnswerRequest` -> `AnswerResponse` | `rag_user` or `rag_admin` | `/answer`; `AnswerApiService` |
| Answer alias | `/rag/ask` | POST | `AnswerRequest` -> `AnswerResponse` | `rag_user` or `rag_admin` | Not separately exposed; same service |
| Compare answers | `/rag/answer/compare` | POST | `AnswerRequest` with `compare_models` -> `AnswerComparisonResponse` | `rag_user` or `rag_admin` | `/compare`; `AnswerApiService` |
| Downstream health summary | `/rag/test-downstream` | GET | none -> service status object | Authenticated | Diagnostics; `HealthApiService` |
| Catalog facets | `/library/catalog/facets` | GET | none -> `CatalogFacetsResponse` | Authenticated | `/catalog`; `CatalogApiService` |
| Catalog search | `/library/catalog/resources` | GET | query filters -> `CatalogResourceListResponse` | Authenticated | `/catalog`; `CatalogApiService` |
| Catalog resource detail | `/library/catalog/resources/{id}` | GET | none -> `CatalogResourceDetailResponse` | Authenticated | `/catalog`; `CatalogApiService` |
| Catalog dependency health | `/library/catalog/health` | GET | none -> health object | Authenticated | Diagnostics; `HealthApiService` |
| Natural-language library query | `/library-search/ask` | POST | `AskRequest` -> `AskResponse` | Authenticated | `/library-search`; `LibraryAgentApiService` |
| Library-agent health | `/library-search/health` | GET | none -> health object | Authenticated | Diagnostics; `HealthApiService` |
| Discover raw MCP tools | `/library-tools/tools` | GET | none -> tool definitions/input schemas | `rag_admin` or `system_admin` | `/admin/library-tools`; `LibraryToolsApiService` |
| Call raw MCP tool | `/library-tools/call` | POST | `{name, arguments}` -> structured tool result | `rag_admin` or `system_admin` | `/admin/library-tools`; `LibraryToolsApiService` |
| MCP dependency health | `/library-tools/health` | GET | none -> health object | `rag_admin` or `system_admin` | Diagnostics; `HealthApiService` |
| Gateway liveness | `/health` | GET | none -> `{status}` | Public | Optional status page; `HealthApiService` |
| Gateway details | `/health/details` | GET | none -> service/version/environment/time | Public | Optional status page; `HealthApiService` |

## Important DTO field mapping

### Authentication

```text
LoginRequest: username, password
TokenResponse: access_token, refresh_token?, token_type, expires_in?, refresh_expires_in?, scope?
CurrentUser: sub, preferred_username?, email?, name?, roles[], issuer
RegistrationRequest: full_name, email, username, password, subscription_tier
RegistrationOptionsResponse: subscription_tiers[], assigned_roles[], role_assignment_mode
```

### Search

```text
SearchRequest
  query
  search_mode?: vector | keyword | hybrid
  top_k?: number
  min_score?: 0..1
  filters: resource_id?, category?, tags[], metadata{}
  include_metadata
  include_chunk_text?

SearchResponse
  query, original_query?, query_intent?, spelling_normalized
  search_mode, top_k, total_results
  embedding_provider, embedding_model
  results[]: rank, resource_id, chunk_id, title, chunk_index,
             page_start?, page_end?, section_title?, heading_path[], score,
             vector_score?, keyword_score?, snippet, chunk_text?, metadata?, debug?
  observability?
```

### Answer and comparison

```text
AnswerRequest
  query
  search_mode: vector | keyword | hybrid
  top_k?: 1..50
  context_top_k?: 1..20
  filters
  include_sources?
  answer_mode: concise | detailed | quote-backed
  include_raw_prompt
  system_instruction?
  compare_models[] (maximum 8)

AnswerResponse
  query, answer, answer_status
  answer_mode, llm_provider, llm_model, search_mode
  search_total_results, context_source_count, cited_source_ranks[]
  citation_verification{}, sources[], raw_search?, raw_prompt?, observability?
```

### Ingestion

```text
IngestMetadata
  title?, description?, resource_type, category_name?, genre?, business_domain?
  source_system, author?, language?, publisher?, published_date?, isbn?, page_count?
  tags[], created_date_from_file?, custom_metadata{}
  chunking: strategy?, chunk_size_tokens?, chunk_overlap_tokens?
  indexing_mode: NONE | STANDARD | GRAPH | BOTH

IngestAcceptedResponse: resource_id, job_id, status, message
```

### Catalog

The gateway forwards these query fields: `q`, `author`, `category`, `genre`, `tag`, `publisher`, `language`, `tier`, `status`, `published_from`, `published_to`, `sort`, `limit`, and `offset`. The current Online Library API returns an envelope with `total`, `count`, `limit`, `offset`, and `resources`, plus a `{resource}` detail envelope. Resource records contain structured authors/tags and catalog, publication, tier, file, and RAG metadata.

### Library agent and tools

```text
AskRequest: question, limit (1..100), offset >= 0, include_raw
AskResponse: question, selected_tool?, tool_arguments{}, answer, debug{}, raw_tool_result?
Tool call: name + arguments object
Tool discovery: tool name, description, and JSON input schema
```

## Role-to-route plan

| Angular route | Minimum capability |
| --- | --- |
| `/books` | Authenticated |
| `/catalog` | Authenticated |
| `/search` | One of `rag_search_user`, `rag_user`, `rag_admin` |
| `/answer`, `/compare` | One of `rag_user`, `rag_admin` |
| `/library-search` | Authenticated |
| `/ingest` | One of `rag_ingest_user`, `rag_admin` |
| `/admin/resources`, `/admin/library-tools` | One of `rag_admin`, `system_admin` |

The legacy UI only exposes Ingest to admins despite the backend permitting `rag_ingest_user`. Angular route visibility should follow the backend capability and therefore improves role fidelity without weakening security.

## Internal APIs that are not currently available through the gateway

These APIs exist but violate the required Browser -> Angular -> Gateway -> services path because the gateway does not proxy them.

| Required/desired capability | Internal endpoint | Method | Backend DTO | Blocker |
| --- | --- | --- | --- | --- |
| SSE model comparison | Answer `:8002/rag/answer/compare/stream` | POST, `text/event-stream` | `AnswerRequest`; event stream | No gateway streaming proxy. |
| Graph search | Search `:8001/rag/graph/search` | POST | `GraphSearchRequest` -> `GraphSearchResponse` | No gateway route. |
| Combined standard + graph search | Search `:8001/rag/search/combined` | POST | combined request -> `CombinedSearchResponse` | No gateway route. |
| Debug search | Search `:8001/rag/search/debug` | POST | `SearchRequest` -> `SearchResponse` | No gateway route. |
| Ingest job polling | Ingest `:8000/rag/ingest/jobs/{job_id}` | GET | `JobStatusResponse` | No gateway route. |
| Ingest job errors | Ingest `:8000/rag/ingest/jobs/{job_id}/errors` | GET | `JobErrorResponse[]` | No gateway route. |
| Graph runtime settings | Ingest `:8000/rag/settings/graph-rag` | GET/PUT | `GraphRagRuntimeSettings*` | No gateway route. |
| Admin Graph settings | Search `:8001/rag/admin/settings/graph-rag` | GET/PUT | `AdminGraphRagSettings*` | No gateway route. |

## API mismatches and constraints

1. The attached requirements mandate SSE, graph/combined/debug search, polling, and Graph RAG controls, but also mandate that the browser use the gateway and that backend APIs not be modified. All three constraints cannot be satisfied simultaneously with the current route set.
2. The gateway's `POST /rag/answer/compare` is non-streaming. Calling the internal SSE endpoint directly would bypass the gateway bearer-role boundary and require separate CORS/auth behavior.
3. Upload-time embedding provider/model controls do not exist in `IngestMetadata`; these are service-level configuration. Angular must not invent request fields.
4. There is no cancellation API for server-side model generation. Angular can abort its client stream/request, but that does not guarantee downstream model cancellation.
5. The gateway maps downstream failures to 502 with nested details. The Angular error normalizer must preserve the nested service/status information.

## Recommended resolution

## Implementation update: approved gateway security proxies

The recommended resolution was approved and implemented. The following routes now exist on the Secure API Gateway and are used by Angular; direct browser access to internal services remains prohibited.

| Angular function | Gateway endpoint | Method | Role |
| --- | --- | --- | --- |
| Graph search | `/rag/graph/search` | POST | `rag_search_user`, `rag_user`, `rag_admin` |
| Combined search | `/rag/search/combined` | POST | `rag_search_user`, `rag_user`, `rag_admin` |
| Debug search | `/rag/search/debug` | POST | `rag_search_user`, `rag_user`, `rag_admin` |
| SSE comparison | `/rag/answer/compare/stream` | POST SSE | `rag_user`, `rag_admin` |
| Job status/errors | `/rag/ingest/jobs/{id}`, `/errors` | GET | `rag_ingest_user`, `rag_admin` |
| Graph settings | `/rag/admin/settings/graph-rag` | GET/PUT | `rag_admin`, `system_admin` |

All proxies use explicit destinations, propagate tracing/user context, add the internal API key server-side, and do not forward the browser bearer token downstream.

Add narrowly scoped authenticated proxy routes to `secure_api` for the missing internal endpoints, including a true streaming pass-through for compare SSE. This preserves the required architecture and internal API-key boundary. This would be an additive gateway change, not a rewrite of downstream APIs, but it requires explicit approval because the master prompt says not to modify backend APIs.
