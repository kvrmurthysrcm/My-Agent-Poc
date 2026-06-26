# RAG Search and Ingestion Quality Fixes

## Symptoms

The local RAG search service returned poor results for these cases:

- `Tell me about Ramayan` returned raw chunks instead of a useful document-level overview.
- `Tell me about Bhagavad Githa` included noisy page/front-matter chunks such as publisher lines and page markers.
- `Tell me about the novel: A Christmas Carol` ranked unrelated Ramayan, Gita, and Upanishads chunks above the correct document.
- An exact quote from `A Christmas Carol` was indexed but ranked below unrelated chunks.

## Root Causes

The SQLite keyword fallback scored raw query substrings. Common words such as `the`, `a`, `and`, `of`, `in`, and `that` counted heavily in long chunks. Long unrelated chunks therefore received very large keyword scores.

Hybrid ranking then forced any keyword result with `keyword_score >= 5` to score `0.95`, so noisy keyword hits overpowered semantic matches and exact document matches.

The query preprocessor removed general conversational prefixes, but it did not remove subject prefixes such as `the novel:`. This made title matching weaker for queries like `Tell me about the novel: A Christmas Carol`.

The ingestion pipeline saved and embedded low-information chunks, including standalone publisher/footer text, roman numeral page fragments, and page-marker-heavy text. These chunks can surface in vector search because short boilerplate embeddings are noisy.

## Search Fixes

The search service now:

- tokenizes keyword queries using meaningful lexical tokens instead of raw substring counts
- removes stopwords and ignores very short tokens
- normalizes common aliases such as `Githa`, `Geetha`, and `Gita`
- normalizes `Ramayana` toward `Ramayan`
- scores exact phrase matches strongly
- promotes exact phrase matches above vector-only candidates
- scores title/resource token overlap
- requires minimum meaningful-term coverage for longer queries
- removes conversational subject prefixes such as `the novel:`
- removes the hard hybrid `keyword_score >= 5` score clamp
- applies a small explicit resource/title match boost instead of letting raw keyword score dominate
- suppresses low-value result chunks at search time, which helps with already-ingested data
- strips page markers from returned snippets and `chunk_text`; page references remain in `page_start` and `page_end`

## Ingestion Fixes

The ingestion chunking path now applies a quality gate before chunks are stored and embedded:

- strips `[Page N]` markers from chunk text while preserving page range metadata
- drops empty chunks after cleanup
- drops very short low-information chunks
- drops short boilerplate chunks such as publisher/footer lines
- drops chunks with very low alphabetic content ratio
- drops chunks dominated by common mojibake/OCR corruption markers
- rehashes and reindexes chunks after cleanup

This means chunks like `Publications Division, T.T.D, Tirupati.` are no longer saved as searchable chunks.

Previously ingested documents still contain their old stored chunks. The search-side display and quality filters reduce the visible impact, but the cleanest result set requires deleting and re-ingesting those resources so low-value chunks are never embedded.

## Remaining Design Work

Search still returns ranked chunks. For prompts like `Tell me about Ramayan`, the best user experience is a document-level answer path:

- identify the resource by title and aliases
- retrieve representative content chunks, not front matter
- generate or return a concise overview
- include citations from page metadata

That is separate from retrieval quality and should be implemented as an answer/composition layer above search.
