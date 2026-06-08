#!/usr/bin/env python3
"""
Analyze Phase C comparison results (multiagent vs mem0_validator).

Loads test reports and compares key metrics.
"""

import json
from pathlib import Path
from typing import Any


def load_report(report_path: Path) -> dict[str, Any]:
    """Load a test report JSON file."""
    if not report_path.exists():
        return {}

    with open(report_path) as f:
        return json.load(f)


def analyze_report(report: dict, backend_name: str) -> dict[str, Any]:
    """Extract key metrics from a test report."""
    summary = report.get("summary", {})
    cases = report.get("cases", [])

    # Calculate metrics
    total = len(cases)
    passed = sum(1 for c in cases if c.get("pass", False))
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Group by scenario type
    acute_cases = [c for c in cases if "acute" in c.get("type", "").lower()]
    acute_passed = sum(1 for c in acute_cases if c.get("pass", False))
    acute_rate = (acute_passed / len(acute_cases) * 100) if acute_cases else 0

    health_cases = [c for c in cases if "health" in c.get("type", "").lower()]
    health_passed = sum(1 for c in health_cases if c.get("pass", False))
    health_rate = (health_passed / len(health_cases) * 100) if health_cases else 0

    # Memory metrics (if available)
    avg_memory_count = 0
    avg_memory_visibility = 0
    if cases:
        memory_counts = [c.get("metadata", {}).get("memory_count", 0) for c in cases]
        memory_visibility = [c.get("metadata", {}).get("memory_visibility", 0) for c in cases]
        avg_memory_count = sum(memory_counts) / len(memory_counts) if memory_counts else 0
        avg_memory_visibility = sum(memory_visibility) / len(memory_visibility) if memory_visibility else 0

    return {
        "backend": backend_name,
        "total_cases": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "acute_cases": len(acute_cases),
        "acute_passed": acute_passed,
        "acute_rate": acute_rate,
        "health_cases": len(health_cases),
        "health_passed": health_passed,
        "health_rate": health_rate,
        "avg_memory_count": avg_memory_count,
        "avg_memory_visibility": avg_memory_visibility,
    }


def compare_backends(multiagent: dict, mem0: dict) -> None:
    """Print comparison of two backends."""
    print("\n" + "=" * 80)
    print("PHASE C COMPARISON RESULTS")
    print("=" * 80)

    print("\nOverall Performance:")
    print(f"{'Metric':<30} {'Multi-Agent':<20} {'Mem0+Validator':<20} {'Difference':<20}")
    print("-" * 90)

    # Overall pass rate
    diff = mem0["pass_rate"] - multiagent["pass_rate"]
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    print(f"{'Pass Rate':<30} {multiagent['pass_rate']:>18.1f}% {mem0['pass_rate']:>18.1f}% {arrow} {diff:>18.1f}%")

    # Acute scenario
    diff = mem0["acute_rate"] - multiagent["acute_rate"]
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    print(f"{'Acute Pass Rate':<30} {multiagent['acute_rate']:>18.1f}% {mem0['acute_rate']:>18.1f}% {arrow} {diff:>18.1f}%")

    # Health scenario
    diff = mem0["health_rate"] - multiagent["health_rate"]
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    print(f"{'Health Pass Rate':<30} {multiagent['health_rate']:>18.1f}% {mem0['health_rate']:>18.1f}% {arrow} {diff:>18.1f}%")

    # Memory count
    diff = mem0["avg_memory_count"] - multiagent["avg_memory_count"]
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    print(f"{'Avg Memory Count':<30} {multiagent['avg_memory_count']:>18.1f} {mem0['avg_memory_count']:>18.1f} {arrow} {diff:>18.1f}")

    # Memory visibility
    diff = mem0["avg_memory_visibility"] - multiagent["avg_memory_visibility"]
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    print(f"{'Avg Memory Visibility':<30} {multiagent['avg_memory_visibility']:>18.1f} {mem0['avg_memory_visibility']:>18.1f} {arrow} {diff:>18.1f}")

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if mem0["pass_rate"] > multiagent["pass_rate"]:
        improvement = mem0["pass_rate"] - multiagent["pass_rate"]
        print(f"\n✅ Mem0+Validator wins with {improvement:.1f}% improvement")
        print(f"   Recommend: Set EXTRACTION_BACKEND=mem0_validator as default")
    elif multiagent["pass_rate"] > mem0["pass_rate"]:
        improvement = multiagent["pass_rate"] - mem0["pass_rate"]
        print(f"\n❌ Multi-Agent wins with {improvement:.1f}% improvement")
        print(f"   Recommend: Keep current system")
    else:
        print(f"\n➡️  Same performance ({mem0['pass_rate']:.1f}%)")
        print(f"   Recommend: Use Mem0 (simpler, fewer API calls)")


def main():
    results_dir = Path("tests/blackbox_multiturn/results")

    # Find most recent reports
    multiagent_reports = sorted(
        results_dir.glob("multiturn_phase0_200_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not multiagent_reports:
        print("No test reports found. Run Phase C tests first.")
        return

    print("Found test reports:")
    for report in multiagent_reports[:5]:
        print(f"  - {report.name} ({report.stat().st_mtime})")

    # For now, just show available reports
    print("\nTo run Phase C comparison:")
    print("  EXTRACTION_BACKEND=multiagent pytest tests/blackbox_multiturn/...")
    print("  EXTRACTION_BACKEND=mem0_validator pytest tests/blackbox_multiturn/...")


if __name__ == "__main__":
    main()
