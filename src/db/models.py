"""
SQLAlchemy 2.0 ORM models using declarative mapped_column style.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    Index,
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Python enums
# ---------------------------------------------------------------------------

class Species(str, enum.Enum):
    CAT = "cat"
    DOG = "dog"
    OTHER = "other"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class NeuteredStatus(str, enum.Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class LifeStage(str, enum.Enum):
    PUPPY = "puppy"
    KITTEN = "kitten"
    ADULT = "adult"
    SENIOR = "senior"


class SubscriptionTier(str, enum.Enum):
    NEW_FREE = "new_free"
    OLD_FREE = "old_free"
    PLUS = "plus"
    PRO = "pro"


class MemoryType(str, enum.Enum):
    PROFILE = "profile"
    CHRONIC = "chronic"
    BASELINE = "baseline"
    PATTERN = "pattern"
    ENVIRONMENT = "environment"
    SAFETY = "safety"
    SNAPSHOT = "snapshot"
    SYMPTOM = "symptom"
    EPISODE = "episode"
    INTERVENTION = "intervention"
    FOLLOWUP = "followup"


class MemoryTerm(str, enum.Enum):
    SHORT = "short"
    MID = "mid"
    LONG = "long"


class MemorySource(str, enum.Enum):
    USER_INPUT = "user_input"
    AI_EXTRACTED = "ai_extracted"
    FORM_ENTRY = "form_entry"


class PendingStatus(str, enum.Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    REJECTED = "rejected"
    EXPIRED = "expired"
    USER_REJECTED = "user_rejected"
    COMMITTED = "committed"


class ChangeReason(str, enum.Enum):
    USER_CONFIRMED = "user_confirmed"
    AUTO_UPDATE = "auto_update"
    CONFLICT_RESOLVED = "conflict_resolved"
    SYSTEM_STAGE_UPDATE = "system_stage_update"


class MessageRole(str, enum.Enum):
    USER = "user"
    BOT = "bot"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"
    CTA = "cta"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"


class Sentiment(str, enum.Enum):
    CALM = "calm"
    ANXIOUS = "anxious"
    PANIC = "panic"


class TriageLevel(str, enum.Enum):
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"


class Severity(str, enum.Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    locale: Mapped[str] = mapped_column(String, default="en", nullable=False)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SAEnum(SubscriptionTier, name="subscriptiontier"),
        default=SubscriptionTier.NEW_FREE,
        nullable=False,
    )
    credit_balance: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    pets: Mapped[list["Pet"]] = relationship("Pet", back_populates="user")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    species: Mapped[Species] = mapped_column(SAEnum(Species, name="species"), nullable=False)
    breed: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    age_in_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Gender] = mapped_column(
        SAEnum(Gender, name="gender"), default=Gender.UNKNOWN, nullable=False
    )
    neutered_status: Mapped[NeuteredStatus] = mapped_column(
        SAEnum(NeuteredStatus, name="neuteredstatus"), default=NeuteredStatus.UNKNOWN, nullable=False
    )
    weight_latest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stage: Mapped[Optional[LifeStage]] = mapped_column(SAEnum(LifeStage, name="lifestage"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="pets")


class RawMessage(Base):
    """Append-only raw message log — no updated_at."""

    __tablename__ = "raw_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    pet_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dialogue_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="messagerole"), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    telegram_msg_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    channel: Mapped[str] = mapped_column(String, default="telegram", nullable=False)
    locale: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entry_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PetMemory(Base):
    __tablename__ = "pet_memories"
    __table_args__ = (
        # Composite index for fast look-ups by pet + field + active status
        Index("ix_pet_memories_pet_field_active", "pet_id", "field", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pets.id"), nullable=False, index=True)
    memory_type: Mapped[MemoryType] = mapped_column(SAEnum(MemoryType, name="memorytype"), nullable=False)
    memory_term: Mapped[MemoryTerm] = mapped_column(SAEnum(MemoryTerm, name="memoryterm"), nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[MemorySource] = mapped_column(SAEnum(MemorySource, name="memorysource"), nullable=False)
    source_message_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)


class PendingMemoryChange(Base):
    __tablename__ = "pending_memory_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    proposed_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[str] = mapped_column(String, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(SAEnum(MemoryType, name="memorytype"), nullable=False)
    memory_term: Mapped[MemoryTerm] = mapped_column(SAEnum(MemoryTerm, name="memoryterm"), nullable=False)
    validation_status: Mapped[PendingStatus] = mapped_column(
        SAEnum(PendingStatus, name="pendingstatus"), nullable=False
    )
    validation_reason: Mapped[str] = mapped_column(String, nullable=False)
    conflict_with_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirmed_by_user: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PetMemoryChangeLog(Base):
    __tablename__ = "pet_memory_change_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    field_changed: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[ChangeReason] = mapped_column(SAEnum(ChangeReason, name="changereason"), nullable=False)
    related_message_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_chat_session_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    dialogues: Mapped[list["Dialogue"]] = relationship("Dialogue", back_populates="session")


class Dialogue(Base):
    __tablename__ = "dialogues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False
    )
    pet_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    topic_primary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="dialogues")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="dialogue")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dialogue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dialogues.id"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="messagerole"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType, name="messagetype"), default=MessageType.TEXT, nullable=False
    )
    intent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    symptom_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(SAEnum(RiskLevel, name="risklevel"), nullable=True)
    sentiment_user: Mapped[Optional[Sentiment]] = mapped_column(SAEnum(Sentiment, name="sentiment"), nullable=True)
    entry_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_risk_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_trigger_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    dialogue: Mapped["Dialogue"] = relationship("Dialogue", back_populates="messages")


class TriageRecord(Base):
    __tablename__ = "triage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    llm_classification: Mapped[TriageLevel] = mapped_column(
        SAEnum(TriageLevel, name="triagelevel"), nullable=False
    )
    rule_classification: Mapped[Optional[TriageLevel]] = mapped_column(
        SAEnum(TriageLevel, name="triagelevel"), nullable=True
    )
    final_classification: Mapped[TriageLevel] = mapped_column(
        SAEnum(TriageLevel, name="triagelevel"), nullable=False
    )
    symptoms: Mapped[dict] = mapped_column(JSON, nullable=False)
    visit_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pets.id"), nullable=False)
    symptom_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity, name="severity"), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_ongoing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interventions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    __table_args__ = (UniqueConstraint("pet_id", "date", name="uq_daily_summary_pet_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"
    __table_args__ = (UniqueConstraint("pet_id", "week_start", name="uq_weekly_summary_pet_week"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
