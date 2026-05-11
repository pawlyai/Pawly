"""add general_kb_entry table + pgvector extension

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-11

Adds the general-purpose pet care knowledge base used for hybrid keyword +
vector retrieval. Covers topics outside the symptom triage SOP (followups.yaml):
indoor enrichment, behaviour, life stages, breed care, region-specific norms.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension. Idempotent; safe to run on a DB that already has it.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "general_kb_entry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # gemini text-embedding-004 default dim is 768.
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("keywords_en", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("keywords_cn", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("citations", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Replace the ARRAY-typed embedding column with a real pgvector column.
    # Doing it in two steps keeps the migration runnable on environments where
    # the extension was just enabled and SQLAlchemy doesn't yet know the type.
    op.execute("ALTER TABLE general_kb_entry DROP COLUMN embedding")
    op.execute("ALTER TABLE general_kb_entry ADD COLUMN embedding vector(768)")

    # Index for fast similarity search. ivfflat needs a sample of rows to build
    # a meaningful index; for an empty table we create it now but rebuild after
    # bulk ingest if the corpus grows beyond a few hundred entries.
    op.execute(
        "CREATE INDEX general_kb_entry_embedding_idx "
        "ON general_kb_entry USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 50)"
    )

    # Postgres FTS over content + keywords for the keyword half of hybrid search.
    op.execute(
        "CREATE INDEX general_kb_entry_content_fts_idx "
        "ON general_kb_entry USING gin (to_tsvector('english', content))"
    )
    op.execute(
        "CREATE INDEX general_kb_entry_keywords_en_idx "
        "ON general_kb_entry USING gin (keywords_en)"
    )
    op.execute(
        "CREATE INDEX general_kb_entry_keywords_cn_idx "
        "ON general_kb_entry USING gin (keywords_cn)"
    )

    op.create_index("ix_general_kb_entry_domain", "general_kb_entry", ["domain"])


def downgrade() -> None:
    op.drop_index("ix_general_kb_entry_domain", table_name="general_kb_entry")
    op.execute("DROP INDEX IF EXISTS general_kb_entry_keywords_cn_idx")
    op.execute("DROP INDEX IF EXISTS general_kb_entry_keywords_en_idx")
    op.execute("DROP INDEX IF EXISTS general_kb_entry_content_fts_idx")
    op.execute("DROP INDEX IF EXISTS general_kb_entry_embedding_idx")
    op.drop_table("general_kb_entry")
    # Leave the pgvector extension installed — other tables/migrations may use it.
