from app.core.config import Settings
from app.core.constants import EmbeddingProviderName
from app.core.exceptions import UnsupportedEmbeddingProviderError
from app.services.embedding_providers.base import EmbeddingProvider
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider


class EmbeddingProviderFactory:
    @staticmethod
    def build(settings: Settings) -> EmbeddingProvider:
        if settings.embedding_provider == EmbeddingProviderName.OPENAI:
            return OpenAIEmbeddingProvider(api_key=settings.openai_api_key, model=settings.embedding_model)
        if settings.embedding_provider == EmbeddingProviderName.OLLAMA:
            return OllamaEmbeddingProvider(base_url=settings.ollama_base_url, model=settings.embedding_model)
        raise UnsupportedEmbeddingProviderError(f"Unsupported embedding provider: {settings.embedding_provider}")
