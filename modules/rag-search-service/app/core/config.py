import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import EmbeddingProviderName
from app.search.lexical import DEFAULT_TOKEN_ALIASES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        "postgresql://library_user:library_pass@localhost:5432/online_library",
        alias="DATABASE_URL",
    )
    app_profile: str = Field("local", alias="APP_PROFILE")
    auto_create_tables: bool = Field(False, alias="AUTO_CREATE_TABLES")
    auto_migrate_on_startup: bool = Field(True, alias="AUTO_MIGRATE_ON_STARTUP")

    embedding_provider: EmbeddingProviderName = Field(EmbeddingProviderName.OLLAMA, alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field("nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_dimension: int | None = Field(None, alias="EMBEDDING_DIMENSION")
    embedding_version: str = Field("v1", alias="EMBEDDING_VERSION")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    allow_fake_embeddings: bool = Field(False, alias="ALLOW_FAKE_EMBEDDINGS")
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")

    search_default_mode: str = Field("hybrid", alias="SEARCH_DEFAULT_MODE")
    search_default_top_k: int = Field(10, alias="SEARCH_DEFAULT_TOP_K")
    search_max_top_k: int = Field(50, alias="SEARCH_MAX_TOP_K")
    search_min_score: float = Field(0.0, alias="SEARCH_MIN_SCORE")
    search_vector_weight: float = Field(0.70, alias="SEARCH_VECTOR_WEIGHT")
    search_keyword_weight: float = Field(0.30, alias="SEARCH_KEYWORD_WEIGHT")
    hybrid_oversampling_factor: int = Field(5, alias="HYBRID_OVERSAMPLING_FACTOR")
    hybrid_fusion_strategy: str = Field("rrf", alias="HYBRID_FUSION_STRATEGY")
    rrf_k: int = Field(60, alias="RRF_K")
    rerank_enabled: bool = Field(True, alias="RERANK_ENABLED")
    rerank_top_n: int = Field(30, alias="RERANK_TOP_N")
    rerank_strategy: str = Field("local", alias="RERANK_STRATEGY")
    search_keep_numeric_table_chunks: bool = Field(True, alias="SEARCH_KEEP_NUMERIC_TABLE_CHUNKS")
    search_min_alpha_ratio: float = Field(0.45, alias="SEARCH_MIN_ALPHA_RATIO")
    search_enable_metadata_filters: bool = Field(True, alias="SEARCH_ENABLE_METADATA_FILTERS")
    search_include_chunk_text_default: bool = Field(True, alias="SEARCH_INCLUDE_CHUNK_TEXT_DEFAULT")
    search_admin_enabled: bool = Field(True, alias="SEARCH_ADMIN_ENABLED")
    search_observability_enabled: bool = Field(False, alias="SEARCH_OBSERVABILITY_ENABLED")
    query_aliases: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_TOKEN_ALIASES), alias="QUERY_ALIASES")
    query_aliases_file: str | None = Field(None, alias="QUERY_ALIASES_FILE")

    @field_validator("embedding_model")
    @classmethod
    def normalize_embedding_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("search_default_mode")
    @classmethod
    def normalize_search_default_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"vector", "keyword", "hybrid"}:
            raise ValueError("SEARCH_DEFAULT_MODE must be vector, keyword, or hybrid")
        return normalized

    @field_validator("search_default_top_k", "search_max_top_k")
    @classmethod
    def validate_search_top_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Search top_k values must be at least 1")
        if value > 200:
            raise ValueError("Search top_k values must be 200 or lower")
        return value

    @field_validator("search_min_score")
    @classmethod
    def validate_search_min_score(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("SEARCH_MIN_SCORE must be between 0 and 1")
        return value

    @field_validator("search_vector_weight", "search_keyword_weight")
    @classmethod
    def validate_search_weight(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("Search weights must be between 0 and 1")
        return value

    @field_validator("hybrid_oversampling_factor")
    @classmethod
    def validate_hybrid_oversampling_factor(cls, value: int) -> int:
        if value < 1:
            raise ValueError("HYBRID_OVERSAMPLING_FACTOR must be at least 1")
        if value > 20:
            raise ValueError("HYBRID_OVERSAMPLING_FACTOR must be 20 or lower")
        return value

    @field_validator("hybrid_fusion_strategy")
    @classmethod
    def normalize_hybrid_fusion_strategy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"rrf", "weighted"}:
            raise ValueError("HYBRID_FUSION_STRATEGY must be rrf or weighted")
        return normalized

    @field_validator("rrf_k")
    @classmethod
    def validate_rrf_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RRF_K must be at least 1")
        if value > 1000:
            raise ValueError("RRF_K must be 1000 or lower")
        return value

    @field_validator("rerank_top_n")
    @classmethod
    def validate_rerank_top_n(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RERANK_TOP_N must be at least 1")
        if value > 500:
            raise ValueError("RERANK_TOP_N must be 500 or lower")
        return value

    @field_validator("rerank_strategy")
    @classmethod
    def normalize_rerank_strategy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local"}:
            raise ValueError("RERANK_STRATEGY must be local")
        return normalized

    @field_validator("search_min_alpha_ratio")
    @classmethod
    def validate_search_min_alpha_ratio(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("SEARCH_MIN_ALPHA_RATIO must be between 0 and 1")
        return value

    @field_validator("query_aliases")
    @classmethod
    def normalize_query_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(source).strip().lower(): str(target).strip().lower()
            for source, target in value.items()
            if str(source).strip() and str(target).strip()
        }

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
        self.query_aliases = self._load_query_aliases()
        return self

    def _load_query_aliases(self) -> dict[str, str]:
        aliases = dict(DEFAULT_TOKEN_ALIASES)
        aliases.update(self.query_aliases)
        if not self.query_aliases_file:
            return aliases

        alias_path = Path(self.query_aliases_file)
        if not alias_path.exists():
            raise ValueError(f"QUERY_ALIASES_FILE does not exist: {self.query_aliases_file}")
        try:
            file_aliases = json.loads(alias_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"QUERY_ALIASES_FILE must contain a JSON object: {self.query_aliases_file}") from exc
        if not isinstance(file_aliases, dict):
            raise ValueError("QUERY_ALIASES_FILE must contain a JSON object")
        aliases.update(
            {
                str(source).strip().lower(): str(target).strip().lower()
                for source, target in file_aliases.items()
                if str(source).strip() and str(target).strip()
            }
        )
        return aliases

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
