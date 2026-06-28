from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.graph_search_repository import GraphSearchRepository
from app.schemas.graph_search import (
    GraphEntityResult,
    GraphRelationshipResult,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphSummaryResult,
    RelatedChunkResult,
)


class GraphSearchService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repository = GraphSearchRepository(db)

    def search(self, request: GraphSearchRequest) -> GraphSearchResponse:
        entities = self.repository.search_entities(request.query, request.resource_ids, request.top_k) if request.include_entities else []
        relationships = (
            self.repository.search_relationships(request.query, request.resource_ids, request.top_k)
            if request.include_relationships
            else []
        )
        summaries = self.repository.search_summaries(request.query, request.resource_ids, request.top_k) if request.include_summaries else []
        related_chunk_ids = _chunk_ids_from_metadata([*entities, *relationships])
        related_resource_ids = list({str(row["resource_id"]) for row in [*entities, *relationships, *summaries]})
        chunks = self.repository.related_chunks(related_resource_ids, related_chunk_ids, request.top_k)
        return GraphSearchResponse(
            query=request.query,
            top_k=request.top_k,
            matched_entities=[GraphEntityResult(**row) for row in entities],
            matched_relationships=[GraphRelationshipResult(**row) for row in relationships],
            graph_summaries=[GraphSummaryResult(**row) for row in summaries],
            related_chunks=[RelatedChunkResult(**row) for row in chunks],
        )


def _chunk_ids_from_metadata(rows: list[dict]) -> list[str]:
    chunk_ids: set[str] = set()
    for row in rows:
        metadata = row.get("metadata") or {}
        for chunk_id in metadata.get("chunk_ids") or []:
            chunk_ids.add(str(chunk_id))
    return list(chunk_ids)
