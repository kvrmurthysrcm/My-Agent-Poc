"""Add RAG search full-text and lookup indexes.

Revision ID: 20260625_0001
Revises:
Create Date: 2026-06-25 22:45:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260625_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        ALTER TABLE public.rag_document_chunks
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_document_chunks_search_vector
        ON public.rag_document_chunks
        USING gin (search_vector)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_document_chunks_resource_page
        ON public.rag_document_chunks (resource_id, page_start, page_end)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunk_embeddings_model_lookup
        ON public.rag_chunk_embeddings
        (embedding_provider, embedding_model, embedding_version, embedding_dimension)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rag_chunk_embeddings_vector_hnsw
        ON public.rag_chunk_embeddings
        USING hnsw (vector vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_rag_chunk_embeddings_vector_hnsw")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_chunk_embeddings_model_lookup")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_document_chunks_resource_page")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_document_chunks_search_vector")
    op.execute("ALTER TABLE public.rag_document_chunks DROP COLUMN IF EXISTS search_vector")
