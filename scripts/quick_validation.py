#!/usr/bin/env python3
"""
Quick validation: Compare multiagent vs mem0_validator on a single health test case.
"""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, str(__file__).split("scripts")[0])

from src.config import settings
from src.memory.extractor import extract_memories
from src.db.models import Pet, Gender, Species, NeuteredStatus


# Simple health test case
HEALTH_CASE = [
    {
        "role": "user",
        "content": "Milo has been limping on his back left leg for the past week. It started after he jumped off the couch."
    },
    {
        "role": "assistant",
        "content": "Limping after an injury is concerning. Has there been any swelling? Is he putting any weight on that leg?"
    },
    {
        "role": "user",
        "content": "There's some mild swelling and he's avoiding putting weight on it. He's eating normally but seems quieter than usual."
    },
    {
        "role": "assistant",
        "content": "This could be a ligament injury or fracture. I recommend a vet visit for X-rays to rule out fractures. Meanwhile, restrict his activity and keep him calm."
    },
]


async def run_extraction(backend: str) -> dict:
    """Run extraction with specified backend."""
    print(f"\n{'='*70}")
    print(f"Testing: {backend.upper()} Backend")
    print(f"{'='*70}")

    # Set backend
    settings.extraction_backend = backend

    pet = Pet(
        id="test-pet-id",
        user_id="test-user-id",
        name="Milo",
        species=Species.DOG,
        breed="Labrador",
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        age_in_months=36,
        weight_latest=30.0,
        created_at=datetime.now(),
    )

    print(f"\nExtracting memories with {backend}...")
    try:
        proposals = await extract_memories(HEALTH_CASE, pet, [])

        print(f"\nResults:")
        print(f"  Facts extracted: {len(proposals)}")

        if proposals:
            # Analyze extracted facts
            types = {}
            for p in proposals:
                t = p.memory_type.value
                types[t] = types.get(t, 0) + 1

            print(f"  By type: {types}")

            # Check for key facts
            fields = {p.field for p in proposals}
            print(f"  Fields: {fields}")

            # Average confidence
            avg_conf = sum(p.confidence for p in proposals) / len(proposals)
            print(f"  Avg confidence: {avg_conf:.2f}")

            # Check for Mem0 fields
            has_keywords = sum(1 for p in proposals if p.keywords)
            has_temporal = sum(1 for p in proposals if p.temporal_context)
            print(f"  Mem0 fields: {has_keywords} with keywords, {has_temporal} with temporal_context")

        return {
            "backend": backend,
            "facts": len(proposals),
            "success": True,
            "proposals": proposals,
        }

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "backend": backend,
            "facts": 0,
            "success": False,
            "error": str(e),
        }


async def main():
    print("\n" + "="*70)
    print("QUICK VALIDATION: Multiagent vs Mem0+Validator")
    print("="*70)

    # Test multiagent
    multiagent_result = await run_extraction("multiagent")

    # Test mem0_validator
    mem0_result = await run_extraction("mem0_validator")

    # Comparison
    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)

    print(f"\nFact Extraction Count:")
    print(f"  Multiagent:      {multiagent_result['facts']} facts")
    print(f"  Mem0+Validator:  {mem0_result['facts']} facts")

    if multiagent_result['facts'] > 0 and mem0_result['facts'] > 0:
        improvement = mem0_result['facts'] - multiagent_result['facts']
        pct = (improvement / multiagent_result['facts'] * 100) if multiagent_result['facts'] > 0 else 0

        if improvement > 0:
            print(f"  >> Mem0 improvement: +{improvement} facts ({pct:.1f}%)")
        elif improvement < 0:
            print(f"  >> Multiagent wins: -{improvement} facts ({abs(pct):.1f}%)")
        else:
            print(f"  >> Same extraction count")

    print(f"\nExecution Status:")
    print(f"  Multiagent: {'[OK] Success' if multiagent_result['success'] else '[FAIL] Failed'}")
    print(f"  Mem0+Validator: {'[OK] Success' if mem0_result['success'] else '[FAIL] Failed'}")

    print("\n" + "="*70)
    if multiagent_result['success'] and mem0_result['success']:
        print("[PASS] Both backends working! Ready for Phase C full test.")
    else:
        print("[FAIL] One or more backends failed. Check errors above.")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
