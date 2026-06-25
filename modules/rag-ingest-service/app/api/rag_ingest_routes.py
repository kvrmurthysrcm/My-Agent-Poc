from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import RagIngestError
from app.db.session import get_db
from app.db.models import Resource
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.rag_profiling_repository import RagProfilingRepository
from app.schemas.dev_delete_response import DevDeleteResourceResponse
from app.schemas.ingest_response import IngestAcceptedResponse
from app.schemas.job_response import JobStatusResponse
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.dev_delete_service import DevDeleteService
from app.services.ingest_service import IngestService
from app.services.metadata_service import MetadataService
from app.utils.file_validation import validate_upload_file
from app.utils.profiling import get_profile_events

router = APIRouter(prefix="/rag", tags=["rag-ingest"])


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
        parser_name=resource.parser_name if resource else None,
        total_chunks=job.total_chunks,
        processed_chunks=job.processed_chunks,
        embedded_chunks=job.embedded_chunks,
        failed_chunks=job.failed_chunks,
        started_at=job.started_at,
        completed_at=job.completed_at,
        message=job.progress_message,
        progress_message=job.progress_message,
        error_message=job.error_message,
        profiling=profiling,
    )


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
