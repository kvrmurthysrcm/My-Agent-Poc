# RAG Search Module

The search module adds retrieval over documents that have completed ingestion and embedding.

## Endpoints

- `GET /ui/search`: browser search UI.
- `POST /rag/search`: retrieval-only API. It returns matching chunks and does not call an LLM.

## Search Modes

- `hybrid`: default. Runs oversampled vector and keyword search, fuses candidates with Reciprocal Rank Fusion by default, and applies a local reranker before returning `top_k`.
- `vector`: embeds the query with the configured ingestion embedding provider/model, then searches `rag_chunk_embeddings`.
- `keyword`: uses PostgreSQL full-text search over `rag_document_chunks.search_vector`. This mode does not call the embedding provider.

## Request

```json
{
  "query": "What does the document say about claim submission timelines?",
  "search_mode": "hybrid",
  "top_k": 10,
  "min_score": 0.0,
  "filters": {
    "resource_id": null,
    "category": "Claims",
    "tags": ["provider-portal"],
    "metadata": {
      "department": "Claims"
    }
  },
  "include_metadata": true,
  "include_chunk_text": true
}
```

## Response

```json
{
  "query": "What does the document say about claim submission timelines?",
  "search_mode": "hybrid",
  "top_k": 10,
  "total_results": 1,
  "embedding_provider": "ollama",
  "embedding_model": "nomic-embed-text",
  "results": [
    {
      "rank": 1,
      "resource_id": "7f78647a-7601-4a27-8c64-73cd25d6a24a",
      "chunk_id": "24fc61f9-b7ef-4ac4-bc83-7bbcedb91350",
      "title": "Provider Claims Submission Policy",
      "chunk_index": 3,
      "page_start": 4,
      "page_end": 5,
      "section_title": "Submission Timelines",
      "heading_path": ["Claims", "Submission Timelines"],
      "score": 0.91,
      "vector_score": 0.88,
      "keyword_score": 0.42,
      "snippet": "Claims should be submitted within...",
      "chunk_text": "Claims should be submitted within...",
      "metadata": {
        "resource": {},
        "chunk": {}
      }
    }
  ]
}
```

## Database

The search module reads from the ingestion tables and adds no new business tables. Migration `20260625_0001` adds:

- `rag_document_chunks.search_vector` generated `tsvector` column.
- GIN index on `rag_document_chunks.search_vector`.
- page/resource lookup index on `rag_document_chunks`.
- embedding provider/model/version/dimension lookup index on `rag_chunk_embeddings`.
- HNSW vector index on `rag_chunk_embeddings.vector`.

Search only returns resources with `resources.rag_enabled = true` and `resources.ingestion_status = 'READY'`. Vector search also requires the stored embedding provider, model, version, and dimension to match the current service configuration.

## Configuration

```text
SEARCH_DEFAULT_MODE=hybrid
SEARCH_DEFAULT_TOP_K=10
SEARCH_MAX_TOP_K=50
SEARCH_MIN_SCORE=0.0
SEARCH_VECTOR_WEIGHT=0.70
SEARCH_KEYWORD_WEIGHT=0.30
HYBRID_OVERSAMPLING_FACTOR=5
HYBRID_FUSION_STRATEGY=rrf
RRF_K=60
RERANK_ENABLED=true
RERANK_TOP_N=30
RERANK_STRATEGY=local
SEARCH_ENABLE_METADATA_FILTERS=true
SEARCH_INCLUDE_CHUNK_TEXT_DEFAULT=true
```

For `hybrid` mode, the service retrieves `top_k * HYBRID_OVERSAMPLING_FACTOR` vector candidates and the same number of keyword candidates before fusion. With `top_k=10` and the default factor `5`, it retrieves 50 vector candidates and 50 keyword candidates, then reranks down to 10.

`HYBRID_FUSION_STRATEGY=rrf` uses Reciprocal Rank Fusion, which is more stable than comparing raw vector and keyword score scales directly. `HYBRID_FUSION_STRATEGY=weighted` keeps the older min-max weighted merge available for comparison.

The local reranker favors exact phrase matches and direct content evidence. Title/resource matches are treated as a boost, not a dominant sort key, except for short title-lookup queries.

More implementation details and test coverage are documented in `OVERSAMPLED_HYBRID_RRF_RERANKING.md`.

The default embedding model remains:

```text
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768
```
