from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Resource
from app.schemas.ingest_request import IngestMetadata
from app.services.library_metadata_persistence_service import LibraryMetadataPersistenceService


class ResourceRepository:
    def __init__(self, db: Session):
        self.db = db
        self.library_metadata = LibraryMetadataPersistenceService(db)

    def create_resource(
        self,
        metadata: IngestMetadata,
        file_name: str,
        content_type: str | None,
        size_bytes: int,
        extension: str,
        file_hash: str,
        storage_path: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_version: str,
    ) -> Resource:
        persisted_metadata = self.library_metadata.prepare(
            metadata=metadata,
            fallback_title=file_name,
        )
        resource = Resource(
            title=persisted_metadata.title,
            description=persisted_metadata.description,
            resource_type=persisted_metadata.resource_type,
            category_id=persisted_metadata.category_id,
            publisher=persisted_metadata.publisher,
            published_date=persisted_metadata.published_date,
            language=persisted_metadata.language,
            isbn=persisted_metadata.isbn,
            page_count=persisted_metadata.page_count,
            file_url=storage_path,
            file_name=file_name,
            file_content_type=content_type,
            file_size_bytes=size_bytes,
            source_system=metadata.source_system,
            original_file_hash_sha256=file_hash,
            file_extension=extension,
            rag_enabled=True,
            ingestion_status="QUEUED",
            resource_metadata=persisted_metadata.metadata_json,
            storage_path=storage_path,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )
        self.db.add(resource)
        self.db.flush()

        self.library_metadata.attach_resource_metadata(
            resource_id=resource.resource_id,
            metadata=persisted_metadata,
        )
        return resource

    def find_existing_by_file_hash(self, file_hash: str) -> Resource | None:
        return self.db.scalar(
            select(Resource)
            .where(Resource.original_file_hash_sha256 == file_hash)
            .where(Resource.ingestion_status.in_(["QUEUED", "PROCESSING", "READY"]))
            .order_by(Resource.created_at.desc())
        )

    def update_status(self, resource_id: str, status: str, **fields) -> None:
        resource = self.db.get(Resource, resource_id)
        if resource:
            resource.ingestion_status = status
            for key, value in fields.items():
                setattr(resource, key, value)
            self.db.flush()
