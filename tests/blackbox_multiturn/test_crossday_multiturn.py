import asyncio
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.db.models import MemorySource, Pet, PetMemory
from src.triage.rules_engine import classify_by_rules, detect_triage_from_response

# ===========================================================================
# Module-level helpers
# ===========================================================================


async def _run_extraction(messages: list[dict], pet: Pet, existing: list[PetMemory]) -> list:
    from src.memory.extractor import extract_memories

    return await extract_memories(messages, pet, existing)


async def _gen_daily_summary(messages: list[dict], pet: Pet) -> Any:
    import json as _json

    from src.config import settings
    from src.llm.providers import get_chat_client
    from src.memory.summarizer import DAILY_PROMPT, _strip_fences

    if not messages:
        return None

    convo = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Pawly'}: {m['content']}"
        for m in messages
    )
    filled = DAILY_PROMPT.format(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "unknown",
        age=f"{pet.age_in_months}mo" if pet.age_in_months else "unknown",
        date=date.today().isoformat(),
        messages=convo,
    )
    model = settings.chat_model or settings.main_model
    client = get_chat_client(model)
    last_exc: Exception | None = None
    for _attempt in range(2):
        try:
            raw = await client.chat(
                system_prompt=filled,
                messages=[{"role": "user", "content": "Generate the summary now."}],
                model=model,
                max_tokens=1024,
                temperature=0.2,
            )
            summary_data = _json.loads(_strip_fences(raw["text"]))
            break
        except Exception as exc:
            last_exc = exc
            summary_data = None
    if summary_data is None:
        summary_data = {
            "core_issues": [],
            "new_symptoms": [],
            "severity_changes": "unknown",
            "follow_up_needed": False,
            "_parse_error": str(last_exc),
        }
    return SimpleNamespace(summary=summary_data)


def _append_log(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"logged_at": datetime.now().isoformat(), **event}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


# ===========================================================================
# Test
# ===========================================================================


def test_crossday_with_conversational_geval(
    crossday_case: dict[str, Any],
    build_user_and_pet,
    build_update,
    mock_crossday_runtime,
    build_router_runtime,
    deepeval_model,
    run_context: dict[str, Any],
    report_state: dict[str, Any],
) -> None:
    pytest.importorskip("deepeval")
    from deepeval.metrics import ConversationalGEval
    from deepeval.test_case import ConversationalTestCase, Turn
    from deepeval.test_case.conversational_test_case import TurnParams

    log_path: Path = run_context["partial_log"]
    case_name = crossday_case.get("name") or "<unnamed_crossday_case>"

    # One test_started event per worker.
    if not report_state["started_logged"]:
        report_state["started_logged"] = True
        _append_log(
            log_path,
            {
                "event": "test_started",
                "topic": run_context["topic"],
                "llm_model": run_context["model_name"],
                "worker_id": run_context["worker_id"],
                "report_path": str(run_context["partial_report"]),
            },
        )

    _append_log(
        log_path,
        {
            "event": "case_started",
            "case_name": case_name,
            "scenario": crossday_case.get("scenario", ""),
            "day_count": len(crossday_case.get("days") or []),
        },
    )

    try:
        user, pet = build_user_and_pet(crossday_case)
        runtime = mock_crossday_runtime(crossday_case, user, pet)
        bot, dp, fake_api, _redis = build_router_runtime(user, pet)

        all_turns: list[Turn] = []
        all_triage_traces: list[dict] = []
        all_full_loops: list[dict] = []
        turn_global_idx = 0

        days = crossday_case.get("days") or []

        for day_idx, day_spec in enumerate(days):
            # Reset day context in the runtime.
            runtime.start_new_day()

            day_label = day_spec.get("label", f"Day {day_idx + 1}")
            user_turns = day_spec.get("user_turns") or []

            for user_text in user_turns:
                turn_global_idx += 1

                before_count = len(fake_api.sent_messages)
                asyncio.run(
                    dp.feed_update(
                        bot,
                        build_update(
                            user_text,
                            message_id=turn_global_idx,
                            telegram_user_id=10001,
                        ),
                    )
                )
                new_messages = fake_api.sent_messages[before_count:]
                assistant_text = "\n".join(item["text"] for item in new_messages)

                runtime.record_exchange(user_text, assistant_text)

                all_turns.append(Turn(role="user", content=user_text))
                all_turns.append(Turn(role="assistant", content=assistant_text))

                # Triage trace — prefer live data captured by the runtime wrapper.
                live_idx = len(all_triage_traces)
                live = (
                    runtime.triage_results[live_idx]
                    if live_idx < len(runtime.triage_results)
                    else {}
                )
                rule_result = classify_by_rules(pet, user_text)
                kw_triage = detect_triage_from_response(assistant_text)
                triage_trace: dict[str, Any] = {
                    "rule": {
                        "level": live.get("rule") or rule_result.classification.value,
                        "matched_rules": live.get("matched_patterns") or rule_result.matched_rules,
                        "score": live.get("score") or rule_result.score,
                    },
                    "llm": {
                        "level": live.get("llm"),
                        "source": live.get("llm_source", "none"),
                        "inferred_level": live.get("llm_inferred"),
                        "inferred_method": live.get("llm_inferred_method"),
                    },
                    "response_keywords": {
                        "level": live.get("llm_response_keywords") or kw_triage.value,
                    },
                    "resolved": {
                        "level": live.get("final") or rule_result.classification.value,
                        "override": live.get("overridden", False),
                        "direction": live.get("override_direction", ""),
                    },
                    "langfuse_trace_url": live.get("langfuse_trace_url"),
                }
                all_triage_traces.append(triage_trace)

                full_loop: dict[str, Any] = {
                    "system_prompt": runtime.last_system_prompt,
                    "memory_context": runtime.last_memory_context,
                    "messages_sent_count": len(runtime.current_day_recent_turns),
                    "day_label": day_label,
                    "extraction_proposals": [],
                }
                all_full_loops.append(full_loop)

                _append_log(
                    log_path,
                    {
                        "event": "turn_completed",
                        "case_name": case_name,
                        "day_label": day_label,
                        "turn_global_idx": turn_global_idx,
                        "user_text": user_text,
                        "assistant_text": assistant_text,
                        "new_message_count": len(new_messages),
                        "triage_trace": triage_trace,
                        "full_loop": {
                            "memory_context": runtime.last_memory_context or "",
                            "system_prompt": runtime.last_system_prompt or "",
                            "messages_sent_count": len(runtime.current_day_recent_turns),
                            "injected_memories": [
                                {
                                    "field": m.field,
                                    "value": m.value if isinstance(m.value, str) else str(m.value),
                                    "memory_term": m.memory_term.value,
                                    "memory_type": m.memory_type.value,
                                    "confidence": m.confidence_score,
                                }
                                for m in runtime.memories
                            ],
                        },
                    },
                )

            # After all user turns in this day: optionally run extraction.
            if day_spec.get("run_extraction", True) and runtime.current_day_raw_messages:
                proposals = asyncio.run(
                    _run_extraction(
                        runtime.current_day_raw_messages,
                        pet,
                        runtime.memories,
                    )
                )
                for p in proposals:
                    value = p.value if isinstance(p.value, dict) else {"v": p.value}
                    runtime.memories.append(
                        PetMemory(
                            id=uuid.uuid4(),
                            pet_id=pet.id,
                            memory_type=p.memory_type,
                            memory_term=p.memory_term,
                            field=p.field,
                            value=value,
                            confidence_score=p.confidence,
                            source=MemorySource.AI_EXTRACTED,
                            source_message_id=None,
                            is_active=True,
                        )
                    )

                # Attach proposal summaries to the last full_loop entry for this day.
                if all_full_loops:
                    all_full_loops[-1]["extraction_proposals"] = [
                        {
                            "field": p.field,
                            "value": str(p.value),
                            "confidence": p.confidence,
                            "memory_term": p.memory_term.value,
                        }
                        for p in proposals
                    ]

                _append_log(
                    log_path,
                    {
                        "event": "day_extraction_complete",
                        "case_name": case_name,
                        "day_label": day_label,
                        "proposal_count": len(proposals),
                    },
                )

            # Optionally generate daily summary.
            if day_spec.get("run_daily_summary", False) and runtime.current_day_raw_messages:
                runtime.daily_summary = asyncio.run(
                    _gen_daily_summary(runtime.current_day_raw_messages, pet)
                )
                summary_data = getattr(runtime.daily_summary, "summary", {}) or {}
                _append_log(
                    log_path,
                    {
                        "event": "day_summary_complete",
                        "case_name": case_name,
                        "day_label": day_label,
                        "core_issues": summary_data.get("core_issues", []),
                        "new_symptoms": summary_data.get("new_symptoms", []),
                        "severity_changes": summary_data.get("severity_changes", ""),
                        "parse_error": summary_data.get("_parse_error"),
                    },
                )

        # ── Judge the full cross-day conversation ──────────────────────────────
        conversation_case = ConversationalTestCase(
            name=case_name,
            scenario=crossday_case.get("scenario", ""),
            expected_outcome=crossday_case.get("expected_outcome", ""),
            chatbot_role=crossday_case.get("chatbot_role", ""),
            turns=all_turns,
            additional_metadata=crossday_case.get("metadata"),
        )
        metric = ConversationalGEval(
            name="CrossDayTriageEffectiveness",
            criteria=crossday_case.get("criteria", ""),
            evaluation_params=[
                TurnParams.ROLE,
                TurnParams.CONTENT,
                TurnParams.SCENARIO,
                TurnParams.EXPECTED_OUTCOME,
            ],
            threshold=crossday_case.get("threshold", 0.85),
            model=deepeval_model,
            async_mode=False,
            verbose_mode=False,
        )
        score = metric.measure(
            conversation_case,
            _show_indicator=False,
            _log_metric_to_confident=False,
        )

        # ── Build serialized turns for the report ──────────────────────────────
        # all_turns alternates user/assistant. For each assistant turn (even index
        # in all_turns = user, odd = assistant), attach triage_trace and full_loop.
        # assistant turn i corresponds to triage_traces[i] (one per exchange).
        serialized_turns: list[dict[str, Any]] = []
        assistant_idx = 0
        for i, turn in enumerate(all_turns):
            t: dict[str, Any] = {"role": turn.role, "content": turn.content}
            if turn.role == "assistant":
                t["triage_trace"] = all_triage_traces[assistant_idx] if assistant_idx < len(all_triage_traces) else {}
                loop = all_full_loops[assistant_idx] if assistant_idx < len(all_full_loops) else {}
                t["full_loop"] = loop
                t["day_label"] = loop.get("day_label", "")
                assistant_idx += 1
            serialized_turns.append(t)

        # Extracted memories summary after all days.
        extracted_memories_after_all_days = [
            {
                "field": m.field,
                "value": m.value,
                "memory_type": m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type),
                "memory_term": m.memory_term.value if hasattr(m.memory_term, "value") else str(m.memory_term),
                "confidence_score": m.confidence_score,
            }
            for m in runtime.memories
        ]

        case_result: dict[str, Any] = {
            "name": case_name,
            "status": "passed_threshold" if score >= metric.threshold else "below_threshold",
            "score": score,
            "threshold": metric.threshold,
            "reason": metric.reason,
            "turn_count": len(all_turns),
            "day_count": len(days),
            "turns": serialized_turns,
            "pet_profile": crossday_case.get("pet_profile", {}),
            "memories": crossday_case.get("memories", []),
            "extracted_memories_after_all_days": extracted_memories_after_all_days,
            "metadata": crossday_case.get("metadata"),
            "langfuse_session_id": runtime.dialogue_id,
            "langfuse_session_url": runtime.langfuse_session_url,
        }
        report_state["cases"].append(case_result)

        _append_log(
            log_path,
            {
                "event": "case_finished",
                "case_name": case_name,
                "status": case_result["status"],
                "score": score,
                "threshold": metric.threshold,
                "day_count": len(days),
                "extracted_memory_count": len(extracted_memories_after_all_days),
            },
        )

    except Exception as exc:
        _append_log(
            log_path,
            {
                "event": "case_failed",
                "case_name": case_name,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        report_state["cases"].append(
            {
                "name": case_name,
                "status": "errored",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "metadata": crossday_case.get("metadata"),
            }
        )
        raise
