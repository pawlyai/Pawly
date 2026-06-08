# Phase C: 200-Case Test Monitoring

## Test Status

**Backend**: Mem0 + Validator (P0-P3 optimized)  
**Dataset**: 200 cross-day multiturn cases  
**Workers**: 8 parallel  
**Model**: deepseek-v4-pro  
**Started**: 2026-06-08 ~15:12 UTC

---

## How to Monitor

### Option 1: Real-time Status
```bash
python scripts/monitor_tests.py --loop
```
Checks every 30 seconds and displays:
- Passed/Failed/Error counts
- Current pass rate
- Estimated time remaining

### Option 2: Tail Log File
```bash
# Watch live output
tail -f test_200cases_mem0.log

# Count progress (passes + fails)
grep -c "PASSED\|FAILED" test_200cases_mem0.log
```

### Option 3: One-off Status Check
```bash
python scripts/monitor_tests.py
```
Shows current status without looping.

---

## Expected Timeline

- **Collection**: ~30 seconds (200 cases parametrized)
- **Setup**: ~1 minute (8 workers booting)
- **Test Run**: ~1-2 hours (200 cases × ~30-60 seconds each)
  - With 8 workers: 200 / 8 = 25 "batches" of parallel work
  - Each batch: ~3-5 minutes (LLM inference time)
  - Total: 75-125 minutes
- **Report Generation**: ~1 minute

**ETA**: 2026-06-08 16:30-18:00 UTC (1.5-3 hours from start)

---

## What We're Testing

Each test case:
1. User messages on Day 1 → extraction + daily summary
2. User messages on Day 2 → extraction (should reference Day 1)
3. Deepeval ConversationalGEval judges:
   - Does LLM remember Day 1 facts? ✓
   - Continuity score >= threshold (0.85)? ✓
   - Response quality on Day 2? ✓

200 cases cover:
- Limping recovery
- Post-surgery follow-up
- Skin rash treatment
- Eye discharge monitoring
- Antibiotic side effects
- Respiratory infections
- Appetite loss
- Environmental stress
- Urinary issues
- Bite wound healing
- Ear infections
- 3-day worsening/recovery

---

## Success Criteria

✅ **Pass Rate >= 80%**
- Baseline (quick validation): 100% on 1 case
- Expected: 85%+ on 200 diverse cases

✅ **No Crashes**
- All 200 cases complete
- No database deadlocks
- No LLM timeout failures

✅ **Memory Quality**
- Facts extracted: >80% of expected
- Validator approves: >90% of extracted
- Cross-day references: >70% of cases

---

## If Tests Fail

### Check 1: Database Connection
```bash
# Verify PostgreSQL running
psql -U test -d test -h localhost -c "SELECT 1"
# Expected: 1 row with value 1
```

### Check 2: API Key
```bash
# Verify Deepseek model access
export DEEPSEEK_API_KEY=...  # if not set
pytest tests/memory/ -k "test_" -n 1  # smoke test
```

### Check 3: Log Errors
```bash
# See what failed
grep -A5 "FAILED\|ERROR" test_200cases_mem0.log | head -50
```

### Check 4: Partial Results
```bash
# If test was interrupted, extract what passed
python scripts/compare_200case_results.py
# Shows partial pass rate
```

---

## Key Files

| File | Purpose |
|------|---------|
| `test_200cases_mem0.log` | Raw pytest output |
| `tests/blackbox_multiturn/results/multiturn_crossday_llm_report_*.json` | Detailed results |
| `scripts/monitor_tests.py` | Live status monitor |
| `scripts/compare_200case_results.py` | Result comparison |
| `docs/P0_P3_OPTIMIZATIONS_SUMMARY.md` | Implementation details |

---

## After Test Completes

### Step 1: View Results
```bash
python scripts/monitor_tests.py
# Shows final pass rate
```

### Step 2: Generate Report
```bash
# Check if automated reports exist
ls tests/blackbox_multiturn/results/ | grep "multiturn_crossday"
# Should have: .json and .log files
```

### Step 3: Analyze Failures
```bash
# Extract failed case details
grep -B5 "FAILED\|AssertionError" test_200cases_mem0.log

# Pattern analysis: what types of cases failed?
python -c "
import json
results = json.load(open('tests/blackbox_multiturn/results/multiturn_crossday_llm_report_*.json'))
fails = [r for r in results if not r.get('pass')]
print(f'Failed: {len(fails)}/{len(results)}')
for f in fails[:5]:
    print(f'  - {f.get(\"name\")}: {f.get(\"reason\")[:100]}')
"
```

### Step 4: Compare to Quick Validation
```
Quick Validation (1 case):   100% pass rate
Phase C (200 cases):         XX% pass rate

Conclusion:
- If >= 80%: P0-P3 successful, proceed to deployment
- If 60-80%: P0-P3 partially effective, debug specific failures
- If < 60%: P0-P3 needs rework, rollback and investigate
```

---

## Debugging Individual Failures

If a specific case fails, debug it standalone:

```bash
# Extract the case name from log
CASE_NAME="limping_recovery_var_042_cross_day"

# Run just that case
pytest tests/blackbox_multiturn/test_crossday_multiturn.py \
  --crossday-topic=multiturn_crossday_llm_200cases \
  -k "$CASE_NAME" \
  -vv --tb=short

# This will:
# 1. Show the full test output
# 2. Display LLM responses (if captured)
# 3. Show DeepEval rubric evaluation
```

---

## Questions?

If monitoring shows issues:
1. Check `test_200cases_mem0.log` for error messages
2. Search for patterns in failures (all same scenario type?)
3. Verify P0-P3 code changes: `git show ce088aa`
4. Re-run quick validation on subset: `pytest tests/memory/ -n 1`

---

**Last Updated**: 2026-06-08 15:12 UTC  
**Status**: ⏳ Tests running in background
