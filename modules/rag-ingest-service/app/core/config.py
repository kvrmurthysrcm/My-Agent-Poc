from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.constants import AsyncBackend, EmbeddingProviderName


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        "postgresql://library_user:library_pass@localhost:5432/online_library",
        alias="DATABASE_URL",
    )
    app_profile: str = Field("local", alias="APP_PROFILE")
    enable_dev_delete_endpoint: bool = Field(True, alias="ENABLE_DEV_DELETE_ENDPOINT")
    storage_root: Path = Field(Path("./storage"), alias="STORAGE_ROOT")
    delete_original_file_after_ingestion: bool = Field(True, alias="DELETE_ORIGINAL_FILE_AFTER_INGESTION")
    duplicate_document_policy: str = Field("version", alias="DUPLICATE_DOCUMENT_POLICY")
    profiling: bool = Field(True, alias="PROFILING")
    max_upload_mb: int = Field(25, alias="MAX_UPLOAD_MB")
    supported_extensions: Annotated[list[str], NoDecode] = Field(
        [".txt", ".pdf", ".docx", ".epub"],
        alias="SUPPORTED_EXTENSIONS",
    )

    default_chunk_size_tokens: int = Field(1200, alias="DEFAULT_CHUNK_SIZE_TOKENS")
    default_chunk_overlap_tokens: int = Field(80, alias="DEFAULT_CHUNK_OVERLAP_TOKENS")
    default_chunking_strategy: str = Field("SEMANTIC_RECURSIVE", alias="DEFAULT_CHUNKING_STRATEGY")
    minimum_chunk_tokens: int = Field(80, alias="MINIMUM_CHUNK_TOKENS")
    chunk_quality_keep_numeric_table_chunks: bool = Field(True, alias="CHUNK_QUALITY_KEEP_NUMERIC_TABLE_CHUNKS")
    chunk_quality_min_alpha_ratio: float = Field(0.45, alias="CHUNK_QUALITY_MIN_ALPHA_RATIO")
    chunk_heading_allow_single_letter: bool = Field(False, alias="CHUNK_HEADING_ALLOW_SINGLE_LETTER")
    pdf_parser: str = Field("pymupdf", alias="PDF_PARSER")
    pdf_repair_drop_caps: bool = Field(True, alias="PDF_REPAIR_DROP_CAPS")
    pdf_remove_repeated_headers_footers: bool = Field(True, alias="PDF_REMOVE_REPEATED_HEADERS_FOOTERS")
    pdf_dehyphenate_line_breaks: bool = Field(True, alias="PDF_DEHYPHENATE_LINE_BREAKS")
    pdf_remove_private_use_glyphs: bool = Field(True, alias="PDF_REMOVE_PRIVATE_USE_GLYPHS")
    pdf_normalize_unicode: bool = Field(True, alias="PDF_NORMALIZE_UNICODE")
    pdf_remove_boilerplate_lines: bool = Field(True, alias="PDF_REMOVE_BOILERPLATE_LINES")
    pdf_remove_page_number_lines: bool = Field(True, alias="PDF_REMOVE_PAGE_NUMBER_LINES")
    pdf_repair_joined_words: bool = Field(True, alias="PDF_REPAIR_JOINED_WORDS")

    embedding_provider: EmbeddingProviderName = Field(EmbeddingProviderName.OLLAMA, alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field("nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_dimension: int | None = Field(None, alias="EMBEDDING_DIMENSION")
    embedding_version: str = Field("v1", alias="EMBEDDING_VERSION")
    embedding_batch_size: int = Field(64, alias="EMBEDDING_BATCH_SIZE")
    embedding_concurrency: int = Field(1, alias="EMBEDDING_CONCURRENCY")
    embedding_max_retries: int = Field(2, alias="EMBEDDING_MAX_RETRIES")
    embedding_retry_backoff_seconds: float = Field(1.0, alias="EMBEDDING_RETRY_BACKOFF_SECONDS")
    embedding_retry_shrink_batch: bool = Field(True, alias="EMBEDDING_RETRY_SHRINK_BATCH")
    embedding_min_batch_size: int = Field(1, alias="EMBEDDING_MIN_BATCH_SIZE")
    ollama_embedding_model_options: dict[str, int] = Field(
        default_factory=lambda: {
            "embeddinggemma": 768,
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
        }
    )
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    allow_fake_embeddings: bool = Field(False, alias="ALLOW_FAKE_EMBEDDINGS")
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_embedding_timeout_seconds: float = Field(60.0, alias="OLLAMA_EMBEDDING_TIMEOUT_SECONDS")
    llm_provider: str = Field("ollama", alias="LLM_PROVIDER")
    llm_model: str = Field("mistral:latest", alias="LLM_MODEL")
    llm_base_url: str = Field("http://localhost:11434", alias="LLM_BASE_URL")
    llm_generate_path: str = Field("/api/generate", alias="LLM_GENERATE_PATH")
    llm_timeout_seconds: float = Field(240.0, alias="LLM_TIMEOUT_SECONDS")
    graph_rag_llm_max_retries: int = Field(2, alias="GRAPH_RAG_LLM_MAX_RETRIES")
    graph_rag_llm_retry_backoff_seconds: float = Field(2.0, alias="GRAPH_RAG_LLM_RETRY_BACKOFF_SECONDS")
    graph_rag_create_chunk_embeddings: bool = Field(False, alias="GRAPH_RAG_CREATE_CHUNK_EMBEDDINGS")
    graph_rag_entity_batch_size: int = Field(1, alias="GRAPH_RAG_ENTITY_BATCH_SIZE")
    graph_rag_relationship_batch_size: int = Field(1, alias="GRAPH_RAG_RELATIONSHIP_BATCH_SIZE")
    recover_processing_jobs_on_startup: bool = Field(True, alias="RECOVER_PROCESSING_JOBS_ON_STARTUP")
    startup_recovery_stale_after_seconds: int = Field(0, alias="STARTUP_RECOVERY_STALE_AFTER_SECONDS")
    process_queued_jobs_on_startup: bool = Field(True, alias="PROCESS_QUEUED_JOBS_ON_STARTUP")

    async_backend: AsyncBackend = Field(AsyncBackend.FASTAPI_BACKGROUND_TASKS, alias="ASYNC_BACKEND")
    rq_redis_url: str = Field("redis://localhost:6379/0", alias="RQ_REDIS_URL")
    kafka_bootstrap_servers: str = Field("localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_ingestion_topic: str = Field("rag.document.ingest.requested", alias="KAFKA_INGESTION_TOPIC")
    db_worker_poll_interval_seconds: int = Field(5, alias="DB_WORKER_POLL_INTERVAL_SECONDS")
    db_worker_batch_size: int = Field(5, alias="DB_WORKER_BATCH_SIZE")
    recovery_worker_poll_interval_seconds: int = Field(30, alias="RECOVERY_WORKER_POLL_INTERVAL_SECONDS")
    recovery_stale_after_seconds: int = Field(900, alias="RECOVERY_STALE_AFTER_SECONDS")
    auto_create_tables: bool = Field(False, alias="AUTO_CREATE_TABLES")

    @field_validator("supported_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return [item.lower() for item in value]

    @field_validator("pdf_parser")
    @classmethod
    def normalize_pdf_parser(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"pymupdf", "pypdf"}:
            raise ValueError("PDF_PARSER must be either 'pymupdf' or 'pypdf'")
        return normalized

    @field_validator("default_chunking_strategy")
    @classmethod
    def normalize_default_chunking_strategy(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"INTELLIGENT_RECURSIVE", "SEMANTIC_RECURSIVE"}:
            raise ValueError("DEFAULT_CHUNKING_STRATEGY must be INTELLIGENT_RECURSIVE or SEMANTIC_RECURSIVE")
        return normalized

    @field_validator("chunk_quality_min_alpha_ratio")
    @classmethod
    def validate_chunk_quality_min_alpha_ratio(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("CHUNK_QUALITY_MIN_ALPHA_RATIO must be between 0 and 1")
        return value

    @field_validator("duplicate_document_policy")
    @classmethod
    def normalize_duplicate_document_policy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"version", "reject"}:
            raise ValueError("DUPLICATE_DOCUMENT_POLICY must be version or reject")
        return normalized

    @field_validator("embedding_batch_size")
    @classmethod
    def validate_embedding_batch_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be at least 1")
        if value > 256:
            raise ValueError("EMBEDDING_BATCH_SIZE must be 256 or lower")
        return value

    @field_validator("embedding_concurrency")
    @classmethod
    def validate_embedding_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EMBEDDING_CONCURRENCY must be at least 1")
        if value > 8:
            raise ValueError("EMBEDDING_CONCURRENCY must be 8 or lower")
        return value

    @field_validator("embedding_max_retries")
    @classmethod
    def validate_embedding_max_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("EMBEDDING_MAX_RETRIES must be 0 or greater")
        if value > 10:
            raise ValueError("EMBEDDING_MAX_RETRIES must be 10 or lower")
        return value

    @field_validator("embedding_retry_backoff_seconds")
    @classmethod
    def validate_embedding_retry_backoff_seconds(cls, value: float) -> float:
        if value < 0:
            raise ValueError("EMBEDDING_RETRY_BACKOFF_SECONDS must be 0 or greater")
        if value > 60:
            raise ValueError("EMBEDDING_RETRY_BACKOFF_SECONDS must be 60 or lower")
        return value

    @field_validator("embedding_min_batch_size")
    @classmethod
    def validate_embedding_min_batch_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EMBEDDING_MIN_BATCH_SIZE must be at least 1")
        if value > 256:
            raise ValueError("EMBEDDING_MIN_BATCH_SIZE must be 256 or lower")
        return value

    @field_validator("ollama_embedding_timeout_seconds")
    @classmethod
    def validate_ollama_embedding_timeout_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("OLLAMA_EMBEDDING_TIMEOUT_SECONDS must be greater than 0")
        if value > 3600:
            raise ValueError("OLLAMA_EMBEDDING_TIMEOUT_SECONDS must be 3600 or lower")
        return value

    @field_validator("graph_rag_entity_batch_size", "graph_rag_relationship_batch_size")
    @classmethod
    def validate_graph_rag_batch_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Graph RAG batch sizes must be at least 1")
        if value > 10:
            raise ValueError("Graph RAG batch sizes must be 10 or lower")
        return value

    @field_validator("graph_rag_llm_max_retries")
    @classmethod
    def validate_graph_rag_llm_max_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("GRAPH_RAG_LLM_MAX_RETRIES must be 0 or greater")
        if value > 5:
            raise ValueError("GRAPH_RAG_LLM_MAX_RETRIES must be 5 or lower")
        return value

    @field_validator("graph_rag_llm_retry_backoff_seconds")
    @classmethod
    def validate_graph_rag_llm_retry_backoff_seconds(cls, value: float) -> float:
        if value < 0:
            raise ValueError("GRAPH_RAG_LLM_RETRY_BACKOFF_SECONDS must be 0 or greater")
        if value > 60:
            raise ValueError("GRAPH_RAG_LLM_RETRY_BACKOFF_SECONDS must be 60 or lower")
        return value

    @field_validator("startup_recovery_stale_after_seconds")
    @classmethod
    def validate_startup_recovery_stale_after_seconds(cls, value: int) -> int:
        if value < 0:
            raise ValueError("STARTUP_RECOVERY_STALE_AFTER_SECONDS must be 0 or greater")
        if value > 86400:
            raise ValueError("STARTUP_RECOVERY_STALE_AFTER_SECONDS must be 86400 or lower")
        return value

    @field_validator("recovery_worker_poll_interval_seconds")
    @classmethod
    def validate_recovery_worker_poll_interval_seconds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RECOVERY_WORKER_POLL_INTERVAL_SECONDS must be at least 1")
        if value > 3600:
            raise ValueError("RECOVERY_WORKER_POLL_INTERVAL_SECONDS must be 3600 or lower")
        return value

    @field_validator("recovery_stale_after_seconds")
    @classmethod
    def validate_recovery_stale_after_seconds(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RECOVERY_STALE_AFTER_SECONDS must be at least 1")
        if value > 86400:
            raise ValueError("RECOVERY_STALE_AFTER_SECONDS must be 86400 or lower")
        return value

    @field_validator("embedding_model")
    @classmethod
    def normalize_embedding_model(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_embedding_configuration(self) -> "Settings":
        from app.services.embedding_model_registry import resolve_embedding_dimension, validate_embedding_model

        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must point to PostgreSQL")
        if self.embedding_dimension is None:
            self.embedding_dimension = resolve_embedding_dimension(self.embedding_provider, self.embedding_model)
        validate_embedding_model(self.embedding_provider, self.embedding_model, self.embedding_dimension)
        if self.embedding_provider == EmbeddingProviderName.OPENAI and not self.openai_api_key and not self.allow_fake_embeddings:
            raise ValueError("OPENAI_API_KEY is required unless ALLOW_FAKE_EMBEDDINGS=true")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
