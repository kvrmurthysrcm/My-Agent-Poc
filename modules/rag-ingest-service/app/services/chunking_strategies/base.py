from abc import ABC, abstractmethod

from app.services.chunking_types import TextChunk


class ChunkingStrategy(ABC):
    strategy_name: str

    @abstractmethod
    def chunk(self, text: str, chunk_size_tokens: int, chunk_overlap_tokens: int) -> list[TextChunk]:
        raise NotImplementedError
