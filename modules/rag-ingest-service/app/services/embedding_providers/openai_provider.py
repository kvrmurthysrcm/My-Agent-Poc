class OpenAIEmbeddingProvider:
    provider_name = "openai"

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            return [self._deterministic_vector(text) for text in texts]
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAI embeddings") from exc
        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def _deterministic_vector(self, text: str) -> list[float]:
        seed = abs(hash((self.model, text)))
        return [((seed >> (index % 32)) & 255) / 255 for index in range(1536)]
