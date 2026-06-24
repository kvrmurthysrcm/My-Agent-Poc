from sqlalchemy.orm import Session

from app.db.models import RagChunkEmbedding


class RagEmbeddingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_embeddings(self, rows: list[dict]) -> list[RagChunkEmbedding]:
        embeddings = [RagChunkEmbedding(**row) for row in rows]
        self.db.add_all(embeddings)
        self.db.flush()
        return embeddings
