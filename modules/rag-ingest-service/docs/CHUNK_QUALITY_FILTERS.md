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
- classifies retained chunks with metadata flags:
  - `quality`
  - `searchable`
  - `front_matter`
  - `boilerplate`
  - `numeric_table_heavy`

This prevents low-value text from being saved as searchable content and prevents embeddings from being generated for those chunks.

## Front Matter and Boilerplate Behavior

Short obvious boilerplate is skipped entirely. Examples include short publisher/copyright/footer chunks such as:

```text
Publications Division, T.T.D, Tirupati.
```

Longer front-matter text is retained when it has enough useful content, but it is marked:

```json
{
  "quality": "front_matter",
  "searchable": true,
  "front_matter": true,
  "boilerplate": false,
  "numeric_table_heavy": false
}
```

The search service can then downrank it instead of losing the content completely.

## Numeric and Table-Heavy Chunks

Numeric/table-heavy chunks are kept by default because enterprise documents often contain:

- invoice numbers
- claim IDs
- policy codes
- part numbers
- financial values
- form fields

This behavior is controlled by:

```text
CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS=true
CHUNK_QUALITY_MIN_ALPHA_RATIO=0.45
```

If `CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS=false`, numeric/table-heavy chunks can be filtered by the alpha-ratio rule.

## Operational Note

Previously ingested resources still contain their old stored chunks and embeddings. Search-side filtering reduces the visible impact, but the cleanest index requires deleting and re-ingesting affected resources so low-value chunks are never stored or embedded.

## Tests

The chunking tests cover:

- page-marker cleanup while preserving page range metadata
- filtering standalone publisher/footer chunks
- keeping short but meaningful content after page-marker cleanup
- retaining long front matter with metadata flags
- keeping numeric/table-heavy chunks when enabled
- filtering numeric/table-heavy chunks when explicitly disabled
