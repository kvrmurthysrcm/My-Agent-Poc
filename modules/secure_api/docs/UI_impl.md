# Secure API UI Implementation

## Purpose

The secure API UI is a lightweight local POC browser UI served by the wrapper service.

Open:

```text
http://localhost:8010/ui
```

The UI is implemented as a simple static HTML file:

```text
modules/secure_api/app/ui/gateway.html
```

It is served by:

```text
modules/secure_api/app/routes/ui_routes.py
```

The UI does not call Keycloak or downstream RAG services directly. It calls only `secure_api` wrapper endpoints on port `8010`.

## Valid Local Users

These users are created by the Keycloak setup scripts under:

```text
scripts/keycloak
```

| Username | Password | Main roles | UI behavior |
| --- | --- | --- | --- |
| `raguser` | `raguser123` | `rag_user`, `rag_search_user` | Can view books, search, and ask questions |
| `ragadmin` | `ragadmin123` | `rag_admin`, `rag_user`, `rag_search_user`, `rag_ingest_user`, `graph_rag_user`, `system_admin` | Can view books, search, ask, ingest, delete, retry, and queue indexing |
| `searchuser` | `searchuser123` | `rag_search_user` | Can view books and search |

`admin / admin123` is the Keycloak admin console user. It is not an application user in the `rag-auth-gateway` realm, so it will not work in the secure API UI login screen.

Use `admin / admin123` only at:

```text
http://localhost:8080/admin
```

## Login Flow

The login screen calls:

```text
POST http://localhost:8010/auth/login
```

Example body:

```json
{
  "username": "raguser",
  "password": "raguser123"
}
```

On success, the wrapper returns Keycloak tokens. The UI stores:

```text
access_token
refresh_token
```

in browser `localStorage` for this local POC session.

After login, the UI calls:

```text
GET http://localhost:8010/auth/me
```

That endpoint validates the JWT and returns user details and roles. The UI uses those roles to decide whether to show admin controls.

## Role-Based UI Behavior

Admin controls are visible only when the JWT roles include one of:

```text
rag_admin
system_admin
```

Admin-only controls:

- Ingest tab
- Delete selected books
- Retry failed books
- Create Standard embeddings or Graph indexes for uploaded books

Regular authenticated users can still:

- View books/resources
- Search books
- Ask questions

## Downstream APIs Reused

The UI reuses downstream RAG APIs, but only through secure_api wrapper endpoints. The browser never calls ports `8000`, `8001`, or `8002` directly.

### Books / Resource List

UI calls:

```text
GET http://localhost:8010/rag/resources
```

Wrapper forwards to:

```text
GET http://localhost:8001/rag/admin/resources
```

This is reused from the RAG Search Service admin resource API.

The Books tab refreshes this list automatically whenever the user clicks back into the tab. The top-bar `Refresh` button and the Books tab `Refresh Books` button use the same wrapper call for manual reloads. The UI guards concurrent reloads so rapid clicks do not send duplicate resource-list requests.

### Delete Books

UI calls:

```text
POST http://localhost:8010/rag/resources/delete
```

Wrapper forwards to:

```text
POST http://localhost:8001/rag/admin/resources/delete
```

Only `rag_admin` or `system_admin` users can call this wrapper endpoint.

### Retry Failed Books

UI calls:

```text
POST http://localhost:8010/rag/resources/{resource_id}/retry
```

Wrapper forwards to:

```text
POST http://localhost:8001/rag/admin/resources/{resource_id}/retry
```

That downstream search-admin endpoint then calls the ingest service retry endpoint.

### Queue Indexing For Existing Books

The secure API UI uses a two-step workflow for fast library loading:

1. Upload in the Ingest tab with `indexing_mode=NONE`.
2. From the Books tab, admins can click `Create Embeddings` or `Create Graph Index`.

Wrapper URL:

```text
POST http://localhost:8010/rag/resources/{resource_id}/index
```

Downstream URL:

```text
POST http://localhost:8001/rag/admin/resources/{resource_id}/index
```

The search-admin endpoint forwards to:

```text
POST http://localhost:8000/rag/ingest/resources/{resource_id}/index
```

Request body:

```json
{
  "indexing_mode": "STANDARD"
}
```

Use `GRAPH` to queue Graph RAG indexing.

Only `rag_admin` or `system_admin` users can call this wrapper endpoint.

### Search Books

UI calls:

```text
POST http://localhost:8010/rag/search
```

Wrapper forwards to:

```text
POST http://localhost:8001/rag/search
```

Allowed roles:

```text
rag_search_user
rag_user
rag_admin
```

### Ask / Answer

UI calls:

```text
POST http://localhost:8010/rag/answer
```

Wrapper forwards to:

```text
POST http://localhost:8002/rag/answer
```

Allowed roles:

```text
rag_user
rag_admin
```

The UI defaults `top_k=1` and `context_top_k=1` because local Ollama generation can be slow.

### Compare Answers

UI calls:

```text
POST http://localhost:8010/rag/answer/compare
```

Wrapper forwards to:

```text
POST http://localhost:8002/rag/answer/compare
```

Allowed roles:

```text
rag_user
rag_admin
```

The Compare tab accepts a comma-separated list of local model names. It defaults to a small context window because each local Ollama model call can be slow.

## Dark Mode

The UI has a top-bar Dark/Light toggle. The selected theme is stored in browser `localStorage` as:

```text
secure_api_theme
```

### Ingest Book

UI calls:

```text
POST http://localhost:8010/rag/ingest
```

Wrapper forwards multipart form data to:

```text
POST http://localhost:8000/rag/ingest
```

Allowed roles:

```text
rag_ingest_user
rag_admin
```

The browser sends:

```text
file
metadata
```

The wrapper sends the same multipart upload downstream and adds internal server-side headers such as:

```text
X-API-Key
X-User-Id
X-Username
X-User-Roles
```

The browser does not see or send `X-API-Key`.

## Why The UI Looks Different

The new secure API UI is not a direct copy of the downstream RAG service UIs.

Existing downstream UIs:

- `rag-search-service/app/ui/search.html`
- `rag-search-service/app/ui/admin_resources.html`
- `rag-ingest-service/app/ui/index.html`
- `rag-answer-service/app/ui/answer.html`

The new UI is a wrapper-level UI. It combines the main workflows into one screen after login:

- Books dashboard
- Search
- Answer
- Compare model answers
- Library Search
- Admin ingest
- Admin delete/retry/indexing
- Admin-only Library Tools

It intentionally calls only secure_api endpoints so authentication and role checks stay centralized.

## Current Limitations

- Token refresh is not automatic yet.
- Library Search depends on `online_library_agent`, `online_library_mcp`, `online_library`, Ollama, and the Online Library database.
- Raw Library Tools are admin-only and intended for diagnostics/debugging, not the normal user workflow.
- Resource list/delete/retry/indexing reuse downstream search admin APIs, so the downstream search service must have admin resource APIs enabled.
- The UI stores tokens in `localStorage`, which is acceptable only for this local laptop POC.
- The answer flow can be slow when local Ollama models receive large context.

## Suggested Next UI Enhancements

- Add automatic token refresh before expiry.
- Add ingest job status polling after upload.
- Add graph search and combined search tabs.
- Add richer Library Search result cards for common book/user/subscription fields.
- Add a request log panel showing wrapper calls and response times.
- Add a compact token/role inspector for debugging local auth.
