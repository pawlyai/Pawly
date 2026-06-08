
# Phase C: Full test comparison with both extraction backends

Write-Host "========================================================================" -ForegroundColor Green
Write-Host "PHASE C: Full Test Comparison (Mem0+Validator vs Multi-Agent)" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""

# Configuration
$TEST_SUITE = "tests/blackbox_multiturn/test_crossday_multiturn.py"
$NUM_WORKERS = 8
$MODEL = "deepseek-v4-pro"
$TEST_DATASET = "multiturn_phase0_200"

# Create results directory
$resultsDir = "tests/blackbox_multiturn/results/phase_c"
if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
}

Write-Host "Test Configuration:" -ForegroundColor Cyan
Write-Host "  Test suite: $TEST_SUITE"
Write-Host "  Workers: $NUM_WORKERS"
Write-Host "  Model: $MODEL"
Write-Host "  Dataset: $TEST_DATASET"
Write-Host ""

# ============================================================================
# Run Backend A: Multi-Agent (Current)
# ============================================================================

Write-Host "========================================================================" -ForegroundColor Green
Write-Host "PHASE C-A: Running Multi-Agent Extraction (Current System)" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""

$env:EXTRACTION_BACKEND = "multiagent"
$env:PYTEST_TIMEOUT = "300"

$multiagentLog = Join-Path $resultsDir "multiagent_run.log"
Write-Host "Running tests... (output saved to $multiagentLog)"

python -m pytest $TEST_SUITE `
  --crossday-topic=$TEST_DATASET `
  --model=$MODEL `
  -n $NUM_WORKERS `
  -v `
  2>&1 | Tee-Object -FilePath $multiagentLog

Write-Host ""
Write-Host "Multi-Agent test run complete."
Write-Host ""

# ============================================================================
# Run Backend B: Mem0+Validator (Phase B Winner)
# ============================================================================

Write-Host "========================================================================" -ForegroundColor Green
Write-Host "PHASE C-B: Running Mem0+Validator Extraction (Phase B)" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""

$env:EXTRACTION_BACKEND = "mem0_validator"

$mem0Log = Join-Path $resultsDir "mem0_validator_run.log"
Write-Host "Running tests... (output saved to $mem0Log)"

python -m pytest $TEST_SUITE `
  --crossday-topic=$TEST_DATASET `
  --model=$MODEL `
  -n $NUM_WORKERS `
  -v `
  2>&1 | Tee-Object -FilePath $mem0Log

Write-Host ""
Write-Host "Mem0+Validator test run complete."
Write-Host ""

# ============================================================================
# Comparison
# ============================================================================

Write-Host "========================================================================" -ForegroundColor Green
Write-Host "PHASE C Results Summary" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Results saved to:" -ForegroundColor Cyan
Write-Host "  - $multiagentLog"
Write-Host "  - $mem0Log"
Write-Host ""
Write-Host "To compare reports, run:" -ForegroundColor Cyan
Write-Host "  python tests/blackbox_multiturn/compare_reports.py --help"
Write-Host ""
