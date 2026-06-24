# RAG Ingestion Service

FastAPI POC for asynchronous RAG document ingestion.

## Endpoints

- `GET /health`
- `POST /rag/ingest`
- `GET /rag/ingest/jobs/{job_id}`

`POST /rag/ingest` accepts `multipart/form-data`:

- `file`: `.txt`, `.pdf`, or `.docx`
- `metadata`: JSON string matching `IngestMetadata`

The endpoint stores the uploaded file and metadata, creates a `resources` row and a `rag_ingestion_jobs` row, returns `resource_id` and `job_id`, then dispatches processing using `ASYNC_BACKEND`.

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

## Tests

```powershell
cd modules\rag-ingest-service
pytest
```
