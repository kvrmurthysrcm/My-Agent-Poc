# FastAPI Keycloak Auth Gateway

This module is a local POC wrapper service for authenticating users through Keycloak before calling protected APIs.

Current service URL:

```text
http://localhost:8010
```

Current Keycloak URL:

```text
http://localhost:8080
```

## Phase Status

| Phase | Scope | Status | Validation |
| --- | --- | --- | --- |
| Phase 1 | Keycloak realm, client, roles, users, token verification scripts | Done | `.\scripts\keycloak\02-keycloak-verify.ps1` |
| Phase 2 | FastAPI scaffold, config, logging, CORS, health endpoints | Done | `GET /health`, unit tests |
| Phase 3 | Keycloak-backed `/auth/login`, `/auth/refresh`, `/auth/logout` | Done | Wrapper auth curl commands below |
| Phase 4 | JWT validation, role extraction, protected `/auth/me` | Done | `GET /auth/me` with bearer token |
| Phase 5 | Protected RAG gateway routes using downstream `X-API-Key` | Done | `/rag/search`, `/rag/ingest`, `/rag/answer`, `/rag/test-downstream` |
| Phase 6 | Final hardening, full README, security review, Library Search and admin tools UI | In progress | This README covers current validation |

## Implemented Components

- Keycloak setup scripts under `scripts/keycloak`
- FastAPI app startup in `app/main.py`
- Environment-driven config in `app/config.py`
- Request logging middleware with `X-Request-ID`
- Trace propagation with W3C `traceparent` and `X-Trace-Id`; see `docs/TRACE_ID_IMPLEMENTATION.md`
- Consistent JSON error responses
- CORS for local frontend origins
- `GET /health`
- `GET /health/details`
- `GET /` and `GET /ui` lightweight browser UI
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- JWT validation with cached Keycloak JWKS
- Realm and client role extraction
- Protected `GET /auth/me`
- Protected RAG gateway routes
- Protected Library Search gateway route backed by `online_library_agent`
- Admin-only Library Tools gateway routes backed by `online_library_mcp`
- Resource list, delete, retry, and indexing gateway routes for the UI
- Multipart upload forwarding for RAG ingest
- Downstream calls using `X-API-Key`
- User context forwarding with `X-User-Id`, `X-Username`, and `X-User-Roles`
- Unit tests for health, auth, JWT validation, role extraction, `/auth/me`, and RAG gateway routing

## Local Configuration

The checked-in Keycloak scripts create and verify this realm:

```text
rag-auth-gateway
```

Create a local `.env` file from `modules/secure_api/.env.example`.

Expected important values:

```env
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=rag-auth-gateway
KEYCLOAK_CLIENT_ID=fastapi-auth-gateway
KEYCLOAK_CLIENT_SECRET=fastapi-auth-gateway-secret
TOKEN_AUDIENCE_VALIDATION_ENABLED=false
DOWNSTREAM_API_KEY=local-poc-internal-api-key
RAG_INGEST_BASE_URL=http://localhost:8000
RAG_SEARCH_BASE_URL=http://localhost:8001
RAG_ANSWER_BASE_URL=http://localhost:8002
ONLINE_LIBRARY_AGENT_BASE_URL=http://localhost:8005
ONLINE_LIBRARY_MCP_URL=http://localhost:8004/mcp
DOWNSTREAM_TIMEOUT_SECONDS=600
```

## Start Services

Start Keycloak first. The expected container name is:

```text
local-keycloak
```

Confirm the `local-keycloak` container is running before calling the Keycloak URLs.

Start the wrapper service with `modules/secure_api/run-secure-api-service.bat`, `modules/secure_api/run_local.ps1`, or `modules/secure_api/run_local.bat`.

Service dependencies by feature:

| Feature | Required services/modules | Batch file |
| --- | --- | --- |
| Login/auth and `/auth/me` | Keycloak | `scripts/keycloak` setup scripts; Keycloak container `local-keycloak` |
| Books dashboard, search, answer, ingest | `rag-ingest-service`, `rag-search-service`, `rag-answer-service` | `modules/rag-ingest-service/run-ingest-service.bat`, `modules/rag-search-service/run-search-service.bat`, `modules/rag-answer-service/run-answer-service.bat` |
| Library Search UI | `online_library` API, `online_library_mcp` tools service, `online_library_agent` NLQ service, Ollama | `modules/online_library/run-library-api-service.bat`, `modules/online_library_mcp/run-library-tools-service.bat`, `modules/online_library_agent/run-library-agent-service.bat` |
| Admin Library Tools UI | `online_library` API and `online_library_mcp` tools service | `modules/online_library/run-library-api-service.bat`, `modules/online_library_mcp/run-library-tools-service.bat` |
| Secure browser UI and wrapper API | `secure_api` | `modules/secure_api/run-secure-api-service.bat` |

Open the browser UI:

```text
http://localhost:8010/ui
```

The UI starts with a login screen, stores the access token in browser local storage for the local POC session, and shows:

- Books/resources with ingestion status
- Search
- Answer generation
- Compare model answers
- Library Search for natural-language Online Library questions
- Admin-only ingest
- Admin-only delete, retry, and indexing actions
- Admin-only Library Tools, backed by the Online Library MCP tools service

Admin actions are shown only when the signed-in user has `rag_admin` or `system_admin`.

## Postman Collection

The wrapper Postman collection is available at:

```text
modules/secure_api/postman/Secure_API_Gateway.postman_collection.json
```

Run `POST /auth/login - raguser` or `POST /auth/login - ragadmin` first. The collection test script saves `access_token` and `refresh_token`; protected wrapper requests use `Authorization: Bearer {{access_token}}`.

## Validate Phase 1: Keycloak Directly

Run `scripts/keycloak/02-keycloak-verify.ps1` from the repository root, or use the curl checks below.

Expected result:

```text
Checking discovery document...
  OK: http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
Checking JWKS document...
  OK: http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs

Requesting user tokens...
  OK: raguser received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: ragadmin received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: searchuser received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
```

Check the discovery URL manually:

```bash
curl -s http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
```

Expected response includes:

```json
{
  "issuer": "http://localhost:8080/realms/rag-auth-gateway",
  "token_endpoint": "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token",
  "jwks_uri": "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs"
}
```

Check JWKS manually:

```bash
curl -s http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs
```

Expected response includes a non-empty `keys` array.

Generate a token directly from Keycloak:

```bash
curl -s -X POST "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=fastapi-auth-gateway" \
  -d "client_secret=fastapi-auth-gateway-secret" \
  -d "username=raguser" \
  -d "password=raguser123" \
  -d "scope=openid profile email"
```

Expected response shape:

```json
{
  "access_token": "<jwt>",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "refresh_token": "<jwt-or-token>",
  "token_type": "Bearer",
  "scope": "profile email"
}
```

Other test users:

| Username | Password | Expected roles |
| --- | --- | --- |
| `raguser` | `raguser123` | `rag_user`, `rag_search_user` |
| `ragadmin` | `ragadmin123` | `rag_admin`, `rag_user`, `rag_search_user`, `rag_ingest_user`, `graph_rag_user`, `system_admin` |
| `searchuser` | `searchuser123` | `rag_search_user` |

## Validate Phase 2: Wrapper Health

Health:

```bash
curl -s http://localhost:8010/health
```

Expected response:

```json
{
  "status": "UP"
}
```

Detailed health:

```bash
curl -s http://localhost:8010/health/details
```

Expected response shape:

```json
{
  "status": "UP",
  "service": "secure-api-gateway",
  "version": "0.1.0",
  "environment": "local",
  "timestamp_utc": "2026-06-30T..."
}
```

The detailed health response must not expose `client_secret`, `api_key`, access tokens, or refresh tokens.

## Validate Phase 3: Wrapper Auth Endpoints

Login through the wrapper:

```bash
curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}'
```

Expected response shape:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh-token>",
  "token_type": "Bearer",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "scope": "profile email"
}
```

Invalid login:

```bash
curl -s -i -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"wrong"}'
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Invalid username or password.",
    "request_id": "<request-id>"
  }
}
```

Refresh through the wrapper. Replace `<refresh-token>` with the value returned by `/auth/login`:

```bash
curl -s -X POST "http://localhost:8010/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

Expected response shape:

```json
{
  "access_token": "<new-jwt>",
  "refresh_token": "<new-refresh-token>",
  "token_type": "Bearer"
}
```

Logout through the wrapper. Replace `<refresh-token>` with a valid refresh token:

```bash
curl -s -X POST "http://localhost:8010/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

Expected response:

```json
{
  "status": "LOGGED_OUT"
}
```

## Validate Phase 4: Protected /auth/me

`/auth/me` requires an access token issued by Keycloak. You can get the token from the wrapper login endpoint.

Expected response:

```json
{
  "sub": "<keycloak-user-id>",
  "preferred_username": "raguser",
  "email": "raguser@example.local",
  "name": "RAG User",
  "roles": [
    "default-roles-rag-auth-gateway",
    "offline_access",
    "rag_search_user",
    "rag_user",
    "uma_authorization"
  ],
  "issuer": "http://localhost:8080/realms/rag-auth-gateway"
}
```

The exact role list can include Keycloak default realm roles in addition to the application roles.

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s "http://localhost:8010/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

Missing bearer token:

```bash
curl -s -i "http://localhost:8010/auth/me"
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "missing_bearer_token",
    "message": "Missing bearer token.",
    "request_id": "<request-id>"
  }
}
```

Invalid bearer token:

```bash
curl -s -i "http://localhost:8010/auth/me" \
  -H "Authorization: Bearer invalid-token"
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "invalid_bearer_token",
    "message": "Invalid or expired bearer token.",
    "request_id": "<request-id>"
  }
}
```

## Validate Phase 5: RAG Gateway Routes

The wrapper validates the Keycloak bearer token, checks roles, and then calls downstream RAG services with internal API key headers. It does not forward the incoming `Authorization` header or JWT to downstream services.

Downstream target URLs:

| Wrapper route | Required role | Downstream URL |
| --- | --- | --- |
| `POST /rag/ingest` | `rag_ingest_user` or `rag_admin` | `http://localhost:8000/rag/ingest` |
| `POST /rag/search` | `rag_search_user`, `rag_user`, or `rag_admin` | `http://localhost:8001/rag/search` |
| `POST /rag/answer` | `rag_user` or `rag_admin` | `http://localhost:8002/rag/answer` |
| `POST /rag/answer/compare` | `rag_user` or `rag_admin` | `http://localhost:8002/rag/answer/compare` |
| `POST /rag/ask` | `rag_user` or `rag_admin` | Compatibility alias to `http://localhost:8002/rag/answer` |
| `GET /rag/test-downstream` | any valid token | `/health` on each downstream service |
| `GET /rag/resources` | any valid token | `http://localhost:8001/rag/admin/resources` |
| `POST /rag/resources/delete` | `rag_admin` or `system_admin` | `http://localhost:8001/rag/admin/resources/delete` |
| `POST /rag/resources/{resource_id}/retry` | `rag_admin` or `system_admin` | `http://localhost:8001/rag/admin/resources/{resource_id}/retry` |
| `POST /rag/resources/{resource_id}/index` | `rag_admin` or `system_admin` | `http://localhost:8001/rag/admin/resources/{resource_id}/index` |

Headers sent downstream:

```text
X-API-Key: local-poc-internal-api-key
X-User-Id: <keycloak-user-id>
X-Username: <preferred_username>
X-User-Roles: <comma-separated-roles>
```

Headers intentionally not sent downstream:

```text
Authorization
```

Create tokens for validation with the login curl commands in each section below.

### RAG Search

Wrapper URL:

```text
POST http://localhost:8010/rag/search
```

Downstream URL:

```text
POST http://localhost:8001/rag/search
```

Request body fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `query` | string | yes | 1-4000 chars, trimmed, must not be blank |
| `search_mode` | string | no | `vector`, `keyword`, or `hybrid` |
| `top_k` | integer | no | Minimum `1`; service default applies when omitted |
| `min_score` | number | no | `0` to `1` |
| `filters.resource_id` | string | no | Restrict search to one resource |
| `filters.category` | string | no | Category filter |
| `filters.tags` | string array | no | Blank tags are ignored |
| `filters.metadata` | object | no | Metadata filters |
| `include_metadata` | boolean | no | Defaults to `true` |
| `include_chunk_text` | boolean | no | Include full chunk text when supported |

Validate with `raguser`:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s -X POST "http://localhost:8010/rag/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"what is graph rag?","search_mode":"hybrid","top_k":5,"filters":{"tags":["architecture"]},"include_metadata":true}'
```

Expected behavior:

- If the RAG search service is running on port `8001`, the wrapper returns the downstream response.
- If the RAG search service is not running, the wrapper returns `502 Bad Gateway`.

Expected response fields include:

```json
{
  "query": "what is graph rag?",
  "search_mode": "hybrid",
  "top_k": 5,
  "total_results": 0,
  "embedding_provider": "...",
  "embedding_model": "...",
  "results": []
}
```

Related downstream search URLs currently not proxied by the wrapper:

| Downstream URL | Method | Request body | Purpose |
| --- | --- | --- | --- |
| `http://localhost:8001/rag/graph/search` | POST | `{"query":"...","resource_ids":[],"top_k":10,"include_entities":true,"include_relationships":true,"include_summaries":true}` | Graph RAG entity, relationship, summary, and related chunk search |
| `http://localhost:8001/rag/search/combined` | POST | Same shape as `/rag/search` | Standard search plus graph search in one response |
| `http://localhost:8001/rag/search/debug` | POST | Same shape as `/rag/search` | Debug/observability search; only available when enabled |
| `http://localhost:8001/rag/admin/resources` | GET | none | List resources; only available when search admin is enabled |
| `http://localhost:8001/rag/admin/resources/delete` | POST | `{"resource_ids":["..."],"force":false}` | Delete resources; only available when search admin is enabled |
| `http://localhost:8001/rag/admin/resources/{resource_id}/retry` | POST | none | Retry a resource by calling ingest retry; only available when search admin is enabled |
| `http://localhost:8001/rag/admin/resources/{resource_id}/index` | POST | `{"indexing_mode":"STANDARD"}` or `{"indexing_mode":"GRAPH"}` | Queue indexing for an existing uploaded/chunked resource |
| `http://localhost:8001/rag/admin/settings/graph-rag` | GET/PUT | `{"entity_batch_size":10,"relationship_batch_size":10}` for PUT | Read or update Graph RAG runtime settings via search admin |

### RAG Ingest

Wrapper URL:

```text
POST http://localhost:8010/rag/ingest
```

Downstream URL:

```text
POST http://localhost:8000/rag/ingest
```

This route is multipart form data, not JSON.

Form fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | Upload file; downstream validates extension and size |
| `metadata` | string | yes | JSON string parsed into ingest metadata |

Metadata JSON fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | no | 1-500 chars |
| `description` | string | no | Free text |
| `resource_type` | string | no | Defaults to `DOCUMENT` |
| `category_name` | string | no | Category label |
| `business_domain` | string | no | Domain label |
| `source_system` | string | no | Defaults to `manual_upload` |
| `author` | string | no | Author name |
| `language` | string | no | Language code/name |
| `publisher` | string | no | Publisher |
| `published_date` | datetime | no | ISO datetime |
| `tags` | string array | no | Defaults to `[]` |
| `custom_metadata` | object | no | Defaults to `{}` |
| `chunking.strategy` | string | no | `INTELLIGENT_RECURSIVE` or `SEMANTIC_RECURSIVE` |
| `chunking.chunk_size_tokens` | integer | no | Minimum `100` |
| `chunking.chunk_overlap_tokens` | integer | no | Minimum `0` |
| `indexing_mode` | string | no | `NONE`, `STANDARD`, `GRAPH`, or `BOTH`; defaults to `STANDARD` downstream. The secure_api UI defaults to `NONE` for fast upload-only ingestion. |

Validate with `ragadmin`:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"ragadmin","password":"ragadmin123"}' | jq -r .access_token)

curl -s -X POST "http://localhost:8010/rag/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@README.md;type=text/markdown' \
  -F 'metadata={"title":"Demo README","resource_type":"DOCUMENT","tags":["demo"],"indexing_mode":"NONE"}'
```

Expected response:

```json
{
  "resource_id": "<resource-id>",
  "job_id": "<job-id>",
  "status": "QUEUED",
  "message": "Document accepted. Ingestion will continue asynchronously."
}
```

Related downstream ingest URLs currently not proxied by the wrapper:

| Downstream URL | Method | Purpose |
| --- | --- | --- |
| `http://localhost:8000/rag/ingest/jobs/{job_id}` | GET | Check ingestion job status |
| `http://localhost:8000/rag/ingest/jobs/{job_id}/errors` | GET | List processing errors |
| `http://localhost:8000/rag/ingest/resources/{resource_id}/retry` | POST | Retry failed resource ingestion |
| `http://localhost:8000/rag/ingest/resources/{resource_id}/index` | POST | Queue `STANDARD`, `GRAPH`, or `BOTH` indexing for an existing resource that already has chunks |
| `http://localhost:8000/rag/settings/graph-rag` | GET/PUT | Read or update Graph RAG runtime settings |

### Two-Step Upload And Index

For fast library loading, upload with `indexing_mode=NONE`. The ingest service parses and chunks the file, marks the resource `READY`, and skips embeddings and Graph RAG. Admins can later use the Books tab buttons:

- `Create Embeddings` queues `STANDARD` indexing for existing chunks.
- `Create Graph Index` queues `GRAPH` indexing for existing chunks.

The buttons call:

```bash
curl -s -X POST "http://localhost:8010/rag/resources/<resource-id>/index" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"indexing_mode":"STANDARD"}'
```

Use `{"indexing_mode":"GRAPH"}` for Graph RAG indexing.

### RAG Answer

Wrapper URL:

```text
POST http://localhost:8010/rag/answer
```

Compatibility wrapper URL:

```text
POST http://localhost:8010/rag/ask
```

Downstream URL:

```text
POST http://localhost:8002/rag/answer
```

Request body fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `query` | string | yes | 1-4000 chars, trimmed, must not be blank |
| `search_mode` | string | no | `vector`, `keyword`, or `hybrid`; defaults to `hybrid` |
| `top_k` | integer | no | `1` to `50` |
| `context_top_k` | integer | no | `1` to `20` |
| `filters.resource_id` | string | no | Restrict context to one resource |
| `filters.category` | string | no | Category filter |
| `filters.tags` | string array | no | Tag filter |
| `filters.metadata` | object | no | Metadata filters |
| `include_sources` | boolean | no | Include source list when supported |
| `answer_mode` | string | no | `concise`, `detailed`, or `quote-backed`; defaults to `concise` |
| `include_raw_prompt` | boolean | no | Defaults to `false` |
| `system_instruction` | string | no | Max 2000 chars |
| `compare_models` | string array | no | Used by compare endpoints, max 8 models |

Validate `/rag/answer` with `raguser`:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s -X POST "http://localhost:8010/rag/ask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"summarize the uploaded material","search_mode":"hybrid","answer_mode":"concise","include_sources":true}'
```

Preferred curl for the real wrapper route:

```bash
curl -s -X POST "http://localhost:8010/rag/answer" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"summarize the uploaded material","search_mode":"hybrid","answer_mode":"concise","include_sources":true}'
```

Expected response fields include:

```json
{
  "query": "summarize the uploaded material",
  "answer": "...",
  "answer_status": "answered",
  "answer_mode": "concise",
  "llm_provider": "...",
  "llm_model": "...",
  "search_mode": "hybrid",
  "search_total_results": 0,
  "context_source_count": 0,
  "sources": []
}
```

Related downstream answer URLs currently not proxied by the wrapper:

| Downstream URL | Method | Purpose |
| --- | --- | --- |
| `http://localhost:8002/rag/answer/compare` | POST | Compare answers across configured models |
| `http://localhost:8002/rag/answer/compare/stream` | POST | Stream comparison events as SSE |

Validate downstream health fan-out:

```bash
curl -s "http://localhost:8010/rag/test-downstream" \
  -H "Authorization: Bearer $TOKEN"
```

Expected response shape:

```json
{
  "status": "OK",
  "services": [
    {
      "service": "rag-ingest",
      "status": "available",
      "status_code": 200,
      "url": "http://localhost:8000/health",
      "response": {
        "status": "UP"
      }
    },
    {
      "service": "rag-search",
      "status": "unavailable",
      "url": "http://localhost:8001/health"
    },
    {
      "service": "rag-answer",
      "status": "available",
      "status_code": 200,
      "url": "http://localhost:8002/health",
      "response": {
        "status": "UP"
      }
    }
  ]
}
```

The endpoint returns a per-service status and does not fail the entire response when one downstream service is unavailable.

## Validate Library Search And Admin Tools

The user-facing UI label is **Library Search** because users ask natural-language questions. It calls `online_library_agent`, which chooses and invokes MCP tools internally.

The admin/debug UI label is **Library Tools**. It exposes raw MCP tool discovery and tool invocation only for users with `rag_admin` or `system_admin`.

Natural-language flow:

```text
secure_api /library-search/ask
  -> online_library_agent http://localhost:8005/ask
  -> online_library_mcp http://localhost:8004/mcp
  -> online_library API http://localhost:8003
```

Admin tools flow:

```text
secure_api /library-tools/*
  -> online_library_mcp http://localhost:8004/mcp
  -> online_library API http://localhost:8003
```

Headers sent by secure_api to the Library Search agent and MCP tools service:

```text
X-API-Key: local-poc-internal-api-key
```

The current agent/tools services do not validate the API key, but the wrapper sends it so the integration contract is already in place.

Start the required services:

```bash
modules/online_library/run-library-api-service.bat
modules/online_library_mcp/run-library-tools-service.bat
modules/online_library_agent/run-library-agent-service.bat
modules/secure_api/run-secure-api-service.bat
```

Direct Online Library API check:

```bash
curl -s "http://localhost:8003/tables"
```

Expected response includes `count` and `tables`.

Direct Library Search agent check:

```bash
curl -s -X POST "http://localhost:8005/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Show me books written by Kelly","limit":5,"offset":0,"include_raw":true}'
```

Expected response includes `question`, `selected_tool`, `answer`, `debug`, and `raw_tool_result`.

Validate Library Search through secure_api as a normal user:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s -X POST "http://localhost:8010/library-search/ask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"Show me books written by Kelly","limit":5,"offset":0,"include_raw":true}'
```

Expected response is the NLQ agent answer. If `online_library_agent`, `online_library_mcp`, `online_library`, Ollama, or the database is unavailable, secure_api returns `502 Bad Gateway` with `library_search_request_failed`.

Direct MCP tools service check:

```bash
curl -s -X POST "http://localhost:8004/mcp" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-poc-internal-api-key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected response includes `result.tools` with tools such as:

```text
list_available_tables
get_resources
get_library_users
get_user_bookshelf
```

Validate admin-only Library Tools through secure_api:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"ragadmin","password":"ragadmin123"}' | jq -r .access_token)

curl -s "http://localhost:8010/library-tools/tools" \
  -H "Authorization: Bearer $TOKEN"
```

Call a library data tool through secure_api:

```bash
curl -s -X POST "http://localhost:8010/library-tools/call" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"get_resources","arguments":{"limit":5,"offset":0}}'
```

Expected response is the Online Library API payload for the selected table. If `online_library` or `online_library_mcp` is not running, secure_api returns `502 Bad Gateway` with `library_tools_request_failed`.

Normal users cannot access raw Library Tools:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s -i "http://localhost:8010/library-tools/tools" \
  -H "Authorization: Bearer $TOKEN"
```

Expected status:

```text
403 Forbidden
```

Validate role rejection. `searchuser` has `rag_search_user`, so search is allowed but ingest is rejected:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"searchuser","password":"searchuser123"}' | jq -r .access_token)

curl -s -i -X POST "http://localhost:8010/rag/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@README.md;type=text/markdown' \
  -F 'metadata={"title":"Demo README"}'
```

Expected status:

```text
403 Forbidden
```

Expected response shape:

```json
{
  "error": {
    "code": "insufficient_role",
    "message": "Insufficient role.",
    "request_id": "<request-id>"
  }
}
```

Expected downstream failure response when a downstream service is unavailable:

```json
{
  "error": {
    "code": "downstream_request_failed",
    "message": "Downstream service request failed.",
    "request_id": "<request-id>",
    "details": {
      "service": "rag-search",
      "error_type": "http_status_error",
      "status_code": 500
    }
  }
}
```

If `error_type` is `timeout`, the downstream service accepted the connection but did not finish before `DOWNSTREAM_TIMEOUT_SECONDS`. Local Ollama answer generation can take several minutes when answer context is large, so this wrapper uses `600` seconds by default for local POC validation.

## Run Automated Tests

From the repository root, run the secure API test suite with the repo virtualenv.

Expected result:

```text
36 passed
```

If you run `pytest` with the global Python installation, dependency imports may fail. Use the repo virtualenv or install `modules/secure_api/requirements.txt`.

## Troubleshooting

If `/auth/login` returns `401` for valid credentials, check that the wrapper is using:

```text
KEYCLOAK_REALM=rag-auth-gateway
```

If Keycloak token generation fails with `invalid_client`, confirm:

```text
KEYCLOAK_CLIENT_ID=fastapi-auth-gateway
KEYCLOAK_CLIENT_SECRET=fastapi-auth-gateway-secret
```

If discovery or JWKS returns `404`, rerun `scripts/keycloak/01-keycloak-setup.ps1`.

If the wrapper service does not start, check port `8010` and run `modules/secure_api/run_local.ps1`.
