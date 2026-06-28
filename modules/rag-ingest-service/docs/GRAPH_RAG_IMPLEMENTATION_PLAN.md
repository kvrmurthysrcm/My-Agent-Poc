# Graph RAG Implementation Plan

Source prompt: `modules/rag-ingest-service/docs/codex_prompt_graph_rag_same_module_fastapi_pgvector.txt`

## What I Understand

The request is to extend the existing FastAPI RAG POC with Graph RAG while preserving current standard RAG ingestion, pgvector storage, hybrid search, and simple HTML UI behavior.

This repository is organized as multiple RAG services:

- `modules/rag-ingest-service` handles upload, resource registration, extraction, chunking, embeddings, jobs, and the upload HTML UI.
- `modules/rag-search-service` handles hybrid search and search/admin HTML UI.
- `modules/rag-answer-service` handles answer generation and already has LLM provider abstractions that may be useful as a reference, but Graph RAG should be added without moving ingestion or search into a new service.

Graph RAG should use the same PostgreSQL database and connect graph records back to existing resource and chunk IDs. It must not introduce SQLite, Neo4j, a separate frontend framework, or a duplicate ingest service. `indexing_mode` must default to `STANDARD` so existing API and UI behavior remains compatible.

## Assumptions For Implementation

- Graph indexing belongs primarily in `rag-ingest-service` because it depends on the shared ingest pipeline and chunks.
- Graph search belongs primarily in `rag-search-service` because existing `/rag/search` and hybrid search live there.
- Shared graph table definitions may need to exist in both ingest and search SQLAlchemy model modules unless the repo already has a shared package pattern suitable for reuse.
- Existing Alembic files are present today, but the requested target state is no Alembic and no SQLite anywhere in the project. Because this is a POC with no existing data to migrate, schema changes should be represented as PostgreSQL/pgvector SQL scripts and startup/runtime code should not depend on Alembic.
- Graph RAG extraction should use the available local Mistral/Ollama-compatible generation endpoint through a clean interface. Mistral is used only for entity, relationship, and summary generation, not embeddings.
- The first Graph RAG implementation should be POC-simple: chunk-level Mistral extraction, entity/relationship persistence, simple graph search, and optional summaries without heavy graph algorithms.
- The implementation should include both per-chunk extraction and resource-level consolidation in this pass.
- Local Ollama is available at `http://localhost:11434`.
- Preferred tested generation endpoint: `POST http://localhost:11434/api/generate`.
- Preferred tested model: `mistral:7b-instruct-v0.3-q2_K`.
- Also available but less preferred for strict JSON extraction: `POST http://localhost:11434/api/chat` and `POST http://localhost:11434/v1/chat/completions`.
- `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=false` is the default. In `GRAPH` mode, this means no rows are saved to `rag_chunk_embeddings`; set it to `true` only when graph-only uploads should also create chunk embeddings for vector search.

## Implementation Phases

### 1. Baseline Inspection

- Inspect current ingest routes, HTML upload form, job worker, job status response, DB models, repositories, and tests.
- Inspect current search schemas, services, repositories, routes, HTML search UI, and tests.
- Identify exact existing table names and ID types for resources, jobs, chunks, and embeddings.
- Confirm whether all remaining SQLite references are inactive documentation only or actual code paths.

### 2. Indexing Mode Support

- Add an `IndexingMode` enum or equivalent constrained type with:
  - `STANDARD`
  - `GRAPH`
  - `BOTH`
- Add `indexing_mode` to ingest request metadata with default `STANDARD`.
- Persist selected indexing mode in job metadata or a model field, following the existing job schema style.
- Update upload API form parsing so missing mode remains `STANDARD`.
- Update tests for default behavior and mode validation.

### 3. HTML Upload UI

- Update `modules/rag-ingest-service/app/ui/index.html`.
- Add a dropdown or radio control for indexing mode:
  - Standard RAG
  - Graph RAG
  - Both Standard RAG and Graph RAG
- Keep the existing plain FastAPI HTML/static style.
- Display selected indexing mode in any job/status details if the current UI exposes job details.

### 4. Graph RAG Schema And Models

- Add PostgreSQL graph tables:
  - `rag_graph_entities`
  - `rag_graph_relationships`
  - `rag_graph_communities`
  - `rag_graph_entity_communities`
  - `rag_graph_summaries`
- Use UUIDs and timestamp/JSONB conventions matching existing models.
- Add indexes for `resource_id`, `chunk_id`, `normalized_name`, `entity_type`, `source_entity_id`, and `target_entity_id`.
- Add SQLAlchemy models in the service modules that need them.
- Do not add Alembic migrations.
- Remove Alembic startup wiring, config files, migration folders, migration references, and Alembic dependencies from ingest/search services.
- Add or update PostgreSQL schema SQL scripts, likely:
  - `modules/rag-ingest-service/sql/schema.sql`
  - `modules/rag-ingest-service/sql/graph_rag_schema.sql` if keeping graph schema separate is clearer.

### 5. Graph RAG Package In Ingest Service

- Add a modular package under `modules/rag-ingest-service/app/graph_rag/` or an equivalent style matching this repo:
  - `models.py`
  - `schemas.py`
  - `repositories/graph_repository.py`
  - `services/graph_indexing_service.py`
  - `services/entity_extraction_service.py`
  - `services/relationship_extraction_service.py`
  - `services/graph_summary_service.py`
  - prompt files if an LLM prompt-based implementation is practical.
- Keep graph business logic out of FastAPI route handlers.
- Add repository methods for upsert, create, fetch, delete, and simple search.
- Add a local Mistral/Ollama generation client configured with:
  - base URL default `http://localhost:11434`
  - endpoint default `/api/generate`
  - model default `mistral:7b-instruct-v0.3-q2_K`
  - `stream=false`
  - strict JSON response parsing with defensive cleanup for occasional markdown/code-fence output.

### 6. Graph Indexing Pipeline

- Reuse existing upload, resource registration, metadata capture, text extraction, chunking, and job tracking.
- Branch after shared chunking:
  - `STANDARD`: current embedding/indexing behavior only.
  - `GRAPH`: graph indexing only; skip embeddings/vector indexing when `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=false`; create chunk embeddings as well when the flag is `true`.
  - `BOTH`: current indexing and graph indexing.
- Implement graph indexing steps:
  - read chunks for the resource/job
  - send chunk text, not the full source file, to local Mistral for entity extraction
  - normalize and deduplicate names per resource
  - send chunk text plus extracted entities to local Mistral for relationship extraction
  - consolidate compact extracted graph facts at resource level using deterministic normalization and Mistral-assisted summary/consolidation where useful
  - merge/strengthen repeated relationships across chunks
  - store canonical entities and relationships while preserving chunk traceability in fields/metadata
  - create resource-level graph summaries
  - create simple communities/clusters where practical for the POC
- Update job status/progress using existing enum/metadata patterns with minimal risk.

Chunking ownership:

- The existing ingest pipeline creates chunks.
- Graph RAG does not create a separate duplicate chunking flow.
- Mistral does not create chunks; Mistral receives already-created chunk text and returns structured graph facts for each chunk.
- For very short documents, the same flow still applies: one or more chunks are created first, then graph extraction runs over those chunks.

### 7. Graph Search In Search Service

- Add schemas for graph search request/response.
- Add a graph repository and service under `modules/rag-search-service/app/`.
- Add endpoint:
  - `POST /rag/graph/search`
- Implement simple PostgreSQL search:
  - entity name/normalized name matching
  - relationship description/type matching
  - optional summaries
  - optional joins back to chunks/resources where practical.
- Add combined endpoint:
  - `POST /rag/search/combined`
- Return existing hybrid results and graph results separately.

### 8. Search UI Updates

- If the existing search HTML supports result rendering cleanly, add an option to show Graph RAG results.
- Keep standard search behavior unchanged.
- Avoid introducing a frontend framework.

### 9. PostgreSQL/Pgvector-Only Cleanup

- Remove any active SQLite code paths if found.
- Do not add SQLite test fixtures or fallback logic.
- Keep PostgreSQL URL validation.
- Remove Alembic completely from the project:
  - `alembic.ini`
  - `alembic/` folders
  - startup migration code
  - Alembic imports
  - Alembic dependencies in `requirements.txt` and `pyproject.toml`
  - tests for Alembic startup behavior
  - README/docs instructions that mention Alembic migration commands
- Remove or simplify `AUTO_MIGRATE_ON_STARTUP` because it is Alembic-specific.
- Review `AUTO_CREATE_TABLES`; keep only if it remains PostgreSQL-compatible and useful for a local POC, otherwise remove it and rely on SQL schema scripts.
- Update README/docs to remove stale SQLite, Alembic, or misleading migration instructions.

### 10. Tests

- Add or update pytest coverage where practical:
  - missing `indexing_mode` defaults to `STANDARD`
  - `STANDARD` does not run graph indexing
  - `GRAPH` runs graph indexing
  - `GRAPH` does not save chunk embeddings when `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=false`
  - `GRAPH` saves chunk embeddings when `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=true`
  - `BOTH` runs both standard and graph indexing
  - entity persistence
  - relationship persistence
  - graph search returns expected entities
  - standard RAG tests still pass
  - PostgreSQL/pgvector-only config remains enforced
  - no active SQLite code path remains
  - no Alembic dependency, startup path, or test path remains
- If database integration tests require local PostgreSQL, document manual test commands and expected results.

### 11. Documentation

- Update service README files or create a concise Graph RAG doc covering:
  - indexing modes
  - `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS` behavior
  - HTML UI usage
  - upload API usage with `indexing_mode`
  - graph tables
  - PostgreSQL/pgvector-only assumption
  - shared ingest pipeline behavior
  - manual schema creation
  - POC limitations

## Proposed File Areas

- `modules/rag-ingest-service/app/schemas/ingest_request.py`
- `modules/rag-ingest-service/app/api/rag_ingest_routes.py`
- `modules/rag-ingest-service/app/services/ingest_service.py`
- `modules/rag-ingest-service/app/workers/rag_ingestion_worker.py`
- `modules/rag-ingest-service/app/db/models.py`
- `modules/rag-ingest-service/app/repositories/`
- `modules/rag-ingest-service/app/graph_rag/`
- `modules/rag-ingest-service/app/ui/index.html`
- `modules/rag-ingest-service/sql/graph_rag_schema.sql`
- `modules/rag-ingest-service/alembic/` cleanup/removal
- `modules/rag-ingest-service/alembic.ini` cleanup/removal
- `modules/rag-search-service/app/api/rag_search_routes.py`
- `modules/rag-search-service/app/schemas/`
- `modules/rag-search-service/app/services/`
- `modules/rag-search-service/app/repositories/`
- `modules/rag-search-service/app/db/models.py`
- `modules/rag-search-service/app/ui/search.html`
- `modules/rag-search-service/alembic/` cleanup/removal
- `modules/rag-search-service/alembic.ini` cleanup/removal
- Related tests and README/docs.

## Final Clarifications From User

- Use local Mistral through Ollama.
- Use tested endpoint `POST http://localhost:11434/api/generate`.
- Use tested model `mistral:7b-instruct-v0.3-q2_K`.
- `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=false` by default.
- `GRAPH` mode skips embeddings and vector indexing when `GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS=false`; it may create chunk embeddings when that flag is `true`.
- Implement both per-chunk extraction and resource-level consolidation now.
- Remove Alembic entirely; use PostgreSQL/pgvector SQL schema scripts only.
- No further critical details are required before implementation.
