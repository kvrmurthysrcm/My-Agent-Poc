# RAG Ingestion Service API Reference

This document describes the current API surface for `rag-ingest-service`.

Base URL for local development:

```text
http://localhost:8000
```

## GET /

Purpose: Serve the browser upload UI.

Request:

```http
GET /
```

Sample response:

```http
200 OK
Content-Type: text/html
```

Description: Returns the same HTML upload interface as `GET /ui`. The UI lets a developer upload a supported document, enter metadata, submit ingestion, and poll job status.

## GET /ui

Purpose: Serve the browser upload UI.

Request:

```http
GET /ui
```

Sample response:

```http
200 OK
Content-Type: text/html
```

Description: Returns `app/ui/index.html`. Supports `.txt`, `.pdf`, `.docx`, and `.epub` uploads through the browser.

## GET /health

Purpose: Lightweight liveness check.

Request:

```http
GET /health
```

Sample response:

```json
{
  "status": "ok",
  "service": "rag-ingest-service"
}
```

Description: Confirms the FastAPI process is running. This endpoint intentionally does not check database connectivity or external embedding providers.

## GET /ready

Purpose: Readiness check for runtime dependencies and embedding configuration.

Request:

```http
GET /ready
```

Sample response:

```json
{
  "status": "ready",
  "database": "ok",
  "embedding_provider": "ollama",
  "embedding_model": "nomic-embed-text"
}
```

Description: Checks database connectivity and validates the configured embedding provider/model/dimension. It does not call expensive OpenAI or Ollama embedding APIs.

## POST /rag/ingest

Purpose: Upload a document and create an asynchronous RAG ingestion job.

Request:

```http
POST /rag/ingest
Content-Type: multipart/form-data
```

Form fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | binary file | yes | Document to ingest. Supported extensions: `.txt`, `.pdf`, `.docx`, `.epub`. |
| `metadata` | JSON string | yes | Document metadata and optional chunking overrides. |

Sample metadata:

```json
{
  "title": "Provider Claims Submission Policy",
  "resource_type": "DOCUMENT",
  "category_name": "Claims",
  "source_system": "manual_upload",
  "tags": ["claims", "policy"],
  "chunking": {
    "strategy": "SEMANTIC_RECURSIVE",
    "chunk_size_tokens": 1200,
    "chunk_overlap_tokens": 80
  }
}
```

Sample curl:

```powershell
$metadata = '{"title":"Provider Claims Submission Policy","resource_type":"DOCUMENT","category_name":"Claims","source_system":"manual_upload","tags":["claims","policy"]}'
curl.exe -X POST http://localhost:8000/rag/ingest -F "file=@sample.txt;type=text/plain" -F "metadata=$metadata"
```

Sample response:

```json
{
  "resource_id": "7f78647a-7601-4a27-8c64-73cd25d6a24a",
  "job_id": "83f1cb84-0667-47e0-8ef8-77d9fe1552ec",
  "status": "QUEUED"
}
```

Description: Stores resource metadata, stages the uploaded file under a unique temporary folder, moves it under the resource folder after resource creation, creates a `rag_ingestion_jobs` row, and dispatches processing using the configured async backend. The response is returned immediately; text extraction, chunking, embedding, and persistence happen asynchronously.

Common failure responses:

```json
{
  "detail": "Unsupported file extension: .exe"
}
```

```json
{
  "detail": "metadata validation failed: ..."
}
```

## GET /rag/ingest/jobs/{job_id}

Purpose: Poll ingestion job status.

Request:

```http
GET /rag/ingest/jobs/{job_id}
```

Path parameters:

| Parameter | Type | Description |
| --- | --- | --- |
| `job_id` | UUID string | Ingestion job ID returned by `POST /rag/ingest`. |

Sample response:

```json
{
  "job_id": "83f1cb84-0667-47e0-8ef8-77d9fe1552ec",
  "resource_id": "7f78647a-7601-4a27-8c64-73cd25d6a24a",
  "status": "COMPLETED",
  "parser_name": "plain_text",
  "total_chunks": 4,
  "processed_chunks": 4,
  "embedded_chunks": 4,
  "failed_chunks": 0,
  "started_at": "2026-06-25T20:50:53.123456",
  "completed_at": "2026-06-25T20:50:54.234567",
  "message": "Ingestion completed",
  "progress_message": "Ingestion completed",
  "error_message": null,
  "profiling": []
}
```

Description: Returns current ingestion status, chunk counters, embedding counters, current progress message, error message if failed, and profiling rows when available.

Possible statuses:

| Status | Meaning |
| --- | --- |
| `QUEUED` | Job has been accepted but not yet processed. |
| `PROCESSING` | Worker/background task is extracting, chunking, embedding, or storing results. |
| `COMPLETED` | Chunks and embeddings were successfully stored and the resource is ready. |
| `FAILED` | Ingestion failed. See `error_message` and `rag_processing_errors`. |

Failure response:

```json
{
  "detail": "Ingestion job not found"
}
```

## DELETE /rag/dev/resources/{resource_id}

Purpose: Local development cleanup endpoint.

Request:

```http
DELETE /rag/dev/resources/{resource_id}
```

Optional query parameters:

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `force` | boolean | `false` | Allows forced deletion where supported by the dev delete service. |

Sample response:

```json
{
  "resource_id": "7f78647a-7601-4a27-8c64-73cd25d6a24a",
  "deleted": true,
  "deleted_file_path": "storage/resources/7f78647a-7601-4a27-8c64-73cd25d6a24a/sample.txt",
  "deleted_counts": {
    "rag_chunk_embeddings": 4,
    "rag_document_chunks": 4,
    "rag_document_extractions": 1,
    "rag_processing_errors": 0,
    "rag_profiling_events": 8,
    "rag_ingestion_jobs": 1,
    "resources": 1
  }
}
```

Description: Deletes an ingested resource and associated RAG rows for local development cleanup. This endpoint is available only when:

```text
APP_PROFILE=local
ENABLE_DEV_DELETE_ENDPOINT=true
```

If disabled, it returns:

```json
{
  "detail": "Not found"
}
```

## Notes

- Security/authentication is intentionally out of scope for this POC.
- `mistral:latest`, `gemma4`, `llama*`, and qwen chat models are not valid `EMBEDDING_MODEL` values.
- Default local embedding configuration is `EMBEDDING_PROVIDER=ollama`, `EMBEDDING_MODEL=nomic-embed-text`, `EMBEDDING_DIMENSION=768`.
- OpenAI embeddings require `OPENAI_API_KEY` unless `ALLOW_FAKE_EMBEDDINGS=true` is explicitly enabled for tests/local smoke runs.
