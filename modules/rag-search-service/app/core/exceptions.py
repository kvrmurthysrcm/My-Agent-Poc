class RagSearchError(Exception):
    """Base exception for expected RAG search failures."""


class UnsupportedEmbeddingProviderError(RagSearchError):
    """Raised when EMBEDDING_PROVIDER is unsupported."""
