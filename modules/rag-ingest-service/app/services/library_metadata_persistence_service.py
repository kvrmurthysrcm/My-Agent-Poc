from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Author, Category, ResourceAuthor, ResourceTag, Tag
from app.schemas.ingest_request import IngestMetadata


@dataclass(frozen=True)
class PersistedLibraryMetadata:
    title: str
    description: str | None
    resource_type: str
    category_id: str | None
    category_name: str | None
    author_names: list[str]
    tag_names: list[str]
    publisher: str | None
    published_date: object | None
    language: str
    isbn: str | None
    page_count: int | None
    metadata_json: dict


class LibraryMetadataPersistenceService:
    """Normalizes document metadata and persists catalog lookup rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def prepare(self, *, metadata: IngestMetadata, fallback_title: str) -> PersistedLibraryMetadata:
        category_name = _clean_text(metadata.category_name) or _clean_text(metadata.genre)
        category = self._get_or_create_category(category_name)
        author_names = _dedupe_preserve_order([_clean_text(metadata.author)])
        tag_names = _dedupe_preserve_order(_clean_text(tag) for tag in metadata.tags)
        language = _clean_text(metadata.language) or "English"
        title = _clean_text(metadata.title) or fallback_title

        metadata_json = metadata.model_dump(mode="json")
        if metadata.genre and not metadata.category_name:
            metadata_json["category_name"] = category_name

        return PersistedLibraryMetadata(
            title=title,
            description=_clean_text(metadata.description),
            resource_type=_clean_text(metadata.resource_type) or "DOCUMENT",
            category_id=category.category_id if category else None,
            category_name=category.category_name if category else None,
            author_names=author_names,
            tag_names=tag_names,
            publisher=_clean_text(metadata.publisher),
            published_date=metadata.published_date.date() if metadata.published_date else None,
            language=language,
            isbn=_clean_text(metadata.isbn),
            page_count=metadata.page_count,
            metadata_json=metadata_json,
        )

    def attach_resource_metadata(self, *, resource_id: str, metadata: PersistedLibraryMetadata) -> None:
        for author_name in metadata.author_names:
            author = self._get_or_create_author(author_name)
            self.db.add(ResourceAuthor(resource_id=resource_id, author_id=author.author_id))

        for tag_name in metadata.tag_names:
            tag = self._get_or_create_tag(tag_name)
            self.db.add(ResourceTag(resource_id=resource_id, tag_id=tag.tag_id))

        self.db.flush()

    def _get_or_create_category(self, name: str | None) -> Category | None:
        if not name:
            return None
        category = self.db.scalar(select(Category).where(Category.category_name == name))
        if category is None:
            category = Category(category_name=name)
            self.db.add(category)
            self.db.flush()
        return category

    def _get_or_create_author(self, name: str) -> Author:
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


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def _dedupe_preserve_order(values) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
