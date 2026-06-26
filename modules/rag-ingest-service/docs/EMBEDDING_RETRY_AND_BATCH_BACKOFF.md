# Embedding Retry and Batch Backoff

## Purpose

Local Ollama embedding generation can be slow for large batches, especially with `nomic-embed-text`. A batch timeout should not fail the whole ingestion job immediately when smaller batches may succeed.

## Configuration

```text
EMBEDDING_BATCH_SIZE=64
EMBEDDING_CONCURRENCY=1
EMBEDDING_MAX_RETRIES=2
EMBEDDING_RETRY_BACKOFF_SECONDS=1.0
EMBEDDING_RETRY_SHRINK_BATCH=true
EMBEDDING_MIN_BATCH_SIZE=1
OLLAMA_EMBEDDING_TIMEOUT_SECONDS=60
```

## Behavior

Embedding batches are sent using `EMBEDDING_BATCH_SIZE`.

If a provider call fails, the embedding service retries up to `EMBEDDING_MAX_RETRIES`.

When `EMBEDDING_RETRY_SHRINK_BATCH=true`, failed batches are retried in smaller pieces. For example:

```text
32 -> 16 + 16 -> 8 + 8 + 8 + 8
```

The split stops at `EMBEDDING_MIN_BATCH_SIZE`.

`EMBEDDING_RETRY_BACKOFF_SECONDS` adds a simple delay before retries. The delay is multiplied by the attempt number.

`OLLAMA_EMBEDDING_TIMEOUT_SECONDS` controls the HTTP timeout for Ollama `/api/embed` calls.

Embeddings are persisted batch by batch by the ingestion worker. If a process restarts after some batches are committed, recovery skips existing embeddings and continues with missing chunk IDs only.

## Operational Guidance

For local `nomic-embed-text`, start conservatively:

```text
EMBEDDING_BATCH_SIZE=32
EMBEDDING_CONCURRENCY=1
EMBEDDING_MAX_RETRIES=2
EMBEDDING_RETRY_SHRINK_BATCH=true
OLLAMA_EMBEDDING_TIMEOUT_SECONDS=90
```

If timeouts continue, reduce `EMBEDDING_BATCH_SIZE` to `16` or increase `OLLAMA_EMBEDDING_TIMEOUT_SECONDS`.
