from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RagIngestionJob


class RagJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, resource_id: str, async_backend: str, strategy: str, size: int, overlap: int) -> RagIngestionJob:
        job = RagIngestionJob(
            resource_id=resource_id,
            status="QUEUED",
            async_backend=async_backend,
            chunking_strategy=strategy,
            chunk_size_tokens=size,
            chunk_overlap_tokens=overlap,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: str) -> RagIngestionJob | None:
        return self.db.get(RagIngestionJob, job_id)

    def get_queued_jobs(self, limit: int) -> list[RagIngestionJob]:
        return list(
            self.db.scalars(
                select(RagIngestionJob)
                .where(RagIngestionJob.status == "QUEUED")
                .order_by(RagIngestionJob.created_at)
                .limit(limit)
            )
        )

    def mark_processing(self, job: RagIngestionJob) -> None:
        job.status = "PROCESSING"
        job.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()

    def update_progress(self, job: RagIngestionJob, message: str) -> None:
        job.error_message = message[:4000]
        self.db.flush()

    def mark_completed(self, job: RagIngestionJob) -> None:
        job.status = "COMPLETED"
        job.error_message = None
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()

    def mark_failed(self, job: RagIngestionJob, message: str) -> None:
        job.status = "FAILED"
        job.error_message = message[:4000]
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()
