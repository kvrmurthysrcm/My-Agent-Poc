# Search And Answer Observability

This feature adds config-gated diagnostics for RAG retrieval and answer generation. It is intended for local, development, QA, and regression environments where developers need to understand why a query returned a particular chunk or why an answer was slow. In production, keep the feature disabled unless there is an explicit operational need, because debug payloads can include retrieval details and snippets that are not normally needed by clients.

Implementation date: 2026-06-27

## Configuration

Search service:

```text
SEARCH_OBSERVABILITY_ENABLED=false
```

Answer service:

```text
ANSWER_OBSERVABILITY_ENABLED=false
```

Recommended environment posture:

- Production: disabled by default.
- Local/dev/QA/regression: enabled when diagnosing ranking, latency, context packing, or LLM behavior.
- Temporary production incident debugging: enable only for controlled windows and review payload exposure.

## Search Observability

When `SEARCH_OBSERVABILITY_ENABLED=true`, normal `POST /rag/search` responses include an `observability` object and each result includes a `debug` object.

The service also exposes:

```text
POST /rag/search/debug
```

When the flag is disabled, `/rag/search/debug` returns `404`.

Search observability includes:

- normalized query
- original query
- query intent
- spelling normalization flag
- embedding provider/model/version/dimension
- vector candidate count and candidate scoring
- keyword candidate count and candidate scoring
- merged hybrid candidates
- filtered candidates and filter reasons
- per-result ranking reasons
- vector score, keyword score, RRF score, retrieval score, rerank score, quality reason, and final score
- timing buckets:
  - `query_embedding_ms`
  - `vector_db_retrieval_ms`
  - `keyword_db_retrieval_ms`
  - `hybrid_merge_ms`
  - `quality_filter_ms`
  - `reranking_ms`
  - `final_ranking_ms`
  - `total_ms`

## Developer UI

The search UI has a Debug checkbox. When checked, it calls `/rag/search/debug` and renders result-level debug payloads plus the full observability payload.

The answer UI renders answer observability when the backend includes it.

## Answer Observability

When `ANSWER_OBSERVABILITY_ENABLED=true`, `POST /rag/answer` includes an `observability` object in the response.

The answer service will try to call `rag-search-service` through `/rag/search/debug`. If search observability is disabled there, it falls back to normal `/rag/search`.

Answer observability includes:

- selected source ranks/chunks used for context
- answer-side timing buckets:
  - `search_request_ms`
  - `context_packing_ms`
  - `llm_provider_build_ms`
  - `llm_generation_ms`
  - `faithfulness_verification_ms`
  - `total_ms`
- nested search observability when the search service returned it

## Usage

Enable search diagnostics:

```powershell
$env:SEARCH_OBSERVABILITY_ENABLED="true"
```

Enable answer diagnostics:

```powershell
$env:ANSWER_OBSERVABILITY_ENABLED="true"
```

Example search debug request:

```powershell
curl.exe -X POST http://localhost:8001/rag/search/debug `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"what was the impression perceived by Paul Brunton when he met Ramana Maharshi?\",\"search_mode\":\"hybrid\",\"top_k\":10}"
```

Example answer request with observability enabled by config:

```powershell
curl.exe -X POST http://localhost:8002/rag/answer `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"what was the impression perceived by Paul Brunton when he met Ramana Maharshi?\",\"search_mode\":\"hybrid\",\"top_k\":10,\"context_top_k\":10,\"include_sources\":true}"
```

## Production Guidance

The better production default is to keep this feature disabled and rely on normal logs/metrics. Enable the debug payload only in lower environments or during a bounded incident investigation. If this becomes a frequent production need, the next step should be structured server-side tracing with redaction, sampling, and correlation IDs instead of returning detailed debug payloads to API clients.
