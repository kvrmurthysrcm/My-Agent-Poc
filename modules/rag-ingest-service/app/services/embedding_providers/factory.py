from app.core.config import Settings
from app.core.constants import EmbeddingProviderName
from app.core.exceptions import UnsupportedEmbeddingProviderError
from app.services.embedding_providers.base import EmbeddingProvider
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding_model_registry import validate_embedding_model


class EmbeddingProviderFactory:
    @staticmethod
    def build(settings: Settings) -> EmbeddingProvider:
        validate_embedding_model(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension)
        if settings.embedding_provider == EmbeddingProviderName.OPENAI:
            return OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
                dimension=settings.embedding_dimension,
                allow_fake_embeddings=settings.allow_fake_embeddings,
            )
        if settings.embedding_provider == EmbeddingProviderName.OLLAMA:
            return OllamaEmbeddingProvider(
                base_url=settings.ollama_base_url,
                model=settings.embedding_model,
                timeout_seconds=settings.ollama_embedding_timeout_seconds,
            )
        raise UnsupportedEmbeddingProviderError(f"Unsupported embedding provider: {settings.embedding_provider}")
