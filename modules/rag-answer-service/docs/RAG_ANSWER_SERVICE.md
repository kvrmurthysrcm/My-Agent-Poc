# RAG Answer Service

## Purpose

`rag-answer-service` adds an answer-composition layer above `rag-search-service`.

The search service retrieves relevant chunks. The answer service sends those chunks to a configured LLM and returns a concise, grounded response with sources.

## Architecture

```text
User question
  -> rag-answer-service /rag/answer
  -> rag-search-service /rag/search
  -> retrieved chunks with chunk_text
  -> LLM prompt with retrieved context
  -> grounded answer + sources
```

The service has no database of its own.

Context packing uses query-focused excerpts from each retrieved chunk. It also orders prompt context by question focus before original search rank. This prevents one or two long early chunks from consuming the whole prompt budget or distracting the LLM from later direct evidence.

## Providers

Supported LLM providers:

- `ollama`
- `openai`

Default local setup:

```text
LLM_PROVIDER=ollama
LLM_MODEL=mistral:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434
ANSWER_CONTEXT_TOP_K=10
ANSWER_MAX_CONTEXT_CHARS=12000
ANSWER_MAX_CHARS_PER_SOURCE=1800
```

OpenAI setup:

```text
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<your key>
```

## Grounding Rules

The prompt tells the model:

- use only the supplied context
- do not add facts from memory
- say when context is insufficient
- answer concisely

This reduces hallucination risk, but answer quality still depends on retrieval quality. If the relevant chunk is not retrieved, the LLM cannot answer correctly without guessing.

## Request Shape

```json
{
  "query": "what was the impression perceived by Paul Brenton when he met Ramana Maharshi?",
  "search_mode": "hybrid",
  "top_k": 10,
  "context_top_k": 10,
  "filters": {
    "resource_id": null,
    "category": null,
    "tags": [],
    "metadata": {}
  },
  "include_sources": true
}
```

## Response Shape

The response includes:

- `answer`
- `llm_provider`
- `llm_model`
- `search_total_results`
- `context_source_count`
- `sources`
- `raw_search` when sources are included

## Operational Notes

Run order:

1. Start ingest service if uploading documents.
2. Start search service.
3. Start answer service.

The answer service readiness check calls search service `/health` and validates the configured LLM provider.
