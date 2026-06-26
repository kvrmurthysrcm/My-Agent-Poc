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

## Search

```text
GET /ui/search
POST /rag/search
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

```powershell
cd modules\rag-search-service
uv run --extra test pytest
```
