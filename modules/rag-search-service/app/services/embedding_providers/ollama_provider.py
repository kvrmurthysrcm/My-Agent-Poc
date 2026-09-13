import logging

import httpx

from app.services.embedding_providers.ollama_dependency import (
    ollama_model_unavailable_error,
    ollama_unavailable_error,
)


logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
                response.raise_for_status()
                payload = response.json()
                embeddings = payload.get("embeddings") or payload.get("embedding")
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings
                return [embeddings]
        except httpx.RequestError as exc:
            error = ollama_unavailable_error(base_url=self.base_url, model=self.model, cause=exc)
            logger.error("Ollama embedding request failed: %s", error)
            raise error from exc
        except httpx.HTTPStatusError as exc:
            error_factory = ollama_model_unavailable_error if exc.response.status_code == 404 else ollama_unavailable_error
            error = error_factory(base_url=self.base_url, model=self.model, cause=exc)
            logger.error("Ollama embedding request failed: %s", error)
            raise error from exc
