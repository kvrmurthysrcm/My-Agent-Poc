# Embedding Input Context Plan

## Problem

Chunk embeddings were previously generated from raw `rag_document_chunks.chunk_text` only. This creates poor retrieval behavior for broad document-level queries such as:

```text
tell me about frankenstein
```

The term may appear as a page header/footer throughout a PDF, while unrelated chunks can still score higher in vector search. Search-time metadata boosting helps, but future ingestions should produce better vectors directly.

## Implemented Behavior

Ingestion now builds embedding-only input text with `app/services/embedding_input_service.py`.

Stored chunk text is not changed. The service still persists the original chunk text, chunk hash, token count, page range, and metadata for auditability and snippets.

The text sent to the embedding provider now includes:

- resource title
- author from request/file metadata
- category
- tags
- description
- section title
- heading path
- page range
- cleaned chunk body

Example embedding input shape:

```text
Title: Frankenstein
Author: Mary Shelley
Category: Scifi
Tags: classic, gothic
Description: A gothic novel.
Section: Letter 1
Heading path: Letters > Letter 1
Page: 2

Letter 1 begins here...
```

The cleanup is intentionally conservative:

- remove control characters from extracted PDFs
- remove `[Page N]` markers from embedding input
- remove repeated title/header fragments from embedding input
- collapse repeated whitespace

## Why This Lives In Ingestion

Embeddings are created once during ingestion and reused by the search service. If embeddings are built from context-poor text, search can only compensate with keyword/title boosting. Context-rich embedding input improves vector retrieval for future ingested documents without changing the search API contract.

## Search Service Interaction

The search service still needs metadata-aware ranking because:

- existing ingested documents have old vectors until re-ingested
- exact title/resource queries should be deterministic
- vector similarity alone is not reliable for broad lookup-style queries

The best behavior comes from both fixes together:

- ingestion creates context-rich vectors
- search ranks exact resource metadata matches above weak vector-only matches

## Re-ingestion Note

Existing resources keep their old embeddings. To benefit from this ingestion change, documents should be re-ingested or a future re-embedding job should regenerate `rag_chunk_embeddings` for existing chunks.

## Future Improvements

- Add a re-embedding endpoint or worker command for existing resources.
- Store `embedding_input_version` with embeddings so search can detect old vectors.
- Add optional title/header/footer detection across pages instead of only removing obvious repeated title fragments.
- Add document-level summary chunks for broad “tell me about X” queries.
- Consider separate embeddings for resource metadata and chunk body, then merge them in search.
