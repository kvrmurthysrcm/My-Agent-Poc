from dataclasses import dataclass

from app.core.constants import EmbeddingProviderName


@dataclass(frozen=True)
class EmbeddingModelSpec:
    provider: EmbeddingProviderName
    model: str
    dimension: int


SUPPORTED_EMBEDDING_MODELS: dict[tuple[EmbeddingProviderName, str], EmbeddingModelSpec] = {
    (EmbeddingProviderName.OPENAI, "text-embedding-3-small"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OPENAI,
        model="text-embedding-3-small",
        dimension=1536,
    ),
    (EmbeddingProviderName.OPENAI, "text-embedding-3-large"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OPENAI,
        model="text-embedding-3-large",
        dimension=3072,
    ),
    (EmbeddingProviderName.OLLAMA, "embeddinggemma"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OLLAMA,
        model="embeddinggemma",
        dimension=768,
    ),
    (EmbeddingProviderName.OLLAMA, "nomic-embed-text"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OLLAMA,
        model="nomic-embed-text",
        dimension=768,
    ),
    (EmbeddingProviderName.OLLAMA, "bge-m3"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OLLAMA,
        model="bge-m3",
        dimension=1024,
    ),
    (EmbeddingProviderName.OLLAMA, "mxbai-embed-large"): EmbeddingModelSpec(
        provider=EmbeddingProviderName.OLLAMA,
        model="mxbai-embed-large",
        dimension=1024,
    ),
}


DENIED_CHAT_MODEL_PREFIXES = ("llama",)
DENIED_CHAT_MODEL_NAMES = {"mistral:latest", "gemma4"}


def get_embedding_model_spec(provider: EmbeddingProviderName, model: str) -> EmbeddingModelSpec | None:
    return SUPPORTED_EMBEDDING_MODELS.get((provider, model.strip()))


def resolve_embedding_dimension(provider: EmbeddingProviderName, model: str) -> int:
    spec = get_embedding_model_spec(provider, model)
    if spec is None:
        _raise_unsupported_model(provider, model)
    return spec.dimension


def validate_embedding_model(provider: EmbeddingProviderName, model: str, dimension: int | None) -> None:
    spec = get_embedding_model_spec(provider, model)
    if spec is None:
        _raise_unsupported_model(provider, model)
    if dimension is None:
        return
    if spec.dimension != dimension:
        raise ValueError(
            f"Embedding dimension mismatch for {provider.value}/{model}: "
            f"expected {spec.dimension}, configured {dimension}"
        )


def _raise_unsupported_model(provider: EmbeddingProviderName, model: str) -> None:
    normalized = model.strip().lower()
    if (
        normalized in DENIED_CHAT_MODEL_NAMES
        or normalized.startswith(DENIED_CHAT_MODEL_PREFIXES)
        or ("qwen" in normalized and "embed" not in normalized)
    ):
        raise ValueError(f"{provider.value}/{model} is a chat/generation model and cannot be used as EMBEDDING_MODEL")

    supported = ", ".join(f"{item.provider.value}/{item.model}" for item in SUPPORTED_EMBEDDING_MODELS.values())
    raise ValueError(
        f"Unsupported embedding model {provider.value}/{model}. "
        f"Use one of: {supported}. Chat/generation models are not valid EMBEDDING_MODEL values."
    )
