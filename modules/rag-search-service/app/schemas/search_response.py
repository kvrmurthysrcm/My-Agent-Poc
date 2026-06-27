from typing import Any

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    rank: int
    resource_id: str
    chunk_id: str
    title: str
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    snippet: str
    chunk_text: str | None = None
    metadata: dict[str, Any] | None = None
    debug: dict[str, Any] | None = None


class SearchResponse(BaseModel):
    query: str
    original_query: str | None = None
    query_intent: str | None = None
    spelling_normalized: bool = False
    search_mode: str
    top_k: int
    total_results: int
    embedding_provider: str
    embedding_model: str
    results: list[SearchResultItem]
    observability: dict[str, Any] | None = None
