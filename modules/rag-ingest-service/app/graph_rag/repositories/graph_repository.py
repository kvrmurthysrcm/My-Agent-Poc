from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    RagGraphCommunity,
    RagGraphEntity,
    RagGraphEntityCommunity,
    RagGraphRelationship,
    RagGraphSummary,
)


class GraphRepository:
    def __init__(self, db: Session):
        self.db = db

    def delete_graph_index_by_resource_id(self, resource_id: str) -> None:
        community_ids = list(
            self.db.scalars(select(RagGraphCommunity.community_id).where(RagGraphCommunity.resource_id == resource_id))
        )
        entity_ids = list(self.db.scalars(select(RagGraphEntity.entity_id).where(RagGraphEntity.resource_id == resource_id)))
        if community_ids:
            self.db.execute(delete(RagGraphEntityCommunity).where(RagGraphEntityCommunity.community_id.in_(community_ids)))
        if entity_ids:
            self.db.execute(delete(RagGraphRelationship).where(RagGraphRelationship.source_entity_id.in_(entity_ids)))
            self.db.execute(delete(RagGraphRelationship).where(RagGraphRelationship.target_entity_id.in_(entity_ids)))
        self.db.execute(delete(RagGraphSummary).where(RagGraphSummary.resource_id == resource_id))
        self.db.execute(delete(RagGraphCommunity).where(RagGraphCommunity.resource_id == resource_id))
        self.db.execute(delete(RagGraphEntity).where(RagGraphEntity.resource_id == resource_id))
        self.db.flush()

    def create_entity(self, **fields) -> RagGraphEntity:
        row = RagGraphEntity(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def create_relationship(self, **fields) -> RagGraphRelationship:
        row = RagGraphRelationship(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def create_summary(self, **fields) -> RagGraphSummary:
        row = RagGraphSummary(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def create_community(self, **fields) -> RagGraphCommunity:
        row = RagGraphCommunity(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def add_entity_to_community(self, entity_id: str, community_id: str) -> RagGraphEntityCommunity:
        row = RagGraphEntityCommunity(entity_id=entity_id, community_id=community_id)
        self.db.add(row)
        self.db.flush()
        return row
