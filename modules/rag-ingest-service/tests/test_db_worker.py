from datetime import UTC, datetime, timedelta

from app.db import models  # noqa: F401
from app.db.models import RagChunkEmbedding, RagDocumentChunk, RagDocumentExtraction, Resource
from app.db.session import Base, SessionLocal, engine
from app.repositories.rag_job_repository import RagJobRepository
from app.services.embedding_input_service import EmbeddingInputService
from app.workers import rag_ingestion_worker
from app.workers import rag_recovery_worker


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_claim_queued_jobs_does_not_reclaim_processing_job():
    db = SessionLocal()
    try:
        resource = Resource(title="Claim Test")
        db.add(resource)
        db.flush()
        jobs = RagJobRepository(db)
        created = jobs.create_job(
            resource_id=resource.resource_id,
            async_backend="db_worker",
            strategy="SEMANTIC_RECURSIVE",
            size=1200,
            overlap=80,
        )
        db.commit()

        first_claim = jobs.claim_queued_jobs(limit=1, worker_id="worker-a")
        db.commit()
        second_claim = jobs.claim_queued_jobs(limit=1, worker_id="worker-b")

        assert [job.job_id for job in first_claim] == [created.job_id]
        assert second_claim == []
        assert created.status == "PROCESSING"
        assert created.worker_id == "worker-a"
        assert created.locked_at is not None
        assert created.heartbeat_at is not None
    finally:
        db.close()


def test_recover_stale_processing_job_requeues_job_and_resource():
    db = SessionLocal()
    try:
        resource = Resource(title="Recover Me", ingestion_status="PROCESSING")
        db.add(resource)
        db.flush()
        jobs = RagJobRepository(db)
        job = jobs.create_job(
            resource_id=resource.resource_id,
            async_backend="fastapi_background_tasks",
            strategy="SEMANTIC_RECURSIVE",
            size=1200,
            overlap=80,
        )
        job.status = "PROCESSING"
        job.heartbeat_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=120)
        job.locked_at = job.heartbeat_at
        db.commit()

        recovered = jobs.recover_stale_processing_jobs(stale_after_seconds=60)
        db.commit()

        assert recovered == 1
        assert job.status == "QUEUED"
        assert job.retry_count == 1
        assert job.next_retry_at is not None
        assert resource.ingestion_status == "QUEUED"
    finally:
        db.close()


def test_worker_main_once_invokes_single_poll(monkeypatch):
    calls = []

    def fake_process_queued_jobs():
        calls.append("called")
        return 0

    monkeypatch.setattr(rag_ingestion_worker, "process_queued_jobs", fake_process_queued_jobs)

    rag_ingestion_worker.main(["--once"])

    assert calls == ["called"]


def test_recovery_worker_once_recovers_then_processes(monkeypatch):
    calls = []

    monkeypatch.setattr(rag_recovery_worker, "recover_stale_jobs_once", lambda stale_after_seconds=None: calls.append("recover") or 1)
    monkeypatch.setattr(rag_recovery_worker, "process_queued_jobs", lambda: calls.append("process") or 1)

    rag_recovery_worker.main(["--once", "--stale-after-seconds", "1"])

    assert calls == ["recover", "process"]


def test_recovery_worker_no_process_only_recovers(monkeypatch):
    calls = []

    monkeypatch.setattr(rag_recovery_worker, "recover_stale_jobs_once", lambda stale_after_seconds=None: calls.append("recover") or 1)
    monkeypatch.setattr(rag_recovery_worker, "process_queued_jobs", lambda: calls.append("process") or 1)

    rag_recovery_worker.main(["--once", "--no-process"])

    assert calls == ["recover"]


def test_process_job_resumes_from_existing_chunks_and_embeddings(monkeypatch):
    embedded_texts = []

    def fake_embed_chunks(self, texts, *args, **kwargs):
        embedded_texts.extend(texts)
        return [[0.2] * self.settings.embedding_dimension for _ in texts]

    monkeypatch.setattr("app.workers.rag_ingestion_worker.EmbeddingService.embed_chunks", fake_embed_chunks)

    db = SessionLocal()
    try:
        resource = Resource(
            title="Resume Resource",
            ingestion_status="QUEUED",
            rag_enabled=True,
            storage_path=None,
            resource_metadata={"author": "Tester"},
        )
        db.add(resource)
        db.flush()
        job = RagJobRepository(db).create_job(
            resource_id=resource.resource_id,
            async_backend="db_worker",
            strategy="SEMANTIC_RECURSIVE",
            size=1200,
            overlap=80,
        )
        db.add(
            RagDocumentExtraction(
                resource_id=resource.resource_id,
                job_id=job.job_id,
                parser_name="test",
                extracted_text="Already extracted text.",
                extracted_text_hash_sha256="extract-hash",
                char_count=23,
                token_count=3,
                extraction_metadata={},
            )
        )
        chunks = []
        for index in range(4):
            chunk = RagDocumentChunk(
                chunk_id=f"chunk-{index}",
                resource_id=resource.resource_id,
                job_id=job.job_id,
                chunk_index=index,
                chunk_text=f"Chunk {index} has enough meaningful content for resume testing.",
                chunk_hash_sha256=f"hash-{index}",
                token_count=9,
                char_count=64,
            )
            chunks.append(chunk)
            db.add(chunk)
        for chunk in chunks[:2]:
            db.add(
                RagChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    embedding_provider="openai",
                    embedding_model="text-embedding-3-small",
                    embedding_version="v1",
                    embedding_dimension=1536,
                    vector=[0.1] * 1536,
                )
            )
        db.commit()
        job_id = job.job_id
    finally:
        db.close()

    rag_ingestion_worker.process_job(job_id)

    db = SessionLocal()
    try:
        job = db.get(models.RagIngestionJob, job_id)
        embeddings = db.query(RagChunkEmbedding).order_by(RagChunkEmbedding.chunk_id).all()
        assert job.status == "COMPLETED"
        assert job.embedded_chunks == 4
        assert len(embeddings) == 4
        assert len(embedded_texts) == 2
        assert all("Chunk 0" not in text and "Chunk 1" not in text for text in embedded_texts)
        assert any("Chunk 2" in text for text in embedded_texts)
        assert any("Chunk 3" in text for text in embedded_texts)
    finally:
        db.close()


def test_embedding_input_adds_resource_context_and_cleans_page_artifacts():
    resource = Resource(
        title="Frankenstein",
        resource_metadata={
            "author": "Mary Shelley",
            "category_name": "Scifi",
            "tags": ["classic", "gothic"],
            "description": "A gothic novel.",
        },
    )
    chunk = RagDocumentChunk(
        chunk_id="chunk-1",
        resource_id="resource-1",
        job_id="job-1",
        chunk_index=0,
        chunk_text="[Page 2] Frankenstein18 Letter 1 begins here.\x18",
        chunk_hash_sha256="hash",
        token_count=7,
        char_count=48,
        section_title="Letter 1",
        heading_path=["Letters", "Letter 1"],
        page_start=2,
    )

    embedding_input = EmbeddingInputService().build(resource, chunk)

    assert "Title: Frankenstein" in embedding_input
    assert "Author: Mary Shelley" in embedding_input
    assert "Category: Scifi" in embedding_input
    assert "Tags: classic, gothic" in embedding_input
    assert "Section: Letter 1" in embedding_input
    assert "[Page 2]" not in embedding_input
    assert "\x18" not in embedding_input
