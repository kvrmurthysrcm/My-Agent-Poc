# RAG Ingestion Service

FastAPI POC for asynchronous RAG document ingestion.

## Endpoints

- `GET /` or `GET /ui`
- `GET /health`
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

For a no-PostgreSQL smoke test, set:

```text
DATABASE_URL=sqlite:///./rag_ingest.db
ASYNC_BACKEND=fastapi_background_tasks
DELETE_ORIGINAL_FILE_AFTER_INGESTION=true
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

## Embeddings

Default local model configuration keeps embeddings and NLQ text processing separate:

```text
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_DIMENSION=768

LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest

OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Use `embeddinggemma` for vector creation. Use `mistral:latest` for NLQ/text processing.

Supported local Ollama embedding options:

| Model | Dimension | Notes |
| --- | ---: | --- |
| `embeddinggemma` | 768 | Current default |
| `nomic-embed-text` | 768 | Available local embedding model |
| `mxbai-embed-large` | 1024 | Available local embedding model with larger vectors |

OpenAI remains supported by switching configuration:

```text
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=<from environment>
```

When `OPENAI_API_KEY` is not set, the OpenAI provider returns deterministic placeholder vectors so local tests can run without external calls.

## Async Backends

- `fastapi_background_tasks`: implemented
- `db_worker`: implemented as DB-queued jobs; run `python worker.py`
- `rq`: adapter class with deployment TODO hook
- `kafka`: adapter class with deployment TODO hook

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

## Tests

```powershell
cd modules\rag-ingest-service
pytest
```

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
