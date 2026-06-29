from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class IndexingMode(StrEnum):
    NONE = "NONE"
    STANDARD = "STANDARD"
    GRAPH = "GRAPH"
    BOTH = "BOTH"


class ChunkingOptions(BaseModel):
    strategy: str | None = None
    chunk_size_tokens: int | None = Field(default=None, ge=100)
    chunk_overlap_tokens: int | None = Field(default=None, ge=0)

    @field_validator("strategy")
    @classmethod
    def normalize_strategy(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in {"INTELLIGENT_RECURSIVE", "SEMANTIC_RECURSIVE"}:
            raise ValueError("chunking.strategy must be INTELLIGENT_RECURSIVE or SEMANTIC_RECURSIVE")
        return normalized


class IngestMetadata(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    resource_type: str = "DOCUMENT"
    category_name: str | None = None
    business_domain: str | None = None
    source_system: str = "manual_upload"
    author: str | None = None
    language: str | None = None
    publisher: str | None = None
    published_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    created_date_from_file: datetime | None = None
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    chunking: ChunkingOptions = Field(default_factory=ChunkingOptions)
    indexing_mode: IndexingMode = IndexingMode.STANDARD
