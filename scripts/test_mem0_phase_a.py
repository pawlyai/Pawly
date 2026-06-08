#!/usr/bin/env python3
"""
Test Phase A: Mem0-inspired memory extraction.

This tests the new Mem0 extraction backend on the Acute dental extraction case
to compare with the current multi-agent approach.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Configure settings BEFORE importing extractor
from src.config import settings

# Import after config setup
from src.memory.extractor import extract_memories
from src.db.models import Pet, Gender, Species, NeuteredStatus

# Test conversation: dental extraction post-operative
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


async def test_mem0_extraction():
    """Test Mem0 extraction on acute post-operative case."""
    # Switch to Mem0 backend
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

    print("=" * 80)
    print("PHASE A: Mem0-inspired Memory Extraction Test")
    print("=" * 80)
    print("\nTest case: Dental extraction post-operative conversation (8 turns)")
    print("Expected memories:")
    print("  - procedure_type: dental extraction")
    print("  - post_op_restrictions: confinement for 2 weeks, soft food only")
    print("  - post_op_medications: gabapentin 300mg 2x daily, doxycycline")
    print("  - post_op_timeline: recheck in 2 weeks")
    print("  - emergency_signs: excessive bleeding, swelling, difficulty breathing, fever")
    print()

    print("Running Mem0 extraction (extraction_backend={})...".format(settings.extraction_backend))
    try:
        # Run extraction with Mem0 backend
        proposals = await extract_memories(TEST_CONVERSATION, pet, [])

        print(f"\nExtraction result: {len(proposals)} facts extracted")

        if proposals:
            print("\nExtracted facts:")
            for i, p in enumerate(proposals, 1):
                print(f"\n{i}. {p.field}")
                print(f"   value: {str(p.value)[:60]}")
                print(f"   confidence: {p.confidence:.2f}")
                print(f"   type: {p.memory_type.value}")
                print(f"   term: {p.memory_term.value}")
                if p.source_quote:
                    print(f"   source: {p.source_quote[:50]}")

            # Check for critical facts
            print("\nCritical facts check:")
            fields = {p.field for p in proposals}

            critical = {
                "procedure_type": "procedure_type" in fields,
                "post_op_restrictions": "post_op_restrictions" in fields,
                "post_op_medications": "post_op_medications" in fields,
                "post_op_timeline": "post_op_timeline" in fields,
                "emergency_signs": "emergency_signs" in fields,
            }

            for field, found in critical.items():
                status = "FOUND" if found else "MISSING"
                print(f"  {status}: {field}")

            found_count = sum(critical.values())
            print(f"\nTotal critical facts: {found_count}/5")

            if found_count >= 3:
                print("\nRESULT: Mem0 extraction working!")
            else:
                print("\nRESULT: Mem0 needs adjustment")
        else:
            print("No facts extracted - check logs for errors")

    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()


async def test_multiagent_extraction():
    """Test current multi-agent extraction (for comparison)."""
    # Temporarily switch to multiagent backend
    original_backend = settings.extraction_backend
    settings.extraction_backend = "multiagent"

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
    print("COMPARISON: Multi-agent Extraction (current approach)")
    print("=" * 80)
    print()

    print("Running multi-agent extraction...")
    try:
        proposals = await extract_memories(TEST_CONVERSATION, pet, [])

        print(f"\nExtraction result: {len(proposals)} facts extracted")

        if proposals:
            print("\nExtracted facts:")
            for i, p in enumerate(proposals, 1):
                print(f"\n{i}. {p.field}")
                print(f"   value: {str(p.value)[:60]}")
                print(f"   confidence: {p.confidence:.2f}")
                print(f"   type: {p.memory_type.value}")
                print(f"   term: {p.memory_term.value}")

            print(f"\nTotal facts extracted: {len(proposals)}")
        else:
            print("No facts extracted")

    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        settings.extraction_backend = original_backend


async def main():
    # Run Mem0 test (Phase A)
    await test_mem0_extraction()

    # Run multiagent test (for comparison)
    await test_multiagent_extraction()

    print("\n" + "=" * 80)
    print("Phase A Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
