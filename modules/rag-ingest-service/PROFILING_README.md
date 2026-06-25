# RAG Ingestion Profiling

The ingestion worker can emit per-stage timing logs for local troubleshooting and performance tuning.

Profiling data is also returned by:

```text
GET /rag/ingest/jobs/{job_id}
```

The browser UI renders these entries at the bottom of the Status panel so developers can see bottlenecks without opening log files.

## Enable Or Disable Profiling

Profiling is enabled by default:

```text
PROFILING=true
```

Disable it in `.env` when you want quieter logs:

```text
PROFILING=false
```

Restart the FastAPI service after changing this setting.

## Where Logs Go

When the service is started with the local helper command used in this project, uvicorn output is redirected to:

```text
D:\tmp\rag_ingest_service.err.log
D:\tmp\rag_ingest_service.out.log
```

Watch profiling logs:

```powershell
Get-Content -Wait -Tail 100 D:\tmp\rag_ingest_service.err.log | Select-String "PROFILE"
```

If you run uvicorn directly in a terminal, profiling lines appear in that terminal.

## Log Format

Profiling logs use a stable `PROFILE` prefix:

```text
PROFILE job_id=<job_id> resource_id=<resource_id> step=<step> elapsed_ms=<milliseconds> <details>
```

Example:

```text
PROFILE job_id=7060d81b-f90a-4745-befa-a21ed8357e39 resource_id=4a610503-06f8-49b9-bece-8326e5666c7d step=file_parse elapsed_ms=1842.17 parser_extension=.pdf file_name=Ramayana.pdf file_size_bytes=737512
```

## Profiled Stages

The worker currently profiles:

- `db_mark_processing`: marks job/resource as processing.
- `file_parse`: parses `.txt`, `.pdf`, `.docx`, or `.epub`.
- `db_store_extraction`: stores extracted text summary and metadata.
- `db_update_chunking_status`: updates the progress message before chunking.
- `chunking`: splits extracted text into chunks.
- `db_store_chunks`: persists chunk rows and updates chunk counters.
- `embedding_provider_factory`: builds the configured embedding provider.
- `embedding_generation`: calls the embedding provider for all chunks.
- `db_store_embeddings`: persists embedding rows and updates counters.
- `file_cleanup`: deletes the original uploaded file when `DELETE_ORIGINAL_FILE_AFTER_INGESTION=true`.
- `db_finalize_job`: marks resource ready and job completed.
- `job_total`: total worker time for the job.

## Useful Details Included

Depending on the stage, the log can include:

- `job_id`
- `resource_id`
- `elapsed_ms`
- `parser_extension`
- `file_name`
- `file_size_bytes`
- `text_chars`
- `text_tokens`
- `chunk_size_tokens`
- `chunk_overlap_tokens`
- `chunk_count`
- `embedding_count`
- `embedding_provider`
- `embedding_model`

## Interpreting Slow Runs

Common bottlenecks:

- Slow `file_parse`: PDF text extraction or very large DOCX/EPUB content.
- Slow `chunking`: very large extracted text or small chunk size with high overlap.
- Slow `embedding_generation`: Ollama model latency, model loading time, CPU/GPU limits, or many chunks.
- Slow `db_store_embeddings`: large vector payloads or database write latency.

For the current local Ollama default:

```text
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_DIMENSION=768
```

Embedding generation is usually the dominant stage for larger documents.

## PDF Parser Selection

PDF parsing is configurable:

```text
PDF_PARSER=pymupdf
```

`pymupdf` is the default because it is generally faster for text-based PDFs. The existing `pypdf` parser remains available as a fallback:

```text
PDF_PARSER=pypdf
```

The implementation uses an interface/factory style:

- `PdfParser` protocol
- `PyMuPdfParser`
- `PyPdfParser`
- `PdfParserFactory`

The `file_parse` profiling row shows which parser path was selected through `parser_extension=.pdf`; the extraction summary stores `parser_name` as either `pymupdf` or `pypdf`.

## Cross-Check With Job Status

The UI and API expose coarse progress:

```text
GET /rag/ingest/jobs/{job_id}
```

The response includes:

- `status`
- `message`
- `total_chunks`
- `processed_chunks`
- `embedded_chunks`
- `failed_chunks`
- `error_message`
- `profiling`

Use the UI profiling table for quick bottleneck checks and the `PROFILE` logs for terminal-based inspection.
