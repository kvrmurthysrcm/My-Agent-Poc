from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


LlmProviderName = Literal["ollama", "openai", "gemini"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_profile: str = Field("local", alias="APP_PROFILE")
    rag_search_base_url: str = Field("http://127.0.0.1:8001", alias="RAG_SEARCH_BASE_URL")
    rag_search_timeout_seconds: float = Field(90.0, alias="RAG_SEARCH_TIMEOUT_SECONDS")
    answer_default_top_k: int = Field(10, alias="ANSWER_DEFAULT_TOP_K")
    answer_context_top_k: int = Field(10, alias="ANSWER_CONTEXT_TOP_K")
    answer_max_context_chars: int = Field(12000, alias="ANSWER_MAX_CONTEXT_CHARS")
    answer_max_chars_per_source: int = Field(1800, alias="ANSWER_MAX_CHARS_PER_SOURCE")
    answer_include_sources: bool = Field(True, alias="ANSWER_INCLUDE_SOURCES")
    answer_require_context: bool = Field(True, alias="ANSWER_REQUIRE_CONTEXT")
    answer_observability_enabled: bool = Field(False, alias="ANSWER_OBSERVABILITY_ENABLED")
    answer_compare_models: str = Field(
        "mistral:latest,gemma4,llama3:8b,gemma:7b,gemini:gemini-2.5-flash",
        alias="ANSWER_COMPARE_MODELS",
    )
    answer_system_instruction: str | None = Field(None, alias="ANSWER_SYSTEM_INSTRUCTION")
    answer_synthesis_instruction: str | None = Field(None, alias="ANSWER_SYNTHESIS_INSTRUCTION")
    answer_guardrail_instruction: str | None = Field(None, alias="ANSWER_GUARDRAIL_INSTRUCTION")

    llm_provider: LlmProviderName = Field("ollama", alias="LLM_PROVIDER")
    llm_model: str = Field("mistral:latest", alias="LLM_MODEL")
    llm_temperature: float = Field(0.1, alias="LLM_TEMPERATURE")
    llm_timeout_seconds: float = Field(180.0, alias="LLM_TIMEOUT_SECONDS")
    ollama_base_url: str = Field("http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4.1-mini", alias="OPENAI_MODEL")
    gemini_api_key: str | None = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta",
        alias="GEMINI_BASE_URL",
    )

    @field_validator("rag_search_base_url", "ollama_base_url", "gemini_base_url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("rag_search_timeout_seconds", "llm_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Timeout values must be greater than 0")
        if value > 600:
            raise ValueError("Timeout values must be 600 seconds or lower")
        return value

    @field_validator("answer_default_top_k", "answer_context_top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        if value < 1:
            raise ValueError("top_k values must be at least 1")
        if value > 50:
            raise ValueError("top_k values must be 50 or lower")
        return value

    @field_validator("answer_max_context_chars")
    @classmethod
    def validate_max_context_chars(cls, value: int) -> int:
        if value < 1000:
            raise ValueError("ANSWER_MAX_CONTEXT_CHARS must be at least 1000")
        if value > 50000:
            raise ValueError("ANSWER_MAX_CONTEXT_CHARS must be 50000 or lower")
        return value

    @field_validator("answer_max_chars_per_source")
    @classmethod
    def validate_max_chars_per_source(cls, value: int) -> int:
        if value < 500:
            raise ValueError("ANSWER_MAX_CHARS_PER_SOURCE must be at least 500")
        if value > 10000:
            raise ValueError("ANSWER_MAX_CHARS_PER_SOURCE must be 10000 or lower")
        return value

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if value < 0 or value > 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        return value

    @model_validator(mode="after")
    def validate_provider_config(self) -> "Settings":
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
