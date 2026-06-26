from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RagIngestionJob, Resource


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
        now = datetime.now(UTC).replace(tzinfo=None)
        statement = (
            select(RagIngestionJob)
            .where(RagIngestionJob.status == "QUEUED")
            .where((RagIngestionJob.next_retry_at.is_(None)) | (RagIngestionJob.next_retry_at <= now))
            .order_by(RagIngestionJob.created_at)
            .limit(limit)
        )
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        return list(self.db.scalars(statement))

    def claim_queued_jobs(self, limit: int, worker_id: str) -> list[RagIngestionJob]:
        jobs = self.get_queued_jobs(limit)
        for job in jobs:
            self.mark_processing(job, worker_id=worker_id)
            job.progress_message = "Job claimed by DB worker"
        self.db.flush()
        return jobs

    def mark_processing(self, job: RagIngestionJob, worker_id: str | None = None) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        job.status = "PROCESSING"
        job.started_at = job.started_at or now
        job.worker_id = worker_id
        job.locked_at = now
        job.heartbeat_at = now
        self.db.flush()

    def update_progress(self, job: RagIngestionJob, message: str) -> None:
        job.progress_message = message[:4000]
        self.db.flush()

    def mark_completed(self, job: RagIngestionJob) -> None:
        job.status = "COMPLETED"
        job.progress_message = "Ingestion completed"
        job.error_message = None
        job.worker_id = None
        job.locked_at = None
        job.heartbeat_at = None
        job.next_retry_at = None
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()

    def mark_failed(self, job: RagIngestionJob, message: str) -> None:
        job.status = "FAILED"
        job.progress_message = "Ingestion failed"
        job.error_message = message[:4000]
        job.worker_id = None
        job.locked_at = None
        job.heartbeat_at = None
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()

    def mark_retry_or_failed(self, job: RagIngestionJob, message: str, retry_delay_seconds: int = 60) -> None:
        job.retry_count += 1
        job.error_message = message[:4000]
        job.worker_id = None
        job.locked_at = None
        job.heartbeat_at = None
        if job.retry_count > job.max_retries:
            self.mark_failed(job, message)
            return
        job.status = "QUEUED"
        job.progress_message = f"Retry scheduled after failure {job.retry_count}/{job.max_retries}"
        job.next_retry_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=retry_delay_seconds * job.retry_count)
        self.db.flush()

    def heartbeat(self, job: RagIngestionJob) -> None:
        job.heartbeat_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.flush()

    def recover_stale_processing_jobs(self, stale_after_seconds: int = 900) -> int:
        stale_before = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=stale_after_seconds)
        jobs = list(
            self.db.scalars(
                select(RagIngestionJob)
                .where(RagIngestionJob.status == "PROCESSING")
                .where((RagIngestionJob.heartbeat_at.is_(None)) | (RagIngestionJob.heartbeat_at < stale_before))
            )
        )
        for job in jobs:
            self.mark_retry_or_failed(job, "Recovered stale PROCESSING job")
            resource = self.db.get(Resource, job.resource_id)
            if resource:
                resource.ingestion_status = "QUEUED" if job.status == "QUEUED" else "FAILED"
                self.db.flush()
        return len(jobs)
