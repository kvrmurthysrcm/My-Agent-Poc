from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChunkingOptions(BaseModel):
    strategy: str = "INTELLIGENT_RECURSIVE"
    chunk_size_tokens: int | None = Field(default=None, ge=100)
    chunk_overlap_tokens: int | None = Field(default=None, ge=0)


class IngestMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    resource_type: str = "DOCUMENT"
    category_name: str | None = None
    business_domain: str | None = None
    source_system: str = "manual_upload"
    author: str | None = None
    language: str = "English"
    publisher: str | None = None
    published_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    created_date_from_file: datetime | None = None
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    chunking: ChunkingOptions = Field(default_factory=ChunkingOptions)
