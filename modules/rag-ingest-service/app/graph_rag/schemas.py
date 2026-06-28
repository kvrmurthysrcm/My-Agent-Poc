from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    name: str
    entity_type: str = "UNKNOWN"
    description: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class ExtractedRelationship(BaseModel):
    source_entity: str
    target_entity: str
    relationship_type: str = "RELATED_TO"
    description: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class ChunkGraphExtraction(BaseModel):
    chunk_id: str
    chunk_index: int
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class GraphIndexingResult(BaseModel):
    entity_count: int
    relationship_count: int
    summary_count: int
    community_count: int
