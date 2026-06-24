from datetime import datetime

from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    job_id: str
    resource_id: str
    status: str
    total_chunks: int
    processed_chunks: int
    embedded_chunks: int
    failed_chunks: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None = None
