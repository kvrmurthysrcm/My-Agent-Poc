# Chunking Strategies

The ingest service supports two chunking strategies:

- `SEMANTIC_RECURSIVE`
- `INTELLIGENT_RECURSIVE`

`SEMANTIC_RECURSIVE` is the default and recommended strategy for most document ingestion, including Graph RAG. `INTELLIGENT_RECURSIVE` is still available from the upload UI and API, but it is the older section-aware fixed token-window behavior.

## Configuration

Default strategy:

```text
DEFAULT_CHUNKING_STRATEGY=SEMANTIC_RECURSIVE
```

Per-upload metadata can override it:

```json
{
  "chunking": {
    "strategy": "SEMANTIC_RECURSIVE",
    "chunk_size_tokens": 1200,
    "chunk_overlap_tokens": 80
  }
}
```

Supported strategy values:

```text
SEMANTIC_RECURSIVE
INTELLIGENT_RECURSIVE
```

## Shared Pipeline

Both strategies follow the same high-level pipeline:

1. Extract text from the file.
2. For PDFs, run configurable text cleanup before chunking.
3. Split text into candidate chunks using the selected strategy.
4. Remove duplicate chunks by SHA-256 hash.
5. Infer page range from `[Page N]` markers when present.
6. Run shared chunk quality cleanup and filtering.
7. Save retained chunks to `rag_document_chunks`.

Saved chunk rows include:

```text
chunk_index
chunk_text
token_count
char_count
chunk_hash_sha256
page_start
page_end
section_title
heading_path
chunk_type
metadata_json
```

## SEMANTIC_RECURSIVE

`SEMANTIC_RECURSIVE` tries to preserve paragraph boundaries before falling back to token windows.

Behavior:

1. Split the document into sections using simple heading detection.
2. Split each section into paragraphs.
3. Add whole paragraphs to the current chunk until the configured token limit would be exceeded.
4. When the current chunk is full, flush it as a `paragraph_group`.
5. Add overlap by carrying the last `chunk_overlap_tokens` words into the next chunk.
6. If a single paragraph is larger than `chunk_size_tokens`, split that paragraph with token windows and mark those chunks as `fallback_token_window`.

Chunk metadata examples:

```json
{
  "strategy": "SEMANTIC_RECURSIVE",
  "split_basis": "paragraph_group",
  "quality": "searchable",
  "searchable": true
}
```

or:

```json
{
  "strategy": "SEMANTIC_RECURSIVE",
  "split_basis": "fallback_token_window",
  "quality": "searchable",
  "searchable": true
}
```

Use this strategy when:

- prose structure matters
- Graph RAG extraction quality matters
- paragraph-level context should stay intact
- you want fewer mid-sentence or mid-paragraph splits

Tradeoffs:

- chunk sizes may vary more than fixed token windows
- extracted PDF artifacts inside paragraphs may still remain unless cleaned earlier
- very large paragraphs still fall back to token windows

## INTELLIGENT_RECURSIVE

`INTELLIGENT_RECURSIVE` is the original section-aware fixed token-window strategy.

Behavior:

1. Split the document into sections using simple heading detection.
2. For each section, split text into word windows of `chunk_size_tokens`.
3. Move forward by `chunk_size_tokens - chunk_overlap_tokens`.
4. Save each retained chunk as `token_window`.

Chunk metadata example:

```json
{
  "strategy": "INTELLIGENT_RECURSIVE",
  "quality": "searchable",
  "searchable": true
}
```

Use this strategy when:

- predictable token-window sizing matters more than paragraph preservation
- you want behavior closer to the original ingestion implementation
- the source text has weak paragraph structure

Tradeoffs:

- can split in the middle of paragraphs
- less ideal for Graph RAG entity/relationship extraction
- may produce less natural context boundaries

## Heading Detection

Both strategies use the same section splitter.

A line is treated as a heading when it is non-empty and one of these is true:

- line length is `120` characters or less and the line is uppercase
- line starts with `#`
- line ends with `:` and looks like a compact label, not a prose sentence

For colon headings, the splitter intentionally accepts only short labels. Examples that are accepted:

```text
CLAIMS:
Introduction:
Stave 1:
```

Examples that are rejected and kept as body text:

```text
Scrooge cried in great excitement:
most preposterous clock. Its rapid little pulse beat twelve:
```

This avoids creating misleading `section_title` values from ordinary story prose.

Single-letter headings are disabled by default:

```text
CHUNK_HEADING_ALLOW_SINGLE_LETTER=false
```

This prevents PDF drop caps from becoming section headings. For example, some PDFs extract the opening word `Marley` as:

```text
M

arley was dead: to begin with.
```

Without this guard, `M` becomes `section_title`, and the actual chunk starts with `arley`.

Detected headings populate:

```text
section_title
heading_path
```

This is intentionally simple and deterministic. It is not a full document-layout parser.

## PDF Text Cleanup

PDF extraction often preserves visual layout artifacts that are bad inputs for embeddings and Graph RAG. Before chunking, the ingest service can clean common PDF issues:

```text
PDF_REPAIR_DROP_CAPS=true
PDF_REMOVE_REPEATED_HEADERS_FOOTERS=true
PDF_DEHYPHENATE_LINE_BREAKS=true
PDF_REMOVE_PRIVATE_USE_GLYPHS=true
PDF_NORMALIZE_UNICODE=true
PDF_REMOVE_BOILERPLATE_LINES=true
PDF_REMOVE_PAGE_NUMBER_LINES=true
PDF_REPAIR_JOINED_WORDS=true
```

The main use case is classic/public-domain PDFs where each page includes repeated headers, footers, page-number glyphs, and decorative first letters. For example:

```text
Sons and Lovers
Free eBooks at Planet eBook.com
M

arley was dead: to begin with. There is no doubt what-
ever about that. It was a mer-
ry Christmas.
10
The idea returned andpresented the same problem.
```

The cleanup pass should produce chunkable text closer to:

```text
Marley was dead: to begin with. There is no doubt whatever about that. It was a merry Christmas.
The idea returned and presented the same problem.
```

These flags default to `true` because noisy PDF artifacts directly reduce entity extraction quality and can create incorrect graph nodes such as `Arley`.

## Quality Cleanup And Filtering

After strategy chunking, `filter_quality_chunks` runs for both strategies.

It does the following:

- removes `[Page N]` markers from saved `chunk_text`
- normalizes whitespace line by line
- recomputes hash, token count, and character count after cleanup
- deduplicates cleaned chunks
- marks or filters low-value chunks

Metadata flags added by the quality pass:

```text
quality
searchable
front_matter
boilerplate
numeric_table_heavy
```

Chunks may be filtered out when:

- text is empty after cleanup
- there are fewer than 5 meaningful tokens
- it is short boilerplate such as publisher/copyright text
- alphabetic character ratio is too low
- text appears to be mojibake/corrupted
- numeric-table-heavy chunks are disabled and the chunk is mostly table/code-like numeric content

Relevant config:

```text
CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS=true
CHUNK_QUALITY_MIN_ALPHA_RATIO=0.45
```

## Recommendation

Use `SEMANTIC_RECURSIVE` as the default.

For Graph RAG, `SEMANTIC_RECURSIVE` is preferred because entity and relationship extraction benefits from complete paragraphs and more coherent local context.

Use `INTELLIGENT_RECURSIVE` mainly as a compatibility or diagnostic option.
