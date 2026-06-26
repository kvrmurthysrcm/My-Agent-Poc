class OpenAIEmbeddingProvider:
    provider_name = "openai"

    def __init__(self, api_key: str | None, model: str, dimension: int = 1536, allow_fake_embeddings: bool = False):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self.allow_fake_embeddings = allow_fake_embeddings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            if not self.allow_fake_embeddings:
                raise RuntimeError("OPENAI_API_KEY is required unless ALLOW_FAKE_EMBEDDINGS=true")
            return [self._deterministic_vector(text) for text in texts]
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAI embeddings") from exc
        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def _deterministic_vector(self, text: str) -> list[float]:
        import hashlib

        digest = hashlib.sha256(f"{self.model}:{text}".encode("utf-8")).digest()
        return [digest[index % len(digest)] / 255 for index in range(self.dimension)]
