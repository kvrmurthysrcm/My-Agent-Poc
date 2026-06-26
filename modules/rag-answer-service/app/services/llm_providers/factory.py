from app.core.config import Settings
from app.services.llm_providers.base import LlmProvider
from app.services.llm_providers.ollama_provider import OllamaLlmProvider
from app.services.llm_providers.openai_provider import OpenAiLlmProvider


class LlmProviderFactory:
    @staticmethod
    def build(settings: Settings) -> LlmProvider:
        if settings.llm_provider == "ollama":
            return OllamaLlmProvider(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        if settings.llm_provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return OpenAiLlmProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=settings.llm_temperature,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
