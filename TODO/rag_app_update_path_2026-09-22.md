# RAG App Update Path — 2026-09-22

## Agreed sequencing

`Pipeline closeout → session-aware feature → remaining RAG hardening and feature work`

## 1. Pipeline closeout

Close the CI/CD work with one successful live Jenkins/Sonar run for the five core services:

- RAG Ingest
- RAG Search
- RAG Answer
- Online Library
- Secure API

The intended lifecycle is:

`Build and Test → Sonar → Deploy`

- Application build and test failures remain blocking.
- Sonar scanner, Quality Gate, credential, and reporting failures remain advisory.
- Validate per-service pytest and coverage import, historical reporting, hotspot review, Kubernetes deployment, and three-image retention.

Do not expand the pipeline scope during this closeout. The remaining five services, blocking Sonar gates, new-code thresholds, and broader security tightening are deferred.

## 2. Immediate feature phase

After the first successful five-service Sonar build, begin the **session-aware feature** as a separate focused change set. The release plan identifies this as the highest-priority next feature, before further CI/CD expansion.

## 3. Remaining RAG roadmap

Do not repeat the RAG work already recorded as complete:

- oversampled hybrid retrieval, RRF, and reranking;
- chunk-quality and front-matter filtering;
- query understanding and configurable aliases;
- answer faithfulness and citation controls;
- search and answer observability.

Resume the outstanding RAG work in this order:

1. Evaluation harness with golden queries and measurable retrieval/answer metrics.
2. File-move rollback and durable source-file retention safeguards.
3. Idempotent ingestion and job-state-transition hardening.
4. Embedding-model and index governance.
5. Reindex, re-embed, rechunk, and document-versioning APIs.
6. Production database and pgvector index strategy.
7. Shared RAG database contracts across services.
8. Kafka asynchronous ingestion backend.
9. Operational runbooks and Postman coverage.
10. Layout-aware parsing, OCR, and table extraction.

## Source records

- `release/releasenote_2026-09-16_13-58-15_EDT.md`
- `docs/SONAR_FIVE_SERVICE_SETUP.md`
- `TODO/RAG_TIGHTENING_PLAN.md`

