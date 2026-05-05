import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"


def _write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)


def _append_log(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"logged_at": datetime.now().isoformat(), **event}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")


def _resolve_model_name(deepeval_model: Any) -> str:
    raw_name = getattr(deepeval_model, "model", None)
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.replace("/", "-")

    get_model_name = getattr(deepeval_model, "get_model_name", None)
    if callable(get_model_name):
        resolved_name = get_model_name()
        if isinstance(resolved_name, str) and resolved_name.strip():
            return resolved_name.replace("/", "-")

    return "gemini-2.5-flash"


def test_handle_message_multiturn_with_conversational_geval(
    load_test_cases,
    build_user_and_pet,
    build_update,
    mock_multiturn_runtime,
    build_router_runtime,
    deepeval_model,
    multiturn_topic,
    git_ref,
) -> None:
    pytest.importorskip("deepeval")
    from deepeval.metrics import ConversationalGEval
    from deepeval.test_case import ConversationalTestCase, Turn
    from deepeval.test_case.conversational_test_case import TurnParams

    # Generate report filename with LLM name, datetime, and (optional) branch/tag.
    # Branch/tag is appended after a double-underscore so legacy filenames keep
    # parsing cleanly while new ones can be filtered by code revision.
    llm_name = _resolve_model_name(deepeval_model)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ref_suffix = f"__{git_ref}" if git_ref else ""
    report_filename = f"{multiturn_topic}_report_{llm_name}_v{timestamp}{ref_suffix}.json"
    report_path = RESULTS_DIR / report_filename
    log_filename = f"{multiturn_topic}_run_{llm_name}_v{timestamp}{ref_suffix}.jsonl"
    log_path = LOGS_DIR / log_filename

    cases = load_test_cases(f"{multiturn_topic}_cases.json")
    report_cases: list[dict[str, Any]] = []
    _append_log(
        log_path,
        {
            "event": "test_started",
            "topic": multiturn_topic,
            "llm_model": llm_name,
            "git_ref": git_ref,
            "case_count": len(cases),
            "report_path": str(report_path),
        },
    )

    for case in cases:
        _append_log(
            log_path,
            {
                "event": "case_started",
                "case_name": case["name"],
                "scenario": case["scenario"],
                "user_turn_count": len(case["user_turns"]),
            },
        )
        try:
            user, pet = build_user_and_pet(case)
            runtime = mock_multiturn_runtime(case, user, pet)
            bot, dp, fake_api, _redis = build_router_runtime(user, pet)
            full_turns: list[Turn] = []

            for index, user_text in enumerate(case["user_turns"], start=1):
                before_count = len(fake_api.sent_messages)
                update = build_update(user_text, message_id=index, telegram_user_id=10001)
                asyncio.run(
                    dp.feed_update(bot, update)
                )
                new_messages = fake_api.sent_messages[before_count:]
                assistant_text = "\n".join(item["text"] for item in new_messages)
                full_turns.append(Turn(role="user", content=user_text))
                full_turns.append(Turn(role="assistant", content=assistant_text))
                runtime.record_exchange(user_text, assistant_text)

                _append_log(
                    log_path,
                    {
                        "event": "turn_completed",
                        "case_name": case["name"],
                        "turn_index": index,
                        "user_text": user_text,
                        "assistant_text": assistant_text,
                        "new_message_count": len(new_messages),
                    },
                )

            conversation_case = ConversationalTestCase(
                name=case["name"],
                scenario=case["scenario"],
                expected_outcome=case["expected_outcome"],
                chatbot_role=case["chatbot_role"],
                turns=full_turns,
                additional_metadata=case.get("metadata"),
            )
            metric = ConversationalGEval(
                name="MultiTurnTriageEffectiveness",
                criteria=case["criteria"],
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

            case_result = {
                "name": case["name"],
                "status": "passed_threshold" if score >= metric.threshold else "below_threshold",
                "score": score,
                "threshold": metric.threshold,
                "reason": metric.reason,
                "turn_count": len(full_turns),
                "turns": [{"role": turn.role, "content": turn.content} for turn in full_turns],
                "metadata": case.get("metadata"),
            }
            report_cases.append(case_result)
            _append_log(
                log_path,
                {
                    "event": "case_finished",
                    "case_name": case["name"],
                    "status": case_result["status"],
                    "score": score,
                    "threshold": metric.threshold,
                },
            )
        except Exception as exc:
            _append_log(
                log_path,
                {
                    "event": "case_failed",
                    "case_name": case["name"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "completed_cases": len(report_cases),
                },
            )
            partial_summary = {
                "report_path": str(report_path),
                "log_path": str(log_path),
                "llm_model": llm_name,
                "git_ref": git_ref,
                "timestamp": timestamp,
                "total_cases": len(cases),
                "completed_cases": len(report_cases),
                "failed_case": case["name"],
            }
            _write_report({"summary": partial_summary, "cases": report_cases}, report_path)
            raise

    summary = {
        "report_path": str(report_path),
        "log_path": str(log_path),
        "llm_model": llm_name,
        "git_ref": git_ref,
        "timestamp": timestamp,
        "total_cases": len(report_cases),
        "passed_threshold": sum(1 for item in report_cases if item["status"] == "passed_threshold"),
        "below_threshold": sum(1 for item in report_cases if item["status"] == "below_threshold"),
    }
    _write_report({"summary": summary, "cases": report_cases}, report_path)
    _append_log(
        log_path,
        {
            "event": "test_finished",
            "total_cases": len(report_cases),
            "passed_threshold": summary["passed_threshold"],
            "below_threshold": summary["below_threshold"],
        },
    )
