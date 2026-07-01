# Phase 4 Catalog Search API Implementation Note

## Implemented

Added structured Online Library catalog search endpoints:

- `GET /catalog/resources`
- `GET /catalog/resources/{resource_id}`
- `GET /catalog/facets`

This is metadata/catalog search, not RAG content search.

## Changes by Module

### `modules/online_library`

Runtime-impacting changes:

- Added catalog repository functions:
  - `repository.py`
- Added catalog API routes:
  - `api.py`

Documentation changes:

- Updated module README:
  - `Readme.md`
- Updated module API plan:
  - `docs/online_library_api_plan.md`

Tests:

- Added catalog API route tests:
  - `tests/test_catalog_api.py`

Restart required:

- Restart `online_library` API service.

Reason:

- New routes and repository functions are loaded at service startup.

### `TODO`

Documentation changes:

- Updated product phase plan:
  - `TODO/product_feature_expansion_phase_plan.md`
- Added this implementation note:
  - `TODO/phase4_catalog_search_api_implementation_note.md`

Restart required:

- None.

## Supported Filters

`GET /catalog/resources` supports:

- `q`
- `author`
- `category`
- `genre`
- `tag`
- `publisher`
- `language`
- `tier`
- `status`
- `published_from`
- `published_to`
- `limit`
- `offset`
- `sort`

`genre` is treated as an alias for category.

Supported sort values:

- `title`
- `created_desc`
- `created_asc`
- `published_desc`
- `published_asc`

## Response Shape

Catalog resource responses include joined arrays:

- `authors`
- `tags`

They exclude binary fields such as:

- `file_content`
- `preview_content`

Optional RAG-enriched columns are included when present:

- `ingestion_status`
- `rag_enabled`
- `metadata_json`
- `storage_path`

## Verified

- `modules/online_library/tests`: 4 passed
- Live local smoke test passed against the `online_library` database:
  - `GET /catalog/facets`
  - `GET /catalog/resources?limit=2`
  - `GET /catalog/resources?q=a&limit=2`

## Restart Checklist

Restart:

- `online_library` API service

No restart required yet for:

- `secure_api`
- `online_library_agent`
- `online_library_mcp`
- `rag-ingest-service`
- `rag-search-service`
- `rag-answer-service`

Phase 5 will add secure gateway routes/UI for this API, so `secure_api` will need a restart then.

