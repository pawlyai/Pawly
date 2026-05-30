import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.triage.rules_engine import classify_by_rules, detect_triage_from_response


def _append_log(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"logged_at": datetime.now().isoformat(), **event}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")


def test_handle_message_multiturn_with_conversational_geval(
    case: dict[str, Any],
    build_user_and_pet,
    build_update,
    mock_multiturn_runtime,
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
    case_name = case.get("name") or "<unnamed_case>"

    # One test_started event per worker (the parametrized tests share a single
    # session-scoped report_state, so the flag prevents duplicate entries).
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
            "scenario": case.get("scenario", ""),
            "user_turn_count": len(case.get("user_turns") or []),
        },
    )

    try:
        user, pet = build_user_and_pet(case)
        runtime = mock_multiturn_runtime(case, user, pet)
        bot, dp, fake_api, _redis = build_router_runtime(user, pet)
        full_turns: list[Turn] = []
        turn_traces: list[dict[str, Any]] = []
        full_loops: list[dict[str, Any]] = []

        user_turns = case.get("user_turns") or []
        for index, user_text in enumerate(user_turns, start=1):
            before_count = len(fake_api.sent_messages)
            update = build_update(user_text, message_id=index, telegram_user_id=10001)
            asyncio.run(dp.feed_update(bot, update))
            new_messages = fake_api.sent_messages[before_count:]
            assistant_text = "\n".join(item["text"] for item in new_messages)
            full_turns.append(Turn(role="user", content=user_text))
            full_turns.append(Turn(role="assistant", content=assistant_text))
            runtime.record_exchange(user_text, assistant_text)

            full_loop: dict[str, Any] = {
                "system_prompt": runtime.last_system_prompt,
                "memory_context": runtime.last_memory_context,
                "messages_sent_count": len(runtime.recent_turns),
            }
            full_loops.append(full_loop)

            # Live triage data captured by the generate_response wrapper in conftest.
            live = runtime.triage_results[index - 1] if index - 1 < len(runtime.triage_results) else {}
            # Post-hoc fallback (used only when live data is absent).
            rule_result = classify_by_rules(pet, user_text)
            kw_triage = detect_triage_from_response(assistant_text)
            triage_trace: dict[str, Any] = {
                "rule": {
                    "level": live.get("rule") or rule_result.classification.value,
                    "matched_rules": live.get("matched_patterns") or rule_result.matched_rules,
                    "score": live.get("score") or rule_result.score,
                },
                "llm": {
                    # Structured triage_level from the LLM's JSON output.
                    "level": live.get("llm"),
                    # "structured" | "plain_fallback"
                    "source": live.get("llm_source", "none"),
                    # Best-effort inference when structured path failed.
                    "inferred_level": live.get("llm_inferred"),
                    "inferred_method": live.get("llm_inferred_method"),
                },
                "response_keywords": {
                    # Audit-only keyword scan of the assistant's reply text.
                    "level": live.get("llm_response_keywords") or kw_triage.value,
                },
                "resolved": {
                    "level": live.get("final") or rule_result.classification.value,
                    "override": live.get("overridden", False),
                    "direction": live.get("override_direction", ""),
                },
                "langfuse_trace_url": live.get("langfuse_trace_url"),
            }
            turn_traces.append(triage_trace)

            _append_log(
                log_path,
                {
                    "event": "turn_completed",
                    "case_name": case_name,
                    "turn_index": index,
                    "user_text": user_text,
                    "assistant_text": assistant_text,
                    "new_message_count": len(new_messages),
                    "triage_trace": triage_trace,
                    "full_loop": {
                        "memory_context": runtime.last_memory_context[:500] if runtime.last_memory_context else "",
                        "messages_sent_count": full_loop["messages_sent_count"],
                    },
                },
            )

        conversation_case = ConversationalTestCase(
            name=case_name,
            scenario=case.get("scenario", ""),
            expected_outcome=case.get("expected_outcome", ""),
            chatbot_role=case.get("chatbot_role", ""),
            turns=full_turns,
            additional_metadata=case.get("metadata"),
        )
        metric = ConversationalGEval(
            name="MultiTurnTriageEffectiveness",
            criteria=case.get("criteria", ""),
            evaluation_params=[
                TurnParams.ROLE,
                TurnParams.CONTENT,
                TurnParams.SCENARIO,
                TurnParams.EXPECTED_OUTCOME,
            ],
            threshold=case.get("threshold", 0.7),
            model=deepeval_model,
            async_mode=False,
            verbose_mode=False,
        )
        score = metric.measure(
            conversation_case,
            _show_indicator=False,
            _log_metric_to_confident=False,
        )

        serialized_turns: list[dict[str, Any]] = []
        for i, turn in enumerate(full_turns):
            t: dict[str, Any] = {"role": turn.role, "content": turn.content}
            if turn.role == "assistant":
                t["triage_trace"] = turn_traces[i // 2]
                t["full_loop"] = full_loops[i // 2] if i // 2 < len(full_loops) else {}
            serialized_turns.append(t)

        case_result: dict[str, Any] = {
            "name": case_name,
            "status": "passed_threshold" if score >= metric.threshold else "below_threshold",
            "score": score,
            "threshold": metric.threshold,
            "reason": metric.reason,
            "turn_count": len(full_turns),
            "turns": serialized_turns,
            "pet_profile": case.get("pet_profile", {}),
            "memories": case.get("memories", []),
            "recent_turns_context": case.get("recent_turns", []),
            "metadata": case.get("metadata"),
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
            },
        )
    except Exception as exc:
        # Record the failure in both jsonl and the merged report so a single
        # bad case shows up in downstream tooling without taking down the run.
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
                "metadata": case.get("metadata"),
            }
        )
        # Re-raise so pytest marks this parametrized invocation as failed; the
        # other cases continue (this is the whole point of parametrizing).
        raise
