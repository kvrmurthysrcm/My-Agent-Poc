from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Author, Category, Resource, ResourceAuthor, ResourceTag, Tag
from app.schemas.ingest_request import IngestMetadata


class ResourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_category(self, name: str | None) -> Category | None:
        if not name:
            return None
        category = self.db.scalar(select(Category).where(Category.category_name == name))
        if category is None:
            category = Category(category_name=name)
            self.db.add(category)
            self.db.flush()
        return category

    def _get_or_create_author(self, name: str | None) -> Author | None:
        if not name:
            return None
        author = self.db.scalar(select(Author).where(Author.author_name == name))
        if author is None:
            author = Author(author_name=name)
            self.db.add(author)
            self.db.flush()
        return author

    def _get_or_create_tag(self, name: str) -> Tag:
        tag = self.db.scalar(select(Tag).where(Tag.tag_name == name))
        if tag is None:
            tag = Tag(tag_name=name)
            self.db.add(tag)
            self.db.flush()
        return tag

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
        category = self._get_or_create_category(metadata.category_name)
        resource = Resource(
            title=metadata.title,
            description=metadata.description,
            resource_type=metadata.resource_type,
            category_id=category.category_id if category else None,
            publisher=metadata.publisher,
            published_date=metadata.published_date.date() if metadata.published_date else None,
            language=metadata.language,
            file_url=storage_path,
            file_name=file_name,
            file_content_type=content_type,
            file_size_bytes=size_bytes,
            source_system=metadata.source_system,
            original_file_hash_sha256=file_hash,
            file_extension=extension,
            rag_enabled=True,
            ingestion_status="QUEUED",
            resource_metadata=metadata.model_dump(mode="json"),
            storage_path=storage_path,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )
        self.db.add(resource)
        self.db.flush()

        author = self._get_or_create_author(metadata.author)
        if author:
            self.db.add(ResourceAuthor(resource_id=resource.resource_id, author_id=author.author_id))
        for tag_name in {tag.strip() for tag in metadata.tags if tag.strip()}:
            tag = self._get_or_create_tag(tag_name)
            self.db.add(ResourceTag(resource_id=resource.resource_id, tag_id=tag.tag_id))
        self.db.flush()
        return resource

    def update_status(self, resource_id: str, status: str, **fields) -> None:
        resource = self.db.get(Resource, resource_id)
        if resource:
            resource.ingestion_status = status
            for key, value in fields.items():
                setattr(resource, key, value)
            self.db.flush()
