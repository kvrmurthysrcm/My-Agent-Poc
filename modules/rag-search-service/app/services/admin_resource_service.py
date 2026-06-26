from pathlib import Path
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    Author,
    Category,
    RagChunkEmbedding,
    RagDocumentChunk,
    RagDocumentExtraction,
    RagIngestionJob,
    RagProcessingError,
    RagProfilingEvent,
    Resource,
    ResourceAuthor,
    ResourceTag,
    Tag,
)
from app.schemas.admin_resources import AdminResourceItem


class AdminResourceService:
    def __init__(self, db: Session):
        self.db = db

    def list_resources(self) -> list[AdminResourceItem]:
        resources = list(self.db.scalars(select(Resource).order_by(Resource.created_at.desc(), Resource.title.asc())))
        if not resources:
            return []

        resource_ids = [resource.resource_id for resource in resources]
        chunk_counts = self._count_by_resource(RagDocumentChunk.resource_id, resource_ids)
        job_counts = self._count_by_resource(RagIngestionJob.resource_id, resource_ids)
        embedding_counts = self._embedding_counts(resource_ids)
        latest_jobs = self._latest_job_statuses(resource_ids)
        categories = self._categories(resource_ids)
        tags = self._tags(resource_ids)
        authors = self._authors(resource_ids)

        return [
            AdminResourceItem(
                resource_id=resource.resource_id,
                title=resource.title,
                author=authors.get(resource.resource_id) or (resource.resource_metadata or {}).get("author"),
                category=categories.get(resource.resource_id) or (resource.resource_metadata or {}).get("category_name"),
                tags=tags.get(resource.resource_id, []),
                ingestion_status=resource.ingestion_status,
                rag_enabled=resource.rag_enabled,
                file_name=resource.file_name,
                file_size_bytes=resource.file_size_bytes,
                chunk_count=chunk_counts.get(resource.resource_id, 0),
                embedding_count=embedding_counts.get(resource.resource_id, 0),
                job_count=job_counts.get(resource.resource_id, 0),
                latest_job_status=latest_jobs.get(resource.resource_id),
                created_at=resource.created_at,
                metadata=resource.resource_metadata or {},
            )
            for resource in resources
        ]

    def delete_resource(self, resource_id: str, force: bool = False) -> tuple[bool, dict[str, int], str | None]:
        resource = self.db.get(Resource, resource_id)
        if resource is None:
            return False, {}, None

        processing_job = self.db.scalar(
            select(RagIngestionJob)
            .where(RagIngestionJob.resource_id == resource_id)
            .where(RagIngestionJob.status == "PROCESSING")
            .limit(1)
        )
        if processing_job and not force:
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
        counts["rag_ingestion_jobs"] = self._delete(RagIngestionJob, RagIngestionJob.job_id.in_(job_ids)) if job_ids else 0
        counts.update(self._delete_optional_library_rows(resource_id))
        counts["resource_tags"] = self._delete(ResourceTag, ResourceTag.resource_id == resource_id)
        counts["resource_authors"] = self._delete(ResourceAuthor, ResourceAuthor.resource_id == resource_id)
        counts["resources"] = self._delete(Resource, Resource.resource_id == resource_id)

        deleted_file_path = self._delete_file(file_path)
        self.db.flush()
        return True, counts, deleted_file_path

    def _count_by_resource(self, column, resource_ids: list[str]) -> dict[str, int]:
        rows = self.db.execute(select(column, func.count()).where(column.in_(resource_ids)).group_by(column))
        return {resource_id: int(count) for resource_id, count in rows}

    def _embedding_counts(self, resource_ids: list[str]) -> dict[str, int]:
        rows = self.db.execute(
            select(RagDocumentChunk.resource_id, func.count(RagChunkEmbedding.embedding_id))
            .join(RagChunkEmbedding, RagChunkEmbedding.chunk_id == RagDocumentChunk.chunk_id)
            .where(RagDocumentChunk.resource_id.in_(resource_ids))
            .group_by(RagDocumentChunk.resource_id)
        )
        return {resource_id: int(count) for resource_id, count in rows}

    def _latest_job_statuses(self, resource_ids: list[str]) -> dict[str, str]:
        rows = self.db.execute(
            select(RagIngestionJob.resource_id, RagIngestionJob.status, RagIngestionJob.created_at)
            .where(RagIngestionJob.resource_id.in_(resource_ids))
            .order_by(RagIngestionJob.resource_id, RagIngestionJob.created_at.desc())
        )
        latest: dict[str, str] = {}
        for resource_id, status, _created_at in rows:
            latest.setdefault(resource_id, status)
        return latest

    def _categories(self, resource_ids: list[str]) -> dict[str, str]:
        rows = self.db.execute(
            select(Resource.resource_id, Category.category_name)
            .join(Category, Category.category_id == Resource.category_id)
            .where(Resource.resource_id.in_(resource_ids))
        )
        return {resource_id: category for resource_id, category in rows}

    def _tags(self, resource_ids: list[str]) -> dict[str, list[str]]:
        rows = self.db.execute(
            select(ResourceTag.resource_id, Tag.tag_name)
            .join(Tag, Tag.tag_id == ResourceTag.tag_id)
            .where(ResourceTag.resource_id.in_(resource_ids))
            .order_by(Tag.tag_name)
        )
        tags: dict[str, list[str]] = {}
        for resource_id, tag_name in rows:
            tags.setdefault(resource_id, []).append(tag_name)
        return tags

    def _authors(self, resource_ids: list[str]) -> dict[str, str]:
        rows = self.db.execute(
            select(ResourceAuthor.resource_id, Author.author_name)
            .join(Author, Author.author_id == ResourceAuthor.author_id)
            .where(ResourceAuthor.resource_id.in_(resource_ids))
            .order_by(Author.author_name)
        )
        authors: dict[str, str] = {}
        for resource_id, author_name in rows:
            authors.setdefault(resource_id, author_name)
        return authors

    def _delete(self, model, condition) -> int:
        result = self.db.execute(delete(model).where(condition))
        return int(result.rowcount or 0)

    def _delete_optional_library_rows(self, resource_id: str) -> dict[str, int]:
        if self.db.bind and self.db.bind.dialect.name != "postgresql":
            return {}

        counts = {}
        for table_name in ("user_bookshelf", "reviews", "reading_progress", "downloads"):
            result = self.db.execute(text(f"DELETE FROM public.{table_name} WHERE resource_id = :resource_id"), {"resource_id": resource_id})
            counts[table_name] = int(result.rowcount or 0)
        return counts

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
