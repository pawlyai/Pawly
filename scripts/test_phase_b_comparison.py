#!/usr/bin/env python3
"""
Test Phase B: Compare Mem0 vs Mem0+Validator on the same test case.

This tests whether the validator improves or hurts Mem0 extraction.
"""

import asyncio
from datetime import datetime

from src.config import settings
from src.memory.extractor import extract_memories
from src.db.models import Pet, Gender, Species, NeuteredStatus

# Same test case as Phase A
TEST_CONVERSATION = [
    {
        "role": "user",
        "content": "Pawly, Charlie just came home from dental extraction recovery. The vet gave me specific instructions - he needs strict confinement for at least 2 weeks."
    },
    {
        "role": "assistant",
        "content": "That's wonderful news that Charlie is home and recovering! Dental extractions can be uncomfortable, so it's great you have clear post-operative instructions. Strict confinement for 2 weeks is the right approach to prevent complications."
    },
    {
        "role": "user",
        "content": "The vet prescribed pain medication - he's on gabapentin 300mg twice daily and doxycycline for infection prevention. The recheck is in 2 weeks."
    },
    {
        "role": "assistant",
        "content": "Perfect. Those are standard post-dental-extraction protocols. Gabapentin manages pain and doxycycline prevents infection. Make sure to complete the full course of antibiotics even if he seems better."
    },
    {
        "role": "user",
        "content": "What should I watch for in the first week that would be emergency-level?"
    },
    {
        "role": "assistant",
        "content": "Watch for these red-flag signs that would need emergency vet attention: excessive bleeding from the extraction sites, severe swelling of the face or jaw, difficulty breathing, and fever above 102.5 F."
    },
    {
        "role": "user",
        "content": "Can he eat normally?"
    },
    {
        "role": "assistant",
        "content": "No - soft food only for at least 5-7 days. Avoid hard kibble, treats, or anything that requires chewing near the extraction sites. Wet food, boiled chicken, and soft medications are best."
    },
]


async def test_phase_a():
    """Test Phase A: Mem0 extraction without validator."""
    settings.extraction_backend = "mem0"

    pet = Pet(
        id=1,
        user_id=1,
        name="Charlie",
        species=Species.DOG,
        breed="Mixed",
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        age_in_months=60,
        weight_latest=25.0,
        created_at=datetime.now(),
    )

    print("\n" + "=" * 80)
    print("PHASE A: Mem0 Extraction (no validator)")
    print("=" * 80)

    try:
        proposals = await extract_memories(TEST_CONVERSATION, pet, [])
        print(f"Facts extracted: {len(proposals)}")

        # Calculate average confidence
        if proposals:
            avg_conf = sum(p.confidence for p in proposals) / len(proposals)
            print(f"Average confidence: {avg_conf:.2f}")

            # Count by type
            types = {}
            for p in proposals:
                types[p.memory_type.value] = types.get(p.memory_type.value, 0) + 1

            print(f"Facts by type: {types}")

        return len(proposals), proposals

    except Exception as e:
        print(f"PHASE A failed: {e}")
        import traceback
        traceback.print_exc()
        return 0, []


async def test_phase_b():
    """Test Phase B: Mem0 extraction with validator."""
    settings.extraction_backend = "mem0_validator"

    pet = Pet(
        id=1,
        user_id=1,
        name="Charlie",
        species=Species.DOG,
        breed="Mixed",
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        age_in_months=60,
        weight_latest=25.0,
        created_at=datetime.now(),
    )

    print("\n" + "=" * 80)
    print("PHASE B: Mem0 + Validator Extraction")
    print("=" * 80)

    try:
        proposals = await extract_memories(TEST_CONVERSATION, pet, [])
        print(f"Facts extracted: {len(proposals)}")

        # Calculate average confidence
        if proposals:
            avg_conf = sum(p.confidence for p in proposals) / len(proposals)
            print(f"Average confidence: {avg_conf:.2f}")

            # Count by type
            types = {}
            for p in proposals:
                types[p.memory_type.value] = types.get(p.memory_type.value, 0) + 1

            print(f"Facts by type: {types}")

        return len(proposals), proposals

    except Exception as e:
        print(f"PHASE B failed: {e}")
        import traceback
        traceback.print_exc()
        return 0, []


async def main():
    print("=" * 80)
    print("PHASE B COMPARISON: Mem0 vs Mem0+Validator")
    print("=" * 80)

    phase_a_count, phase_a_props = await test_phase_a()
    phase_b_count, phase_b_props = await test_phase_b()

    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    print(f"\nFact counts:")
    print(f"  Phase A (Mem0 only):        {phase_a_count} facts")
    print(f"  Phase B (Mem0+Validator):   {phase_b_count} facts")

    if phase_b_count > phase_a_count:
        print(f"\n  -> Validator IMPROVES extraction by {phase_b_count - phase_a_count} facts")
        print("     Recommendation: Use Phase B for production")
    elif phase_b_count < phase_a_count:
        print(f"\n  -> Validator HURTS extraction, removes {phase_a_count - phase_b_count} facts")
        print("     Recommendation: Use Phase A for production")
    else:
        print(f"\n  -> No difference")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
