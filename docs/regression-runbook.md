# Pawly regression — runbook for humans and agents

This is the **single canonical reference** for running regression on Pawly.
Both Atlas (the Multica agent) and human reviewers should follow this. If
you find yourself improvising commands, the runbook is wrong — fix it
here so the next person doesn't have to re-derive.

## TL;DR

```bash
# 1. SSH to the deploy VPS
ssh root@129.212.231.81

# 2. cd into the repo
cd /opt/pawly

# 3. Make sure code is current
git pull origin main          # or `git checkout <pr-branch>` for a PR

# 4. Pick a target
make regression-light         # 30 cases, ~20 min, ~$2
make regression-full          # 223 cases, 1-3 hr, ~$50

# 5. Compare against baseline
make regression-diff          # auto-picks two most recent reports
# Or explicitly:
python scripts/regression-diff.py path/to/baseline.json path/to/candidate.json

# 6. (one-time, post light-30) seed the CI baseline so PRs get real diffs
#    instead of "first run" — see "How the baseline cache works" below.
make regression-promote-baseline
```

## Why on the VPS, not in the agent env

- Agent envs (Multica's Atlas runner, Codespaces, ephemeral CI) **don't have the LLM API keys** baked in. Running there means leaking keys via env vars.
- Pawly's regression needs Postgres + Redis. The VPS already has them running and seeded; agent envs would need to bring them up from scratch every time, eating 10+ minutes per run.
- 223 cases × multi-turn × LLM judge = thousands of API calls. **The cost is real.** Centralizing on the VPS lets you see the bill in one place and avoid double-billing for failed agent runs.

If the VPS is unreachable or busy, **stop and ask the human** instead of trying to reproduce the env elsewhere.

## What "regression" means in this repo

| Suite | File | Cases | Use when |
|---|---|---|---|
| **Light-30** | `tests/blackbox_multiturn/test_data/multiturn_pawly_regression_light_30_cases.json` | 30 | Every PR — fast smoke test |
| **Full-223** | `tests/blackbox_multiturn/test_data/multiturn_pawly_regression_cases.json` | 223 | Before merging a non-trivial change to main |

The `make regression-{light,full}` targets are the ONLY supported invocations. Don't run pytest by hand — the targets pin the right `--multiturn-topic` and the right report path.

## Default model

`MODEL=deepseek-v4-pro` (set in the Makefile). Override with:

```bash
make regression-light MODEL=gemini-2.0-flash
```

We picked DeepSeek V4 Pro after V4 Flash showed too many compliance regressions on dosage and euthanasia cases. Don't switch back without explicit approval.

## Required env on the VPS

The VPS already has these in `/opt/pawly/.env`:

- `DEEPSEEK_API_KEY` — chat path (default model)
- `GOOGLE_API_KEY` — Gemini fallback + judge
- `OPENAI_API_KEY` — embedding model for memory layer (optional for blackbox runs)

If a `make regression-light` fails with "API key not set", check `.env` first.

## Reading the result

Each run writes a JSON report to:

```
tests/blackbox_multiturn/results/multiturn_pawly_regression{,_light_30}_report_<model>_v<timestamp>.json
```

Top-level fields:

```json
{
  "summary": {
    "total_cases": 30,
    "passed_threshold": 27,
    "below_threshold": 3,
    "llm_model": "...",
    "timestamp": "..."
  },
  "cases": [
    { "name": "...", "status": "passed_threshold|below_threshold",
      "score": 0.87, "threshold": 0.9, "reason": "judge feedback...",
      "turn_count": 4, "turns": [...], "metadata": {...} }
  ]
}
```

A case is "pass" iff `status == "passed_threshold"`.

## Comparing two runs (diff)

```bash
python scripts/regression-diff.py BASELINE.json CANDIDATE.json
# or auto-pick the two most recent reports of the same topic:
python scripts/regression-diff.py --auto
```

Outputs a markdown summary with:

1. **Headline**: `+X.Y pp` pass-rate delta + ✓/✗ verdict
2. **Top-level table**: total / passed / failed (baseline vs candidate)
3. **New failures**: cases that passed before, fail now (the regressions you care about)
4. **New passes**: cases that failed before, pass now (improvements)
5. **Score-only deltas**: same status but score moved ≥ 0.1

Pipe to `--out report-summary.md` for use in PR comments.

## CI: when does regression run automatically

- **Every PR** → light-30 via `.github/workflows/regression-light.yml`. Takes ~20 min on the VPS. Pass/fail is a required check; can't merge while red.
- **Add `regression` label to PR** → full-223 via `.github/workflows/regression-full.yml`. Takes 1-3 hours. Only run before merging significant prompt / model / pipeline changes.
- **Add `skip-regression` label to PR** → light-30 is skipped. Use only when you're confident the change has no observable behavior impact (log-format tweaks, comment-only edits in `src/**`, internal refactors with no semantic change). Path filter already auto-skips pure docs/CI PRs, so this label is for cases where the path filter matched but you know regression isn't needed.
- **Manual** (this runbook) → run on the VPS for ad-hoc experiments.

PR comments are auto-generated by `scripts/regression-diff.py` against the latest `main` baseline.

### When to use which label

| Situation | Action |
|---|---|
| Normal feature / fix touching `src/**` | Do nothing — light-30 runs automatically |
| Pure docs / README / `.gitignore` edit | Do nothing — path filter auto-skips |
| Touched `src/**` but only logging / comments / dead-code removal | Add `skip-regression` **before opening PR** |
| Changed prompts / model / orchestrator / scoring logic | Add `regression` (after light-30 passes) |
| Both apply somehow (you regret skipping) | Remove `skip-regression`, push a no-op commit to retrigger |

**Important**: `skip-regression` only takes effect for PR-open and new-commit events. Adding it mid-run does NOT cancel an already-running light-30 — cancel via the GitHub Actions UI if you really care about the $2.

## How the baseline cache works

The CI workflows persist regression data on the VPS at
`/opt/pawly/regression-cache/`:

```
/opt/pawly/regression-cache/
├── baseline-light-30.json                  ← what every PR's diff compares against
└── reports-light-30/<MODEL>/<tree-sha>.json  ← per-tree report cache
```

**Why a cache**: the runner workdir is wiped by `git clean` on every
checkout, so any baseline written there evaporates. Storing outside the
workdir survives between runs.

**Why keyed by tree SHA, not commit SHA**: same code → same tree SHA,
even if commit SHAs differ (squash merge, rebase). Lets us detect "this
exact code state has already been measured" and skip re-running.

### Lifecycle

| Event | What happens |
|---|---|
| PR opened, light-30 runs | Job restores baseline from cache → runs tests → diffs → caches its own report keyed by `tree-sha` |
| Push to main (PR merged) | `refresh-baseline` job checks if `<merge-tree-sha>.json` is already in cache. **Hit**: cp to baseline, done in 5 sec. **Miss**: runs light-30, saves both as baseline and cache entry. |
| You run `make regression-light` on the VPS | Just produces a local report. Does NOT touch the cache. |
| You run `make regression-promote-baseline` | Copies the latest local report into both `baseline-light-30.json` and `reports-light-30/<MODEL>/<tree>.json`. |

### Bootstrap (first time after VPS setup)

The first PR ever opened will see "first run, no baseline yet" because
the cache is empty. Two options:

**Option A — let CI populate it**: open a no-op PR (e.g. fix a README
typo on a branch that touches `src/**` somehow). Light-30 runs; merge;
`refresh-baseline` writes the first baseline. Next PR diffs cleanly.

**Option B — seed manually (recommended)**: if you've already run
light-30 on the VPS once, just promote it:

```bash
ssh root@129.212.231.81
cd /opt/pawly
git checkout main && git pull
make regression-light                 # ~20 min, ~$2 — skip if already done
make regression-promote-baseline      # 1 sec — seeds baseline + tree-SHA cache
```

After this, the next PR opened against this main commit will diff
against your seeded baseline. The push-to-main from that PR's merge
will hit the cache (if main hasn't moved) and skip re-running.

### Cache-miss scenarios

`refresh-baseline` will re-run light-30 (cache miss) when:

- Main moved between PR open and merge → squash produced a new tree
- You merged via "create a merge commit" rather than squash
- The MODEL env var changed (model is part of the cache path)
- Cache was pruned / never populated for this tree

Cache misses are not a bug, just the fallback. They cost ~$2 + 20 min
(same as before the cache existed).

## When a run fails halfway

Symptoms: pytest exits non-zero, no report.json written, OR report.json has `total_cases < expected`.

1. **Check API key quotas first**. DeepSeek and Gemini both rate-limit; a 429 mid-run kills pytest. `tail -50` the run log for `429`/`rate limit`/`quota`.
2. **Check disk space**. Reports + logs accumulate; if `/opt/pawly` is full, writes silently truncate.
3. **Check container health**. `docker ps | grep -E "postgres|redis"` — if either is restarting, blackbox runs that touch the orchestrator's DB stub will hang.
4. **Re-run from scratch.** Don't try to "resume" — there's no checkpointing, and partial runs corrupt the comparison baseline.

Don't quietly retry > 2 times. If the third run fails, escalate to a human.

## What NOT to do

- ❌ Don't run regression in your own agent env. Always SSH the VPS.
- ❌ Don't run `pytest tests/blackbox_multiturn` directly. Use `make regression-{light,full}`.
- ❌ Don't commit report.json files into the repo. They live under `tests/blackbox_multiturn/results/` which is gitignored.
- ❌ Don't change `MODEL` for the same PR's baseline vs candidate runs. Apples-to-apples comparison only.
- ❌ Don't run `regression-full` without first running `regression-light` and seeing it pass. If light fails, full will fail too — and you'll have spent $50 to confirm it.
- ❌ Don't kick off `regression-full` if the VPS already has another full run going. The blackbox tests share state in the orchestrator stubs and concurrent runs corrupt each other's reports.

## For Atlas / agents specifically

If a human asks you to run regression:

1. Confirm you're on the VPS (`hostname` should be `Pawly`).
2. Confirm the branch you want (`git status; git log -1 --oneline`).
3. Run `make regression-light` first. Wait for it to finish. Don't background it.
4. Run `make regression-diff` and paste the markdown output back to the human.
5. If the human says "looks good, run full" → run `make regression-full`. Otherwise, stop.
6. **Never** modify test cases or the Makefile to "make tests pass" without explicit human approval.
7. **Never** invent your own pytest invocation — always use the make targets.

If something blocks you (key missing, container down, file conflict), say what's wrong and stop. Don't try to repair the env autonomously.
