from datetime import datetime

from pydantic import BaseModel


class ProfilingStep(BaseModel):
    step: str
    status: str = "DONE"
    elapsed_ms: float
    details: dict = {}


class JobStatusResponse(BaseModel):
    job_id: str
    resource_id: str
    status: str
    indexing_mode: str = "STANDARD"
    parser_name: str | None = None
    total_chunks: int
    processed_chunks: int
    embedded_chunks: int
    graph_entities_count: int = 0
    graph_relationships_count: int = 0
    failed_chunks: int
    started_at: datetime | None
    completed_at: datetime | None
    message: str | None = None
    progress_message: str | None = None
    error_message: str | None = None
    profiling: list[ProfilingStep] = []
