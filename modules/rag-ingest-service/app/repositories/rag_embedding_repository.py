from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import RagChunkEmbedding


class RagEmbeddingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_embeddings(self, rows: list[dict]) -> list[RagChunkEmbedding]:
        embeddings = [RagChunkEmbedding(**row) for row in rows]
        self.db.add_all(embeddings)
        self.db.flush()
        return embeddings

    def list_existing_embeddings(
        self,
        chunk_ids: list[str],
        provider: str,
        model: str,
        version: str,
    ) -> list[RagChunkEmbedding]:
        if not chunk_ids:
            return []
        return list(
            self.db.scalars(
                select(RagChunkEmbedding)
                .where(RagChunkEmbedding.chunk_id.in_(chunk_ids))
                .where(RagChunkEmbedding.embedding_provider == provider)
                .where(RagChunkEmbedding.embedding_model == model)
                .where(RagChunkEmbedding.embedding_version == version)
            )
        )

    def existing_chunk_ids(
        self,
        chunk_ids: list[str],
        provider: str,
        model: str,
        version: str,
    ) -> set[str]:
        return {
            embedding.chunk_id
            for embedding in self.list_existing_embeddings(
                chunk_ids=chunk_ids,
                provider=provider,
                model=model,
                version=version,
            )
        }
