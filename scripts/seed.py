"""
Seed script: inserts a test user (telegram_id="test_001") with pet Milo.
Run from the project root:
    python scripts/seed.py
"""

import asyncio
import sys
from pathlib import Path

# Allow importing src from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings  # noqa: E402 — must come after sys.path insert
from src.db.engine import close_engine, init_engine, get_session_factory
from src.db.models import Gender, NeuteredStatus, Pet, Species, User


async def seed() -> None:
    await init_engine()
    factory = get_session_factory()

    from sqlalchemy import select

    async with factory() as db:
        # Check if test user already exists
        result = await db.execute(
            select(User).where(User.telegram_id == "test_001")
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id="test_001",
                telegram_username="test_user",
                display_name="Test User",
                locale="en",
            )
            db.add(user)
            await db.flush()
            print(f"Created user: {user.id}")
        else:
            print(f"User already exists: {user.id}")

        # Check if Milo already exists
        pet_result = await db.execute(
            select(Pet).where(Pet.user_id == user.id, Pet.name == "Milo")
        )
        pet = pet_result.scalar_one_or_none()

        if pet is None:
            pet = Pet(
                user_id=user.id,
                name="Milo",
                species=Species.CAT,
                breed="British Shorthair",
                age_in_months=36,  # 3 years
                gender=Gender.MALE,
                neutered_status=NeuteredStatus.YES,
                weight_latest=4.2,
                is_active=True,
            )
            db.add(pet)
            await db.flush()
            print(f"Created pet: {pet.id} ({pet.name})")
        else:
            print(f"Pet already exists: {pet.id} ({pet.name})")

        await db.commit()
        print("Seed complete.")

    await close_engine()


if __name__ == "__main__":
    asyncio.run(seed())
