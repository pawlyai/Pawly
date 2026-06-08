#!/usr/bin/env python3
"""
Quick test to verify fixture loading works.
"""
import json
from pathlib import Path

# Test if data file exists
data_path = Path("tests/blackbox_multiturn/test_data/multiturn_crossday_llm_200cases_cases.json")
print(f"Data file exists: {data_path.exists()}")

if data_path.exists():
    with open(data_path) as f:
        cases = json.load(f)
    print(f"Cases in file: {len(cases)}")
    if cases:
        print(f"First case name: {cases[0].get('name', 'unnamed')}")
        print(f"First case has {len(cases[0].get('days', []))} days")
        print(f"Required fields: {list(cases[0].keys())}")

        # Check if pytest_generate_tests can parametrize this
        print(f"\nFixture should parametrize {len(cases)} cases")
        print("To run the test:")
        print("  pytest tests/blackbox_multiturn/test_crossday_multiturn.py \\")
        print("    --crossday-topic=multiturn_crossday_llm_200cases -n 8")
else:
    print("ERROR: Data file not found!")
    import sys
    sys.exit(1)
