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
- merges truly tiny compatible fragments, such as orphan verse questions, with adjacent chunks
- classifies retained chunks with metadata flags:
  - `quality`
  - `content_type`
  - `searchable`
  - `front_matter`
  - `toc`
  - `boilerplate`
  - `numeric_table_heavy`

This prevents low-value text from being saved as searchable content and prevents embeddings from being generated for those chunks.

## Front Matter and Boilerplate Behavior

Short obvious boilerplate is skipped entirely. Examples include short publisher/copyright/footer chunks such as:

```text
Publications Division, T.T.D, Tirupati.
```

Longer front-matter text is retained when it has enough useful content, but it is excluded from normal search/answer context:

```json
{
  "quality": "front_matter",
  "content_type": "front_matter",
  "searchable": false,
  "front_matter": true,
  "toc": false,
  "boilerplate": false,
  "numeric_table_heavy": false
}
```

Table-of-contents style chunks are handled similarly with `quality: "toc"` and `searchable: false`.

The phrase lists for boilerplate, front matter, and table-of-contents detection are stored in:

```text
app/config/chunk_quality_rules.json
```

Use `CHUNK_QUALITY_RULES_PATH` to point at a different JSON file for source-specific tuning.

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
CHUNK_QUALITY_RULES_PATH=app/config/chunk_quality_rules.json
```

If `CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS=false`, numeric/table-heavy chunks can be filtered by the alpha-ratio rule.

## Operational Note

Previously ingested resources still contain their old stored chunks and embeddings. Search-side filtering reduces the visible impact, but the cleanest index requires deleting and re-ingesting affected resources so low-value chunks are never stored or embedded.

## Tests

The chunking tests cover:

- page-marker cleanup while preserving page range metadata
- filtering standalone publisher/footer chunks
- keeping short but meaningful content after page-marker cleanup
- retaining long front matter with metadata flags while marking it non-searchable
- marking HolyBooks download/front matter text as non-searchable
- keeping verse markers with their verse body
- moving trailing chapter headings into metadata for the following chunk
- keeping numeric/table-heavy chunks when enabled
- filtering numeric/table-heavy chunks when explicitly disabled
