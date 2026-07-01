# Online Library FastAPI Module Plan

## Status

Approved and implemented as a read-only POC.

Phase 4 update: structured catalog search endpoints are now implemented.

## Module Name

Use Python-standard lowercase package naming:

```text
modules/online_library/
```

This differs from the earlier display name `Online_Library`, but avoids non-standard Python package casing.

## Goal

Create a simple read-only FastAPI module that exposes selected Online Library database tables as JSON.

This API is intended to support a later MCP and Tools layer so an agent can query library data through stable HTTP endpoints instead of connecting directly to PostgreSQL.

## Confirmed Database Connection

Connection tested successfully with:

```text
host: localhost
port: 5432
database: online_library
user: library_user
```

PostgreSQL version detected:

```text
PostgreSQL 16.13
```

The TCP port is reachable and login succeeds.

## Dependency Plan

The project already uses FastAPI.

Add PostgreSQL driver dependency:

```text
psycopg[binary]
```

Reason:

- It is the modern PostgreSQL driver for Python.
- It works cleanly with SQL queries.
- It is enough for this POC without introducing SQLAlchemy.

No ORM is planned for the first version. The implementation will use explicit SQL queries so the API behavior is easy to inspect and later convert into MCP tools.

## Proposed Folder Structure

```text
modules/online_library/
  __init__.py
  api.py
  config.py
  db.py
  repository.py
  docs/
    online_library_api_plan.md
  postman/
    Online_Library.postman_collection.json
  sql/
    schema.sql
```

## Proposed Runtime Configuration

Use environment variables, with local defaults that match the supplied DB:

```env
ONLINE_LIBRARY_DB_HOST=localhost
ONLINE_LIBRARY_DB_PORT=5432
ONLINE_LIBRARY_DB_NAME=online_library
ONLINE_LIBRARY_DB_USER=library_user
ONLINE_LIBRARY_DB_PASSWORD=library_pass
```

The password should later move to a secret manager or Kubernetes Secret.

## Initial API Scope

Read-only endpoints only.

No authentication in the first version.

Do not return binary columns from `resources`:

- `file_content`
- `preview_content`

Those fields are `bytea` and can be large. The first API should return metadata and URLs only.

## Implemented Endpoints

### Catalog Search

```text
GET /catalog/resources
```

Purpose:

- Search online library catalog metadata from structured columns and lookup tables.
- This is separate from RAG content/chunk search.
- Binary resource columns are not returned.

Supported filters:

```text
q
author
category
genre
tag
publisher
language
tier
status
published_from
published_to
limit
offset
sort
```

`genre` is treated as an alias for category.

Supported sort values:

```text
title
created_desc
created_asc
published_desc
published_asc
```

Returned resource fields include:

```text
resource_id
title
resource_type
description
category
genre
authors
tags
publisher
published_date
language
isbn
page_count
file_url
preview_file_url
cover_image_url
file_name
file_content_type
file_size_bytes
is_premium
minimum_tier_code
status
ingestion_status, when available
rag_enabled, when available
metadata_json, when available
```

```text
GET /catalog/resources/{resource_id}
```

Purpose:

- Return detail for one catalog resource.
- Include authors and tags as arrays.
- Exclude binary content.

```text
GET /catalog/facets
```

Purpose:

- Return lookup values for search UI filters:
  - categories
  - genres
  - authors
  - tags
  - languages
  - subscription tiers

### Health

```text
GET /health/db
```

Purpose:

- Verify that the API can connect to PostgreSQL.
- Return database name, current user, and a simple status.

Example response:

```json
{
  "status": "ok",
  "database": "online_library",
  "user": "library_user"
}
```

### Table SELECT APIs

The implementation now exposes `select *` style APIs only for tables that had data during schema inspection.

Non-empty tables exposed:

```text
GET /authors
GET /categories
GET /library-users
GET /reading-progress
GET /resource-authors
GET /resource-tags
GET /resources
GET /subscription-rules
GET /subscription-tiers
GET /tags
GET /user-approval-requests
GET /user-bookshelf
GET /user-subscriptions
```

Empty tables not exposed:

```text
audit_log
downloads
reviews
```

All table endpoints support:

```text
?limit=20&offset=0
```

### Earlier Resource-Oriented API Ideas

These richer endpoint ideas were deferred in the first implementation and are now partially implemented by the `/catalog/*` endpoints.

### Resources

The original resource-oriented idea is implemented as:

```text
GET /catalog/resources?q=&category=&resource_type=&status=ACTIVE&limit=20&offset=0
```

Purpose:

- Return a paginated list of library resources.
- Include category name.
- Include premium/tier metadata.
- Exclude binary content.

Recommended fields:

- `resource_id`
- `title`
- `resource_type`
- `description`
- `category_id`
- `category_name`
- `publisher`
- `published_date`
- `language`
- `isbn`
- `page_count`
- `cover_image_url`
- `file_url`
- `preview_file_url`
- `is_premium`
- `minimum_tier_code`
- `status`

```text
GET /catalog/resources/{resource_id}
```

Purpose:

- Return detail for one resource.
- Include authors and tags as arrays.
- Exclude binary content.

### Lookups

```text
GET /categories
GET /authors
GET /tags
```

Purpose:

- Return lookup data for filtering and search.
- These are simple list endpoints for the MCP/tool layer.

### Subscription Metadata

```text
GET /subscription-tiers
GET /subscription-tiers/{tier_code}/rules
```

Purpose:

- Allow the agent or UI to understand what subscription tiers exist.
- Show rule metadata such as limits or entitlements.

### User Library State

```text
GET /users/{user_id}/bookshelf
GET /users/{user_id}/reading-progress
GET /users/{user_id}/subscriptions
```

Purpose:

- Return user-specific library state.
- No auth for POC, but these endpoints should be protected later.

### Approval Requests

```text
GET /approval-requests?status=PENDING_APPROVAL
```

Purpose:

- Return user approval requests.
- Useful for admin/approval workflows.
- No auth for POC, but this should be admin-protected later.

## Query Design

Use parameterized SQL queries through `psycopg`.

Do not use string interpolation for user-provided query values.

Apply simple limits:

- Default `limit`: 20
- Maximum `limit`: 100
- Default `offset`: 0

Use explicit selected columns instead of `select *`.

## Code Commenting Requirement

The implementation will include comments explaining:

- How configuration is loaded.
- How database connections are created.
- Why binary columns are excluded.
- How query parameters are validated.
- How each repository function maps to an endpoint.

Comments will explain intent and control flow without restating obvious Python syntax.

## Implementation Completed

Implemented files:

```text
modules/online_library/__init__.py
modules/online_library/api.py
modules/online_library/config.py
modules/online_library/db.py
modules/online_library/repository.py
modules/online_library/Readme.md
```

Implemented behavior:

- Environment-based database configuration.
- PostgreSQL connection helper.
- Read-only `select *` repository function.
- JSON-safe conversion for UUID, date, datetime, decimal, and bytea values.
- Explicit FastAPI routes for non-empty tables.
- Pagination with default `limit=20`, max `limit=100`, and default `offset=0`.

## Implementation Steps After Approval

1. Add `psycopg[binary]` to `pyproject.toml`.
2. Create `modules/online_library/__init__.py`.
3. Create `config.py` for environment-based DB settings.
4. Create `db.py` for connection handling.
5. Create `repository.py` with read-only SQL query functions.
6. Create `api.py` with FastAPI endpoints.
7. Add a module `Readme.md` with setup and run commands.
8. Test DB health and representative endpoints.
9. Update the Postman collection if endpoint paths or parameters change during implementation.

## Run Command After Implementation

Expected command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

Expected base URL:

```text
http://127.0.0.1:8003
```

## Current Planning Artifacts

Schema snapshot:

```text
modules/online_library/sql/schema.sql
```

Draft Postman collection:

```text
modules/online_library/postman/Online_Library.postman_collection.json
```

## Approval Needed

Please confirm whether to proceed with this read-only FastAPI implementation.

Open choices before implementation:

- Keep all proposed endpoints or start with a smaller subset?
- Keep port `8003`?
- Return user email fields in user-specific responses, or omit emails for privacy even in the POC?
