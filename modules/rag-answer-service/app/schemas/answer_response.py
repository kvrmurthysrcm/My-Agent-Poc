from typing import Any, Literal

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
    answer_status: Literal["answered", "insufficient_context"] = "answered"
    answer_mode: str = "concise"
    llm_provider: str
    llm_model: str
    search_mode: str
    search_total_results: int
    context_source_count: int
    cited_source_ranks: list[int] = Field(default_factory=list)
    citation_verification: dict[str, Any] = Field(default_factory=dict)
    sources: list[AnswerSource] = Field(default_factory=list)
    raw_search: dict[str, Any] | None = None
    raw_prompt: str | None = None
