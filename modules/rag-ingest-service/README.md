# RAG Ingestion Service

FastAPI POC for asynchronous RAG document ingestion.

## Endpoints

- `GET /` or `GET /ui`
- `GET /health`
- `GET /ready`
- `POST /rag/ingest`
- `GET /rag/ingest/jobs/{job_id}`

## Browser UI

Start the service and open:

```text
http://localhost:8000/ui
```

The same UI is also available at:

```text
http://localhost:8000/
```

The UI file is stored at `app/ui/index.html`. It supports `.txt`, `.pdf`, `.docx`, and `.epub` uploads. It builds the metadata JSON from form fields, submits the binary file to `POST /rag/ingest`, and polls `GET /rag/ingest/jobs/{job_id}` until ingestion completes or fails.

UI fields:

- binary file picker
- title, author, category, language, source system, business domain, and description
- comma-separated tags
- custom metadata JSON
- chunk size and chunk overlap
- metadata JSON preview
- resource/job status display

`POST /rag/ingest` accepts `multipart/form-data`:

- `file`: `.txt`, `.pdf`, `.docx`, or `.epub`
- `metadata`: JSON string matching `IngestMetadata`

The endpoint stores the uploaded file and metadata, creates a `resources` row and a `rag_ingestion_jobs` row, returns `resource_id` and `job_id`, then dispatches processing using `ASYNC_BACKEND`.

When available, the service reads document metadata from the uploaded file and fills missing request fields. EPUB metadata is read from the OPF package metadata, PDF metadata from the PDF document info, and DOCX metadata from core properties. Request metadata takes precedence over file metadata. If no title is supplied by either source, the filename is used.

After a successful ingestion, the original uploaded file is deleted by default. The service keeps resource metadata, SHA-256 hashes, extracted text, chunks, and embeddings. Failed jobs keep the original file for troubleshooting. To retain originals after successful ingestion, set:

```text
DELETE_ORIGINAL_FILE_AFTER_INGESTION=false
```

## Run Locally

```powershell
cd modules\rag-ingest-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

By default, this module uses the same local PostgreSQL settings as `online_library`:

```text
DATABASE_URL=postgresql://library_user:library_pass@localhost:5432/online_library
```

Apply the RAG schema to that database:

```powershell
alembic upgrade head
```

The full base schema is in `sql/schema.sql`.

For `APP_PROFILE=local`, `APP_PROFILE=dev`, or `APP_PROFILE=development`, PostgreSQL schema migrations run automatically on API startup when:

```text
AUTO_MIGRATE_ON_STARTUP=true
```

This uses Alembic `upgrade head`, not SQLAlchemy `create_all`.

Production startup does not create tables automatically. `AUTO_CREATE_TABLES=false` is the default; set it to `true` only for local throwaway environments that intentionally use SQLAlchemy `create_all`. For production profiles, run Alembic explicitly as part of deployment.

## Chunking

Default chunking is semantic-first with a token fallback:

```text
DEFAULT_CHUNKING_STRATEGY=SEMANTIC_RECURSIVE
DEFAULT_CHUNK_SIZE_TOKENS=1200
DEFAULT_CHUNK_OVERLAP_TOKENS=80
```

Supported strategies:

| Strategy | Behavior |
| --- | --- |
| `SEMANTIC_RECURSIVE` | Groups text by detected headings and paragraphs, then falls back to token windows for oversized paragraphs |
| `INTELLIGENT_RECURSIVE` | Preserves the original section-aware fixed token window behavior |

Request metadata can override the default per upload:

```json
"chunking": {
  "strategy": "SEMANTIC_RECURSIVE",
  "chunk_size_tokens": 1200,
  "chunk_overlap_tokens": 80
}
```

Chunk quality filtering marks retained chunks with `quality`, `searchable`, `front_matter`, `boilerplate`, and `numeric_table_heavy` metadata. Short boilerplate is skipped. Longer front matter is kept and marked for search-side downranking. Numeric/table-heavy chunks are kept by default:

```text
CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS=true
CHUNK_QUALITY_MIN_ALPHA_RATIO=0.45
```

Details are in `docs/CHUNK_QUALITY_FILTERS.md`.

## Embeddings

Default local model configuration keeps embeddings and NLQ text processing separate:

```text
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768
EMBEDDING_BATCH_SIZE=64
EMBEDDING_CONCURRENCY=1
EMBEDDING_MAX_RETRIES=2
EMBEDDING_RETRY_BACKOFF_SECONDS=1.0
EMBEDDING_RETRY_SHRINK_BATCH=true
EMBEDDING_MIN_BATCH_SIZE=1

LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_EMBEDDING_TIMEOUT_SECONDS=60
```

Use `nomic-embed-text` for vector creation. Use `mistral:latest` for NLQ/text processing.

`EMBEDDING_CONCURRENCY` defaults to `1`. Increase to `2` only when testing whether local Ollama can process embedding batches in parallel without slowing down.

Embedding generation retries transient provider failures by default. When `EMBEDDING_RETRY_SHRINK_BATCH=true`, a failed batch is retried in smaller pieces. For example, a failed batch of `32` is retried as `16 + 16`, down to `EMBEDDING_MIN_BATCH_SIZE`. Details are in `docs/EMBEDDING_RETRY_AND_BATCH_BACKOFF.md`.

`DUPLICATE_DOCUMENT_POLICY=version` allows repeated uploads of the same file. Set `DUPLICATE_DOCUMENT_POLICY=reject` to reject an exact duplicate by SHA-256 file hash.

Supported local Ollama embedding options:

| Model | Dimension | Notes |
| --- | ---: | --- |
| `nomic-embed-text` | 768 | Current local embedding model |
| `embeddinggemma` | 768 | Available local embedding model |
| `bge-m3` | 1024 | Available local embedding model with larger vectors |
| `mxbai-embed-large` | 1024 | Available local embedding model with larger vectors |

OpenAI remains supported by switching configuration:

```text
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
OPENAI_API_KEY=<from environment>
```

`EMBEDDING_MODEL` is validated against a registry at startup. Chat/generation models such as `mistral:latest` are valid for `LLM_MODEL`, but are rejected as `EMBEDDING_MODEL`.

Fake OpenAI embeddings are disabled by default. Tests or local-only smoke runs can opt in with:

```text
ALLOW_FAKE_EMBEDDINGS=true
```

Without that flag, OpenAI embedding configuration fails fast when `OPENAI_API_KEY` is missing.

## Async Backends

- `fastapi_background_tasks`: implemented
- `db_worker`: implemented as DB-queued jobs; run `python -m app.workers.rag_ingestion_worker`
- `rq`: adapter class with deployment TODO hook
- `kafka`: adapter class with deployment TODO hook

Run the DB worker continuously:

```powershell
cd modules\rag-ingest-service
python -m app.workers.rag_ingestion_worker
```

For a single polling batch during local development or tests:

```powershell
python -m app.workers.rag_ingestion_worker --once
```

The worker claims queued jobs in batches using `DB_WORKER_BATCH_SIZE`, sleeps between polls using `DB_WORKER_POLL_INTERVAL_SECONDS`, and uses PostgreSQL row locking when running against PostgreSQL.

TODO: Add retry/requeue support for failed ingestion jobs. The schema has retry fields for the DB worker path, but the current processing flow marks embedding failures such as Ollama `ReadTimeout` as `FAILED` without automatic retry. A future pass should add retryable failure handling and/or a manual retry endpoint such as `POST /rag/ingest/jobs/{job_id}/retry`.

Run the recovery worker to requeue stale `PROCESSING` jobs after service or worker restarts:

```powershell
python -m app.workers.rag_recovery_worker
```

For a single local recovery poll:

```powershell
python -m app.workers.rag_recovery_worker --once
```

The recovery worker uses:

```text
RECOVERY_STALE_AFTER_SECONDS=900
RECOVERY_WORKER_POLL_INTERVAL_SECONDS=30
```

By default it requeues stale jobs and processes queued jobs in the same process. Use `--no-process` to only requeue jobs.

## Example Upload

```powershell
$metadata = '{"title":"Provider Claims Submission Policy","resource_type":"DOCUMENT","category_name":"Claims","source_system":"manual_upload","tags":["claims","policy"]}'
curl.exe -X POST http://localhost:8000/rag/ingest -F "file=@sample.txt;type=text/plain" -F "metadata=$metadata"
```

For EPUB/PDF/DOCX files with embedded metadata, `title` and `author` can be omitted:

```powershell
$metadata = '{"source_system":"manual_upload","tags":["ebook"]}'
curl.exe -X POST http://localhost:8000/rag/ingest -F "file=@book.epub;type=application/epub+zip" -F "metadata=$metadata"
```

## Local Dev Delete

The local-only cleanup endpoint is enabled by:

```text
APP_PROFILE=local
ENABLE_DEV_DELETE_ENDPOINT=true
```

Delete an ingested resource and its chunks, embeddings, jobs, profiling rows, errors, and stored file:

```powershell
curl.exe -X DELETE http://localhost:8000/rag/dev/resources/<resource_id>
```

Details are in `docs/DEV_DELETE_ENDPOINT.md`.

## Tests

Tests use PostgreSQL. Create a separate test database; do not point tests at `online_library` because the test setup drops and recreates tables.

Default test URL:

```text
postgresql://library_user:library_pass@localhost:5432/online_library_test
```

Override when needed:

```powershell
$env:RAG_INGEST_TEST_DATABASE_URL="postgresql://library_user:library_pass@localhost:5432/online_library_test"
```

```powershell
cd modules\rag-ingest-service
uv run pytest
```

The current suite covers registry validation, fake embedding behavior, dimension/count mismatch failures, empty extraction failure, zero chunk failure, temp upload path uniqueness, and worker/dispatcher behavior.

## Background Progress

The UI polls:

```text
GET /rag/ingest/jobs/{job_id}
```

During processing, the response includes `message` with the current stage, such as text extraction, chunking, embedding generation, or finalization.

When running with uvicorn redirected to files, progress and request logs are written to:

```text
D:\tmp\rag_ingest_service.err.log
D:\tmp\rag_ingest_service.out.log
```

Watch logs in PowerShell:

```powershell
Get-Content -Wait -Tail 100 D:\tmp\rag_ingest_service.err.log
Get-Content -Wait -Tail 100 D:\tmp\rag_ingest_service.out.log
```

Check a job directly in PostgreSQL:

```sql
select job_id, status, total_chunks, processed_chunks, embedded_chunks, error_message, started_at, completed_at
from rag_ingestion_jobs
where job_id = '<job_id>';
```

Check persisted stage outputs:

```sql
select count(*) from rag_document_extractions where job_id = '<job_id>';
select count(*) from rag_document_chunks where job_id = '<job_id>';
select count(*)
from rag_chunk_embeddings e
join rag_document_chunks c on c.chunk_id = e.chunk_id
where c.job_id = '<job_id>';
select stage, error_type, error_message, created_at
from rag_processing_errors
where job_id = '<job_id>'
order by created_at desc;
```
