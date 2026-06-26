"""rag ingestion schema

Revision ID: 20260624_0001
Revises:
Create Date: 2026-06-24
"""

from alembic import op

revision = "20260624_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with open("sql/schema.sql", encoding="utf-8") as handle:
        op.execute(handle.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.rag_profiling_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_processing_errors CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_chunk_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_document_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_document_extractions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_ingestion_jobs CASCADE")
