from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.rag_job_repository import RagJobRepository
from app.repositories.resource_repository import ResourceRepository
from app.schemas.ingest_request import IngestMetadata
from app.services.file_storage_service import FileStorageService


class IngestService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.resources = ResourceRepository(db)
        self.jobs = RagJobRepository(db)
        self.storage = FileStorageService(settings)

    async def create_resource_and_job(self, file: UploadFile, metadata: IngestMetadata, extension: str) -> tuple[str, str]:
        temp_resource_id = "pending"
        storage_path, size, file_hash = await self.storage.save_upload(file, temp_resource_id)

        chunk_size = metadata.chunking.chunk_size_tokens or self.settings.default_chunk_size_tokens
        chunk_overlap = metadata.chunking.chunk_overlap_tokens or self.settings.default_chunk_overlap_tokens

        resource = self.resources.create_resource(
            metadata=metadata,
            file_name=file.filename or storage_path.name,
            content_type=file.content_type,
            size_bytes=size,
            extension=extension,
            file_hash=file_hash,
            storage_path=str(storage_path),
            embedding_provider=self.settings.embedding_provider.value,
            embedding_model=self.settings.embedding_model,
            embedding_version=self.settings.embedding_version,
        )

        final_path = self.settings.storage_root / "resources" / resource.resource_id / storage_path.name
        final_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.replace(final_path)
        resource.storage_path = str(final_path)
        resource.file_url = str(final_path)

        job = self.jobs.create_job(
            resource_id=resource.resource_id,
            async_backend=self.settings.async_backend.value,
            strategy=metadata.chunking.strategy,
            size=chunk_size,
            overlap=chunk_overlap,
        )
        self.db.commit()
        return resource.resource_id, job.job_id
