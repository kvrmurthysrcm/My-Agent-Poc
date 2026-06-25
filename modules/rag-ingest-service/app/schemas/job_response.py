from datetime import datetime

from pydantic import BaseModel


class ProfilingStep(BaseModel):
    step: str
    elapsed_ms: float
    details: dict = {}


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
    message: str | None = None
    error_message: str | None = None
    profiling: list[ProfilingStep] = []
