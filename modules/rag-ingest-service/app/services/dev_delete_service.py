from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    Resource,
    ResourceAuthor,
    ResourceTag,
    RagChunkEmbedding,
    RagDocumentChunk,
    RagDocumentExtraction,
    RagIngestionJob,
    RagProcessingError,
    RagProfilingEvent,
)


class DevDeleteService:
    def __init__(self, db: Session):
        self.db = db

    def delete_resource(self, resource_id: str, force: bool = False) -> tuple[bool, dict[str, int], str | None]:
        resource = self.db.get(Resource, resource_id)
        if resource is None:
            return False, {}, None

        processing_count = self.db.scalar(
            select(RagIngestionJob)
            .where(RagIngestionJob.resource_id == resource_id)
            .where(RagIngestionJob.status == "PROCESSING")
            .limit(1)
        )
        if processing_count and not force:
            raise ValueError("Resource has a PROCESSING job. Retry after completion or pass force=true.")

        file_path = resource.storage_path
        job_ids = list(self.db.scalars(select(RagIngestionJob.job_id).where(RagIngestionJob.resource_id == resource_id)))
        chunk_ids = list(self.db.scalars(select(RagDocumentChunk.chunk_id).where(RagDocumentChunk.resource_id == resource_id)))

        counts: dict[str, int] = {}
        counts["rag_chunk_embeddings"] = self._delete(RagChunkEmbedding, RagChunkEmbedding.chunk_id.in_(chunk_ids)) if chunk_ids else 0
        counts["rag_processing_errors"] = self._delete(RagProcessingError, RagProcessingError.resource_id == resource_id)
        counts["rag_profiling_events"] = self._delete(RagProfilingEvent, RagProfilingEvent.resource_id == resource_id)
        counts["rag_document_chunks"] = self._delete(RagDocumentChunk, RagDocumentChunk.resource_id == resource_id)
        counts["rag_document_extractions"] = self._delete(RagDocumentExtraction, RagDocumentExtraction.resource_id == resource_id)
        counts["rag_ingestion_jobs"] = (
            self._delete(RagIngestionJob, RagIngestionJob.job_id.in_(job_ids)) if job_ids else 0
        )
        counts.update(self._delete_optional_library_rows(resource_id))
        counts["resource_tags"] = self._delete(ResourceTag, ResourceTag.resource_id == resource_id)
        counts["resource_authors"] = self._delete(ResourceAuthor, ResourceAuthor.resource_id == resource_id)
        counts["resources"] = self._delete(Resource, Resource.resource_id == resource_id)

        deleted_file_path = self._delete_file(file_path)
        self.db.flush()
        return True, counts, deleted_file_path

    def _delete(self, model, condition) -> int:
        result = self.db.execute(delete(model).where(condition))
        return int(result.rowcount or 0)

    def _delete_optional_library_rows(self, resource_id: str) -> dict[str, int]:
        if self.db.bind and self.db.bind.dialect.name != "postgresql":
            return {}

        counts = {}
        for table_name in ("user_bookshelf", "reviews", "reading_progress", "downloads"):
            if not self._table_exists(table_name):
                counts[table_name] = 0
                continue
            result = self.db.execute(text(f"DELETE FROM public.{table_name} WHERE resource_id = :resource_id"), {"resource_id": resource_id})
            counts[table_name] = int(result.rowcount or 0)
        return counts

    def _table_exists(self, table_name: str) -> bool:
        result = self.db.execute(text("select to_regclass(:table_name)"), {"table_name": f"public.{table_name}"})
        return result.scalar() is not None

    def _delete_file(self, file_path: str | None) -> str | None:
        if not file_path:
            return None
        path = Path(file_path)
        deleted_path = str(path)
        if path.exists() and path.is_file():
            path.unlink()
        parent = path.parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        return deleted_path
