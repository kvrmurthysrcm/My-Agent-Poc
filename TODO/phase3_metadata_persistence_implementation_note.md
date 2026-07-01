# Phase 3 Metadata Persistence Implementation Note

## Implemented

- Added dedicated metadata persistence service:
  - `modules/rag-ingest-service/app/services/library_metadata_persistence_service.py`
- Added first-class ingest metadata fields:
  - `genre`
  - `isbn`
  - `page_count`
- Updated resource persistence so searchable catalog data lands in columns and join tables:
  - `resources.title`
  - `resources.description`
  - `resources.publisher`
  - `resources.published_date`
  - `resources.language`
  - `resources.isbn`
  - `resources.page_count`
  - `categories`
  - `authors`
  - `tags`
  - `resource_authors`
  - `resource_tags`
- Preserved full request metadata in `resources.metadata_json`.

## Changes by Module

### `modules/rag-ingest-service`

Runtime-impacting changes:

- Added metadata service:
  - `app/services/library_metadata_persistence_service.py`
- Updated resource creation:
  - `app/repositories/resource_repository.py`
- Updated ingest request contract:
  - `app/schemas/ingest_request.py`
- Updated SQLAlchemy resource model:
  - `app/db/models.py`
- Hardened dev delete cleanup:
  - `app/services/dev_delete_service.py`

Schema/documentation changes:

- Updated base schema indexes:
  - `sql/schema.sql`

Tests:

- Added metadata persistence coverage:
  - `tests/test_rag_ingest_api.py`

Restart required:

- Restart `rag-ingest-service`.
- Restart any active DB worker process for `rag-ingest-service`, if one is running.

Reason:

- Ingest request parsing changed.
- Resource persistence logic changed.
- New metadata persistence service is imported at runtime.

### `modules/rag-search-service`

Runtime-impacting changes:

- Hardened optional library-table cleanup during admin resource delete:
  - `app/services/admin_resource_service.py`

Tests:

- Updated admin resource test fixtures to use valid PostgreSQL UUID values and explicit flush ordering:
  - `tests/test_admin_resources.py`

Restart required:

- Restart `rag-search-service`.

Reason:

- Admin delete behavior changed.
- Future catalog/admin resource views benefit from the newly persisted columns after ingest.

### `modules/online_library`

Schema/documentation changes:

- Updated schema snapshot with catalog lookup indexes:
  - `sql/schema.sql`

Restart required:

- No restart required for the current online library service because no Python runtime code changed in this module.
- If the service has long-lived connection/schema metadata caching later, restart it, but current implementation uses direct SQL per request.

Database action:

- Applied catalog indexes to the local `online_library` DB using `CREATE INDEX IF NOT EXISTS`.

### `TODO`

Documentation changes:

- Updated phase plan:
  - `TODO/product_feature_expansion_phase_plan.md`
- Added this implementation note:
  - `TODO/phase3_metadata_persistence_implementation_note.md`

Restart required:

- None.

## Restart Checklist

Restart these modules after pulling/running this phase:

- `rag-ingest-service`
- any `rag-ingest-service` DB worker/background worker
- `rag-search-service`

No restart is required for these modules for Phase 3:

- `secure_api`, unless you want the gateway to reconnect to restarted downstreams cleanly
- `online_library`
- `online_library_agent`
- `online_library_mcp`
- `rag-answer-service`

## Local DB Indexes Applied

The following indexes were applied to the local `online_library` DB:

- `ix_resources_title`
- `ix_resources_publisher`
- `ix_resources_isbn`
- `ix_resources_published_date`
- `ix_authors_author_name`
- `ix_categories_category_name`
- `ix_tags_tag_name`

## Genre Handling

For now, `genre` is an alias for `category_name`.

Rules:

- If `category_name` is supplied, it wins.
- If `category_name` is missing and `genre` is supplied, `genre` becomes the category.
- The normalized category value is stored in `metadata_json.category_name` so downstream catalog search can use a consistent key.

## Normalization

- Text fields are trimmed and internal repeated whitespace is collapsed.
- Tags are deduplicated case-insensitively.
- Empty author/tag/category values are ignored.

## Indexes

Schema snapshots now include catalog lookup indexes for:

- `resources.title`
- `resources.publisher`
- `resources.isbn`
- `resources.published_date`
- `authors.author_name`
- `categories.category_name`
- `tags.tag_name`

For existing local databases, apply equivalent `CREATE INDEX IF NOT EXISTS` statements.

## Tests

Verified:

- Full RAG ingest test suite passes.
- RAG search admin resource tests pass.
- Secure API gateway tests still pass after dependency installation.
