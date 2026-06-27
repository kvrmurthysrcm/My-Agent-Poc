from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SearchMode = Literal["vector", "keyword", "hybrid"]
AnswerMode = Literal["concise", "detailed", "quote-backed"]


class AnswerFilters(BaseModel):
    resource_id: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    search_mode: SearchMode = "hybrid"
    top_k: int | None = Field(None, ge=1, le=50)
    context_top_k: int | None = Field(None, ge=1, le=20)
    filters: AnswerFilters = Field(default_factory=AnswerFilters)
    include_sources: bool | None = None
    answer_mode: AnswerMode = "concise"
    include_raw_prompt: bool = False
    system_instruction: str | None = Field(None, max_length=2000)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized
