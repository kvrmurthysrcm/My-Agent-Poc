from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.constants import AsyncBackend, EmbeddingProviderName


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        "postgresql://library_user:library_pass@localhost:5432/online_library",
        alias="DATABASE_URL",
    )
    storage_root: Path = Field(Path("./storage"), alias="STORAGE_ROOT")
    delete_original_file_after_ingestion: bool = Field(True, alias="DELETE_ORIGINAL_FILE_AFTER_INGESTION")
    profiling: bool = Field(True, alias="PROFILING")
    max_upload_mb: int = Field(25, alias="MAX_UPLOAD_MB")
    supported_extensions: Annotated[list[str], NoDecode] = Field(
        [".txt", ".pdf", ".docx", ".epub"],
        alias="SUPPORTED_EXTENSIONS",
    )

    default_chunk_size_tokens: int = Field(800, alias="DEFAULT_CHUNK_SIZE_TOKENS")
    default_chunk_overlap_tokens: int = Field(120, alias="DEFAULT_CHUNK_OVERLAP_TOKENS")
    minimum_chunk_tokens: int = Field(80, alias="MINIMUM_CHUNK_TOKENS")
    pdf_parser: str = Field("pymupdf", alias="PDF_PARSER")

    embedding_provider: EmbeddingProviderName = Field(EmbeddingProviderName.OLLAMA, alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field("embeddinggemma", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(768, alias="EMBEDDING_DIMENSION")
    embedding_version: str = Field("v1", alias="EMBEDDING_VERSION")
    ollama_embedding_model_options: dict[str, int] = Field(
        default_factory=lambda: {
            "embeddinggemma": 768,
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
        }
    )
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    llm_provider: str = Field("ollama", alias="LLM_PROVIDER")
    llm_model: str = Field("mistral:latest", alias="LLM_MODEL")

    async_backend: AsyncBackend = Field(AsyncBackend.FASTAPI_BACKGROUND_TASKS, alias="ASYNC_BACKEND")
    rq_redis_url: str = Field("redis://localhost:6379/0", alias="RQ_REDIS_URL")
    kafka_bootstrap_servers: str = Field("localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_ingestion_topic: str = Field("rag.document.ingest.requested", alias="KAFKA_INGESTION_TOPIC")
    db_worker_poll_interval_seconds: int = Field(5, alias="DB_WORKER_POLL_INTERVAL_SECONDS")
    db_worker_batch_size: int = Field(5, alias="DB_WORKER_BATCH_SIZE")

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
