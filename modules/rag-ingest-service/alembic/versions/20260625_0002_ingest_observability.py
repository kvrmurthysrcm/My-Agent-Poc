"""ingest observability and progress fields

Revision ID: 20260625_0002
Revises: 20260624_0001
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260625_0002"
down_revision = "20260624_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_ingestion_jobs", sa.Column("progress_message", sa.Text(), nullable=True), schema="public")
    op.create_table(
        "rag_profiling_events",
        sa.Column("profile_event_id", postgresql.UUID(as_uuid=False), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("step", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("elapsed_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("details_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("profile_event_id"),
        sa.ForeignKeyConstraint(["job_id"], ["public.rag_ingestion_jobs.job_id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["public.resources.resource_id"]),
        schema="public",
    )
    op.create_index("ix_rag_profile_events_job_id", "rag_profiling_events", ["job_id", "event_index"], schema="public")
    op.create_index("ix_rag_profile_events_resource_id", "rag_profiling_events", ["resource_id"], schema="public")


def downgrade() -> None:
    op.drop_index("ix_rag_profile_events_resource_id", table_name="rag_profiling_events", schema="public")
    op.drop_index("ix_rag_profile_events_job_id", table_name="rag_profiling_events", schema="public")
    op.drop_table("rag_profiling_events", schema="public")
    op.drop_column("rag_ingestion_jobs", "progress_message", schema="public")
