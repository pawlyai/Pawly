import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.db.models import MemoryTerm, MemoryType, PendingStatus
from src.memory.extractor import MemoryProposal
from src.memory.validator import validate_proposal


def _proposal(
    *,
    field: str,
    value: object,
    confidence: float,
    memory_term: MemoryTerm = MemoryTerm.SHORT,
    memory_type: MemoryType = MemoryType.SNAPSHOT,
) -> MemoryProposal:
    return MemoryProposal(
        field=field,
        value=value,
        confidence=confidence,
        source_quote="quoted text",
        memory_type=memory_type,
        memory_term=memory_term,
        observed_at=None,
    )


def _memory(
    *,
    field: str,
    value: object,
    created_at: datetime,
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        field=field,
        value=value if isinstance(value, dict) else {"v": value},
        is_active=is_active,
        created_at=created_at,
        updated_at=None,
    )


def _pet() -> SimpleNamespace:
    # validate_proposal currently does not inspect pet fields.
    return SimpleNamespace()


def test_validate_rejects_unknown_field() -> None:
    result = validate_proposal(
        _proposal(field="not_a_real_field", value="x", confidence=0.95),
        [],
        _pet(),
    )
    assert result.status == PendingStatus.REJECTED
    assert result.reason == "unknown_field:not_a_real_field"


def test_validate_critical_field_needs_confirmation() -> None:
    existing = [
        _memory(
            field="breed",
            value="husky",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    ]
    result = validate_proposal(
        _proposal(
            field="breed",
            value="samoyed",
            confidence=0.99,
            memory_term=MemoryTerm.LONG,
            memory_type=MemoryType.PROFILE,
        ),
        existing,
        _pet(),
    )
    assert result.status == PendingStatus.NEEDS_CONFIRMATION
    assert result.reason == "critical_field"
    assert result.conflict_with_id == str(existing[0].id)
    assert result.expires_at is not None


def test_validate_rejects_duplicate_value() -> None:
    existing = [
        _memory(
            field="current_appetite",
            value="normal",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    ]
    result = validate_proposal(
        _proposal(field="current_appetite", value="normal", confidence=0.9),
        existing,
        _pet(),
    )
    assert result.status == PendingStatus.REJECTED
    assert result.reason == "duplicate"


def test_validate_conflict_high_confidence_auto_approved() -> None:
    existing = [
        _memory(
            field="current_appetite",
            value="low",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    ]
    result = validate_proposal(
        _proposal(field="current_appetite", value="normal", confidence=0.95),
        existing,
        _pet(),
    )
    assert result.status == PendingStatus.AUTO_APPROVED
    assert result.reason == "high_confidence_override"
    assert result.conflict_with_id == str(existing[0].id)


def test_validate_new_fact_low_confidence_rejected() -> None:
    result = validate_proposal(
        _proposal(field="current_appetite", value="normal", confidence=0.2),
        [],
        _pet(),
    )
    assert result.status == PendingStatus.REJECTED
    assert result.reason.startswith("low_confidence:")
