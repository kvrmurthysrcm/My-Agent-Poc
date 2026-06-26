# Oversampled Hybrid Search, RRF, and Local Reranking

## Purpose

This change tightens hybrid retrieval so relevant chunks are less likely to be missed or buried below weaker title/front-matter matches.

Previously, hybrid search retrieved only `top_k` vector candidates and `top_k` keyword candidates, then merged them with min-max normalized weighted scores. That was fragile because vector and keyword score scales are not naturally comparable, and title/resource boosts could push early chunks above direct evidence.

## Current Flow

For `search_mode=hybrid`:

1. Normalize the user query.
2. Retrieve oversampled vector candidates.
3. Retrieve oversampled keyword candidates.
4. Fuse candidates using Reciprocal Rank Fusion by default.
5. Apply local reranking to the fused candidate set.
6. Return the requested `top_k`.

With the default settings:

```text
top_k=10
HYBRID_OVERSAMPLING_FACTOR=5
```

the service retrieves:

```text
vector_k=50
keyword_k=50
return_k=10
```

## Configuration

```text
HYBRID_OVERSAMPLING_FACTOR=5
HYBRID_FUSION_STRATEGY=rrf
RRF_K=60
RERANK_ENABLED=true
RERANK_TOP_N=30
RERANK_STRATEGY=local
```

`HYBRID_FUSION_STRATEGY=weighted` keeps the older min-max weighted merge available for comparison.

## RRF Behavior

Reciprocal Rank Fusion combines result ranks instead of comparing raw vector and keyword scores directly. A chunk found by both vector and keyword retrieval gets a stronger fused signal than a chunk found by only one retriever.

## Local Reranker Behavior

The local reranker applies a stable score after retrieval. It favors:

- exact phrase matches
- query term coverage in chunk text
- direct evidence for question-style queries
- title/resource matches as a boost, not a dominant sort key

For short title lookup queries, early title chunks still receive a small boost so queries like `tell me about frankenstein` can return the document opening/title chunk.

For normal questions, content relevance dominates title/resource match. This addresses cases where a title match previously pushed front matter above the actual answer passage.

## PostgreSQL Keyword Parsing

This behavior is intended to run against PostgreSQL because keyword parsing and vector search depend on PostgreSQL full-text search and pgvector.

PostgreSQL keyword search now uses:

```sql
websearch_to_tsquery('english', :query)
```

instead of only:

```sql
plainto_tsquery('english', :query)
```

This handles natural user-entered search text and quoted/search-like syntax more naturally.

## Tests Added

The search test suite now validates:

- hybrid mode oversamples vector and keyword retrieval
- RRF rewards candidates found by both retrievers
- direct evidence can outrank title/front-matter chunks for question queries
- title lookup behavior still prefers early title chunks
- exact phrase regression behavior remains covered

Run:

```powershell
cd modules\rag-search-service
.\.venv\Scripts\python.exe -m pytest
```

Expected result after this change:

```text
22 passed
```

## Live Notes

The Ramana Maharshi impression query now keeps the relevant meeting/evidence chunk in the top retrieval set instead of burying it below early setup/front-matter results.

The exact `A Christmas Carol` quote behavior is covered by tests. A live check requires the active database to contain the exact matching chunk.
