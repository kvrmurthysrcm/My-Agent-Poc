from app.core.config import get_settings
from app.services.chunking_strategies.factory import ChunkingStrategyFactory
from app.services.chunking_types import TextChunk
from app.services.chunk_quality import filter_quality_chunks


class ChunkingService:
    def chunk(
        self,
        text: str,
        chunk_size_tokens: int,
        chunk_overlap_tokens: int,
        strategy: str = "SEMANTIC_RECURSIVE",
    ) -> list[TextChunk]:
        settings = get_settings()
        chunking_strategy = ChunkingStrategyFactory.build(strategy)
        return filter_quality_chunks(
            chunking_strategy.chunk(text, chunk_size_tokens, chunk_overlap_tokens),
            keep_numeric_table_chunks=settings.chunk_quality_keep_numeric_table_chunks,
            min_alpha_ratio=settings.chunk_quality_min_alpha_ratio,
        )
