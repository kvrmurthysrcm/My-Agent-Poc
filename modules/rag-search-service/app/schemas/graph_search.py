from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.search_response import SearchResponse


class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    resource_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(10, ge=1, le=50)
    include_entities: bool = True
    include_relationships: bool = True
    include_summaries: bool = True

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class GraphEntityResult(BaseModel):
    entity_id: str
    resource_id: str
    name: str
    normalized_name: str
    entity_type: str
    description: str | None = None
    confidence_score: float | None = None
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    resource_title: str | None = None


class GraphRelationshipResult(BaseModel):
    relationship_id: str
    resource_id: str
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    relationship_type: str
    description: str | None = None
    confidence_score: float | None = None
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    resource_title: str | None = None


class GraphSummaryResult(BaseModel):
    summary_id: str
    resource_id: str
    summary_type: str
    summary_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    resource_title: str | None = None


class RelatedChunkResult(BaseModel):
    chunk_id: str
    resource_id: str
    chunk_index: int
    snippet: str
    resource_title: str | None = None


class GraphSearchResponse(BaseModel):
    query: str
    top_k: int
    matched_entities: list[GraphEntityResult] = Field(default_factory=list)
    matched_relationships: list[GraphRelationshipResult] = Field(default_factory=list)
    graph_summaries: list[GraphSummaryResult] = Field(default_factory=list)
    related_chunks: list[RelatedChunkResult] = Field(default_factory=list)


class CombinedSearchResponse(BaseModel):
    standard_results: SearchResponse
    graph_results: GraphSearchResponse
