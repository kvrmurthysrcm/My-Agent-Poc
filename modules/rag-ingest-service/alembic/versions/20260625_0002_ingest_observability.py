"""ingest observability and progress fields

Revision ID: 20260625_0002
Revises: 20260624_0001
Create Date: 2026-06-25
"""

from alembic import op

revision = "20260625_0002"
down_revision = "20260624_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.rag_ingestion_jobs ADD COLUMN IF NOT EXISTS progress_message text")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.rag_profiling_events (
            profile_event_id uuid NOT NULL DEFAULT gen_random_uuid(),
            job_id uuid NOT NULL,
            resource_id uuid NOT NULL,
            step varchar(120) NOT NULL,
            status varchar(30) NOT NULL,
            elapsed_ms double precision NOT NULL DEFAULT 0,
            event_index integer NOT NULL,
            details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT rag_profiling_events_pkey PRIMARY KEY (profile_event_id),
            CONSTRAINT rag_profiling_events_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.rag_ingestion_jobs(job_id),
            CONSTRAINT rag_profiling_events_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_profile_events_job_id ON public.rag_profiling_events (job_id, event_index)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_profile_events_resource_id ON public.rag_profiling_events (resource_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_rag_profile_events_resource_id")
    op.execute("DROP INDEX IF EXISTS public.ix_rag_profile_events_job_id")
    op.execute("DROP TABLE IF EXISTS public.rag_profiling_events")
    op.execute("ALTER TABLE public.rag_ingestion_jobs DROP COLUMN IF EXISTS progress_message")
