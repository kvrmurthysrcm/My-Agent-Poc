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
    op.execute("DROP TABLE IF EXISTS public.rag_processing_errors CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_chunk_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_document_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_document_extractions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.rag_ingestion_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS public.user_bookshelf CASCADE")
    op.execute("DROP TABLE IF EXISTS public.reviews CASCADE")
    op.execute("DROP TABLE IF EXISTS public.reading_progress CASCADE")
    op.execute("DROP TABLE IF EXISTS public.downloads CASCADE")
    op.execute("DROP TABLE IF EXISTS public.audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS public.subscription_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS public.user_subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.user_approval_requests CASCADE")
    op.execute("DROP TABLE IF EXISTS public.resource_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS public.resource_authors CASCADE")
    op.execute("DROP TABLE IF EXISTS public.resources CASCADE")
    op.execute("DROP TABLE IF EXISTS public.library_users CASCADE")
    op.execute("DROP TABLE IF EXISTS public.tags CASCADE")
    op.execute("DROP TABLE IF EXISTS public.subscription_tiers CASCADE")
    op.execute("DROP TABLE IF EXISTS public.categories CASCADE")
    op.execute("DROP TABLE IF EXISTS public.authors CASCADE")
