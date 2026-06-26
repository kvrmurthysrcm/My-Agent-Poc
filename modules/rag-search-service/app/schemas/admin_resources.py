from datetime import datetime

from pydantic import BaseModel, Field


class AdminResourceItem(BaseModel):
    resource_id: str
    title: str
    author: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    ingestion_status: str
    rag_enabled: bool
    file_name: str | None = None
    file_size_bytes: int | None = None
    chunk_count: int = 0
    embedding_count: int = 0
    job_count: int = 0
    latest_job_status: str | None = None
    created_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class AdminResourceListResponse(BaseModel):
    total: int
    resources: list[AdminResourceItem]


class AdminDeleteResourcesRequest(BaseModel):
    resource_ids: list[str] = Field(min_length=1)
    force: bool = False


class AdminDeleteResourceResult(BaseModel):
    resource_id: str
    deleted: bool
    deleted_file_path: str | None = None
    deleted_counts: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class AdminDeleteResourcesResponse(BaseModel):
    requested: int
    deleted: int
    results: list[AdminDeleteResourceResult]
