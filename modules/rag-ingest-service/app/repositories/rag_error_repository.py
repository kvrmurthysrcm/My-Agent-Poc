from sqlalchemy.orm import Session
import traceback

from app.db.models import RagProcessingError


class RagErrorRepository:
    def __init__(self, db: Session):
        self.db = db

    def record(self, job_id: str, resource_id: str, stage: str, error: Exception, chunk_id: str | None = None) -> None:
        self.db.add(
            RagProcessingError(
                job_id=job_id,
                resource_id=resource_id,
                chunk_id=chunk_id,
                stage=stage,
                error_type=type(error).__name__,
                error_message=str(error),
                error_details={
                    "exception_module": type(error).__module__,
                    "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__))[-12000:],
                },
            )
        )
        self.db.flush()
