# Proactive nudge quality

Scores what Toki says when nobody asked: red-flag follow-ups, unfinished
consultations, win-backs, trend notes.

> **Not to be confused with `test_proactive_quality.py` in this directory.**
> That one calls `src.jobs.followup` in the Phase-0 Python monolith, which
> still exists in this repo but is not what ships. It is driven by the
> `6_Proactive_Quality.py` Streamlit page and reads
> `test_data/proactive_quality_cases.json`. Everything described below targets
> the Go stack over HTTP and shares nothing with it but the results directory.

```bash
# 1. the stack (from the backend checkout)
export EVAL_LLM_API_KEY=...            # the SUT's provider key
docker compose -f deploy/docker-compose.eval.yml -p pawly-eval up -d --build \
    postgres-notif notification-service

# 2. the run (from the Pawly checkout)
export ANTHROPIC_API_KEY=...           # judge
export DEEPSEEK_API_KEY=...            # second D7 judge
python tests/blackbox_proactive/run_proactive_eval.py \
    --corpus tests/blackbox_proactive/test_data/proactive_smoke_20_cases.json
```

The report lands in `../blackbox_multiturn/results/` and shows up in the
existing Streamlit panel.

## How a case works

A reactive case posts a user turn and reads the reply. A proactive case has no
user turn — the whole question is what the system says unprompted — so it
declares a *situation* instead and asks the service what it would do with it.

    POST /v1/internal/proactive/dry-run
      { now, candidate, state }  →  { verdict, gate, reason, content, ... }

That endpoint runs the real gates in the real order, the real prompt modules and
the real output veto, writes nothing and delivers nothing. See
`notification-service/internal/proactive/dryrun.go` for exactly what it shares
with the delivery path and what it does not.

Nothing is provisioned — no users, no pets, no sessions, no database — which is
why 200 of these run in about the time it takes to drive a dozen chat cases.

## Times are relative, on purpose

Cases say "20:00 in the owner's zone, fourteen hours after the RED turn", never
a timestamp. `proactive_driver.py` resolves those against a fixed epoch
(2026-03-10, a Tuesday well clear of any DST transition in the corpus's zones),
so a run in August reproduces a run in March exactly, and no case rots when a
date passes.

`local_hour` is the owner's wall clock and the UTC instant is derived from it,
never the reverse — a corpus pinned to UTC hours would mean a different local
hour per region, and every SG case would land on the wrong side of quiet hours.

## Three gates

A case passes only if all three hold.

**1 · Deterministic** (`check_asserts`) — `should_send` and the gate that
decided it, anchors to this pet and this episode, no other pet's name, no
invented dose, emoji and length. Facts, not opinions. A judge is never asked
whether `daily_cap` fired.

This is also where D5 (timing) lives. Every part of it is decided by a gate and
reported by the dry-run, so it is a fact before scoring starts; asking a model
to opine on it would add cost and variance to something that already has an
answer.

**2 · D7, binary** — no commercial pull where the PRD forbids it. Judged,
because a soft upsell is prose and the Go output gate only matches five literal
markers. Judged *twice*, by different families, because this verdict kills a
case on its own. A split vote is reported as `needs_review` and fails in the
meantime.

**3 · D1–D4, D6** — one GEval each, because the brief's rule ("D2/D3/D4 are
core; any one too low fails") is a decision tree, not a weighted sum. A single
metric carrying six criteria returns one number, and a warm, well-timed,
completely generic nudge scores about 0.7 on it — the exact failure this corpus
exists to catch, averaged away by the dimensions it got right.

D6 is only scored for `POST_REDFLAG`. Handed that question about a milestone
note, a judge invents an emergency to protect and starts marking down messages
for not mentioning a vet.

### The template check needs the whole corpus

"Generic template" is the hardest redline to see one message at a time: read
alone, a competent generic nudge looks fine. Read against the other 199 it is
obvious — the same sentence eleven times with a different name in it. So
`generic_pairs()` blanks the pet's name out of every delivered message and
compares the remainder; anything above 0.82 similarity fails both cases. This
catches what the per-case anchor check cannot: a message that dutifully includes
its anchors and is otherwise a form letter.

## Two traps worth knowing before adding cases

**A template fallback is not a passing case.** If the provider fails, or the
category has no prompt module, the renderer ships the trigger's template — and
the templates are decent, so the case would usually pass. That is the most
dangerous kind of green. `expect_llm_render` (default true) asserts
`render_source == "llm"`; leave it on unless you specifically mean to score the
template.

**`max_tokens` truncates reasoning models.** At the config default of 512,
`gemini-2.5-flash` spends the budget thinking and returns a nudge cut off
mid-sentence. Nothing in the renderer catches it — the only length guard is an
upper bound — so it clears every gate and ships. The eval compose sets 2048
explicitly. See the note in `notification-service/PROACTIVE_STATUS.md`.

## Corpus validation

`validate_corpus.py` runs before every eval and splits its findings in two.

**Errors** stop the run: a case missing its trigger, a `should_send=false` case
that does not say which rule should hold the nudge (it would pass on the wrong
kind of silence), a `POST_REDFLAG` with no prior transcript to be following up
on. A malformed case does not fail — it produces a confident number about
nothing.

**Warnings** are the brief's coverage quotas — persona spread, region mix,
memory depth, restraint share, D7 negatives — expressed as fractions so they
hold for a 20-case smoke run and the 200-case regression alike. They never
block; they are the QA summary, computed rather than counted by hand.

```bash
python tests/blackbox_proactive/validate_corpus.py test_data/<corpus>.json
```

## Corpora

| File | Cases | What it is for |
|---|---|---|
| `proactive_smoke_20_cases.json` | 20 | All `POST_REDFLAG`. Proves the chain and the judge before spending a full run. |

## Judges

Default `claude-sonnet-5`, cross-family from the `gemini-2.5-flash` SUT and
never the model under test — a judge sharing a family with the SUT reads its
blind spots as fine, so exactly the failures worth catching go unflagged. The
report records `judge_same_family` so a number read weeks later still says
whether the judge was independent.
