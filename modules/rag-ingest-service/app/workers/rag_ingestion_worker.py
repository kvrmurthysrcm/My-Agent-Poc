from pathlib import Path

from app.core.config import get_settings
from app.db.models import Resource
from app.db.session import SessionLocal
from app.repositories.rag_chunk_repository import RagChunkRepository
from app.repositories.rag_embedding_repository import RagEmbeddingRepository
from app.repositories.rag_error_repository import RagErrorRepository
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.chunking_service import ChunkingService
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.embedding_service import EmbeddingService
from app.services.text_extraction_service import TextExtractionService
from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens


def process_job(job_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        jobs = RagJobRepository(db)
        job = jobs.get(job_id)
        if job is None:
            return
        resource = db.get(Resource, job.resource_id)
        if resource is None:
            return

        errors = RagErrorRepository(db)
        resources = ResourceRepository(db)
        chunks_repo = RagChunkRepository(db)
        embeddings_repo = RagEmbeddingRepository(db)

        try:
            jobs.mark_processing(job)
            resources.update_status(resource.resource_id, "PROCESSING")
            db.commit()
            extraction = TextExtractionService().extract(path=Path(resource.storage_path), extension=resource.file_extension)
        except Exception as exc:
            _fail(db, jobs, errors, resources, job, resource, "extraction", exc)
            return

        try:
            text_hash = sha256_text(extraction.text)
            chunks_repo.create_extraction(
                resource_id=resource.resource_id,
                job_id=job.job_id,
                parser_name=extraction.parser_name,
                extracted_text=extraction.text,
                extracted_text_hash_sha256=text_hash,
                page_count=extraction.page_count,
                char_count=len(extraction.text),
                token_count=count_tokens(extraction.text),
                extraction_metadata=extraction.metadata,
            )
            resource.parser_name = extraction.parser_name
            resource.extracted_text_hash_sha256 = text_hash

            chunked = ChunkingService().chunk(
                extraction.text,
                chunk_size_tokens=job.chunk_size_tokens,
                chunk_overlap_tokens=job.chunk_overlap_tokens,
            )
            chunk_rows = chunks_repo.create_chunks(
                [
                    {
                        "resource_id": resource.resource_id,
                        "job_id": job.job_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.chunk_text,
                        "chunk_hash_sha256": chunk.chunk_hash_sha256,
                        "token_count": chunk.token_count,
                        "char_count": chunk.char_count,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "section_title": chunk.section_title,
                        "heading_path": chunk.heading_path,
                        "chunk_type": chunk.chunk_type,
                        "chunk_metadata": chunk.metadata,
                    }
                    for chunk in chunked
                ]
            )
            job.total_chunks = len(chunk_rows)
            job.processed_chunks = len(chunk_rows)

            provider = EmbeddingProviderFactory.build(settings)
            vectors = EmbeddingService(provider, settings).embed_chunks([chunk.chunk_text for chunk in chunk_rows])
            embeddings_repo.create_embeddings(
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "embedding_provider": provider.provider_name,
                        "embedding_model": provider.model,
                        "embedding_version": settings.embedding_version,
                        "embedding_dimension": settings.embedding_dimension,
                        "vector": vector,
                    }
                    for chunk, vector in zip(chunk_rows, vectors, strict=False)
                ]
            )
            job.embedded_chunks = len(vectors)
            resources.update_status(resource.resource_id, "READY")
            jobs.mark_completed(job)
            db.commit()
        except Exception as exc:
            _fail(db, jobs, errors, resources, job, resource, "processing", exc)
    finally:
        db.close()


def process_queued_jobs(limit: int | None = None) -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        jobs = RagJobRepository(db)
        queued = jobs.get_queued_jobs(limit or settings.db_worker_batch_size)
        ids = [job.job_id for job in queued]
    finally:
        db.close()

    for job_id in ids:
        process_job(job_id)
    return len(ids)


def _fail(db, jobs, errors, resources, job, resource, stage: str, exc: Exception) -> None:
    errors.record(job.job_id, resource.resource_id, stage, exc)
    jobs.mark_failed(job, str(exc))
    resources.update_status(resource.resource_id, "FAILED")
    db.commit()
