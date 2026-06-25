# Dev Delete Endpoint

This endpoint exists only for local development cleanup.

## Python Profile Equivalent

Python applications commonly use environment variables for profile-specific behavior, similar to Spring profiles.

This service uses:

```text
APP_PROFILE=local
ENABLE_DEV_DELETE_ENDPOINT=true
```

The endpoint returns `404` unless both are true:

```text
APP_PROFILE=local
ENABLE_DEV_DELETE_ENDPOINT=true
```

For shared, QA, staging, or production environments, use:

```text
APP_PROFILE=prod
ENABLE_DEV_DELETE_ENDPOINT=false
```

## Endpoint

```http
DELETE /rag/dev/resources/{resource_id}
```

Optional force delete for a resource with a currently processing job:

```http
DELETE /rag/dev/resources/{resource_id}?force=true
```

Without `force=true`, the endpoint returns `409` if any job for the resource is still `PROCESSING`.

## What It Deletes

The endpoint deletes rows related to the resource in this order:

```text
rag_chunk_embeddings
rag_processing_errors
rag_profiling_events
rag_document_chunks
rag_document_extractions
rag_ingestion_jobs
user_bookshelf, reviews, reading_progress, downloads when PostgreSQL tables exist
resource_tags
resource_authors
resources
```

It also deletes the stored source file if `resources.storage_path` still points to a file.

It does not delete shared lookup rows such as:

```text
authors
categories
tags
subscription_tiers
```

## Example

```powershell
curl.exe -X DELETE http://localhost:8000/rag/dev/resources/<resource_id>
```

Expected response:

```json
{
  "resource_id": "<resource_id>",
  "deleted": true,
  "deleted_file_path": null,
  "deleted_counts": {
    "rag_chunk_embeddings": 401,
    "rag_processing_errors": 0,
    "rag_profiling_events": 22,
    "rag_document_chunks": 401,
    "rag_document_extractions": 1,
    "rag_ingestion_jobs": 1,
    "resource_tags": 1,
    "resource_authors": 0,
    "resources": 1
  }
}
```

## Validate After Delete

```sql
SELECT COUNT(*) FROM public.resources WHERE resource_id = '<resource_id>';

SELECT COUNT(*)
FROM public.rag_document_chunks
WHERE resource_id = '<resource_id>';

SELECT COUNT(*)
FROM public.rag_chunk_embeddings e
JOIN public.rag_document_chunks c ON c.chunk_id = e.chunk_id
WHERE c.resource_id = '<resource_id>';

SELECT COUNT(*)
FROM public.rag_profiling_events
WHERE resource_id = '<resource_id>';
```

Expected:

```text
0 rows/count for deleted resource-owned data
```
