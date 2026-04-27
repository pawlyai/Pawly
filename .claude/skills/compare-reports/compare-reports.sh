#!/bin/bash
# Wrapper script for compare-reports skill
# This makes the Python script easier to invoke from Claude Code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAWLY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPARE_SCRIPT="$PAWLY_ROOT/tests/blackbox_multiturn/compare_reports.py"

# Change to Pawly root directory
cd "$PAWLY_ROOT"

# Run the Python script with all arguments
python3 "$COMPARE_SCRIPT" "$@"
