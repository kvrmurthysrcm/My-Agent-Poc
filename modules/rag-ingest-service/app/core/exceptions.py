class RagIngestError(Exception):
    """Base exception for expected RAG ingestion failures."""


class ValidationError(RagIngestError):
    """Raised when request validation fails."""


class UnsupportedAsyncBackendError(RagIngestError):
    """Raised when ASYNC_BACKEND is unsupported."""


class UnsupportedEmbeddingProviderError(RagIngestError):
    """Raised when EMBEDDING_PROVIDER is unsupported."""
