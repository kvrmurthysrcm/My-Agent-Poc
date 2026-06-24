import httpx


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        with httpx.Client(timeout=60) as client:
            for text in texts:
                response = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": text})
                response.raise_for_status()
                payload = response.json()
                embeddings = payload.get("embeddings") or payload.get("embedding")
                if embeddings and isinstance(embeddings[0], list):
                    vectors.append(embeddings[0])
                else:
                    vectors.append(embeddings)
        return vectors
