"""
Custom context types shared across bot handlers and middleware.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from src.db.models import Pet, User


@dataclass
class PawlyContext:
    """Resolved per-request context injected by middleware."""

    user: User
    pet: Optional[Pet] = None
    session_id: Optional[str] = None
    dialogue_id: Optional[str] = None
    locale: str = "en"
    extra: dict = field(default_factory=dict)

    @property
    def user_id_str(self) -> str:
        return str(self.user.id)

    @property
    def pet_id_str(self) -> Optional[str]:
        return str(self.pet.id) if self.pet else None

    @property
    def telegram_id(self) -> str:
        return self.user.telegram_id
