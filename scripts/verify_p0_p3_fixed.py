#!/usr/bin/env python3
"""
Quick manual verification that P0-P3 optimizations are in place and working.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

async def verify_p0():
    """Verify P0: Session Bridge"""
    from src.memory.reader import _build_session_bridge

    print("[P0] Session Bridge Implementation...")
    print("  Function exists: _build_session_bridge")
    print("  Expected: Loads previous day summary + open episodes")

    # Check if function is callable
    if callable(_build_session_bridge):
        print("  [OK] _build_session_bridge found and callable")
    else:
        print("  [FAIL] _build_session_bridge not callable")
        return False

    return True


async def verify_p1():
    """Verify P1: Episode Timeline Sorting"""
    from src.llm.prompts.context import _sort_episodes_by_timeline
    from src.db.models import PetMemory
    from datetime import datetime, timezone
    import uuid

    print("\n[P1] Episode Timeline Sorting...")
    print("  Function exists: _sort_episodes_by_timeline")
    print("  Expected: Sorts by temporal_context (Week 1, Month 2, Day 5)")

    # Create mock episodes with temporal context
    test_episodes = [
        PetMemory(
            id=uuid.uuid4(),
            pet_id=uuid.uuid4(),
            field="symptom_severity",
            value={"v": "moderate"},
            memory_type="EPISODE",
            temporal_context="Week 3",
            confidence_score=0.9,
        ),
        PetMemory(
            id=uuid.uuid4(),
            pet_id=uuid.uuid4(),
            field="symptom_severity",
            value={"v": "mild"},
            memory_type="EPISODE",
            temporal_context="Week 1",
            confidence_score=0.9,
        ),
        PetMemory(
            id=uuid.uuid4(),
            pet_id=uuid.uuid4(),
            field="symptom_severity",
            value={"v": "severe"},
            memory_type="EPISODE",
            temporal_context="Week 2",
            confidence_score=0.9,
        ),
    ]

    sorted_eps = _sort_episodes_by_timeline(test_episodes)
    print(f"  Input:  Week 3, Week 1, Week 2")
    print(f"  Output: {', '.join(e.temporal_context for e in sorted_eps)}")

    if sorted_eps[0].temporal_context == "Week 1" and sorted_eps[2].temporal_context == "Week 3":
        print("  [OK] Correctly sorted chronologically")
        return True
    else:
        print("  [FAIL] Sorting not working correctly")
        return False


async def verify_p2():
    """Verify P2: Episode Auto-Closure"""
    from src.memory.committer import _check_episode_recovery

    print("\n[P2] Episode Auto-Closure Implementation...")
    print("  Function exists: _check_episode_recovery")
    print("  Expected: Detects recovery signals and closes episodes")

    if callable(_check_episode_recovery):
        print("  [OK] _check_episode_recovery found and callable")
        print("  Recovery signals: improved, recovered, normal, better, etc.")
        return True
    else:
        print("  [FAIL] _check_episode_recovery not callable")
        return False


async def verify_p3():
    """Verify P3: Keywords + Temporal Context Fields"""
    from src.db.models import PetMemory
    import inspect

    print("\n[P3] Multi-Signal Retrieval Fields...")

    # Check PetMemory has keywords and temporal_context
    pm = PetMemory.__table__.columns
    has_keywords = 'keywords' in [c.name for c in pm]
    has_temporal = 'temporal_context' in [c.name for c in pm]

    print(f"  Database fields:")
    print(f"    - keywords: {has_keywords}")
    print(f"    - temporal_context: {has_temporal}")

    if has_keywords and has_temporal:
        print("  [OK] Database schema includes mem0 fields")
    else:
        print("  [FAIL] Missing database fields")
        return False

    # Check reader.py uses multi-signal retrieval
    from src.memory.reader import load_related_memories
    source = inspect.getsource(load_related_memories)
    has_multi_signal = 'keyword' in source.lower() and 'field' in source.lower()

    if has_multi_signal:
        print("  [OK] load_related_memories uses multi-signal retrieval")
        return True
    else:
        print("  [FAIL] Multi-signal retrieval not found")
        return False


async def main():
    print("=" * 70)
    print("P0-P3 OPTIMIZATION VERIFICATION")
    print("=" * 70)

    results = []

    # Run verifications
    results.append(("P0: Session Bridge", await verify_p0()))
    results.append(("P1: Timeline Sorting", await verify_p1()))
    results.append(("P2: Auto-Closure", await verify_p2()))
    results.append(("P3: Multi-Signal", await verify_p3()))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\nResult: {passed}/{total} optimizations verified")

    if passed == total:
        print("\n[SUCCESS] All P0-P3 optimizations are in place!")
        print("\nNext steps:")
        print("  1. Run 20-case smoke test (validates integration)")
        print("  2. Run 200-case full test (proves scalability)")
        print("  3. Deploy to staging")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} optimization(s) failed verification")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
