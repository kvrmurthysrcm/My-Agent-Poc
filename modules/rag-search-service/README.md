# RAG Search Service

FastAPI POC for retrieval over documents created by `rag-ingest-service`.

## Endpoints

- `GET /` or `GET /ui/search`
- `GET /health`
- `GET /ready`
- `POST /rag/search`

## Run Locally

```powershell
cd modules\rag-search-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8001
```

The service reads the same RAG ingestion tables. Use the same `DATABASE_URL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, and `EMBEDDING_VERSION` values as the ingest service so vector queries match stored embeddings.

PostgreSQL is the intended runtime database for this service:

```text
DATABASE_URL=postgresql://library_user:library_pass@localhost:5432/online_library
```

Apply schema changes through the ingest service SQL files:

```powershell
psql "postgresql://library_user:library_pass@localhost:5432/online_library" -f ..\rag-ingest-service\sql\schema.sql
```

This POC uses SQL schema files only.

PostgreSQL is required. Do not use file-based local databases when validating ingest/search behavior across services.

## Search

```text
GET /ui/search
POST /rag/search
POST /rag/graph/search
POST /rag/search/combined
```

Search modes:

| Mode | Behavior |
| --- | --- |
| `hybrid` | Oversamples vector and keyword candidates, fuses them with RRF, then reranks locally |
| `vector` | Embeds the query, then searches `rag_chunk_embeddings` |
| `keyword` | Uses `rag_document_chunks.search_vector` and does not call the embedding provider |

Example:

```powershell
curl.exe -X POST http://localhost:8001/rag/search `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"claim submission timeline\",\"search_mode\":\"hybrid\",\"top_k\":5}"
```

Details are in `docs/RAG_SEARCH_MODULE.md`.

Hybrid retrieval/ranking details are in `docs/OVERSAMPLED_HYBRID_RRF_RERANKING.md`.

Chunk quality/searchability handling is in `docs/SEARCH_CHUNK_QUALITY_HANDLING.md`.

Useful tuning settings:

```text
HYBRID_OVERSAMPLING_FACTOR=5
HYBRID_FUSION_STRATEGY=rrf
RRF_K=60
RERANK_ENABLED=true
RERANK_TOP_N=30
RERANK_STRATEGY=local
```

## Tests

Tests use PostgreSQL. Create a separate test database; do not point tests at `online_library` because the test setup drops and recreates tables.

Default test URL:

```text
postgresql://library_user:library_pass@localhost:5432/online_library_test
```

Override when needed:

```powershell
$env:RAG_SEARCH_TEST_DATABASE_URL="postgresql://library_user:library_pass@localhost:5432/online_library_test"
```

```powershell
cd modules\rag-search-service
uv run --extra test pytest
```
