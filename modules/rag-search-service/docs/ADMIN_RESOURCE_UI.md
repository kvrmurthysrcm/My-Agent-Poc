# Admin Resource UI

## Purpose

The admin resource UI lets a local developer inspect and clean up books/resources stored in the online library RAG tables.

It is meant for operational visibility and cleanup during local development:

- see ingested books/resources
- inspect key metadata
- verify chunk and embedding counts
- identify failed or incomplete ingestion jobs
- bulk delete selected resources from the online library

## UI Route

```text
GET /ui/admin/resources
```

Local URL:

```text
http://127.0.0.1:8001/ui/admin/resources
```

The page loads resource data from `GET /rag/admin/resources` and deletes selected rows through `POST /rag/admin/resources/delete`.

## API Routes

### List Resources

```http
GET /rag/admin/resources
```

Response:

```json
{
  "total": 1,
  "resources": [
    {
      "resource_id": "be3014f3-1c38-46de-8eee-6f3dc2b118e3",
      "title": "Frankenstein",
      "author": "Mary Shelley",
      "category": "Scifi",
      "tags": ["classic", "gothic"],
      "ingestion_status": "READY",
      "rag_enabled": true,
      "file_name": "frankenstein.pdf",
      "file_size_bytes": 1234567,
      "chunk_count": 127,
      "embedding_count": 127,
      "job_count": 1,
      "latest_job_status": "COMPLETED",
      "created_at": "2026-06-26T10:15:30",
      "metadata": {}
    }
  ]
}
```

### Delete Selected Resources

```http
POST /rag/admin/resources/delete
Content-Type: application/json
```

Request:

```json
{
  "resource_ids": [
    "be3014f3-1c38-46de-8eee-6f3dc2b118e3"
  ],
  "force": false
}
```

Response:

```json
{
  "requested": 1,
  "deleted": 1,
  "results": [
    {
      "resource_id": "be3014f3-1c38-46de-8eee-6f3dc2b118e3",
      "deleted": true,
      "deleted_file_path": "storage/resources/be3014f3-1c38-46de-8eee-6f3dc2b118e3/frankenstein.pdf",
      "deleted_counts": {
        "rag_chunk_embeddings": 127,
        "rag_processing_errors": 0,
        "rag_profiling_events": 12,
        "rag_document_chunks": 127,
        "rag_document_extractions": 1,
        "rag_ingestion_jobs": 1,
        "user_bookshelf": 0,
        "reviews": 0,
        "reading_progress": 0,
        "downloads": 0,
        "resource_tags": 2,
        "resource_authors": 1,
        "resources": 1
      },
      "error": null
    }
  ]
}
```

## Displayed Columns

The UI table shows:

- selection checkbox
- title
- resource ID
- author
- category
- tags
- ingestion status
- RAG enabled/disabled flag
- chunk count
- embedding count
- job count
- latest job status
- file name
- file size
- created timestamp

There is also a client-side filter input. It filters by title, author, category, tag, status, latest job status, and file name.

## Delete Behavior

Bulk delete is intentionally submitted through one button:

```text
Delete Selected
```

The browser asks for confirmation before sending the request.

For each selected resource, the backend deletes related rows in this order:

- `rag_chunk_embeddings`
- `rag_processing_errors`
- `rag_profiling_events`
- `rag_document_chunks`
- `rag_document_extractions`
- `rag_ingestion_jobs`
- optional online-library rows:
  - `user_bookshelf`
  - `reviews`
  - `reading_progress`
  - `downloads`
- `resource_tags`
- `resource_authors`
- `resources`
- stored resource file, if present

Each selected resource is handled independently. If one resource fails to delete, the response includes an error for that resource and continues reporting the others.

## Force Delete

The request supports:

```json
"force": true
```

Without `force`, resources with a `PROCESSING` ingestion job are not deleted.

With `force`, the backend allows deleting those resources. Use this only for local cleanup or known-abandoned jobs.

## Configuration

The admin endpoints are controlled by:

```text
SEARCH_ADMIN_ENABLED=true
```

If disabled, the admin JSON endpoints return `404 Not found`.

Recommended default:

```text
SEARCH_ADMIN_ENABLED=true
```

for local development only.

For shared, staging, or production environments:

```text
SEARCH_ADMIN_ENABLED=false
```

until authentication and authorization are added.

## Safety Notes

This feature deletes online library resources and their RAG data. It should be treated as an admin-only tool.

Current limitations:

- no authentication
- no authorization
- no audit table for delete operations
- no soft-delete mode
- no undo

Recommended next hardening steps:

- require admin authentication
- record delete audit events
- add soft-delete or archive mode
- require typed confirmation for large deletes
- hide or disable the UI unless `APP_PROFILE=local`
- expose a dry-run endpoint that returns delete counts without deleting

## Testing

Run:

```powershell
cd modules\rag-search-service
uv run --extra test pytest tests\test_admin_resources.py
```

Covered behavior:

- admin UI route loads
- resource list includes metadata and counts
- bulk delete removes selected resource, chunks, embeddings, and jobs
