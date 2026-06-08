# Phase C: Full 200-Case Comparison (Mem0+Validator vs Multi-Agent)

## Goal
Run the complete test suite with both extraction backends to determine which should be production default.

## Backends to Compare
- **Backend A**: `multiagent` (current system)
  - Triage + 4 Specialists (health, medication, behavior, acute) + Validator
  - Known issues: validator over-filters Acute facts (0/2 → memory visibility = 0)
  
- **Backend B**: `mem0_validator` (Phase B winner)
  - Single-pass extraction + entity linking + Validator
  - Improves on Phase A (11 → 13 facts, validator keeps all)

## Metrics to Track

### Extraction Metrics
- Facts per case (count)
- Average confidence (higher = better)
- Memory visibility (facts actually injected into context)

### Test Performance Metrics
- Acute scenario score (known problematic)
- Overall test pass rate
- Cross-day continuity (facts from Day 1 available on Day 3)

### Efficiency Metrics
- Extraction time per case
- API call count (fewer = better)
- Token usage (lower = cheaper)

## Test Plan

### Phase C1: Run Test Suite (Both Backends)
```bash
# Current system (multiagent)
EXTRACTION_BACKEND=multiagent pytest tests/blackbox_multiturn/ -n 8 --model=deepseek-v4-pro

# Mem0+Validator (Phase B)
EXTRACTION_BACKEND=mem0_validator pytest tests/blackbox_multiturn/ -n 8 --model=deepseek-v4-pro
```

### Phase C2: Compare Reports
- Load both test reports
- Compare: pass rate, scores, memory_visibility
- Identify which backend wins on each metric

### Phase C3: Deep Analysis (Acute Scenario)
- Compare Acute case results in detail
- Validate that Mem0+Validator improves Acute memory visibility
- Check if validator now keeps post-op facts

## Decision Criteria

1. **Overall Score**: Higher pass rate wins
   - If Backend B > Backend A by > 5%: Use Backend B
   - If difference < 5%: Use Backend B (same performance, simpler pipeline)

2. **Acute Scenario Specific**:
   - If Backend B memories > Backend A: Use Backend B
   - Critical to verify post-op facts are visible

3. **Extraction Count**:
   - Backend B should extract more facts with Mem0
   - Validator should keep them (unlike multi-agent scenario)

## Expected Outcome
Backend B (mem0_validator) likely to win based on:
- Phase B showed +18% improvement
- Validator works better on single-pass vs multi-agent duplicates
- No specialist redundancy overhead
- Simpler, more transparent pipeline
