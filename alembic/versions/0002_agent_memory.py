"""add agent_memories table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New enums
    op.execute(
        "CREATE TYPE agentmemorycategory AS ENUM "
        "('preference','communication','pattern','relationship','goal')"
    )
    op.execute(
        "CREATE TYPE agentmemoryscope AS ENUM ('short','long')"
    )

    op.create_table(
        "agent_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "category",
            postgresql.ENUM(
                "preference", "communication", "pattern", "relationship", "goal",
                name="agentmemorycategory",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "scope",
            postgresql.ENUM(
                "short", "long",
                name="agentmemoryscope",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("source_message_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_field", "agent_memories", ["field"])
    op.create_index("ix_agent_memories_is_active", "agent_memories", ["is_active"])
    op.create_index(
        "ix_agent_memories_user_field_active",
        "agent_memories",
        ["user_id", "field", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_memories_user_field_active", table_name="agent_memories")
    op.drop_index("ix_agent_memories_is_active", table_name="agent_memories")
    op.drop_index("ix_agent_memories_field", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_id", table_name="agent_memories")
    op.drop_table("agent_memories")
    op.execute("DROP TYPE agentmemoryscope")
    op.execute("DROP TYPE agentmemorycategory")
