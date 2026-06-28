import re
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import RagDocumentChunk, RagIngestionJob, Resource
from app.graph_rag.repositories.graph_repository import GraphRepository
from app.graph_rag.schemas import ChunkGraphExtraction, ExtractedEntity, ExtractedRelationship, GraphIndexingResult
from app.graph_rag.services.entity_extraction_service import EntityExtractionService
from app.graph_rag.services.graph_summary_service import GraphSummaryService
from app.graph_rag.services.ollama_generation_client import OllamaGenerationClient
from app.graph_rag.services.relationship_extraction_service import RelationshipExtractionService
from app.repositories.rag_job_repository import RagJobRepository


class GraphIndexingService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        llm = OllamaGenerationClient(settings)
        self.entities = EntityExtractionService(llm)
        self.relationships = RelationshipExtractionService(llm)
        self.summaries = GraphSummaryService(llm)
        self.repository = GraphRepository(db)

    def index_resource(
        self,
        job: RagIngestionJob,
        resource: Resource,
        chunks: list[RagDocumentChunk],
        jobs: RagJobRepository,
    ) -> GraphIndexingResult:
        self.repository.delete_graph_index_by_resource_id(resource.resource_id)
        jobs.update_progress(job, "Graph entity extraction started")
        self.db.commit()

        extracted: list[ChunkGraphExtraction] = []
        for index, chunk in enumerate(chunks, start=1):
            jobs.update_progress(job, f"Graph extraction chunk {index}/{len(chunks)}")
            jobs.heartbeat(job)
            self.db.commit()
            entities = self.entities.extract(chunk.chunk_text)
            relationships = self.relationships.extract(chunk.chunk_text, entities)
            extracted.append(
                ChunkGraphExtraction(
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    entities=entities,
                    relationships=relationships,
                )
            )

        jobs.update_progress(job, "Graph resource consolidation started")
        self.db.commit()
        canonical_entities = self._consolidate_entities(extracted)
        entity_rows = {}
        for key, payload in canonical_entities.items():
            row = self.repository.create_entity(
                resource_id=resource.resource_id,
                chunk_id=None,
                name=payload["name"],
                normalized_name=key,
                entity_type=payload["entity_type"],
                description=payload.get("description"),
                confidence_score=payload.get("confidence_score"),
                metadata_json={
                    "chunk_ids": sorted(payload["chunk_ids"]),
                    "mentions": payload["mentions"],
                    "source": "local_mistral_chunk_extraction",
                },
            )
            entity_rows[key] = row

        relationship_payloads = self._consolidate_relationships(extracted, canonical_entities)
        relationship_rows = []
        for payload in relationship_payloads:
            source = entity_rows.get(payload["source_key"])
            target = entity_rows.get(payload["target_key"])
            if source is None or target is None or source.entity_id == target.entity_id:
                continue
            relationship_rows.append(
                self.repository.create_relationship(
                    resource_id=resource.resource_id,
                    source_entity_id=source.entity_id,
                    target_entity_id=target.entity_id,
                    relationship_type=payload["relationship_type"],
                    description=payload.get("description"),
                    confidence_score=payload.get("confidence_score"),
                    chunk_id=None,
                    metadata_json={
                        "chunk_ids": sorted(payload["chunk_ids"]),
                        "mention_count": payload["mention_count"],
                        "source": "local_mistral_chunk_extraction",
                    },
                )
            )

        facts = self._compact_facts(canonical_entities, relationship_payloads)
        summary_text = self.summaries.summarize_resource(facts) if canonical_entities else "No graph entities were extracted."
        self.repository.create_summary(
            resource_id=resource.resource_id,
            summary_type="RESOURCE_GRAPH",
            summary_text=summary_text,
            metadata_json={"entity_count": len(entity_rows), "relationship_count": len(relationship_rows)},
        )

        community_count = self._create_communities(resource.resource_id, entity_rows, relationship_payloads)
        job.graph_entities_count = len(entity_rows)
        job.graph_relationships_count = len(relationship_rows)
        jobs.update_progress(job, "Graph indexing completed")
        self.db.flush()
        return GraphIndexingResult(
            entity_count=len(entity_rows),
            relationship_count=len(relationship_rows),
            summary_count=1,
            community_count=community_count,
        )

    def _consolidate_entities(self, extracted: list[ChunkGraphExtraction]) -> dict[str, dict]:
        canonical: dict[str, dict] = {}
        for chunk in extracted:
            for entity in chunk.entities:
                key = normalize_name(entity.name)
                if not key:
                    continue
                existing = canonical.setdefault(
                    key,
                    {
                        "name": entity.name.strip(),
                        "entity_type": normalize_type(entity.entity_type, "UNKNOWN"),
                        "description": entity.description,
                        "confidence_score": entity.confidence_score,
                        "chunk_ids": set(),
                        "mentions": [],
                    },
                )
                existing["chunk_ids"].add(chunk.chunk_id)
                existing["mentions"].append({"chunk_id": chunk.chunk_id, "chunk_index": chunk.chunk_index, "name": entity.name})
                if entity.confidence_score is not None:
                    current = existing.get("confidence_score")
                    existing["confidence_score"] = max(float(current or 0), float(entity.confidence_score))
                if not existing.get("description") and entity.description:
                    existing["description"] = entity.description
                if existing["entity_type"] == "UNKNOWN" and entity.entity_type:
                    existing["entity_type"] = normalize_type(entity.entity_type, "UNKNOWN")
        return canonical

    def _consolidate_relationships(self, extracted: list[ChunkGraphExtraction], entities: dict[str, dict]) -> list[dict]:
        merged: dict[tuple[str, str, str], dict] = {}
        for chunk in extracted:
            for relationship in chunk.relationships:
                source_key = normalize_name(relationship.source_entity)
                target_key = normalize_name(relationship.target_entity)
                if source_key not in entities or target_key not in entities or source_key == target_key:
                    continue
                relationship_type = normalize_type(relationship.relationship_type, "RELATED_TO")
                key = (source_key, target_key, relationship_type)
                existing = merged.setdefault(
                    key,
                    {
                        "source_key": source_key,
                        "target_key": target_key,
                        "relationship_type": relationship_type,
                        "description": relationship.description,
                        "confidence_score": relationship.confidence_score,
                        "chunk_ids": set(),
                        "mention_count": 0,
                    },
                )
                existing["chunk_ids"].add(chunk.chunk_id)
                existing["mention_count"] += 1
                if relationship.confidence_score is not None:
                    current = existing.get("confidence_score")
                    existing["confidence_score"] = max(float(current or 0), float(relationship.confidence_score))
                if not existing.get("description") and relationship.description:
                    existing["description"] = relationship.description
        return list(merged.values())

    def _compact_facts(self, entities: dict[str, dict], relationships: list[dict]) -> dict:
        return {
            "entities": [
                {
                    "name": payload["name"],
                    "normalized_name": key,
                    "entity_type": payload["entity_type"],
                    "description": payload.get("description"),
                    "chunk_count": len(payload["chunk_ids"]),
                }
                for key, payload in list(entities.items())[:200]
            ],
            "relationships": [
                {
                    "source": item["source_key"],
                    "target": item["target_key"],
                    "relationship_type": item["relationship_type"],
                    "description": item.get("description"),
                    "mention_count": item["mention_count"],
                }
                for item in relationships[:300]
            ],
        }

    def _create_communities(self, resource_id: str, entity_rows: dict, relationships: list[dict]) -> int:
        adjacency: dict[str, set[str]] = defaultdict(set)
        for item in relationships:
            adjacency[item["source_key"]].add(item["target_key"])
            adjacency[item["target_key"]].add(item["source_key"])
        visited: set[str] = set()
        community_count = 0
        for key in entity_rows:
            if key in visited:
                continue
            members = []
            queue = deque([key])
            visited.add(key)
            while queue:
                current = queue.popleft()
                members.append(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            if len(members) < 2:
                continue
            names = [entity_rows[member].name for member in members[:8]]
            community = self.repository.create_community(
                resource_id=resource_id,
                name=", ".join(names[:3]),
                summary=f"Related graph cluster containing {', '.join(names)}.",
                metadata_json={"entity_count": len(members), "entity_keys": members},
            )
            for member in members:
                self.repository.add_entity_to_community(entity_rows[member].entity_id, community.community_id)
            community_count += 1
        return community_count


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def normalize_type(value: str | None, default: str) -> str:
    if not value:
        return default
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().upper()).strip("_")
    return normalized or default
