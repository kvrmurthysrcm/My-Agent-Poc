# RAG Tightening Plan

Source review date: 2026-06-26

## Source Material Reviewed

- `rag_search_module_action_plan.docx`
- `modules/rag-search-service/docs/rag_search_module_action_plan.docx`
- `modules/rag-ingest-service/docs/RAG_Ingest_Service_Action_Plan_v1_1_Updated.docx`
- `TODO/kafka-setup-4-processing-file.docx`
- `TODO/apachekafka-details.txt`
- `C:\Users\kvrmu\OneDrive\Desktop\RAG-improvements.txt`
- Current code in:
  - `modules/rag-ingest-service`
  - `modules/rag-search-service`
  - `modules/rag-answer-service`

Note: `RAG-improvements.txt` was provided from the desktop path after this plan was first created. The priority markers below reflect that file.

## Current System Summary

The project now has three RAG modules:

- `rag-ingest-service`: accepts uploads, extracts text, chunks documents, creates embeddings, stores chunks and vectors, supports retry/backoff, resumes missing embeddings, and has DB/recovery worker paths.
- `rag-search-service`: exposes retrieval-only `/rag/search`, supports vector, keyword, and hybrid search, applies query cleanup, quality filters, snippet cleanup, and current heuristic ranking.
- `rag-answer-service`: calls search, builds grounded context, invokes configurable LLM providers, and returns an answer with sources.

The remaining hardening work should focus on reliability, repeatable relevance evaluation, reranking, citation faithfulness, and operational controls. Kafka is configured as an async backend option but the actual producer/consumer implementation is not complete.

## Numbered Task Plan

Priority legend:

- `P0`: should be handled first because it affects correctness, data safety, or the ability to measure later changes.
- `P1`: high-value quality/relevance work.
- `P2`: production hardening after the core quality path is stable.

### Task 1: Build a RAG Evaluation Harness

Priority: `P0`

Goal: create a repeatable way to measure search and answer quality before tuning.

Scope:

- Add a small golden query set covering the known bad cases:
  - Ramayan broad query
  - Bhagavad Gita broad query
  - A Christmas Carol exact quote
  - Christmas Carol misspelling or conversational query
  - Ramana Maharshi impression question
- Store expected resource IDs, expected chunk text fragments, and acceptable answer facts.
- Add scripts/tests to run the queries against `rag-search-service` and `rag-answer-service`.
- Report metrics such as expected chunk in top 1/top 3/top 10, exact quote hit rank, answer contains expected source, and answer avoids unsupported claims.

Acceptance:

- One command runs the evaluation set locally.
- Current failures are visible as a report instead of only manual observation.
- Future search/answer changes can be compared before and after.

### Task 2: Complete Kafka Async Ingestion Backend

Priority: `P1`

Goal: make `ASYNC_BACKEND=kafka` actually publish and consume ingestion jobs while keeping the database as source of truth.

Scope:

- Implement `KafkaJobDispatcher` with `confluent-kafka`.
- Publish only identifiers and metadata, not file contents.
- Add config for:
  - `KAFKA_BOOTSTRAP_SERVERS`
  - `KAFKA_INGESTION_TOPIC`
  - `KAFKA_CONSUMER_GROUP`
  - optional completed/failed/DLQ topics
- Add a Kafka ingestion worker that consumes messages and calls existing `process_job(job_id)`.
- Commit Kafka offsets only after successful DB-backed processing.
- Add invalid-event handling and a DLQ path.
- Update docs, README, Postman notes, and local run commands.

Acceptance:

- With Kafka running, `/rag/ingest` returns immediately and publishes a Kafka event.
- The Kafka worker consumes the event and completes ingestion.
- Restarting the worker does not duplicate chunks or embeddings.
- Failed messages are not silently lost.

### Task 3: Formalize Idempotency and Job State Transitions

Priority: `P0`

Goal: make ingestion retries safe across FastAPI background tasks, DB worker, recovery worker, and Kafka worker.

Scope:

- Audit unique constraints and repository methods for extraction, chunks, and embeddings.
- Add explicit idempotency tests for:
  - extraction already exists
  - chunks already exist
  - partial embeddings exist
  - job restarts after N batches
  - duplicate Kafka event delivery
- Tighten status transitions so invalid transitions are rejected or logged.
- Add worker ownership/heartbeat checks to reduce two workers processing the same job.
- Ensure `process_job(job_id)` only processes claimable jobs:
  - `QUEUED`
  - or `PROCESSING` owned by the current worker/lock token.
- For PostgreSQL, use atomic claim semantics such as `SELECT ... FOR UPDATE SKIP LOCKED` or an equivalent atomic `QUEUED -> PROCESSING` update.

Acceptance:

- Duplicate event delivery does not duplicate chunk or embedding rows.
- Partial ingestion resumes from missing embeddings.
- Stale `PROCESSING` jobs are safely recovered.

### Task 4: Add Oversampled Hybrid Search, RRF, and Reranking

Priority: `P0`
Status: `DONE` on 2026-06-26

Goal: improve ranking when hybrid retrieval finds the right chunk but buries it below weaker metadata/title hits.

Scope:

- Retrieve more than requested `top_k` for hybrid search:
  - `vector_k = top_k * 5`
  - `keyword_k = top_k * 5`
  - rerank down to requested `top_k`
- Replace or supplement min-max score normalization with Reciprocal Rank Fusion.
- Add an optional reranking stage after initial retrieval.
- Start with a lightweight local heuristic reranker using:
  - exact phrase proximity
  - query term coverage
  - subject/title match
  - direct evidence terms
  - penalties for front matter, publisher lines, table of contents, and metadata-only chunks
- Keep the interface open for a future cross-encoder or LLM reranker.
- Add config:
  - `HYBRID_OVERSAMPLING_FACTOR`
  - `HYBRID_FUSION_STRATEGY`
  - `RERANK_ENABLED`
  - `RERANK_TOP_N`
  - `RERANK_STRATEGY`
- Return rerank signals in debug mode.

Acceptance:

- The Christmas Carol quote ranks first.
- The Ramana Maharshi impression chunk ranks high enough for answer generation.
- Broad title queries still return the intended document without front matter dominating.
- Hybrid search retrieves 50 vector and 50 keyword candidates for `top_k=10` when the oversampling factor is `5`.

### Task 5: Improve Chunk Quality and Front-Matter Handling

Priority: `P0`
Status: `DONE` on 2026-06-26

Goal: prevent low-value chunks from being embedded or over-ranked.

Scope:

- Strengthen chunk quality classification for:
  - publisher-only lines
  - edition/impression lines
  - table of contents fragments
  - copyright/front matter
  - isolated page headers/footers
- Decide whether such chunks should be skipped entirely or stored as non-searchable.
- Add chunk metadata flags:
  - `quality`
  - `front_matter`
  - `boilerplate`
  - `searchable`
- Make search filter or downrank these flags.
- Keep numeric/table-heavy chunk handling configurable. For now, numeric/table-heavy chunks should remain enabled, because enterprise documents can contain invoice numbers, policy codes, claim IDs, financial values, part numbers, and form fields.

Acceptance:

- Chunks like `Publications Division, T.T.D, Tirupati.` do not appear in normal search results.
- Useful preface content can still be found when explicitly queried.
- Numeric/table-heavy chunks are not globally rejected when the feature is enabled.

### Task 6: Strengthen Query Understanding

Priority: `P1`

Goal: improve retrieval for conversational, misspelled, and intent-heavy queries.

Scope:

- Expand query preprocessing beyond simple prefix stripping.
- Add optional spelling normalization for common title/entity typos:
  - `Christams` to `Christmas`
  - `Githa` to `Gita`
  - `Brenton` to `Brunton` when matching known metadata
- Detect query type:
  - exact quote
  - title lookup
  - summary request
  - factual question
  - broad document query
- Pass query intent into search ranking and answer context packing.
- Move hard-coded lexical aliases from code into configuration or a DB-backed synonym/glossary source:
  - domain synonyms
  - query rewrites
  - business glossary
  - tenant-specific synonyms
- Use `websearch_to_tsquery` for PostgreSQL keyword search when available instead of only `plainto_tsquery`.

Acceptance:

- Misspelled but recognizable queries retrieve the intended resource.
- Exact quotes prioritize lexical/phrase matching.
- Broad summary questions do not return random page/header fragments.
- Search aliases can be changed without editing Python code.

### Task 7: Add Answer Faithfulness and Citation Controls

Priority: `P1`

Goal: make `rag-answer-service` answer only from retrieved evidence and cite the exact supporting chunks.

Scope:

- Require the LLM to cite source rank/chunk/page in the answer.
- Add a post-generation verifier that checks whether cited facts are present in selected context.
- Return `insufficient_context` when retrieval lacks support.
- Add answer modes:
  - concise
  - detailed
  - quote-backed
- Add optional raw prompt/debug output only when explicitly requested.

Acceptance:

- The answer cites the chunk/page that supports it.
- Unsupported answer claims are rejected or replaced with an insufficient-context response.
- The Ramana Maharshi answer cites the passage about peace/stillness rather than the guide/Yogi passage.

### Task 8: Add Search and Answer Observability

Priority: `P0`

Goal: make bad results diagnosable without reading raw logs manually.

Scope:

- Add debug fields for:
  - normalized query
  - query intent
  - vector score
  - keyword score
  - rerank score
  - quality penalties
  - final score
- Add request timing for:
  - query embedding
  - DB retrieval
  - reranking
  - context packing
  - LLM generation
- Add a developer UI toggle to show scoring/debug details.
- Add `POST /rag/search/debug` returning:
  - normalized query
  - query embedding model
  - vector candidates
  - keyword candidates
  - merged candidates
  - ranking reasons

Acceptance:

- A bad result can be explained from the API response in debug mode.
- Slow Ollama embedding/LLM calls are visible in response timing.
- Developers can see why each returned chunk was selected.

### Task 9: Align Embedding Model and Index Governance

Priority: `P1`

Goal: prevent mismatched embeddings and make reindexing explicit.

Scope:

- Validate search embedding provider/model/version against stored chunk embeddings.
- Add admin/report endpoint showing indexed embedding models and dimensions.
- Add reindex plan or command for changing embedding models.
- Add tests for mixed-provider data.
- Track and expose:
  - document version
  - parser name and parser version
  - chunking strategy and chunking version
  - embedding provider, model, and version
  - source file hash
  - extracted text hash

Acceptance:

- Search never compares query vectors against incompatible stored vectors.
- Operators can see which documents were indexed by which embedding model/version.

### Task 10: Add Operational Runbooks and Postman Coverage

Priority: `P2`

Goal: keep the tightened system usable by developers.

Scope:

- Update service READMEs for:
  - FastAPI background task mode
  - DB worker mode
  - Kafka mode
  - recovery worker mode
  - answer service mode
- Add Postman examples for:
  - ingest
  - job status
  - search debug
  - answer with citations
  - Kafka-mode expectations
- Add troubleshooting sections for:
  - Ollama slow/timeout
  - stuck jobs
  - bad rankings
  - missing embeddings

Acceptance:

- A developer can start all needed services and run the golden evaluation set from docs alone.

### Task 11: Extract Shared RAG DB Contracts

Priority: `P1`

Goal: prevent schema drift between ingest and search services.

Scope:

- Create or plan a shared package such as:
  - `rag-common/db/models.py`
  - `rag-common/schemas/`
  - `rag-common/embedding_model_registry.py`
- Move duplicated DB model definitions out of per-service copies over time.
- Version the shared package so ingest/search/answer services declare which contract version they use.
- Keep the first implementation small enough for the current monorepo.

Acceptance:

- `rag-ingest-service` and `rag-search-service` do not maintain independent copies of the same DB model definitions.
- Schema changes are made in one place and consumed consistently.

### Task 12: Fix File Move Rollback and Source File Retention

Priority: `P0`

Goal: avoid orphan files when file storage succeeds but the DB transaction fails.

Scope:

- In `IngestService.create_resource_and_job()`, track both temp path and final path.
- If an exception happens after `storage_path.replace(final_path)` but before DB commit, delete the final path during rollback cleanup.
- Add tests for failure after file move and before DB commit.
- Revisit `DELETE_ORIGINAL_FILE_AFTER_INGESTION`; production should retain source files in object storage or controlled durable storage.

Acceptance:

- A simulated DB commit failure after file move leaves no orphan file under `storage/resources/{resource_id}`.
- Cleanup behavior is covered by tests.

### Task 13: Add Re-index, Re-embed, Re-chunk, and Versioning APIs

Priority: `P1`

Goal: support production lifecycle changes when parsers, chunking, or embedding models change.

Scope:

- Add endpoints or worker commands for:
  - re-index resource
  - re-embed resource
  - re-chunk resource
  - bulk re-embedding when model changes
- Add document versioning and duplicate detection by file hash and extracted-text hash.
- Add parser/chunking/embedding version tracking into metadata and search filters.
- Add batch ingestion support after single-document lifecycle is stable.

Acceptance:

- A document can be reprocessed without manual DB edits.
- A model change has an explicit re-embedding path.
- Duplicate files can be detected by hash.

### Task 14: Add Production DB Indexes and Vector Index Strategy

Priority: `P1`

Goal: make retrieval and job processing scale predictably.

Scope:

- Add or verify indexes for:
  - resource RAG status
  - original file hash
  - job status/retry scheduling
  - chunk resource/chunk index
  - chunk keyword search vector
  - embedding vector index
- Prefer HNSW for pgvector as the first production vector index strategy unless testing shows a reason to use IVFFlat.
- Document PostgreSQL production behavior and remove file-based local database fallback paths.

Acceptance:

- Alembic migrations include the required production indexes.
- Search docs state the chosen pgvector index strategy and why.

### Task 15: Add Layout-Aware Parsing, OCR, and Table Extraction

Priority: `P2`

Goal: improve ingestion quality for scanned PDFs, tables, forms, and enterprise documents.

Scope:

- Add layout-aware PDF parsing option.
- Add OCR fallback for scanned PDFs.
- Add table extraction and table-to-text conversion.
- Preserve per-page citation metadata.
- Add parent-child chunking for long structured documents.

Acceptance:

- Scanned PDFs can be detected and routed to OCR.
- Tables are represented in searchable text without being discarded by alpha-ratio filters.
- Answers can cite page-level evidence reliably.

## Recommended Execution Order

1. Task 1: evaluation harness
2. Task 12: file move rollback cleanup
3. Task 3: idempotency/state-transition hardening
4. Task 4: oversampled hybrid search, RRF, and reranking
5. Task 8: search and answer observability/debug endpoint
6. Task 5: chunk quality/front-matter and numeric/table controls
7. Task 6: query understanding and configurable synonyms
8. Task 7: answer faithfulness/citations
9. Task 9: embedding/index governance
10. Task 13: re-index/re-embed/re-chunk/versioning APIs
11. Task 14: production DB indexes and vector strategy
12. Task 11: shared RAG DB contracts
13. Task 2: Kafka backend
14. Task 10: docs/Postman/runbooks
15. Task 15: layout-aware parsing, OCR, table extraction

The evaluation harness should come first because it gives a stable way to prove each later task improves the system rather than only changing behavior for one example query.
