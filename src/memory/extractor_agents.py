"""PLACEHOLDER for a missing module.

`src/memory/extractor.py` imports `triage_message`, `validate_facts`, and the
four `*_SPECIALIST_PROMPT` constants from this module, but `extractor_agents.py`
was never committed to the repository (absent from git history on every branch).
On a clean checkout of `main` this breaks `import src.memory.extractor`, which in
turn breaks anything that imports it — including the blackbox multiturn eval
harness (`tests/blackbox_multiturn/conftest.py`).

This stub exists ONLY to make the import resolve so the multiturn harness (which
never runs memory extraction — the ARQ `run_extraction` enqueue is stubbed in
conftest) can execute. The real extraction logic is NOT reconstructed here: the
callables raise loudly if actually invoked, so no fake behavior can slip into a
real extraction run. Restore the genuine `extractor_agents.py` to re-enable
memory extraction.
"""

from __future__ import annotations

from typing import Any

_MISSING = (
    "extractor_agents.py is a placeholder — the real module was never committed "
    "to the repo. Restore it to run memory extraction."
)

# extractor.py uses these as system prompts for per-domain specialist extraction.
# Placeholder text; never consumed unless the (stubbed-out) extraction job runs.
HEALTH_SPECIALIST_PROMPT: str = "PLACEHOLDER: health specialist prompt missing."
MEDICATION_SPECIALIST_PROMPT: str = "PLACEHOLDER: medication specialist prompt missing."
BEHAVIOR_SPECIALIST_PROMPT: str = "PLACEHOLDER: behavior specialist prompt missing."
ACUTE_SPECIALIST_PROMPT: str = "PLACEHOLDER: acute specialist prompt missing."


async def triage_message(*_args: Any, **_kwargs: Any) -> Any:
    """Real impl routes a message to specialist extractors. Placeholder raises."""
    raise NotImplementedError(_MISSING)


def validate_facts(*_args: Any, **_kwargs: Any) -> Any:
    """Real impl validates extracted facts. Placeholder raises."""
    raise NotImplementedError(_MISSING)
