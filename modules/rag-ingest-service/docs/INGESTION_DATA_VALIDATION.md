# Ingestion Data Validation

Use this guide after a UI or API upload reaches `COMPLETED`.

## 1. Capture IDs

From the `/ui` Status panel, copy:

```text
Resource ID
Job ID
```

For the examples below:

```sql
-- Replace these values before running queries.
\set resource_id 'PASTE_RESOURCE_ID_HERE'
\set job_id 'PASTE_JOB_ID_HERE'
```

## 2. Resource Row

The uploaded document metadata is stored in `resources`.

```sql
SELECT
    resource_id,
    title,
    file_name,
    file_extension,
    file_size_bytes,
    rag_enabled,
    ingestion_status,
    parser_name,
    embedding_provider,
    embedding_model,
    embedding_version,
    original_file_hash_sha256,
    extracted_text_hash_sha256,
    storage_path,
    metadata_json
FROM public.resources
WHERE resource_id = :'resource_id';
```

Expected:

```text
ingestion_status = READY
rag_enabled = true
embedding_model = nomic-embed-text
storage_path = null when DELETE_ORIGINAL_FILE_AFTER_INGESTION=true
```

## 3. Job Row

The ingestion job status, chunking settings, progress, and error state are stored in `rag_ingestion_jobs`.

```sql
SELECT
    job_id,
    resource_id,
    status,
    progress_message,
    error_message,
    chunking_strategy,
    chunk_size_tokens,
    chunk_overlap_tokens,
    total_chunks,
    processed_chunks,
    embedded_chunks,
    failed_chunks,
    started_at,
    completed_at
FROM public.rag_ingestion_jobs
WHERE job_id = :'job_id';
```

Expected:

```text
status = COMPLETED
progress_message = Ingestion completed
error_message = null
processed_chunks = total_chunks
embedded_chunks = total_chunks
failed_chunks = 0
```

## 4. Extracted Text

Parsed source text and parser metadata are stored in `rag_document_extractions`.

```sql
SELECT
    extraction_id,
    parser_name,
    page_count,
    char_count,
    token_count,
    extracted_text_hash_sha256,
    metadata_json
FROM public.rag_document_extractions
WHERE job_id = :'job_id';
```

Expected:

```text
parser_name = pymupdf for PDF when PDF_PARSER=pymupdf
char_count > 0
token_count > 0
```

## 5. Chunks

Chunk records are stored in `rag_document_chunks`.

```sql
SELECT
    COUNT(*) AS chunk_count,
    MIN(token_count) AS min_tokens,
    MAX(token_count) AS max_tokens,
    ROUND(AVG(token_count), 2) AS avg_tokens
FROM public.rag_document_chunks
WHERE job_id = :'job_id';
```

Expected:

```text
chunk_count = rag_ingestion_jobs.total_chunks
```

Inspect sample chunks:

```sql
SELECT
    chunk_index,
    chunk_type,
    section_title,
    token_count,
    char_count,
    LEFT(chunk_text, 500) AS chunk_preview,
    metadata_json
FROM public.rag_document_chunks
WHERE job_id = :'job_id'
ORDER BY chunk_index
LIMIT 5;
```

For semantic chunking, expect `chunk_type` values such as:

```text
paragraph_group
fallback_token_window
```

## 6. Embeddings

Embeddings are stored in `rag_chunk_embeddings`.

```sql
SELECT
    COUNT(*) AS embedding_count,
    embedding_provider,
    embedding_model,
    embedding_version,
    embedding_dimension
FROM public.rag_chunk_embeddings e
JOIN public.rag_document_chunks c ON c.chunk_id = e.chunk_id
WHERE c.job_id = :'job_id'
GROUP BY
    embedding_provider,
    embedding_model,
    embedding_version,
    embedding_dimension;
```

Expected:

```text
embedding_count = rag_ingestion_jobs.embedded_chunks
embedding_provider = ollama
embedding_model = nomic-embed-text
embedding_dimension = 768
```

Inspect vector length:

```sql
SELECT
    c.chunk_index,
    e.embedding_model,
    e.embedding_dimension,
    vector_dims(e.vector) AS vector_length
FROM public.rag_chunk_embeddings e
JOIN public.rag_document_chunks c ON c.chunk_id = e.chunk_id
WHERE c.job_id = :'job_id'
ORDER BY c.chunk_index
LIMIT 5;
```

Expected:

```text
vector_length = embedding_dimension
```

## 7. Profiling Rows

Final profiling rows are persisted in `rag_profiling_events`.

```sql
SELECT
    event_index,
    step,
    status,
    elapsed_ms,
    details_json
FROM public.rag_profiling_events
WHERE job_id = :'job_id'
ORDER BY event_index;
```

Expected rows include:

```text
file_parse
chunking
chunk_diagnostics
embedding_generation
embedding_batch_1
db_store_embeddings
job_total
```

Useful summary:

```sql
SELECT
    step,
    status,
    elapsed_ms,
    details_json
FROM public.rag_profiling_events
WHERE job_id = :'job_id'
  AND step IN ('chunk_diagnostics', 'embedding_generation', 'job_total')
ORDER BY event_index;
```

## 8. Processing Errors

For completed jobs, there should be no errors.

```sql
SELECT
    stage,
    error_type,
    error_message,
    error_details,
    created_at
FROM public.rag_processing_errors
WHERE job_id = :'job_id'
ORDER BY created_at;
```

Expected:

```text
0 rows
```

## 9. File Cleanup

When cleanup is enabled:

```text
DELETE_ORIGINAL_FILE_AFTER_INGESTION=true
```

The successful job should clear these fields:

```sql
SELECT
    storage_path,
    file_url
FROM public.resources
WHERE resource_id = :'resource_id';
```

Expected:

```text
storage_path = null
file_url = null
```

If cleanup is disabled, these fields should point to the saved file under `STORAGE_ROOT`.

## 10. One-Shot Validation Query

```sql
SELECT
    r.resource_id,
    r.title,
    r.ingestion_status,
    j.status AS job_status,
    j.progress_message,
    j.total_chunks,
    j.processed_chunks,
    j.embedded_chunks,
    COUNT(DISTINCT c.chunk_id) AS chunk_rows,
    COUNT(DISTINCT e.embedding_id) AS embedding_rows,
    COUNT(DISTINCT p.profile_event_id) AS profiling_rows,
    COUNT(DISTINCT err.error_id) AS error_rows
FROM public.resources r
JOIN public.rag_ingestion_jobs j ON j.resource_id = r.resource_id
LEFT JOIN public.rag_document_chunks c ON c.job_id = j.job_id
LEFT JOIN public.rag_chunk_embeddings e ON e.chunk_id = c.chunk_id
LEFT JOIN public.rag_profiling_events p ON p.job_id = j.job_id
LEFT JOIN public.rag_processing_errors err ON err.job_id = j.job_id
WHERE r.resource_id = :'resource_id'
  AND j.job_id = :'job_id'
GROUP BY
    r.resource_id,
    r.title,
    r.ingestion_status,
    j.status,
    j.progress_message,
    j.total_chunks,
    j.processed_chunks,
    j.embedded_chunks;
```

Expected:

```text
ingestion_status = READY
job_status = COMPLETED
chunk_rows = total_chunks
embedding_rows = embedded_chunks
profiling_rows > 0
error_rows = 0
```
