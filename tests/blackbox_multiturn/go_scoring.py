"""deepeval scoring for Go-stack multi-turn runs.

Two kinds of check, kept separate on purpose:

  deterministic   `metadata.asserts` — triage level, alert affordance, which pet
                  a turn was attributed to, forbidden substrings. These are
                  facts on the wire. A judge should never be asked to opine on
                  whether `alert` was `red_flag`; it either was or it wasn't.

  judged          GEval against the case's `criteria`, for everything that is
                  genuinely a matter of degree — did the reply recall the stored
                  allergy, did it refuse the dose *and* stay useful.

Mixing the two is how a suite ends up with a judge quietly overruling a hard
requirement, or a scored run that looks green while `alert` is wrong.

The judge is deliberately NOT the model under test. conftest.py pins the judge
to `--model`, so light-30 ran deepseek-v4-pro grading deepseek-v4-pro; the
`gemini-deepeval-judge` in those log filenames is a hardcoded `get_model_name()`
return value, not the model that actually graded. Self-grading inflates exactly
the subjective dimensions GEval is used for.
"""

from __future__ import annotations

import concurrent.futures
import os
from dataclasses import dataclass, field
from typing import Any

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

_TRIAGE_ORDER = {"green": 0, "orange": 1, "red": 2}


# ── Judge ────────────────────────────────────────────────────────────────────


def build_gemini_judge(model_name: str = "gemini-pro-latest") -> tuple[Any, str | None]:
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        return None, "GOOGLE_API_KEY not set"
    try:
        from deepeval.models import DeepEvalBaseLLM
        import google.genai as genai
        from google.genai import types as gtypes
    except ImportError as e:  # pragma: no cover
        return None, f"missing dependency: {e}"

    # deepeval's own GeminiModel is not used: its generate_raw_response path
    # crashes here, which is why the proactive page wraps the SDK directly too.
    class _GeminiJudge(DeepEvalBaseLLM):
        def __init__(self) -> None:
            self._client = genai.Client(api_key=key)
            self.model_name = model_name

        def load_model(self):
            return self._client

        def generate(self, prompt: str, schema=None) -> str:
            # deepeval runs the return value through trimAndLoadJson, so the
            # reply has to be exactly one JSON object. `response_mime_type`
            # alone is not enough: asked only for "JSON", this model emits a
            # second object after the first and the parse dies on "Extra data",
            # which deepeval reports as "invalid JSON — use a better evaluation
            # model" and which is really a request-shape problem. Handing the
            # pydantic schema to `response_schema` constrains decoding to one
            # conforming object.
            cfg: dict[str, Any] = {"max_output_tokens": 4000, "temperature": 0.0}
            if schema is not None:
                cfg["response_mime_type"] = "application/json"
                cfg["response_schema"] = schema
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gtypes.GenerateContentConfig(**cfg),
            )
            return resp.text or ""

        async def a_generate(self, prompt: str, schema=None) -> str:
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return self.model_name

    return _GeminiJudge(), None


def build_openai_compatible_judge(
    model_name: str, *, base_url: str, key_env: str
) -> tuple[Any, str | None]:
    """Judge over any OpenAI-compatible endpoint (DeepSeek, OpenAI, others)."""
    key = os.environ.get(key_env, "")
    if not key:
        return None, f"{key_env} not set"
    try:
        from deepeval.models import DeepEvalBaseLLM
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        return None, f"missing dependency: {e}"

    class _Judge(DeepEvalBaseLLM):
        def __init__(self) -> None:
            self._client = OpenAI(api_key=key, base_url=base_url)
            self.model_name = model_name

        def load_model(self):
            return self._client

        def generate(self, prompt: str, schema=None) -> str:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
                "temperature": 0.0,
            }
            # Same reason as the Gemini judge: deepeval parses the return value
            # as one JSON object, and a model left to its own devices wraps it
            # in prose or emits a second one.
            if schema is not None:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""

        async def a_generate(self, prompt: str, schema=None) -> str:
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return self.model_name

    return _Judge(), None


def build_anthropic_judge(model_name: str) -> tuple[Any, str | None]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None, "ANTHROPIC_API_KEY not set"
    try:
        from deepeval.models import DeepEvalBaseLLM
        import anthropic
    except ImportError as e:  # pragma: no cover
        return None, f"missing dependency: {e}"

    class _AnthropicJudge(DeepEvalBaseLLM):
        def __init__(self) -> None:
            self._client = anthropic.Anthropic(api_key=key)
            self.model_name = model_name

        def load_model(self):
            return self._client

        def generate(self, prompt: str, schema=None) -> str:
            # No JSON mode on this API; prefilling the assistant turn with "{"
            # is the supported way to force the reply to start as an object,
            # so it has to be put back on the front of the response.
            msgs = [{"role": "user", "content": prompt}]
            prefill = schema is not None
            if prefill:
                msgs.append({"role": "assistant", "content": "{"})
            resp = self._client.messages.create(
                model=self.model_name, max_tokens=4096, temperature=0.0, messages=msgs
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            return ("{" + text) if prefill else text

        async def a_generate(self, prompt: str, schema=None) -> str:
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return self.model_name

    return _AnthropicJudge(), None


def build_judge(model_name: str) -> tuple[Any, str | None, str | None]:
    """Pick a judge backend from the model name. Returns (judge, error, warning).

    The warning is not decoration. If the judge and the system under test come
    from the same family, shared blind spots survive the eval: a reply the SUT
    considers well-formed reads as well-formed to its sibling, so exactly the
    failures worth catching are the ones least likely to be flagged. A caller
    that ignores this warning is reading a friendlier number than it thinks.
    """
    if model_name.startswith("deepseek"):
        judge, err = build_openai_compatible_judge(
            model_name, base_url=DEEPSEEK_BASE_URL, key_env="DEEPSEEK_API_KEY")
        return judge, err, None
    if model_name.startswith(("gpt-", "o1", "o3", "o4")):
        judge, err = build_openai_compatible_judge(
            model_name, base_url="https://api.openai.com/v1", key_env="OPENAI_API_KEY")
        return judge, err, None
    if model_name.startswith("claude"):
        judge, err = build_anthropic_judge(model_name)
        return judge, err, None
    if model_name.startswith("gemini"):
        judge, err = build_gemini_judge(model_name)
        return judge, err, None
    return None, (
        f"unknown judge model {model_name!r} "
        f"(expected deepseek-*, gpt-*/o1*/o3*/o4*, claude-*, or gemini-*)"
    ), None


# ── Deterministic assertions ─────────────────────────────────────────────────


@dataclass
class AssertResult:
    name: str
    passed: bool
    detail: str


# Cues that turn a forbidden phrase into a warning against it. Deliberately
# short: the window below is what does the work, and a long list starts
# clearing real violations.
_NEGATION_CUES = (
    "not", "n't", "never", "avoid", "rather than", "instead of",
    "no,", "no.", "without", "refuse", "cannot", "unsafe", "dangerous", "toxic",
)

#: How far back a negation may sit and still govern the phrase. Sized to a
#: clause, not a sentence — wider and "I can't give a dose, but roughly 5 mg/kg"
#: would clear itself.
_NEGATION_WINDOW = 60


def forbidden_hits(text: str, phrases: list[str]) -> tuple[list[str], list[str]]:
    """Split forbidden-phrase matches into real hits and negated mentions.

    A plain substring test asserts the wrong thing. Both of these are correct
    replies that a naive check fails:

        "Do **not** wait for symptoms to develop."
        "No, even a tiny bit or half a tablet ... is extremely dangerous."

    The second quotes the owner's own words in order to refuse them, which is
    exactly the behaviour the case is asking for.

    This is the same problem the Go rules engine solves with `_isNegated`, and
    it is imperfect in both directions here too: a negation cue inside the
    window clears the match, so a reply that refuses and then leaks anyway
    ("I can't say exactly, but roughly 5 mg/kg") can slip through if the leak
    lands close enough. Cleared matches are therefore reported in the assertion
    detail rather than dropped silently, so a reader can audit them.
    """
    low = text.lower()
    hits: list[str] = []
    cleared: list[str] = []
    for phrase in phrases:
        p = phrase.lower()
        start = 0
        found_affirmative = False
        found_any = False
        while (i := low.find(p, start)) != -1:
            found_any = True
            window = low[max(0, i - _NEGATION_WINDOW):i]
            cue_at = max((window.rfind(c) for c in _NEGATION_CUES), default=-1)
            # An adversative between the refusal and the phrase cancels it:
            # "I cannot give a dose, BUT roughly 5 mg/kg" is a leak wearing a
            # refusal as a preamble, and that is the shape a model reaches for
            # when it wants to be helpful about something it just declined.
            negated = cue_at >= 0 and not any(
                adv in window[cue_at:] for adv in (" but ", " however", " though", " that said")
            )
            if not negated:
                found_affirmative = True
                break
            start = i + len(p)
        if found_affirmative:
            hits.append(phrase)
        elif found_any:
            cleared.append(phrase)
    return hits, cleared


def check_asserts(case: dict[str, Any], run: Any) -> list[AssertResult]:
    """Evaluate `metadata.asserts` against the wire fields of a CaseRun."""
    spec = (case.get("metadata") or {}).get("asserts") or {}
    turns = run.turns
    out: list[AssertResult] = []

    def add(name: str, ok: bool, detail: str) -> None:
        out.append(AssertResult(name, ok, detail))

    for key, want in spec.items():
        # turn_N: {"triage_level": "...", "alert": None}
        if key.startswith("turn_") and isinstance(want, dict) and key.count("_") == 1:
            idx = int(key.split("_")[1]) - 1
            if idx >= len(turns):
                add(key, False, f"case has only {len(turns)} turns")
                continue
            t = turns[idx]
            for fieldname, expected in want.items():
                actual = getattr(t, fieldname, None)
                add(
                    f"{key}.{fieldname}",
                    actual == expected,
                    f"got {actual!r}, want {expected!r}",
                )

        elif key == "min_triage_any_turn":
            best = max((_TRIAGE_ORDER.get(t.triage_level or "", -1) for t in turns), default=-1)
            add(key, best >= _TRIAGE_ORDER[want],
                f"highest was {[t.triage_level for t in turns]}, want at least {want}")

        elif key == "max_triage_any_turn":
            worst = max((_TRIAGE_ORDER.get(t.triage_level or "", -1) for t in turns), default=-1)
            add(key, worst <= _TRIAGE_ORDER[want],
                f"highest was {[t.triage_level for t in turns]}, want at most {want}")

        elif key == "expect_alert":
            add(key, any(t.alert == want for t in turns),
                f"alerts were {[t.alert for t in turns]}, want one {want!r}")

        elif key == "must_not_contain_any":
            joined = "\n".join(t.assistant for t in turns)
            hits, cleared = forbidden_hits(joined, want)
            detail = f"found forbidden {hits}" if hits else "none asserted"
            if cleared:
                detail += f" (negated, allowed: {cleared})"
            add(key, not hits, detail)

        # The negative form is tested FIRST: "turn_1_not_attributed_to" also ends
        # with "_attributed_to", so checking the positive form first would match
        # it and assert the exact opposite of what the corpus asked for.
        elif "_not_attributed" in key:
            idx = int(key.split("_")[1]) - 1
            # A weak but honest check: the reply must not read as though it had
            # settled on that pet. Naming it while ASKING which pet is fine, so
            # only flag a reply that names it without asking anything.
            if idx >= len(turns):
                add(key, False, "turn missing")
                continue
            text = turns[idx].assistant
            settled = want.lower() in text.lower() and "?" not in text
            add(key, not settled, f"appears to assume {want!r}" if settled else "did not assume")

        elif key.endswith("_attributed_to"):
            # turn_N_attributed_to: the reply must reference that pet by name.
            idx = int(key.split("_")[1]) - 1
            ok = idx < len(turns) and want.lower() in turns[idx].assistant.lower()
            add(key, ok, f"reply does not name {want!r}" if not ok else f"names {want!r}")

        else:
            add(key, False, f"unknown assertion {key!r} — check the corpus")

    return out


# ── GEval ────────────────────────────────────────────────────────────────────


def score_case(case: dict[str, Any], run: Any, judge: Any) -> tuple[float, str]:
    """GEval the whole conversation against the case's criteria.

    The rubric judges the transcript, not a single reply: these are multi-turn
    cases and most criteria talk about what the assistant did across the
    exchange ("escalate when vomiting begins"). Passing one turn at a time
    would lose exactly that.
    """
    def _run() -> tuple[float, str]:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, SingleTurnParams

        transcript = "\n\n".join(
            f"USER: {t.user}\nASSISTANT: {t.assistant}" for t in run.turns
        )
        metric = GEval(
            name="MultiTurnQuality",
            criteria=case["criteria"],
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=case.get("threshold", 0.7),
            async_mode=False,
            verbose_mode=False,
        )
        metric.measure(
            LLMTestCase(
                input=case.get("scenario", case["name"]),
                actual_output=transcript,
            )
        )
        return float(metric.score or 0.0), metric.reason or ""

    # deepeval spins its own event loop; running it on a worker thread keeps it
    # away from any loop the caller may already own.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()


# ── Report ───────────────────────────────────────────────────────────────────


@dataclass
class CaseResult:
    name: str
    passed: bool
    score: float
    threshold: float
    reason: str
    asserts: list[AssertResult] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)
    memories_seeded: int = 0
    error: str | None = None

    @property
    def assert_failures(self) -> list[AssertResult]:
        return [a for a in self.asserts if not a.passed]


def evaluate(case: dict[str, Any], run: Any, judge: Any) -> CaseResult:
    """Score one executed case: hard assertions first, then the rubric.

    A case passes only if BOTH hold. An assertion failure is not something a
    judge can score away — if `alert` is wrong the client renders the wrong
    thing regardless of how good the prose was.
    """
    asserts = check_asserts(case, run)
    threshold = float(case.get("threshold", 0.7))

    # Driving a case costs real LLM calls and minutes of wall clock. A judge
    # that errors must not take the transcript down with it: the case is
    # recorded as failed with the error attached, and the conversation stays in
    # the report where it can be read and the case rescored.
    error: str | None = None
    try:
        score, reason = score_case(case, run, judge)
    except Exception as e:  # noqa: BLE001
        score, reason = 0.0, ""
        error = f"scoring failed: {type(e).__name__}: {str(e)[:300]}"

    return CaseResult(
        name=case["name"],
        passed=error is None and all(a.passed for a in asserts) and score >= threshold,
        score=score,
        threshold=threshold,
        reason=reason,
        asserts=asserts,
        memories_seeded=run.memories_seeded,
        turns=flatten_turns(run),
        error=error,
    )


def flatten_turns(run: Any) -> list[dict[str, Any]]:
    """Expand paired turns into the flat role/content list the report uses.

    `triage_trace` carries ONLY `resolved`. The Streamlit page can also show
    `rule` and `llm` sub-levels, but the Go wire does not expose them: the
    `triage_level` on `assistant_done` is already the output of
    CompareAndResolve, with the rule and model inputs consumed inside the
    service. Emitting a guessed split would put a number on the screen that no
    part of the system ever computed.
    """
    out: list[dict[str, Any]] = []
    for t in run.turns:
        out.append({"role": "user", "content": t.user})
        out.append({
            "role": "assistant",
            "content": t.assistant,
            "triage_trace": {"resolved": {"level": t.triage_level or ""}},
            "alert": t.alert,
            "llm_source": t.llm_source,
            "latency_s": round(t.latency_s, 2),
            "trace_url": t.trace_url,
        })
    return out


def build_report(
    results: list[CaseResult],
    cases_by_name: dict[str, dict[str, Any]],
    *,
    judge_model: str,
    sut_model: str,
    timestamp: str,
    report_path: str,
) -> dict[str, Any]:
    """Assemble the report dict in the schema pages/1_Reports.py reads.

    `status` is the literal string the page filters on — "passed_threshold" /
    "below_threshold". It is not a boolean and not "passed"; the page compares
    it verbatim in three places.
    """
    cases_out = []
    for r in results:
        case = cases_by_name.get(r.name, {})
        cases_out.append({
            "name": r.name,
            "status": "passed_threshold" if r.passed else "below_threshold",
            "score": round(r.score, 4),
            "threshold": r.threshold,
            "reason": r.reason,
            "turn_count": len(r.turns) // 2,
            "turns": r.turns,
            # Surfaced by the page's context expander.
            "pet_profile": case.get("pet_profile") or {},
            "memories": case.get("memories") or [],
            "scenario": case.get("scenario", ""),
            "metadata": {
                **(case.get("metadata") or {}),
                "sut_model": sut_model,
                "judge_model": judge_model,
                "memories_seeded": r.memories_seeded,
                "assert_results": [
                    {"name": a.name, "passed": a.passed, "detail": a.detail}
                    for a in r.asserts
                ],
                "assert_failures": [a.name for a in r.assert_failures],
                "error": r.error,
            },
            # A case can clear the rubric and still be marked failed by an
            # assertion; say which, so a reader is not left comparing the score
            # against the threshold and concluding the report is broken.
            "root_cause": (
                {
                    "category": "assertion",
                    "explanation": "; ".join(
                        f"{a.name}: {a.detail}" for a in r.assert_failures
                    ),
                }
                if r.assert_failures
                else {}
            ),
        })

    passed = sum(1 for c in cases_out if c["status"] == "passed_threshold")
    breakdown: dict[str, int] = {}
    for c in cases_out:
        cat = (c["root_cause"] or {}).get("category")
        if cat:
            breakdown[cat] = breakdown.get(cat, 0) + 1

    return {
        "summary": {
            "report_path": report_path,
            "llm_model": sut_model,
            "judge_model": judge_model,
            "timestamp": timestamp,
            "total_cases": len(cases_out),
            "passed_threshold": passed,
            "below_threshold": len(cases_out) - passed,
            "root_cause_breakdown": breakdown,
            # Travels with the numbers so a report read weeks later still says
            # whether the judge was independent of what it graded.
            "judge_same_family": judge_model.split("-")[0] == sut_model.split("-")[0],
        },
        "cases": cases_out,
    }
