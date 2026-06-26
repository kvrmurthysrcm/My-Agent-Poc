from typing import Any

from pydantic import BaseModel, Field


class AnswerSource(BaseModel):
    rank: int
    resource_id: str
    chunk_id: str
    title: str
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    score: float
    snippet: str


class AnswerResponse(BaseModel):
    query: str
    answer: str
    llm_provider: str
    llm_model: str
    search_mode: str
    search_total_results: int
    context_source_count: int
    sources: list[AnswerSource] = Field(default_factory=list)
    raw_search: dict[str, Any] | None = None
