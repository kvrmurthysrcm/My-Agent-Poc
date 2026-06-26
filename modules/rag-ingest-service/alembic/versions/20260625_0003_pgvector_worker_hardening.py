"""pgvector dimension and db worker hardening

Revision ID: 20260625_0003
Revises: 20260625_0002
Create Date: 2026-06-25
"""

from alembic import op

revision = "20260625_0003"
down_revision = "20260625_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE public.rag_ingestion_jobs ADD COLUMN IF NOT EXISTS worker_id varchar(120)")
    op.execute("ALTER TABLE public.rag_ingestion_jobs ADD COLUMN IF NOT EXISTS locked_at timestamp without time zone")
    op.execute("ALTER TABLE public.rag_ingestion_jobs ADD COLUMN IF NOT EXISTS heartbeat_at timestamp without time zone")
    op.execute("ALTER TABLE public.rag_ingestion_jobs ADD COLUMN IF NOT EXISTS next_retry_at timestamp without time zone")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_jobs_worker_id ON public.rag_ingestion_jobs (worker_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_jobs_next_retry_at ON public.rag_ingestion_jobs (next_retry_at)")
    op.execute("ALTER TABLE public.rag_chunk_embeddings ALTER COLUMN vector TYPE vector(768) USING vector::text::vector(768)")
    op.execute("ALTER TABLE public.rag_chunk_embeddings ALTER COLUMN vector SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE public.rag_chunk_embeddings ALTER COLUMN vector DROP NOT NULL")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_jobs_next_retry_at")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_jobs_worker_id")
    op.execute("ALTER TABLE public.rag_ingestion_jobs DROP COLUMN IF EXISTS next_retry_at")
    op.execute("ALTER TABLE public.rag_ingestion_jobs DROP COLUMN IF EXISTS heartbeat_at")
    op.execute("ALTER TABLE public.rag_ingestion_jobs DROP COLUMN IF EXISTS locked_at")
    op.execute("ALTER TABLE public.rag_ingestion_jobs DROP COLUMN IF EXISTS worker_id")
