from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import RagDocumentChunk, RagDocumentExtraction


class RagChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_extraction(self, **fields) -> RagDocumentExtraction:
        extraction = RagDocumentExtraction(**fields)
        self.db.add(extraction)
        self.db.flush()
        return extraction

    def get_extraction_for_job(self, job_id: str) -> RagDocumentExtraction | None:
        return self.db.scalar(
            select(RagDocumentExtraction)
            .where(RagDocumentExtraction.job_id == job_id)
            .order_by(RagDocumentExtraction.created_at.desc())
        )

    def create_chunks(self, chunks: list[dict]) -> list[RagDocumentChunk]:
        rows = [RagDocumentChunk(**chunk) for chunk in chunks]
        self.db.add_all(rows)
        self.db.flush()
        return rows

    def list_chunks_for_job(self, job_id: str) -> list[RagDocumentChunk]:
        return list(
            self.db.scalars(
                select(RagDocumentChunk)
                .where(RagDocumentChunk.job_id == job_id)
                .order_by(RagDocumentChunk.chunk_index)
            )
        )
