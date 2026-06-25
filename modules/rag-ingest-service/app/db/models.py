from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator

from app.db.session import Base


class GUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))


class JsonCompat(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB)
        return dialect.type_descriptor(JSON)


def uuid_str() -> str:
    return str(uuid4())


class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    category_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class Author(Base):
    __tablename__ = "authors"

    author_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    bio: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class Tag(Base):
    __tablename__ = "tags"

    tag_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Resource(Base):
    __tablename__ = "resources"

    resource_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, default="DOCUMENT")
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("categories.category_id"))
    publisher: Mapped[str | None] = mapped_column(String(200))
    published_date: Mapped[date | None] = mapped_column(Date)
    language: Mapped[str] = mapped_column(String(80), nullable=False, default="English")
    file_url: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(500))
    file_content_type: Mapped[str | None] = mapped_column(String(200))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_tier_code: Mapped[str] = mapped_column(String(30), nullable=False, default="FREE")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())

    source_system: Mapped[str | None] = mapped_column(String(100))
    original_file_hash_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    extracted_text_hash_sha256: Mapped[str | None] = mapped_column(String(64))
    file_extension: Mapped[str | None] = mapped_column(String(30))
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_INDEXED")
    resource_metadata: Mapped[dict] = mapped_column("metadata_json", JsonCompat, nullable=False, default=dict)
    storage_path: Mapped[str | None] = mapped_column(Text)
    parser_name: Mapped[str | None] = mapped_column(String(100))
    embedding_provider: Mapped[str | None] = mapped_column(String(50))
    embedding_model: Mapped[str | None] = mapped_column(String(150))
    embedding_version: Mapped[str | None] = mapped_column(String(50))

    jobs: Mapped[list["RagIngestionJob"]] = relationship(back_populates="resource")


class ResourceAuthor(Base):
    __tablename__ = "resource_authors"

    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), primary_key=True)
    author_id: Mapped[str] = mapped_column(GUID, ForeignKey("authors.author_id"), primary_key=True)


class ResourceTag(Base):
    __tablename__ = "resource_tags"

    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(GUID, ForeignKey("tags.tag_id"), primary_key=True)


class RagIngestionJob(Base):
    __tablename__ = "rag_ingestion_jobs"

    job_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED", index=True)
    async_backend: Mapped[str] = mapped_column(String(50), nullable=False)
    chunking_strategy: Mapped[str] = mapped_column(String(80), nullable=False, default="SEMANTIC_RECURSIVE")
    chunk_size_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    chunk_overlap_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedded_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress_message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())

    resource: Mapped[Resource] = relationship(back_populates="jobs")


class RagDocumentExtraction(Base):
    __tablename__ = "rag_document_extractions"

    extraction_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), nullable=False)
    job_id: Mapped[str] = mapped_column(GUID, ForeignKey("rag_ingestion_jobs.job_id"), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_metadata: Mapped[dict] = mapped_column("metadata_json", JsonCompat, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"
    __table_args__ = (UniqueConstraint("resource_id", "chunk_hash_sha256", name="ux_rag_chunks_resource_hash"),)

    chunk_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(GUID, ForeignKey("rag_ingestion_jobs.job_id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    heading_path: Mapped[list] = mapped_column(JsonCompat, nullable=False, default=list)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    chunk_metadata: Mapped[dict] = mapped_column("metadata_json", JsonCompat, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RagChunkEmbedding(Base):
    __tablename__ = "rag_chunk_embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", "embedding_provider", "embedding_model", "embedding_version", name="ux_rag_embedding_version"),)

    embedding_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    chunk_id: Mapped[str] = mapped_column(GUID, ForeignKey("rag_document_chunks.chunk_id"), nullable=False, index=True)
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(150), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list] = mapped_column(JsonCompat, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RagProcessingError(Base):
    __tablename__ = "rag_processing_errors"

    error_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(GUID, ForeignKey("rag_ingestion_jobs.job_id"), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("rag_document_chunks.chunk_id"))
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    error_type: Mapped[str] = mapped_column(String(150), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_details: Mapped[dict] = mapped_column(JsonCompat, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RagProfilingEvent(Base):
    __tablename__ = "rag_profiling_events"

    profile_event_id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(GUID, ForeignKey("rag_ingestion_jobs.job_id"), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(GUID, ForeignKey("resources.resource_id"), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    elapsed_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_details: Mapped[dict] = mapped_column("details_json", JsonCompat, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
