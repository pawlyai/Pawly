"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE subscriptiontier AS ENUM ('new_free','old_free','plus','pro')")
    op.execute("CREATE TYPE species AS ENUM ('cat','dog','other')")
    op.execute("CREATE TYPE gender AS ENUM ('male','female','unknown')")
    op.execute("CREATE TYPE neuteredstatus AS ENUM ('yes','no','unknown')")
    op.execute("CREATE TYPE lifestage AS ENUM ('puppy','kitten','adult','senior')")
    op.execute("CREATE TYPE memorytype AS ENUM ('profile','chronic','baseline','pattern','environment','safety','snapshot','symptom','episode','intervention','followup')")
    op.execute("CREATE TYPE memoryterm AS ENUM ('short','mid','long')")
    op.execute("CREATE TYPE memorysource AS ENUM ('user_input','ai_extracted','form_entry')")
    op.execute("CREATE TYPE pendingstatus AS ENUM ('auto_approved','needs_confirmation','rejected','expired','user_rejected','committed')")
    op.execute("CREATE TYPE changereason AS ENUM ('user_confirmed','auto_update','conflict_resolved','system_stage_update')")
    op.execute("CREATE TYPE messagerole AS ENUM ('user','bot')")
    op.execute("CREATE TYPE messagetype AS ENUM ('text','image','audio','file','cta')")
    op.execute("CREATE TYPE risklevel AS ENUM ('low','med','high')")
    op.execute("CREATE TYPE sentiment AS ENUM ('calm','anxious','panic')")
    op.execute("CREATE TYPE triagelevel AS ENUM ('red','orange','green')")
    op.execute("CREATE TYPE severity AS ENUM ('mild','moderate','severe','critical')")

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.String(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("locale", sa.String(), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("subscription_tier", sa.Enum("new_free","old_free","plus","pro", name="subscriptiontier", create_type=False), nullable=False, server_default="new_free"),
        sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # ── pets ───────────────────────────────────────────────────────────────────
    op.create_table(
        "pets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("species", sa.Enum("cat","dog","other", name="species", create_type=False), nullable=False),
        sa.Column("breed", sa.String(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("age_in_months", sa.Integer(), nullable=True),
        sa.Column("gender", sa.Enum("male","female","unknown", name="gender", create_type=False), nullable=False, server_default="unknown"),
        sa.Column("neutered_status", sa.Enum("yes","no","unknown", name="neuteredstatus", create_type=False), nullable=False, server_default="unknown"),
        sa.Column("weight_latest", sa.Float(), nullable=True),
        sa.Column("stage", sa.Enum("puppy","kitten","adult","senior", name="lifestage", create_type=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── raw_messages ───────────────────────────────────────────────────────────
    op.create_table(
        "raw_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("pet_id", sa.String(), nullable=True),
        sa.Column("dialogue_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("user","bot", name="messagerole", create_type=False), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("media_urls", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("telegram_msg_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False, server_default="telegram"),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("entry_source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── pet_memories ───────────────────────────────────────────────────────────
    op.create_table(
        "pet_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pets.id"), nullable=False),
        sa.Column("memory_type", sa.Enum("profile","chronic","baseline","pattern","environment","safety","snapshot","symptom","episode","intervention","followup", name="memorytype", create_type=False), nullable=False),
        sa.Column("memory_term", sa.Enum("short","mid","long", name="memoryterm", create_type=False), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("source", sa.Enum("user_input","ai_extracted","form_entry", name="memorysource", create_type=False), nullable=False),
        sa.Column("source_message_id", sa.String(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pet_memories_pet_id", "pet_memories", ["pet_id"])
    op.create_index("ix_pet_memories_field", "pet_memories", ["field"])
    op.create_index("ix_pet_memories_is_active", "pet_memories", ["is_active"])
    op.create_index("ix_pet_memories_pet_field_active", "pet_memories", ["pet_id", "field", "is_active"])

    # ── pending_memory_changes ─────────────────────────────────────────────────
    op.create_table(
        "pending_memory_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("proposed_value", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.String(), nullable=False),
        sa.Column("memory_type", sa.Enum("profile","chronic","baseline","pattern","environment","safety","snapshot","symptom","episode","intervention","followup", name="memorytype", create_type=False), nullable=False),
        sa.Column("memory_term", sa.Enum("short","mid","long", name="memoryterm", create_type=False), nullable=False),
        sa.Column("validation_status", sa.Enum("auto_approved","needs_confirmation","rejected","expired","user_rejected","committed", name="pendingstatus", create_type=False), nullable=False),
        sa.Column("validation_reason", sa.String(), nullable=False),
        sa.Column("conflict_with_id", sa.String(), nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by_user", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── pet_memory_change_logs ─────────────────────────────────────────────────
    op.create_table(
        "pet_memory_change_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("field_changed", sa.String(), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Enum("user_confirmed","auto_update","conflict_resolved","system_stage_update", name="changereason", create_type=False), nullable=False),
        sa.Column("related_message_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── chat_sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.UniqueConstraint("user_id", "date", name="uq_chat_session_user_date"),
    )

    # ── dialogues ─────────────────────────────────────────────────────────────
    op.create_table(
        "dialogues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("pet_id", sa.String(), nullable=True),
        sa.Column("topic_primary", sa.String(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dialogue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dialogues.id"), nullable=False),
        sa.Column("role", sa.Enum("user","bot", name="messagerole", create_type=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Enum("text","image","audio","file","cta", name="messagetype", create_type=False), nullable=False, server_default="text"),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("symptom_tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("risk_level", sa.Enum("low","med","high", name="risklevel", create_type=False), nullable=True),
        sa.Column("sentiment_user", sa.Enum("calm","anxious","panic", name="sentiment", create_type=False), nullable=True),
        sa.Column("entry_source", sa.String(), nullable=True),
        sa.Column("is_risk_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("risk_trigger_name", sa.String(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── triage_records ────────────────────────────────────────────────────────
    op.create_table(
        "triage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("llm_classification", sa.Enum("red","orange","green", name="triagelevel", create_type=False), nullable=False),
        sa.Column("rule_classification", sa.Enum("red","orange","green", name="triagelevel", create_type=False), nullable=True),
        sa.Column("final_classification", sa.Enum("red","orange","green", name="triagelevel", create_type=False), nullable=False),
        sa.Column("symptoms", sa.JSON(), nullable=False),
        sa.Column("visit_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── episodes ──────────────────────────────────────────────────────────────
    op.create_table(
        "episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pets.id"), nullable=False),
        sa.Column("symptom_type", sa.String(), nullable=False),
        sa.Column("severity", sa.Enum("mild","moderate","severe","critical", name="severity", create_type=False), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("is_ongoing", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("interventions", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── daily_summaries ───────────────────────────────────────────────────────
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pet_id", "date", name="uq_daily_summary_pet_date"),
    )

    # ── weekly_summaries ──────────────────────────────────────────────────────
    op.create_table(
        "weekly_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pet_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pet_id", "week_start", name="uq_weekly_summary_pet_week"),
    )


def downgrade() -> None:
    op.drop_table("weekly_summaries")
    op.drop_table("daily_summaries")
    op.drop_table("episodes")
    op.drop_table("triage_records")
    op.drop_table("messages")
    op.drop_table("dialogues")
    op.drop_table("chat_sessions")
    op.drop_table("pet_memory_change_logs")
    op.drop_table("pending_memory_changes")
    op.drop_table("pet_memories")
    op.drop_table("raw_messages")
    op.drop_table("pets")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS severity")
    op.execute("DROP TYPE IF EXISTS triagelevel")
    op.execute("DROP TYPE IF EXISTS sentiment")
    op.execute("DROP TYPE IF EXISTS risklevel")
    op.execute("DROP TYPE IF EXISTS messagetype")
    op.execute("DROP TYPE IF EXISTS messagerole")
    op.execute("DROP TYPE IF EXISTS changereason")
    op.execute("DROP TYPE IF EXISTS pendingstatus")
    op.execute("DROP TYPE IF EXISTS memorysource")
    op.execute("DROP TYPE IF EXISTS memoryterm")
    op.execute("DROP TYPE IF EXISTS memorytype")
    op.execute("DROP TYPE IF EXISTS lifestage")
    op.execute("DROP TYPE IF EXISTS neuteredstatus")
    op.execute("DROP TYPE IF EXISTS gender")
    op.execute("DROP TYPE IF EXISTS species")
    op.execute("DROP TYPE IF EXISTS subscriptiontier")
