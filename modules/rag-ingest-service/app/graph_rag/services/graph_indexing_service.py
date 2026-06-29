import logging
import re
from collections import defaultdict, deque
from time import perf_counter

from sqlalchemy.orm.attributes import flag_modified
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
from app.repositories.runtime_settings_repository import RuntimeSettingsRepository
from app.utils.profiling import record_profile_event

logger = logging.getLogger("rag_ingestion_worker.graph_rag")
GRAPH_EXTRACTION_METADATA_KEY = "graph_rag_extraction"
GRAPH_EXTRACTION_VERSION = "v1"


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

        extracted_by_chunk_id: dict[str, ChunkGraphExtraction] = {
            chunk.chunk_id: ChunkGraphExtraction(chunk_id=chunk.chunk_id, chunk_index=chunk.chunk_index)
            for chunk in chunks
        }
        for chunk in chunks:
            cached = _load_cached_graph_extraction(chunk)
            if cached:
                extracted_by_chunk_id[chunk.chunk_id] = cached

        entity_batch_index = 0
        while True:
            entity_batch_size, _relationship_batch_size = RuntimeSettingsRepository(self.db).get_graph_rag_batch_sizes(
                self.settings.graph_rag_entity_batch_size,
                self.settings.graph_rag_relationship_batch_size,
            )
            pending_batch = _next_entity_batch(chunks, extracted_by_chunk_id, entity_batch_size)
            if not pending_batch:
                break
            entity_batch_index += 1
            completed_chunks = _count_chunks_with_entities(extracted_by_chunk_id)
            jobs.update_progress(
                job,
                f"Graph entities {completed_chunks}/{len(chunks)} chunks; batch {entity_batch_index}; batch_size={entity_batch_size}",
            )
            jobs.heartbeat(job)
            self.db.commit()
            batch_started = perf_counter()
            payload = [_chunk_payload(chunk) for chunk in pending_batch]
            try:
                entities_by_chunk_id = self.entities.extract_batch(payload)
            except Exception as exc:
                logger.warning("Graph entity batch %s failed; falling back to single chunk extraction: %s", entity_batch_index, exc)
                entities_by_chunk_id = {item["chunk_id"]: self.entities.extract(item["chunk_text"]) for item in payload}
            entity_count = 0
            for chunk in pending_batch:
                entities = entities_by_chunk_id.get(chunk.chunk_id, [])
                extracted_by_chunk_id[chunk.chunk_id].entities = entities
                _store_cached_graph_extraction(chunk, extracted_by_chunk_id[chunk.chunk_id])
                entity_count += len(entities)
            completed_chunks = _count_chunks_with_entities(extracted_by_chunk_id)
            jobs.update_progress(
                job,
                f"Graph entities {completed_chunks}/{len(chunks)} chunks; batch {entity_batch_index} done; batch_size={entity_batch_size}",
            )
            self.db.commit()
            record_profile_event(
                self.settings.profiling,
                logger,
                job.job_id,
                resource.resource_id,
                f"graph_entity_batch_{entity_batch_index}",
                "DONE",
                (perf_counter() - batch_started) * 1000,
                batch_size=len(pending_batch),
                configured_batch_size=entity_batch_size,
                entity_count=entity_count,
            )

        relationship_batch_index = 0
        while True:
            _entity_batch_size, relationship_batch_size = RuntimeSettingsRepository(self.db).get_graph_rag_batch_sizes(
                self.settings.graph_rag_entity_batch_size,
                self.settings.graph_rag_relationship_batch_size,
            )
            pending_batch = _next_relationship_batch(chunks, extracted_by_chunk_id, relationship_batch_size)
            if not pending_batch:
                break
            relationship_batch_index += 1
            completed_chunks = _count_chunks_with_relationships(extracted_by_chunk_id)
            jobs.update_progress(
                job,
                f"Graph relationships {completed_chunks}/{len(chunks)} chunks; batch {relationship_batch_index}; batch_size={relationship_batch_size}",
            )
            jobs.heartbeat(job)
            self.db.commit()
            batch_started = perf_counter()
            payload = [
                {
                    **_chunk_payload(chunk),
                    "entities": extracted_by_chunk_id[chunk.chunk_id].entities,
                }
                for chunk in pending_batch
            ]
            try:
                relationships_by_chunk_id = self.relationships.extract_batch(payload)
            except Exception as exc:
                logger.warning("Graph relationship batch %s failed; falling back to single chunk extraction: %s", relationship_batch_index, exc)
                relationships_by_chunk_id = {
                    item["chunk_id"]: self.relationships.extract(item["chunk_text"], item["entities"])
                    for item in payload
                }
            relationship_count = 0
            for chunk in pending_batch:
                relationships = relationships_by_chunk_id.get(chunk.chunk_id, [])
                extracted_by_chunk_id[chunk.chunk_id].relationships = relationships
                _store_cached_graph_extraction(chunk, extracted_by_chunk_id[chunk.chunk_id])
                relationship_count += len(relationships)
            completed_chunks = _count_chunks_with_relationships(extracted_by_chunk_id)
            jobs.update_progress(
                job,
                f"Graph relationships {completed_chunks}/{len(chunks)} chunks; batch {relationship_batch_index} done; batch_size={relationship_batch_size}",
            )
            self.db.commit()
            record_profile_event(
                self.settings.profiling,
                logger,
                job.job_id,
                resource.resource_id,
                f"graph_relationship_batch_{relationship_batch_index}",
                "DONE",
                (perf_counter() - batch_started) * 1000,
                batch_size=len(pending_batch),
                configured_batch_size=relationship_batch_size,
                relationship_count=relationship_count,
            )

        extracted = [extracted_by_chunk_id[chunk.chunk_id] for chunk in chunks]
        for index, chunk in enumerate(extracted, start=1):
            record_profile_event(
                self.settings.profiling,
                logger,
                job.job_id,
                resource.resource_id,
                f"graph_chunk_{index}",
                "DONE",
                0,
                chunk_index=chunk.chunk_index,
                chunk_id=chunk.chunk_id,
                entity_count=len(chunk.entities),
                relationship_count=len(chunk.relationships),
                entities=", ".join(entity.name for entity in chunk.entities[:8]),
                relationship_types=", ".join(relationship.relationship_type for relationship in chunk.relationships[:8]),
            )

        jobs.update_progress(job, "Graph consolidation and summary started")
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
        jobs.update_progress(job, "Graph summary generation started")
        self.db.commit()
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


def _chunk_batches(chunks: list[RagDocumentChunk], batch_size: int):
    safe_batch_size = max(1, batch_size)
    for start in range(0, len(chunks), safe_batch_size):
        yield chunks[start : start + safe_batch_size]


def _next_entity_batch(
    chunks: list[RagDocumentChunk],
    extracted_by_chunk_id: dict[str, ChunkGraphExtraction],
    batch_size: int,
) -> list[RagDocumentChunk]:
    pending = [chunk for chunk in chunks if not extracted_by_chunk_id[chunk.chunk_id].entities]
    return pending[: max(1, batch_size)]


def _next_relationship_batch(
    chunks: list[RagDocumentChunk],
    extracted_by_chunk_id: dict[str, ChunkGraphExtraction],
    batch_size: int,
) -> list[RagDocumentChunk]:
    pending = [
        chunk
        for chunk in chunks
        if extracted_by_chunk_id[chunk.chunk_id].entities
        and not extracted_by_chunk_id[chunk.chunk_id].relationships
    ]
    return pending[: max(1, batch_size)]


def _count_chunks_with_entities(extracted_by_chunk_id: dict[str, ChunkGraphExtraction]) -> int:
    return sum(1 for extraction in extracted_by_chunk_id.values() if extraction.entities)


def _count_chunks_with_relationships(extracted_by_chunk_id: dict[str, ChunkGraphExtraction]) -> int:
    return sum(1 for extraction in extracted_by_chunk_id.values() if extraction.relationships)


def _chunk_payload(chunk: RagDocumentChunk) -> dict[str, str | int]:
    return {
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "chunk_text": chunk.chunk_text,
    }


def _load_cached_graph_extraction(chunk: RagDocumentChunk) -> ChunkGraphExtraction | None:
    payload = (chunk.chunk_metadata or {}).get(GRAPH_EXTRACTION_METADATA_KEY)
    if not isinstance(payload, dict) or payload.get("version") != GRAPH_EXTRACTION_VERSION:
        return None
    try:
        return ChunkGraphExtraction(
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            entities=[ExtractedEntity.model_validate(item) for item in payload.get("entities", []) if isinstance(item, dict)],
            relationships=[
                ExtractedRelationship.model_validate(item)
                for item in payload.get("relationships", [])
                if isinstance(item, dict)
            ],
        )
    except Exception:
        return None


def _store_cached_graph_extraction(chunk: RagDocumentChunk, extraction: ChunkGraphExtraction) -> None:
    metadata = dict(chunk.chunk_metadata or {})
    metadata[GRAPH_EXTRACTION_METADATA_KEY] = {
        "version": GRAPH_EXTRACTION_VERSION,
        "entities": [entity.model_dump() for entity in extraction.entities],
        "relationships": [relationship.model_dump() for relationship in extraction.relationships],
    }
    chunk.chunk_metadata = metadata
    flag_modified(chunk, "chunk_metadata")
