from app.services.chunking_strategies.factory import ChunkingStrategyFactory
from app.services.chunking_types import TextChunk


class ChunkingService:
    def chunk(
        self,
        text: str,
        chunk_size_tokens: int,
        chunk_overlap_tokens: int,
        strategy: str = "SEMANTIC_RECURSIVE",
    ) -> list[TextChunk]:
        chunking_strategy = ChunkingStrategyFactory.build(strategy)
        return chunking_strategy.chunk(text, chunk_size_tokens, chunk_overlap_tokens)
