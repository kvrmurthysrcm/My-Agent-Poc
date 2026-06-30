import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import RagIngestError
from app.db.session import get_db
from app.db.models import RagProcessingError, Resource
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.rag_profiling_repository import RagProfilingRepository
from app.repositories.runtime_settings_repository import RuntimeSettingsRepository
from app.schemas.dev_delete_response import DevDeleteResourceResponse
from app.schemas.ingest_response import IngestAcceptedResponse
from app.schemas.ingest_request import IndexingMode
from app.schemas.job_response import JobErrorResponse, JobRetryResponse, JobStatusResponse, ResourceIndexRequest, ResourceIndexResponse
from app.schemas.runtime_settings import GraphRagRuntimeSettingsRequest, GraphRagRuntimeSettingsResponse
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.dev_delete_service import DevDeleteService
from app.services.ingest_service import IngestService
from app.services.metadata_service import MetadataService
from app.utils.file_validation import validate_upload_file
from app.utils.profiling import get_profile_events

router = APIRouter(prefix="/rag", tags=["rag-ingest"])
logger = logging.getLogger("rag_ingest_service.api")


def _require_local_dev(settings: Settings) -> None:
    if settings.app_profile.lower() != "local" or not settings.enable_dev_delete_endpoint:
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/ingest", response_model=IngestAcceptedResponse, status_code=202)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestAcceptedResponse:
    try:
        extension = validate_upload_file(file, settings)
        parsed_metadata = MetadataService().parse(metadata)
        resource_id, job_id = await IngestService(db, settings).create_resource_and_job(file, parsed_metadata, extension)
        dispatcher = JobDispatcherFactory.build(settings, background_tasks)
        dispatcher.dispatch_ingestion_job(job_id, resource_id)
        return IngestAcceptedResponse(resource_id=resource_id, job_id=job_id, status="QUEUED")
    except RagIngestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected ingestion request failure")
        raise HTTPException(status_code=500, detail=f"Unexpected ingestion error: {type(exc).__name__}") from exc


@router.get("/ingest/jobs/{job_id}", response_model=JobStatusResponse)
def get_ingestion_job(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = RagJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    resource = db.get(Resource, job.resource_id)
    profiling = get_profile_events(job.job_id) or RagProfilingRepository(db).list_events(job.job_id)
    return JobStatusResponse(
        job_id=job.job_id,
        resource_id=job.resource_id,
        status=job.status,
        indexing_mode=job.indexing_mode,
        parser_name=resource.parser_name if resource else None,
        total_chunks=job.total_chunks,
        processed_chunks=job.processed_chunks,
        embedded_chunks=job.embedded_chunks,
        graph_entities_count=job.graph_entities_count,
        graph_relationships_count=job.graph_relationships_count,
        failed_chunks=job.failed_chunks,
        started_at=job.started_at,
        completed_at=job.completed_at,
        message=job.progress_message,
        progress_message=job.progress_message,
        error_message=job.error_message,
        profiling=profiling,
    )


@router.get("/ingest/jobs/{job_id}/errors", response_model=list[JobErrorResponse])
def get_ingestion_job_errors(job_id: str, db: Session = Depends(get_db)) -> list[JobErrorResponse]:
    job = RagJobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    rows = db.scalars(
        select(RagProcessingError)
        .where(RagProcessingError.job_id == job_id)
        .order_by(RagProcessingError.created_at.desc())
    ).all()
    return [
        JobErrorResponse(
            error_id=row.error_id,
            job_id=row.job_id,
            resource_id=row.resource_id,
            chunk_id=row.chunk_id,
            stage=row.stage,
            error_type=row.error_type,
            error_message=row.error_message,
            error_details=row.error_details,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/settings/graph-rag", response_model=GraphRagRuntimeSettingsResponse)
def get_graph_rag_runtime_settings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GraphRagRuntimeSettingsResponse:
    values = RuntimeSettingsRepository(db).get_graph_rag_settings(
        settings.graph_rag_entity_batch_size,
        settings.graph_rag_relationship_batch_size,
    )
    return GraphRagRuntimeSettingsResponse(**values)


@router.put("/settings/graph-rag", response_model=GraphRagRuntimeSettingsResponse)
def update_graph_rag_runtime_settings(
    request: GraphRagRuntimeSettingsRequest,
    db: Session = Depends(get_db),
) -> GraphRagRuntimeSettingsResponse:
    values = RuntimeSettingsRepository(db).update_graph_rag_settings(
        request.entity_batch_size,
        request.relationship_batch_size,
    )
    db.commit()
    return GraphRagRuntimeSettingsResponse(
        **values,
        message="Graph RAG runtime settings saved. New Graph RAG jobs will use these values without service restart.",
    )


@router.post("/ingest/resources/{resource_id}/retry", response_model=JobRetryResponse, status_code=202)
def retry_resource_ingestion(
    resource_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobRetryResponse:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    job_repo = RagJobRepository(db)
    job = job_repo.latest_for_resource(resource_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No ingestion job found for resource")
    if job.status in {"PROCESSING", "QUEUED"}:
        raise HTTPException(status_code=409, detail=f"Latest ingestion job is already {job.status}")
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail=f"Latest ingestion job is {job.status}; only FAILED jobs can be retried")

    try:
        job_repo.queue_admin_retry(job)
        resource.ingestion_status = "QUEUED"
        db.commit()
        dispatcher = JobDispatcherFactory.build(settings, background_tasks)
        dispatcher.dispatch_ingestion_job(job.job_id, resource.resource_id)
        return JobRetryResponse(
            resource_id=resource.resource_id,
            job_id=job.job_id,
            status=job.status,
            indexing_mode=job.indexing_mode,
            message="Retry queued. Existing upload, chunking settings, and indexing mode were reused.",
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected ingestion retry failure")
        raise HTTPException(status_code=500, detail=f"Unexpected retry error: {type(exc).__name__}") from exc


@router.post("/ingest/resources/{resource_id}/index", response_model=ResourceIndexResponse, status_code=202)
def index_existing_resource(
    resource_id: str,
    request: ResourceIndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ResourceIndexResponse:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    if request.indexing_mode == IndexingMode.NONE:
        raise HTTPException(status_code=400, detail="indexing_mode must be STANDARD, GRAPH, or BOTH")

    job_repo = RagJobRepository(db)
    latest_job = job_repo.latest_for_resource(resource_id)
    if latest_job and latest_job.status in {"PROCESSING", "QUEUED"}:
        raise HTTPException(status_code=409, detail=f"Latest ingestion job is already {latest_job.status}")

    try:
        chunk_size = latest_job.chunk_size_tokens if latest_job else settings.default_chunk_size_tokens
        chunk_overlap = latest_job.chunk_overlap_tokens if latest_job else settings.default_chunk_overlap_tokens
        chunking_strategy = latest_job.chunking_strategy if latest_job else settings.default_chunking_strategy
        job = job_repo.create_job(
            resource_id=resource.resource_id,
            async_backend=settings.async_backend.value,
            strategy=chunking_strategy,
            size=chunk_size,
            overlap=chunk_overlap,
            indexing_mode=request.indexing_mode.value,
        )
        resource.ingestion_status = "QUEUED"
        db.commit()
        dispatcher = JobDispatcherFactory.build(settings, background_tasks)
        dispatcher.dispatch_ingestion_job(job.job_id, resource.resource_id)
        return ResourceIndexResponse(
            resource_id=resource.resource_id,
            job_id=job.job_id,
            status=job.status,
            indexing_mode=job.indexing_mode,
            message=f"{job.indexing_mode} indexing queued for existing resource.",
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected resource indexing failure")
        raise HTTPException(status_code=500, detail=f"Unexpected indexing error: {type(exc).__name__}") from exc


@router.delete("/dev/resources/{resource_id}", response_model=DevDeleteResourceResponse)
def delete_dev_resource(
    resource_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DevDeleteResourceResponse:
    _require_local_dev(settings)
    try:
        deleted, counts, deleted_file_path = DevDeleteService(db).delete_resource(resource_id, force=force)
        if not deleted:
            raise HTTPException(status_code=404, detail="Resource not found")
        db.commit()
        return DevDeleteResourceResponse(
            resource_id=resource_id,
            deleted=True,
            deleted_file_path=deleted_file_path,
            deleted_counts=counts,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
