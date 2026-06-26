# Processing Job Recovery

## Problem

When `ASYNC_BACKEND=fastapi_background_tasks`, ingestion runs inside the API process. If the API process restarts while a file is being processed, the in-memory task is lost and the database job can remain stuck in `PROCESSING`.

## Recovery Worker

Run a separate recovery process:

```powershell
cd modules\rag-ingest-service
python -m app.workers.rag_recovery_worker
```

The recovery worker:

1. Finds `PROCESSING` jobs whose `heartbeat_at` is older than `RECOVERY_STALE_AFTER_SECONDS`.
2. Requeues them using the existing retry fields.
3. Sets the resource `ingestion_status` back to `QUEUED`.
4. Processes queued jobs using the existing ingestion worker path.

## Resume Behavior

The ingestion worker is resumable across the main persisted stages:

- If an extraction row already exists for the job, the worker reuses it and does not require the original file for extraction.
- If chunks already exist for the job, the worker reuses them and does not create duplicate chunks.
- Before embedding, the worker checks which chunk IDs already have embeddings for the configured provider, model, and version.
- Only chunks missing embeddings are sent to the embedding provider.
- Embeddings are committed batch by batch.
- `embedded_chunks` is updated after each committed embedding batch.

Example:

```text
320 chunks, EMBEDDING_BATCH_SIZE=32
10 embedding batches total
restart after 5 committed batches
recovery requeues the job
worker resumes by embedding only the remaining 160 chunks
```

## Configuration

```text
RECOVERY_STALE_AFTER_SECONDS=900
RECOVERY_WORKER_POLL_INTERVAL_SECONDS=30
DB_WORKER_BATCH_SIZE=5
```

For local testing, use a shorter threshold:

```powershell
python -m app.workers.rag_recovery_worker --once --stale-after-seconds 30
```

To only requeue stale jobs and let another DB worker process them:

```powershell
python -m app.workers.rag_recovery_worker --no-process
```

## Caveats

Recovery is still job-level. A stale job must first pass the `RECOVERY_STALE_AFTER_SECONDS` threshold before it is requeued.

If a restart happens before a batch commit, that in-memory batch is regenerated. If a restart happens after a batch commit, that batch is skipped on retry.
