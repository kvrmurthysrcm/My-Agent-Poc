from app.core.config import Settings
from app.core.constants import AsyncBackend, EmbeddingProviderName
from app.services.async_backends.db_worker_dispatcher import DbWorkerDispatcher
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider


def test_embedding_provider_factory_selects_openai():
    settings = Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OPENAI, EMBEDDING_MODEL="text-embedding-3-small")
    assert isinstance(EmbeddingProviderFactory.build(settings), OpenAIEmbeddingProvider)


def test_embedding_provider_factory_selects_ollama():
    settings = Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA, EMBEDDING_MODEL="mistral:latest")
    assert isinstance(EmbeddingProviderFactory.build(settings), OllamaEmbeddingProvider)


def test_dispatcher_factory_selects_db_worker():
    settings = Settings(ASYNC_BACKEND=AsyncBackend.DB_WORKER)
    assert isinstance(JobDispatcherFactory.build(settings), DbWorkerDispatcher)
