from pathlib import Path
import argparse
import logging
import socket
from time import perf_counter, sleep
from uuid import uuid4

from app.core.config import get_settings
from app.db.models import RagDocumentChunk, Resource
from app.db.session import SessionLocal
from app.graph_rag.services.graph_indexing_service import GraphIndexingService
from app.repositories.rag_chunk_repository import RagChunkRepository
from app.repositories.rag_embedding_repository import RagEmbeddingRepository
from app.repositories.rag_error_repository import RagErrorRepository
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.rag_profiling_repository import RagProfilingRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.chunking_service import ChunkingService
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.embedding_input_service import EmbeddingInputService
from app.services.embedding_service import EmbeddingService
from app.services.text_extraction_service import TextExtractionService
from app.utils.hashing import sha256_text
from app.utils.profiling import clear_profile_events, get_profile_events, profile_step, record_profile_event
from app.utils.token_counter import count_tokens

logger = logging.getLogger("rag_ingestion_worker")


def process_job(job_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    job_started = None
    job_resource_id = None
    job_started_at = perf_counter()
    try:
        jobs = RagJobRepository(db)
        job = jobs.get(job_id)
        if job is None:
            return
        resource = db.get(Resource, job.resource_id)
        if resource is None:
            return
        job_resource_id = resource.resource_id
        clear_profile_events(job.job_id)

        errors = RagErrorRepository(db)
        resources = ResourceRepository(db)
        chunks_repo = RagChunkRepository(db)
        embeddings_repo = RagEmbeddingRepository(db)
        job_started = job.job_id

        try:
            with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "db_mark_processing"):
                jobs.mark_processing(job, worker_id=job.worker_id)
                jobs.update_progress(job, "Starting text extraction")
                resources.update_status(resource.resource_id, "PROCESSING")
                db.commit()

            existing_extraction = chunks_repo.get_extraction_for_job(job.job_id)
            if existing_extraction:
                logger.info("RAG job %s resource %s: reusing existing extraction", job.job_id, resource.resource_id)
                extracted_text = existing_extraction.extracted_text
                extraction_parser_name = existing_extraction.parser_name
                extraction_page_count = existing_extraction.page_count
                extraction_metadata = existing_extraction.extraction_metadata
                text_hash = existing_extraction.extracted_text_hash_sha256
                extraction_token_count = existing_extraction.token_count
            else:
                if not resource.storage_path:
                    raise ValueError("Resource storage_path is missing and no extraction exists to resume from")
                logger.info("RAG job %s resource %s: extracting text from %s", job.job_id, resource.resource_id, resource.file_name)
                with profile_step(
                    settings.profiling,
                    logger,
                    job.job_id,
                    resource.resource_id,
                    "file_parse",
                    parser_extension=resource.file_extension,
                    configured_pdf_parser=settings.pdf_parser if resource.file_extension == ".pdf" else None,
                    file_name=resource.file_name,
                    file_size_bytes=resource.file_size_bytes,
                ):
                    extraction = TextExtractionService().extract(path=Path(resource.storage_path), extension=resource.file_extension)
                if not extraction.text.strip():
                    raise ValueError("Extracted text is empty")
                extracted_text = extraction.text
                extraction_parser_name = extraction.parser_name
                extraction_page_count = extraction.page_count
                extraction_metadata = extraction.metadata
                text_hash = sha256_text(extracted_text)
                extraction_token_count = count_tokens(extracted_text)
                if settings.profiling:
                    logger.info(
                        "PROFILE job_id=%s resource_id=%s step=file_parser_selected parser_name=%s",
                        job.job_id,
                        resource.resource_id,
                        extraction_parser_name,
                    )
        except Exception as exc:
            _fail(db, jobs, errors, resources, job, resource, "extraction", exc)
            return

        try:
            with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "db_store_extraction"):
                jobs.update_progress(job, "Text extracted; storing extraction summary")
                db.commit()
                if not existing_extraction:
                    chunks_repo.create_extraction(
                        resource_id=resource.resource_id,
                        job_id=job.job_id,
                        parser_name=extraction_parser_name,
                        extracted_text=extracted_text,
                        extracted_text_hash_sha256=text_hash,
                        page_count=extraction_page_count,
                        char_count=len(extracted_text),
                        token_count=extraction_token_count,
                        extraction_metadata=extraction_metadata,
                    )
                resource.parser_name = extraction_parser_name
                resource.extracted_text_hash_sha256 = text_hash

            with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "db_update_chunking_status"):
                jobs.update_progress(job, "Chunking extracted text")
                db.commit()
            logger.info(
                "RAG job %s resource %s: extracted chars=%s tokens=%s parser=%s",
                job.job_id,
                resource.resource_id,
                len(extracted_text),
                extraction_token_count,
                extraction_parser_name,
            )
            chunk_rows = chunks_repo.list_chunks_for_job(job.job_id)
            if chunk_rows:
                logger.info("RAG job %s resource %s: reusing existing chunks=%s", job.job_id, resource.resource_id, len(chunk_rows))
            else:
                with profile_step(
                    settings.profiling,
                    logger,
                    job.job_id,
                    resource.resource_id,
                    "chunking",
                    chunk_size_tokens=job.chunk_size_tokens,
                    chunk_overlap_tokens=job.chunk_overlap_tokens,
                    chunking_strategy=job.chunking_strategy,
                    text_chars=len(extracted_text),
                    text_tokens=extraction_token_count,
                ):
                    chunked = ChunkingService().chunk(
                        extracted_text,
                        chunk_size_tokens=job.chunk_size_tokens,
                        chunk_overlap_tokens=job.chunk_overlap_tokens,
                        strategy=job.chunking_strategy,
                    )
                if not chunked:
                    raise ValueError("Chunking produced zero chunks")
                _record_chunk_diagnostics(settings, job, resource, chunked)
                with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "db_store_chunks", chunk_count=len(chunked)):
                    job.total_chunks = len(chunked)
                    db.commit()
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
                    jobs.update_progress(job, _next_indexing_message(job.indexing_mode, len(chunk_rows)))
                    db.commit()
            if not chunk_rows:
                raise ValueError("No chunks available for indexing")
            if job.total_chunks != len(chunk_rows) or job.processed_chunks != len(chunk_rows):
                job.total_chunks = len(chunk_rows)
                job.processed_chunks = len(chunk_rows)
                jobs.update_progress(job, _next_indexing_message(job.indexing_mode, len(chunk_rows)))
                db.commit()
            logger.info("RAG job %s resource %s: created chunks=%s", job.job_id, resource.resource_id, len(chunk_rows))

            should_create_embeddings = _should_create_chunk_embeddings(job.indexing_mode, settings.graph_rag_create_chunk_embeddings)
            if should_create_embeddings:
                with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "embedding_provider_factory"):
                    provider = EmbeddingProviderFactory.build(settings)
                with profile_step(
                    settings.profiling,
                    logger,
                    job.job_id,
                    resource.resource_id,
                    "embedding_generation",
                    embedding_provider=provider.provider_name,
                    embedding_model=provider.model,
                    embedding_batch_size=settings.embedding_batch_size,
                    embedding_concurrency=settings.embedding_concurrency,
                    chunk_count=len(chunk_rows),
                    embedding_input_context_enabled=True,
                ):
                    embedded_count = _embed_missing_chunks(
                        db=db,
                        settings=settings,
                        jobs=jobs,
                        embeddings_repo=embeddings_repo,
                        job=job,
                        resource=resource,
                        chunk_rows=chunk_rows,
                        provider=provider,
                    )
                logger.info(
                    "RAG job %s resource %s: generated embeddings=%s provider=%s model=%s",
                    job.job_id,
                    resource.resource_id,
                    embedded_count,
                    provider.provider_name,
                    provider.model,
                )
            else:
                job.embedded_chunks = 0
                jobs.update_progress(job, _skip_embedding_message(job.indexing_mode))
                db.commit()

            if job.indexing_mode in {"GRAPH", "BOTH"}:
                with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "graph_indexing", chunk_count=len(chunk_rows)):
                    graph_result = GraphIndexingService(db, settings).index_resource(job, resource, chunk_rows, jobs)
                    db.commit()
                logger.info(
                    "RAG job %s resource %s: graph entities=%s relationships=%s",
                    job.job_id,
                    resource.resource_id,
                    graph_result.entity_count,
                    graph_result.relationship_count,
                )
            if settings.delete_original_file_after_ingestion:
                with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "file_cleanup"):
                    try:
                        _delete_original_file(resource)
                    except Exception as exc:
                        errors.record(job.job_id, resource.resource_id, "cleanup", exc)
            with profile_step(settings.profiling, logger, job.job_id, resource.resource_id, "db_finalize_job"):
                resources.update_status(resource.resource_id, "READY")
                jobs.mark_completed(job)
                db.commit()
        except Exception as exc:
            _fail(db, jobs, errors, resources, job, resource, "processing", exc)
    finally:
        if settings.profiling and job_started:
            record_profile_event(
                settings.profiling,
                logger,
                job_started,
                job_resource_id or "",
                "job_total",
                "DONE",
                (perf_counter() - job_started_at) * 1000,
            )
            if job_resource_id:
                try:
                    RagProfilingRepository(db).replace_events(job_started, job_resource_id, get_profile_events(job_started))
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Unable to persist profiling events for job %s", job_started)
        db.close()


def _embed_missing_chunks(
    db,
    settings,
    jobs: RagJobRepository,
    embeddings_repo: RagEmbeddingRepository,
    job,
    resource: Resource,
    chunk_rows: list[RagDocumentChunk],
    provider,
) -> int:
    chunk_ids = [chunk.chunk_id for chunk in chunk_rows]
    existing_chunk_ids = embeddings_repo.existing_chunk_ids(
        chunk_ids=chunk_ids,
        provider=provider.provider_name,
        model=provider.model,
        version=settings.embedding_version,
    )
    job.embedded_chunks = len(existing_chunk_ids)
    jobs.update_progress(job, f"Embedding resume check: {job.embedded_chunks}/{len(chunk_rows)} chunks already embedded")
    db.commit()

    if len(existing_chunk_ids) == len(chunk_rows):
        jobs.update_progress(job, "All chunk embeddings already exist; finalizing ingestion")
        db.commit()
        return len(existing_chunk_ids)

    embedding_service = EmbeddingService(provider, settings)
    pending_chunks = [chunk for chunk in chunk_rows if chunk.chunk_id not in existing_chunk_ids]
    batch_size = settings.embedding_batch_size
    batch_count = (len(pending_chunks) + batch_size - 1) // batch_size

    for batch_index, start in enumerate(range(0, len(pending_chunks), batch_size), start=1):
        batch_chunks = pending_chunks[start : start + batch_size]
        current_existing = embeddings_repo.existing_chunk_ids(
            chunk_ids=[chunk.chunk_id for chunk in batch_chunks],
            provider=provider.provider_name,
            model=provider.model,
            version=settings.embedding_version,
        )
        batch_chunks = [chunk for chunk in batch_chunks if chunk.chunk_id not in current_existing]
        if not batch_chunks:
            continue

        jobs.update_progress(
            job,
            f"Embedding batch {batch_index}/{batch_count}; embedded {job.embedded_chunks}/{len(chunk_rows)} chunks",
        )
        jobs.heartbeat(job)
        db.commit()

        embedding_texts = [EmbeddingInputService().build(resource, chunk) for chunk in batch_chunks]
        vectors = embedding_service.embed_chunks(
            embedding_texts,
            batch_size=len(batch_chunks),
            on_batch_profile=lambda event: record_profile_event(
                settings.profiling,
                logger,
                job.job_id,
                f"{resource.resource_id}",
                f"embedding_batch_{batch_index}_attempt_{event.get('attempt', 1)}",
                event["status"],
                event["elapsed_ms"],
                batch_index=batch_index,
                batch_count=batch_count,
                batch_size=event["batch_size"],
                attempt=event.get("attempt", 1),
                error_message=event.get("error_message"),
                embedding_provider=provider.provider_name,
                embedding_model=provider.model,
            ),
        )
        if not vectors:
            raise ValueError("Embedding provider returned zero embeddings")
        if len(vectors) != len(batch_chunks):
            raise ValueError(f"Embedding count mismatch: chunks={len(batch_chunks)}, vectors={len(vectors)}")

        with profile_step(
            settings.profiling,
            logger,
            job.job_id,
            resource.resource_id,
            "db_store_embedding_batch",
            batch_index=batch_index,
            batch_count=batch_count,
            embedding_count=len(vectors),
        ):
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
                    for chunk, vector in zip(batch_chunks, vectors, strict=False)
                ]
            )
            job.embedded_chunks += len(vectors)
            jobs.update_progress(job, f"Embedded {job.embedded_chunks}/{len(chunk_rows)} chunks")
            jobs.heartbeat(job)
            db.commit()

    final_existing_count = len(
        embeddings_repo.existing_chunk_ids(
            chunk_ids=chunk_ids,
            provider=provider.provider_name,
            model=provider.model,
            version=settings.embedding_version,
        )
    )
    job.embedded_chunks = final_existing_count
    if final_existing_count != len(chunk_rows):
        raise ValueError(f"Embedding count mismatch after resume: chunks={len(chunk_rows)}, embedded={final_existing_count}")
    jobs.update_progress(job, "Finalizing ingestion")
    db.commit()
    return final_existing_count


def _next_indexing_message(indexing_mode: str, chunk_count: int) -> str:
    if indexing_mode == "NONE":
        return f"Created {chunk_count} chunks; indexing disabled"
    if indexing_mode == "GRAPH":
        return f"Created {chunk_count} chunks; extracting graph"
    if indexing_mode == "BOTH":
        return f"Created {chunk_count} chunks; generating embeddings and extracting graph"
    return f"Created {chunk_count} chunks; generating embeddings"


def _should_create_chunk_embeddings(indexing_mode: str, graph_rag_create_chunk_embeddings: bool) -> bool:
    if indexing_mode == "NONE":
        return False
    if indexing_mode in {"STANDARD", "BOTH"}:
        return True
    return indexing_mode == "GRAPH" and graph_rag_create_chunk_embeddings


def _skip_embedding_message(indexing_mode: str) -> str:
    if indexing_mode == "NONE":
        return "Indexing disabled; chunks saved without embeddings or graph"
    return "Graph-only mode selected; chunk embeddings disabled"


def process_queued_jobs(limit: int | None = None) -> int:
    settings = get_settings()
    worker_id = f"{socket.gethostname()}-{uuid4()}"
    max_jobs = limit or settings.db_worker_batch_size
    processed = 0
    for _ in range(max_jobs):
        db = SessionLocal()
        try:
            jobs = RagJobRepository(db)
            jobs.recover_stale_processing_jobs(stale_after_seconds=settings.recovery_stale_after_seconds)
            queued = jobs.claim_queued_jobs(1, worker_id=worker_id)
            ids = [job.job_id for job in queued]
            db.commit()
        finally:
            db.close()
        if not ids:
            break
        process_job(ids[0])
        processed += 1
    return processed


def run_worker(once: bool = False) -> None:
    settings = get_settings()
    logger.info(
        "Starting RAG DB worker once=%s poll_interval_seconds=%s batch_size=%s",
        once,
        settings.db_worker_poll_interval_seconds,
        settings.db_worker_batch_size,
    )
    while True:
        processed = process_queued_jobs()
        logger.info("RAG DB worker processed %s queued job(s)", processed)
        if once:
            return
        sleep(settings.db_worker_poll_interval_seconds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the RAG ingestion DB worker")
    parser.add_argument("--once", action="store_true", help="Process one polling batch and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        run_worker(once=args.once)
    except KeyboardInterrupt:
        logger.info("RAG DB worker stopped")


def _fail(db, jobs, errors, resources, job, resource, stage: str, exc: Exception) -> None:
    errors.record(job.job_id, resource.resource_id, stage, exc)
    jobs.mark_failed(job, str(exc))
    resources.update_status(resource.resource_id, "FAILED")
    db.commit()


def _delete_original_file(resource: Resource) -> None:
    if not resource.storage_path:
        return

    original_path = Path(resource.storage_path)
    if original_path.exists() and original_path.is_file():
        original_path.unlink()

    parent = original_path.parent
    try:
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass

    resource.storage_path = None
    resource.file_url = None


def _record_chunk_diagnostics(settings, job, resource, chunks) -> None:
    if not chunks:
        record_profile_event(
            settings.profiling,
            logger,
            job.job_id,
            resource.resource_id,
            "chunk_diagnostics",
            "DONE",
            0,
            chunk_count=0,
        )
        return

    token_counts = [chunk.token_count for chunk in chunks]
    type_counts: dict[str, int] = {}
    for chunk in chunks:
        type_counts[chunk.chunk_type] = type_counts.get(chunk.chunk_type, 0) + 1

    record_profile_event(
        settings.profiling,
        logger,
        job.job_id,
        resource.resource_id,
        "chunk_diagnostics",
        "DONE",
        0,
        chunk_count=len(chunks),
        min_chunk_tokens=min(token_counts),
        max_chunk_tokens=max(token_counts),
        avg_chunk_tokens=round(sum(token_counts) / len(token_counts), 2),
        **{f"{chunk_type}_chunks": count for chunk_type, count in type_counts.items()},
    )


if __name__ == "__main__":
    main()
