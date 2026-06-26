# RAG Ingestion Flow and DB Relations

This document explains what happens when a user uploads a document from the browser UI at `/ui`.

## 1. User Clicks Submit

The browser sends a multipart request:

```text
POST /rag/ingest
```

Request parts:

```text
file      = uploaded document binary
metadata  = JSON string from the UI form
```

Supported file types:

```text
.txt, .pdf, .docx, .epub
```

## 2. File Is Saved Temporarily

The uploaded file is first saved under a unique temporary upload folder:

```text
storage/tmp/{upload_id}/{original_filename}
```

Example:

```text
storage/tmp/8c30fb64-0b4d-4e1a-b06b-83f918ebdb1a/great-expectations.pdf
```

This avoids filename collisions when two users upload files with the same name.

During this stage, the service also calculates:

```text
file size
SHA-256 file hash
file extension
basic file metadata
```

## 3. Resource Row Is Created

The service creates a row in:

<span style="color: maroon;">resources table</span>

This row represents the uploaded document as a library resource.

Important fields:

```text
resource_id
title
description
resource_type
language
file_name
file_content_type
file_size_bytes
original_file_hash_sha256
file_extension
rag_enabled
ingestion_status
storage_path
embedding_provider
embedding_model
embedding_version
```

Initial ingestion status is usually:

```text
PROCESSING
```

or queued/indexing-related depending on the exact stage.

## 4. File Is Moved to Resource Folder

After `resource_id` exists, the file is moved from the temp folder to the resource folder:

```text
storage/resources/{resource_id}/{original_filename}
```

Example:

```text
storage/resources/2d707b6f-eaa3-496d-b3ea-04b7e5a0a652/great-expectations.pdf
```

The final file path is stored on the <span style="color: maroon;">resources table</span> row:

```text
resources.storage_path
resources.file_url
```

If setup fails before this point, the temp file is cleaned up.

## 5. Ingestion Job Row Is Created

The service creates a row in:

<span style="color: maroon;">rag_ingestion_jobs table</span>

This row tracks asynchronous processing.

Important fields:

```text
job_id
resource_id
status
async_backend
chunking_strategy
chunk_size_tokens
chunk_overlap_tokens
total_chunks
processed_chunks
embedded_chunks
failed_chunks
retry_count
max_retries
progress_message
error_message
started_at
completed_at
```

Foreign key:

<span style="color: maroon;">rag_ingestion_jobs table</span> `resource_id`

-> <span style="color: maroon;">resources table</span> `resource_id`

Initial job status:

```text
QUEUED
```

The API immediately returns:

```json
{
  "resource_id": "...",
  "job_id": "...",
  "status": "QUEUED"
}
```

## 6. Async Processing Starts

Depending on configuration:

```text
ASYNC_BACKEND=fastapi_background_tasks
```

or:

```text
ASYNC_BACKEND=db_worker
```

the job is processed asynchronously.

The worker/background task performs:

```text
1. Extract text
2. Store extraction result
3. Create chunks
4. Generate embeddings
5. Store embeddings
6. Mark job completed
7. Mark resource ready
```

## 7. Text Extraction Is Stored

After parsing the file, one row is inserted into:

<span style="color: maroon;">rag_document_extractions table</span>

Important fields:

```text
extraction_id
resource_id
job_id
parser_name
extracted_text
extracted_text_hash_sha256
page_count
char_count
token_count
metadata_json
created_at
```

Foreign keys:

<span style="color: maroon;">rag_document_extractions table</span> `resource_id`

-> <span style="color: maroon;">resources table</span> `resource_id`

<span style="color: maroon;">rag_document_extractions table</span> `job_id`

-> <span style="color: maroon;">rag_ingestion_jobs table</span> `job_id`

If extracted text is empty, the job fails here.

## 8. Chunks Are Created

The extracted text is split into chunks and inserted into:

<span style="color: maroon;">rag_document_chunks table</span>

There is one row per chunk.

Important fields:

```text
chunk_id
resource_id
job_id
chunk_index
chunk_text
chunk_hash_sha256
token_count
char_count
page_start
page_end
section_title
heading_path
chunk_type
metadata_json
created_at
```

Foreign keys:

<span style="color: maroon;">rag_document_chunks table</span> `resource_id`

-> <span style="color: maroon;">resources table</span> `resource_id`

<span style="color: maroon;">rag_document_chunks table</span> `job_id`

-> <span style="color: maroon;">rag_ingestion_jobs table</span> `job_id`

Unique constraint:

```text
UNIQUE(resource_id, chunk_hash_sha256)
```

If zero chunks are created, the job fails.

## 9. Embeddings Are Created

Each chunk is sent to the configured embedding provider.

Default local configuration:

```text
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768
```

The service validates:

```text
number of vectors == number of chunks
each vector length == EMBEDDING_DIMENSION
```

If validation fails, the job fails.

## 10. Embeddings Are Stored in pgvector

Embeddings are inserted into:

<span style="color: maroon;">rag_chunk_embeddings table</span>

There is one row per chunk embedding.

Important fields:

```text
embedding_id
chunk_id
embedding_provider
embedding_model
embedding_version
embedding_dimension
vector
created_at
```

Foreign key:

<span style="color: maroon;">rag_chunk_embeddings table</span> `chunk_id`

-> <span style="color: maroon;">rag_document_chunks table</span> `chunk_id`

Unique constraint:

```text
UNIQUE(chunk_id, embedding_provider, embedding_model, embedding_version)
```

The `vector` column is PostgreSQL `pgvector`:

```text
vector(768)
```

for the default `nomic-embed-text` model.

## 11. Profiling Rows Are Stored

Timing and diagnostic rows are stored in:

<span style="color: maroon;">rag_profiling_events table</span>

Important fields:

```text
profile_event_id
job_id
resource_id
step
status
elapsed_ms
event_index
details_json
created_at
```

Foreign keys:

<span style="color: maroon;">rag_profiling_events table</span> `job_id`

-> <span style="color: maroon;">rag_ingestion_jobs table</span> `job_id`

<span style="color: maroon;">rag_profiling_events table</span> `resource_id`

-> <span style="color: maroon;">resources table</span> `resource_id`

Examples of profiling steps:

```text
file_parse
chunking
db_store_chunks
embedding_generation
embedding_batch_1
db_store_embeddings
job_total
```

## 12. If Processing Fails

Failures are inserted into:

<span style="color: maroon;">rag_processing_errors table</span>

Important fields:

```text
error_id
job_id
resource_id
chunk_id
stage
error_type
error_message
error_details
created_at
```

Foreign keys:

<span style="color: maroon;">rag_processing_errors table</span> `job_id`

-> <span style="color: maroon;">rag_ingestion_jobs table</span> `job_id`

<span style="color: maroon;">rag_processing_errors table</span> `resource_id`

-> <span style="color: maroon;">resources table</span> `resource_id`

<span style="color: maroon;">rag_processing_errors table</span> `chunk_id`

-> <span style="color: maroon;">rag_document_chunks table</span> `chunk_id`

On failure:

```text
rag_ingestion_jobs table.status = FAILED
resources table.ingestion_status = FAILED
rag_ingestion_jobs table.error_message = failure reason
```

## 13. If Processing Succeeds

On success:

```text
rag_ingestion_jobs table.status = COMPLETED
resources table.ingestion_status = READY
rag_ingestion_jobs table.embedded_chunks = total embedded vectors
```

If configured:

```text
DELETE_ORIGINAL_FILE_AFTER_INGESTION=true
```

then the original uploaded file is deleted after successful ingestion.

## DB Relationship Summary

Primary job relationship:

<span style="color: maroon;">resources table</span>

-> <span style="color: maroon;">rag_ingestion_jobs table</span> using `rag_ingestion_jobs.resource_id`

-> <span style="color: maroon;">rag_document_extractions table</span> using `rag_document_extractions.job_id`

-> <span style="color: maroon;">rag_document_chunks table</span> using `rag_document_chunks.job_id`

-> <span style="color: maroon;">rag_chunk_embeddings table</span> using `rag_chunk_embeddings.chunk_id`

-> <span style="color: maroon;">rag_processing_errors table</span> using `rag_processing_errors.job_id`

-> <span style="color: maroon;">rag_profiling_events table</span> using `rag_profiling_events.job_id`

Resource-level links:

<span style="color: maroon;">resources table</span> `resource_id` links to:

- <span style="color: maroon;">rag_ingestion_jobs table</span> `resource_id`
- <span style="color: maroon;">rag_document_extractions table</span> `resource_id`
- <span style="color: maroon;">rag_document_chunks table</span> `resource_id`
- <span style="color: maroon;">rag_processing_errors table</span> `resource_id`
- <span style="color: maroon;">rag_profiling_events table</span> `resource_id`

Chunk-level links:

<span style="color: maroon;">rag_document_chunks table</span> `chunk_id` links to:

- <span style="color: maroon;">rag_chunk_embeddings table</span> `chunk_id`
- <span style="color: maroon;">rag_processing_errors table</span> `chunk_id`

## Useful SQL

Set IDs:

```sql
\set resource_id 'PASTE_RESOURCE_ID_HERE'
\set job_id 'PASTE_JOB_ID_HERE'
```

Check job:

```sql
SELECT
    job_id,
    resource_id,
    status,
    total_chunks,
    processed_chunks,
    embedded_chunks,
    error_message
FROM public.rag_ingestion_jobs
WHERE job_id = :'job_id';
```

Check chunks and embeddings:

```sql
SELECT COUNT(*) AS chunk_count
FROM public.rag_document_chunks
WHERE job_id = :'job_id';

SELECT
    COUNT(*) AS embedding_count,
    e.embedding_provider,
    e.embedding_model,
    e.embedding_dimension,
    vector_dims(e.vector) AS actual_vector_dimension
FROM public.rag_chunk_embeddings e
JOIN public.rag_document_chunks c ON c.chunk_id = e.chunk_id
WHERE c.job_id = :'job_id'
GROUP BY
    e.embedding_provider,
    e.embedding_model,
    e.embedding_dimension,
    vector_dims(e.vector);
```

Check errors:

```sql
SELECT
    stage,
    error_type,
    error_message,
    created_at
FROM public.rag_processing_errors
WHERE job_id = :'job_id'
ORDER BY created_at DESC;
```
