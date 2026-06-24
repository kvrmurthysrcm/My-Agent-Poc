from app.core.config import Settings
from app.services.embedding_providers.base import EmbeddingProvider


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    def embed_chunks(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(self.provider.embed_texts(texts[start : start + batch_size]))
        return vectors
