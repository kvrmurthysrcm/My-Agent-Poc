# Chunk Quality Filters

## Problem

The ingestion pipeline saved and embedded low-information chunks extracted from PDFs and front matter, including:

- standalone publisher/footer lines
- roman numeral page fragments
- page-marker-heavy chunks
- short boilerplate text
- text dominated by OCR or encoding noise

Examples such as `Publications Division, T.T.D, Tirupati.` are not useful for retrieval, but once embedded they can still appear in vector or hybrid search.

## Fixes

Chunking now runs a quality filter before chunks are stored and embedded:

- removes `[Page N]` markers from chunk text
- preserves page ranges in `page_start` and `page_end`
- drops empty chunks after cleanup
- drops very short low-information chunks
- drops short boilerplate chunks such as publisher/footer lines
- drops chunks with very low alphabetic content ratio
- drops chunks dominated by common mojibake/OCR corruption markers
- rehashes and reindexes chunks after cleanup

This prevents low-value text from being saved as searchable content and prevents embeddings from being generated for those chunks.

## Operational Note

Previously ingested resources still contain their old stored chunks and embeddings. Search-side filtering reduces the visible impact, but the cleanest index requires deleting and re-ingesting affected resources so low-value chunks are never stored or embedded.

## Tests

The chunking tests cover:

- page-marker cleanup while preserving page range metadata
- filtering standalone publisher/footer chunks
- keeping short but meaningful content after page-marker cleanup
