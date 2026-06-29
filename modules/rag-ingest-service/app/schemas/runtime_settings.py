from datetime import datetime

from pydantic import BaseModel, Field


class GraphRagRuntimeSettingsRequest(BaseModel):
    entity_batch_size: int = Field(ge=1, le=10)
    relationship_batch_size: int = Field(ge=1, le=10)


class GraphRagRuntimeSettingsResponse(BaseModel):
    entity_batch_size: int
    relationship_batch_size: int
    updated_at: datetime | None = None
    message: str = "Graph RAG runtime settings loaded."
