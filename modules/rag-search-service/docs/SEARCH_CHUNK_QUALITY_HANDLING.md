# Search Chunk Quality Handling

## Purpose

The ingest service now stores quality metadata on retained chunks:

```json
{
  "quality": "searchable",
  "searchable": true,
  "front_matter": false,
  "boilerplate": false,
  "numeric_table_heavy": false
}
```

Search uses these flags to avoid returning known low-value chunks and to downrank retained front matter.

## Filtering Rules

Search filters out chunks when:

- `metadata_json.searchable` is `false`
- `metadata_json.quality` is `filtered`
- the text is short boilerplate such as publisher/copyright/footer lines
- the text is too short or dominated by encoding noise

Front matter is not automatically removed. If it is retained by ingestion, it remains available for explicit queries but receives a reranker penalty.

## Numeric and Table-Heavy Chunks

Numeric/table-heavy chunks are kept searchable by default:

```text
SEARCH_KEEP_NUMERIC_TABLE_CHUNKS=true
SEARCH_MIN_ALPHA_RATIO=0.45
```

This avoids dropping enterprise content such as invoice tables, policy codes, claim IDs, part numbers, and form fields.

## Tests

The search tests cover:

- filtering chunks marked `searchable=false`
- retaining numeric/table-heavy chunks when enabled
- existing publisher/footer filtering
- front-matter downranking through the local reranker
