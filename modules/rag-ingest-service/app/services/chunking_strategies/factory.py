from app.services.chunking_strategies.base import ChunkingStrategy
from app.services.chunking_strategies.intelligent_recursive import IntelligentRecursiveChunkingStrategy
from app.services.chunking_strategies.semantic_recursive import SemanticRecursiveChunkingStrategy


class ChunkingStrategyFactory:
    @staticmethod
    def build(strategy: str) -> ChunkingStrategy:
        normalized = strategy.strip().upper()
        if normalized == "INTELLIGENT_RECURSIVE":
            return IntelligentRecursiveChunkingStrategy()
        if normalized == "SEMANTIC_RECURSIVE":
            return SemanticRecursiveChunkingStrategy()
        raise ValueError("Unsupported chunking strategy. Use INTELLIGENT_RECURSIVE or SEMANTIC_RECURSIVE.")
