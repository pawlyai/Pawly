#!/bin/bash
# Phase C: Full test comparison with both extraction backends

set -e

echo "========================================================================"
echo "PHASE C: Full Test Comparison (Mem0+Validator vs Multi-Agent)"
echo "========================================================================"
echo ""

# Configuration
TEST_SUITE="tests/blackbox_multiturn/test_crossday_multiturn.py"
NUM_WORKERS=8
MODEL="deepseek-v4-pro"
TEST_DATASET="multiturn_phase0_200"

# Create results directory
mkdir -p tests/blackbox_multiturn/results/phase_c

echo "Test Configuration:"
echo "  Test suite: $TEST_SUITE"
echo "  Workers: $NUM_WORKERS"
echo "  Model: $MODEL"
echo "  Dataset: $TEST_DATASET"
echo ""

# ============================================================================
# Run Backend A: Multi-Agent (Current)
# ============================================================================

echo "========================================================================"
echo "PHASE C-A: Running Multi-Agent Extraction (Current System)"
echo "========================================================================"
echo ""

export EXTRACTION_BACKEND="multiagent"
export PYTEST_TIMEOUT=300

python -m pytest "$TEST_SUITE" \
  --crossday-topic="$TEST_DATASET" \
  --model="$MODEL" \
  -n "$NUM_WORKERS" \
  -v \
  2>&1 | tee "tests/blackbox_multiturn/results/phase_c/multiagent_run.log"

echo ""
echo "Multi-Agent test run complete. Saving results..."
echo ""

# ============================================================================
# Run Backend B: Mem0+Validator (Phase B Winner)
# ============================================================================

echo "========================================================================"
echo "PHASE C-B: Running Mem0+Validator Extraction (Phase B)"
echo "========================================================================"
echo ""

export EXTRACTION_BACKEND="mem0_validator"

python -m pytest "$TEST_SUITE" \
  --crossday-topic="$TEST_DATASET" \
  --model="$MODEL" \
  -n "$NUM_WORKERS" \
  -v \
  2>&1 | tee "tests/blackbox_multiturn/results/phase_c/mem0_validator_run.log"

echo ""
echo "Mem0+Validator test run complete. Saving results..."
echo ""

# ============================================================================
# Comparison
# ============================================================================

echo "========================================================================"
echo "PHASE C Results Summary"
echo "========================================================================"
echo ""
echo "Results saved to:"
echo "  - tests/blackbox_multiturn/results/phase_c/multiagent_run.log"
echo "  - tests/blackbox_multiturn/results/phase_c/mem0_validator_run.log"
echo ""
echo "To compare reports, run:"
echo "  python tests/blackbox_multiturn/compare_reports.py --help"
echo ""
