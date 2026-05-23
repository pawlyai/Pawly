"""add proactive_events table and daily_summaries.pushed_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_summaries",
        sa.Column("pushed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "proactive_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("telegram_id", sa.String(64), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "triage_followup",
                "daily_summary_push",
                "episode_checkin",
                "memory_reminder",
                "pending_memory_nudge",
                name="proactiveeventtype",
            ),
            nullable=False,
        ),
        sa.Column("trigger_ref_id", sa.String(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("skipped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("skipped_reason", sa.String(), nullable=True),
        sa.Column("content_preview", sa.String(300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "event_type", "trigger_ref_id", "stage",
            name="uq_proactive_event_type_ref_stage",
        ),
    )
    op.create_index("ix_proactive_events_user_id", "proactive_events", ["user_id"])
    op.create_index(
        "ix_proactive_events_pending",
        "proactive_events",
        ["scheduled_at"],
        postgresql_where=sa.text("sent_at IS NULL AND skipped = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_proactive_events_pending", table_name="proactive_events")
    op.drop_index("ix_proactive_events_user_id", table_name="proactive_events")
    op.drop_table("proactive_events")
    op.execute("DROP TYPE IF EXISTS proactiveeventtype")
    op.drop_column("daily_summaries", "pushed_at")
