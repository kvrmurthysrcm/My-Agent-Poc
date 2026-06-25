from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import RagIngestError
from app.db.session import get_db
from app.repositories.rag_job_repository import RagJobRepository
from app.schemas.ingest_response import IngestAcceptedResponse
from app.schemas.job_response import JobStatusResponse
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.ingest_service import IngestService
from app.services.metadata_service import MetadataService
from app.utils.file_validation import validate_upload_file
from app.utils.profiling import get_profile_events

router = APIRouter(prefix="/rag", tags=["rag-ingest"])


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
    return JobStatusResponse(
        job_id=job.job_id,
        resource_id=job.resource_id,
        status=job.status,
        total_chunks=job.total_chunks,
        processed_chunks=job.processed_chunks,
        embedded_chunks=job.embedded_chunks,
        failed_chunks=job.failed_chunks,
        started_at=job.started_at,
        completed_at=job.completed_at,
        message=job.error_message if job.status != "FAILED" else None,
        error_message=job.error_message,
        profiling=get_profile_events(job.job_id),
    )
