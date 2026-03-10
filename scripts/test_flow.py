"""
End-to-end test script: simulates the full message handling flow.
Run from the project root after seeding:
    python scripts/test_flow.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.config import settings
from src.db.engine import close_engine, get_session_factory, init_engine
from src.db.models import Pet, User
from src.db.redis import close_redis, init_redis
from src.llm.orchestrator import generate_response
from src.triage.rules_engine import classify_triage, get_matched_symptoms


async def run() -> None:
    print("=== Pawly E2E Test Flow ===\n")

    await init_engine()
    await init_redis()

    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == "test_001"))
        user = result.scalar_one_or_none()
        if user is None:
            print("ERROR: test user not found. Run scripts/seed.py first.")
            return

        pet_result = await db.execute(select(Pet).where(Pet.user_id == user.id, Pet.name == "Milo"))
        pet = pet_result.scalar_one_or_none()
        print(f"User: {user.display_name} (telegram_id={user.telegram_id})")
        print(f"Pet : {pet.name if pet else 'None'}\n")

    # Test triage classification
    test_messages = [
        ("Milo is eating well and playing!", "GREEN"),
        ("He has been vomiting for 2 hours", "ORANGE"),
        ("My cat collapsed and is not breathing", "RED"),
    ]
    print("--- Triage Tests ---")
    for msg, expected in test_messages:
        result = classify_triage(msg)
        symptoms = get_matched_symptoms(msg)
        status = "PASS" if result == expected else "FAIL"
        print(f"[{status}] '{msg[:50]}...' => {result} (expected {expected})")
        if symptoms:
            print(f"       Symptoms: {symptoms}")

    # Test LLM response (requires valid API key)
    print("\n--- LLM Response Test ---")
    if settings.anthropic_api_key and settings.anthropic_api_key != "your-anthropic-api-key-here":
        async with factory() as db:
            result = await db.execute(select(User).where(User.telegram_id == "test_001"))
            user = result.scalar_one_or_none()
            pet_result = await db.execute(
                select(Pet).where(Pet.user_id == user.id, Pet.name == "Milo")
            )
            pet = pet_result.scalar_one_or_none()

        result = await generate_response(
            user=user,
            pet=pet,
            dialogue_id="00000000-0000-0000-0000-000000000001",
            user_message="Milo sneezed 3 times this morning. Should I be worried?",
        )
        print(f"Triage : {result.triage_result}")
        print(f"Bot reply:\n{result.response_text}")
    else:
        print("Skipping LLM test — ANTHROPIC_API_KEY not configured.")

    await close_redis()
    await close_engine()
    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(run())
