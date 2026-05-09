# Pawly — common dev/ops targets.
#
# Goal: every reproducible operation lives behind a `make <target>` so that
# Atlas / agents / CI / humans all run the same command. If you find yourself
# pasting a multi-line shell snippet into a runbook, it should probably move
# here instead.

.PHONY: help install lint test test-memory \
        regression-light regression-full regression-diff \
        regression-report-latest regression-promote-baseline

# Default model for regression. Override on the command line:
#   make regression-light MODEL=gemini-2.0-flash
MODEL ?= deepseek-v4-pro

# Where pytest writes report.json + run.jsonl files.
REPORTS_DIR = tests/blackbox_multiturn/results

# Persistent regression cache on the VPS — lives outside the runner
# workdir so `actions/checkout`'s `git clean` can't wipe it. The CI
# workflows read baseline from / write reports to this dir; agent
# envs and laptops won't have it (the promote-baseline target degrades
# gracefully with a clear error).
REGRESSION_CACHE_DIR = /opt/pawly/regression-cache

help:
	@echo "Pawly — common targets"
	@echo "  make install                       install deps (incl. dev extras)"
	@echo "  make lint                          ruff check ."
	@echo "  make test-memory                   fast unit tests (no LLM, no DB)"
	@echo "  make regression-light              run 30-case regression (light, ~5-20min, ~\$$2)"
	@echo "  make regression-full               run 223-case regression (full, ~1-3hr, ~\$$50)"
	@echo "  make regression-diff               compare two regression runs (BASELINE=... CANDIDATE=...)"
	@echo "  make regression-promote-baseline   VPS-only — promote latest light-30 report to CI baseline"
	@echo ""
	@echo "Override: MODEL=$(MODEL)  (e.g. MODEL=gemini-2.0-flash)"

install:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

lint:
	ruff check .

test-memory:
	python -m pytest tests/memory -q

# ── Regression ────────────────────────────────────────────────────────────
#
# Both targets reuse the same pytest entry; the only difference is the data
# file (selected via --multiturn-topic). After a run, the latest report
# lives at $(REPORTS_DIR)/multiturn_pawly_regression{_light_30,}_report_*.json
#
# Required env: DEEPSEEK_API_KEY (or whichever provider $(MODEL) needs).
# DB / Redis are NOT required — conftest stubs them out for blackbox runs.

regression-light:
	@echo "==> light-30 regression on $(MODEL)"
	python -m pytest tests/blackbox_multiturn/test_message_handler_multiturn.py \
	    --multiturn-topic=multiturn_pawly_regression_light_30 \
	    --model=$(MODEL) \
	    -s -v
	@echo ""
	@echo "==> latest report:"
	@ls -1t $(REPORTS_DIR)/multiturn_pawly_regression_light_30_report_*.json 2>/dev/null | head -1

regression-full:
	@echo "==> full-223 regression on $(MODEL) (this takes 1-3 hours)"
	python -m pytest tests/blackbox_multiturn/test_message_handler_multiturn.py \
	    --multiturn-topic=multiturn_pawly_regression \
	    --model=$(MODEL) \
	    -s -v
	@echo ""
	@echo "==> latest report:"
	@ls -1t $(REPORTS_DIR)/multiturn_pawly_regression_report_*.json 2>/dev/null | head -1

# Compare two report.json files. Outputs a markdown summary suitable for a
# PR comment.
#   make regression-diff BASELINE=results/foo.json CANDIDATE=results/bar.json
# Or auto-pick the two most recent reports of the same topic:
#   make regression-diff
regression-diff:
	@if [ -n "$(BASELINE)" ] && [ -n "$(CANDIDATE)" ]; then \
	    python scripts/regression-diff.py "$(BASELINE)" "$(CANDIDATE)"; \
	else \
	    python scripts/regression-diff.py --auto; \
	fi

# Show path of the latest light-30 report (handy for chaining with diff).
regression-report-latest:
	@ls -1t $(REPORTS_DIR)/multiturn_pawly_regression*_report_*.json 2>/dev/null | head -1

# VPS-only — promote the most recent local light-30 report into the
# persistent CI cache. Use when you've manually run `make regression-light`
# on the VPS and want to seed the baseline without waiting for CI.
#
# Writes to two places:
#   1. <cache>/baseline-light-30.json  — what the next PR diffs against
#   2. <cache>/reports-light-30/<MODEL>/<tree-sha>.json  — content cache,
#      keyed by git tree SHA so a future push-to-main with the same tree
#      can short-circuit refresh-baseline.
regression-promote-baseline:
	@if [ ! -d "$(REGRESSION_CACHE_DIR)" ]; then \
	    echo "ERROR: $(REGRESSION_CACHE_DIR) does not exist."; \
	    echo "       Create it on the VPS with:"; \
	    echo "         sudo mkdir -p $(REGRESSION_CACHE_DIR)/reports-light-30"; \
	    echo "         sudo chown -R \$$(whoami) $(REGRESSION_CACHE_DIR)"; \
	    exit 1; \
	fi
	@LATEST=$$(ls -1t $(REPORTS_DIR)/multiturn_pawly_regression_light_30_report_*.json 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
	    echo "ERROR: no light-30 report found in $(REPORTS_DIR)."; \
	    echo "       Run \`make regression-light\` first."; \
	    exit 1; \
	fi; \
	TREE=$$(git rev-parse HEAD^{tree}); \
	mkdir -p "$(REGRESSION_CACHE_DIR)/reports-light-30/$(MODEL)"; \
	cp "$$LATEST" "$(REGRESSION_CACHE_DIR)/baseline-light-30.json"; \
	cp "$$LATEST" "$(REGRESSION_CACHE_DIR)/reports-light-30/$(MODEL)/$$TREE.json"; \
	echo "Promoted: $$(basename $$LATEST)"; \
	echo "  -> $(REGRESSION_CACHE_DIR)/baseline-light-30.json"; \
	echo "  -> $(REGRESSION_CACHE_DIR)/reports-light-30/$(MODEL)/$$TREE.json"
