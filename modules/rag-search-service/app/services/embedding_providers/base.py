from typing import Protocol


class EmbeddingProvider(Protocol):
    provider_name: str
    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...
