from sqlalchemy.orm import Session

from app.db.models import RagDocumentChunk, RagDocumentExtraction


class RagChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_extraction(self, **fields) -> RagDocumentExtraction:
        extraction = RagDocumentExtraction(**fields)
        self.db.add(extraction)
        self.db.flush()
        return extraction

    def create_chunks(self, chunks: list[dict]) -> list[RagDocumentChunk]:
        rows = [RagDocumentChunk(**chunk) for chunk in chunks]
        self.db.add_all(rows)
        self.db.flush()
        return rows
