from enum import StrEnum


class EmbeddingProviderName(StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
