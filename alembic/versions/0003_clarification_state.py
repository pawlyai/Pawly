"""add clarification loop state to dialogues

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-05
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dialogues",
        sa.Column(
            "clarification_round",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "dialogues",
        sa.Column("clarification_state", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dialogues", "clarification_state")
    op.drop_column("dialogues", "clarification_round")
