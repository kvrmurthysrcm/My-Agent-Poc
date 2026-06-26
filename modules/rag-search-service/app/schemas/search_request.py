from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SearchMode = Literal["vector", "keyword", "hybrid"]


class SearchFilters(BaseModel):
    resource_id: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    search_mode: SearchMode | None = None
    top_k: int | None = Field(None, ge=1)
    min_score: float | None = Field(None, ge=0, le=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    include_metadata: bool = True
    include_chunk_text: bool | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized
