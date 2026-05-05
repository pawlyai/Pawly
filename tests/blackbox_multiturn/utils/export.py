"""CSV export utilities for the blackbox multiturn test-results app."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_TRANSLATION_MODEL = "deepseek-chat"
_BATCH_SIZE = 10
_MAX_WORKERS = 5  # concurrent DeepSeek API calls

CSV_HEADERS = [
    "report_name",
    "test_case_id",
    "user_id",
    "pet_id",
    "provider",
    "model",
    "git_ref",
    "test_time",
    "score",
    "threshold",
    "pass_fail",
    "eval_rationale",
    "category",
    "focus",
    "priority",
    "total_turns",
    "turn_number",
    "speaker",
    "content_en",
    "content_zh",
    "annotation",
]


def _provider_for_model(model: str) -> str:
    """Infer provider name from model identifier prefix."""
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gpt"):
        return "openai"
    if model.startswith("deepseek"):
        return "deepseek"
    return "unknown"


def _fmt_timestamp(ts: str) -> str:
    """Convert YYYYMMDD_HHMMSS to ISO 8601 (YYYY-MM-DDTHH:MM:SS); returns ts unchanged on error."""
    try:
        date_part, time_part = ts.split("_", 1)
        return (
            f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
            f"T{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
        )
    except Exception:
        return ts


def cache_key(report_name: str, turn_index: int, content: str) -> str:
    """SHA-256 hash that uniquely identifies a single turn for translation caching."""
    raw = f"{report_name}:{turn_index}:{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_translation_cache(cache_path: Path) -> dict[str, str]:
    """Load the translation cache; returns an empty dict if the file is absent or unreadable."""
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            logger.warning("Could not load translation cache %s: %s", cache_path, exc)
    return {}


def save_translation_cache(cache: dict[str, str], cache_path: Path) -> None:
    """Persist translation cache to disk; creates parent directories if needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def _translate_batch(texts: list[str], api_key: str) -> list[str]:
    """Translate up to _BATCH_SIZE English strings to Simplified Chinese via DeepSeek.

    Returns translated strings in the same order; on any error returns '[translation failed]'
    for each item so the export can always complete.
    """
    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError:
        logger.error("openai SDK not installed; translation skipped")
        return ["[translation failed]"] * len(texts)

    try:
        client = OpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
        prompt = (
            "Translate the following texts from English to Simplified Chinese. "
            'Return a JSON object with a single key "translations" whose value is an array '
            "of translated strings in exactly the same order as the input.\n\n"
            f"Input (JSON array):\n{json.dumps(texts, ensure_ascii=False)}"
        )
        resp = client.chat.completions.create(
            model=_TRANSLATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=4096,
            temperature=0.1,
        )
        payload = json.loads(resp.choices[0].message.content or "{}")
        translations = payload.get("translations", [])
        logger.info(
            "DeepSeek translation: requested=%d returned=%d",
            len(texts),
            len(translations),
        )
        if len(translations) == len(texts):
            return [str(t) for t in translations]
        logger.warning(
            "Count mismatch (expected %d, got %d); marking batch as failed",
            len(texts),
            len(translations),
        )
        return ["[translation failed]"] * len(texts)
    except Exception as exc:
        logger.error("DeepSeek translation error: %s", exc)
        return ["[translation failed]"] * len(texts)


def translate_uncached(
    items: list[tuple[str, str]],
    cache: dict[str, str],
    api_key: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, str]:
    """Translate any items whose cache key is not yet in cache; mutates and returns cache.

    items: list of (cache_key, content) for every turn in the export set.
    on_progress(done, total) is called after each batch completes.
    """
    # Deduplicate: keep first-seen content for each unseen key
    seen: dict[str, str] = {}
    for k, c in items:
        if k not in cache and k not in seen:
            seen[k] = c
    pending = list(seen.items())

    total = len(pending)
    done = 0

    # Build batches upfront so futures map cleanly to their keys.
    batches: list[tuple[list[str], list[str]]] = []
    for batch_start in range(0, total, _BATCH_SIZE):
        batch = pending[batch_start : batch_start + _BATCH_SIZE]
        batches.append(([k for k, _ in batch], [c for _, c in batch]))

    # Run up to _MAX_WORKERS batches concurrently; as_completed returns each
    # future in completion order so progress and cache updates stay on the
    # main thread (no lock needed).
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_keys = {
            executor.submit(_translate_batch, texts, api_key): keys
            for keys, texts in batches
        }
        for future in as_completed(future_to_keys):
            keys = future_to_keys[future]
            results = future.result()
            for key, result in zip(keys, results):
                cache[key] = result
            done += len(keys)
            if on_progress:
                on_progress(done, total)

    return cache


def translate_for_display(text: str, cache_path: Path) -> str:
    """Translate a single text to Chinese for UI display using the shared cache.

    Returns the original text if DEEPSEEK_API_KEY is not set or translation fails.
    """
    if not text:
        return text

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return text

    ck = hashlib.sha256(f"ui:{text}".encode("utf-8")).hexdigest()
    cache = load_translation_cache(cache_path)

    if ck in cache:
        return cache[ck]

    results = _translate_batch([text], api_key)
    translated = results[0] if results else "[translation failed]"

    if translated != "[translation failed]":
        cache[ck] = translated
        save_translation_cache(cache, cache_path)
        return translated

    return text


def pre_translate_report(
    report_path: Path,
    cache_path: Path,
    api_key: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Translate all turns in a single report file and persist the cache.

    Called automatically after a test run so CSV downloads are instant later.
    Returns the number of turns that were newly translated (0 if all cached).
    """
    try:
        with report_path.open("r", encoding="utf-8") as fh:
            report_data = json.load(fh)
    except Exception as exc:
        logger.error("Cannot read report %s: %s", report_path, exc)
        return 0

    report_name = report_path.stem
    cache = load_translation_cache(cache_path)

    items: list[tuple[str, str]] = []
    for case in report_data.get("cases", []):
        for ti, turn in enumerate(case.get("turns", [])):
            content = turn.get("content", "")
            ck = cache_key(report_name, ti, content)
            items.append((ck, content))

    uncached = [(k, c) for k, c in items if k not in cache]
    if not uncached:
        return 0

    translate_uncached(uncached, cache, api_key, on_progress=on_progress)
    save_translation_cache(cache, cache_path)
    logger.info("Pre-translated %d turns for %s", len(uncached), report_name)
    return len(uncached)


def generate_csv(
    reports: list[tuple[str, dict[str, Any]]],
    cache_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> bytes:
    """Build a UTF-8-with-BOM CSV from the given reports and return as bytes.

    reports: list of (filename_stem, parsed_report_dict)
    cache_path: path to translation_cache.json in the results directory
    on_progress: callback(fraction 0.0–1.0, status_message) for progress reporting

    Translations are cached; subsequent exports of the same turns skip API calls.
    Export always completes even if 100% of translations fail.
    """

    def _prog(frac: float, msg: str) -> None:
        if on_progress:
            on_progress(frac, msg)

    _prog(0.0, "Loading translation cache…")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    cache = load_translation_cache(cache_path)

    # ── First pass: build row data and collect (cache_key, content) pairs ──────
    rows: list[dict[str, Any]] = []
    translation_items: list[tuple[str, str]] = []  # (cache_key, content)

    for report_name, report_data in reports:
        summary = report_data.get("summary", {})
        model = summary.get("llm_model", "unknown")
        provider = _provider_for_model(model)
        test_time = _fmt_timestamp(summary.get("timestamp", ""))
        git_ref = summary.get("git_ref", "") or ""
        # Fall back to filename-encoded git_ref for legacy reports whose
        # summary block predates the field. report_name is the stem.
        if not git_ref and "__" in report_name:
            git_ref = report_name.rsplit("__", 1)[1]

        for case in report_data.get("cases", []):
            case_name = case.get("name", "")
            score = float(case.get("score", 0.0))
            threshold = float(case.get("threshold", 0.7))
            pass_fail = "PASS" if score >= threshold else "FAIL"
            eval_rationale = case.get("reason", "")
            metadata = case.get("metadata", {})
            category = metadata.get("category", "")
            focus = metadata.get("focus", "")
            priority = metadata.get("priority", "")
            turns = case.get("turns", [])
            total_turns = len(turns)

            name_parts = case_name.split("_")
            if len(name_parts) >= 2:
                user_id, pet_id = name_parts[0], name_parts[1]
            else:
                user_id, pet_id = "unknown", "unknown"
                logger.warning(
                    "Cannot parse user_id/pet_id from test_case_id: %s", case_name
                )

            for ti, turn in enumerate(turns):
                content = turn.get("content", "")
                ck = cache_key(report_name, ti, content)
                translation_items.append((ck, content))
                rows.append(
                    {
                        "report_name": report_name,
                        "test_case_id": case_name,
                        "user_id": user_id,
                        "pet_id": pet_id,
                        "provider": provider,
                        "model": model,
                        "git_ref": git_ref,
                        "test_time": test_time,
                        "score": score,
                        "threshold": threshold,
                        "pass_fail": pass_fail,
                        "eval_rationale": eval_rationale,
                        "category": category,
                        "focus": focus,
                        "priority": priority,
                        "total_turns": total_turns,
                        "turn_number": ti + 1,
                        "speaker": "USER" if turn.get("role") == "user" else "AI",
                        "content_en": content,
                        "_ck": ck,
                    }
                )

    # ── Second pass: translate uncached turns ─────────────────────────────────
    uncached_count = sum(1 for k, _ in translation_items if k not in cache)

    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set; content_zh will be '[translation failed]'")
    elif uncached_count > 0:
        _prog(0.05, f"Translating {uncached_count} turns…")

        def _batch_prog(done: int, total: int) -> None:
            _prog(
                0.05 + 0.85 * done / max(total, 1),
                f"Translating turns… ({done}/{total})",
            )

        cache = translate_uncached(
            translation_items, cache, api_key, on_progress=_batch_prog
        )
        save_translation_cache(cache, cache_path)
    else:
        _prog(0.9, "All turns already cached — skipping translation API calls.")

    # ── Third pass: write CSV ─────────────────────────────────────────────────
    _prog(0.92, "Building CSV…")
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_HEADERS)

    for row in rows:
        ck = row["_ck"]
        content_zh = cache.get(ck, "[translation failed]")
        writer.writerow(
            [
                row["report_name"],
                row["test_case_id"],
                row["user_id"],
                row["pet_id"],
                row["provider"],
                row["model"],
                row["git_ref"],
                row["test_time"],
                row["score"],
                row["threshold"],
                row["pass_fail"],
                row["eval_rationale"].replace("\n", "\\n"),
                row["category"],
                row["focus"],
                row["priority"],
                row["total_turns"],
                row["turn_number"],
                row["speaker"],
                row["content_en"].replace("\n", "\\n"),
                content_zh.replace("\n", "\\n"),
                "",  # annotation — empty column for human annotators
            ]
        )

    _prog(1.0, "Export complete.")
    # utf-8-sig encoding adds the BOM that Google Sheets needs for correct Chinese rendering
    return output.getvalue().encode("utf-8-sig")
