"""Shared UI translations for the Streamlit test-results app."""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "language": "语言 / Language",
        # shared
        "no_reports": "No reports yet. Run tests first.",
        "score": "Score",
        "threshold": "Threshold",
        "turn_count": "Turn Count",
        "reason": "Reason",
        "passed": "Passed",
        "failed": "Failed",
        "pass_rate": "Pass Rate",
        "total_cases": "Total Cases",
        "case": "Case",
        "status_passed_label": "Passed Threshold",
        "status_failed_label": "Below Threshold",
        # Reports page
        "report_title": "📋 Report Detail",
        "select_report": "Select Report",
        "filters": "🔍 Filters",
        "report_filters": "📊 Report Filters",
        "filter_by_model": "Model",
        "filter_by_category": "Category",
        "all_models": "All Models",
        "all_categories": "All Categories",
        "status": "Status",
        "status_all": "All",
        "status_passed": "Passed",
        "status_failed": "Failed",
        "minimum_score": "Minimum Score",
        "sort_by": "Sort By",
        "sort_name": "Name",
        "sort_score_high": "Score (High to Low)",
        "sort_score_low": "Score (Low to High)",
        "sort_turns": "Turn Count",
        "showing_cases": "Showing {n} of {total} test cases",
        "test_cases": "Test Cases",
        "no_cases_match": "No test cases match the current filters.",
        "eval_reason": "📝 Evaluation Reason",
        "root_cause_breakdown": "🔍 Failure Breakdown by Root Cause",
        "root_cause": "🔍 Root Cause",
        "rc_category": "Category",
        "rc_explanation": "Explanation",
        "rc_count": "Count",
        "rc_share": "Share",
        "transcript": "💬 Conversation Transcript",
        "no_turns": "No conversation turns available",
        "user_turn": "👤 User (Turn {i}):",
        "assistant_turn": "🤖 Assistant (Turn {i}):",
        # Compare page
        "compare_title": "⚖️ Compare Runs",
        "compare_caption": "Pick 2–6 reports to compare pass rates and per-case scores.",
        "no_reports_compare": "No reports yet — run tests first.",
        "reports_to_compare": "Reports to compare",
        "pick_two": "Pick at least two reports.",
        "summary": "Summary",
        "pass_rate_chart": "Pass rate",
        "per_case_scores": "Per-case scores",
        "drill_into": "Drill into a case",
        "not_in_report": "Not in this report.",
        "col_report": "Report",
        "col_topic": "Topic",
        "col_model": "Model",
        "col_cases": "Cases",
        "col_passed": "Passed",
        "col_pass_rate": "Pass Rate (%)",
        "col_avg_score": "Avg Score",
        # Go Eval page
        "go_title": "Go Eval",
        "go_tab_run": "Run",
        "go_tab_stability": "Stability across {n} runs",
        "go_report": "Report",
        "go_no_reports": "No Go reports yet. Bring the eval stack up and run:",
        "go_judged_by": "System under test **{sut}** · judged by **{judge}**",
        "go_same_family": "Judge **{judge}** and system under test **{sut}** are the same model family. Scores on subjective criteria are optimistic; the assertions below are unaffected.",
        "go_col_asserts": "Asserts",
        "go_col_failed_assert": "Failed assert",
        "go_col_mem": "Mem",
        "go_col_turns": "Turns",
        "go_col_scored": "Scored",
        "go_col_rate": "Rate",
        "go_col_verdict": "Verdict",
        "go_col_history": "History",
        "go_col_drive_errors": "Drive errors",
        "go_assertions": "**Assertions** — wire fields, not opinions",
        "go_no_asserts": "none declared",
        "go_judged_score": "**Judged score** — the case's own criteria",
        "go_rubric_but_assert": "Cleared the rubric but failed an assertion. The judge scored the prose; the assertion checked what actually went over the wire.",
        "go_context": "Context — {label} · {n} memories seeded",
        "go_user": "User",
        "go_assistant": "Assistant",
        "go_no_alert": "no alert",
        "go_v_stable_pass": "stable pass",
        "go_v_stable_fail": "stable fail",
        "go_v_never_ran": "never ran",
        "go_v_flaky": "FLAKY ({ok}/{n})",
        "go_v_fixed": "fixed ({n} straight)",
        "go_v_regressed": "REGRESSED ({n} straight)",
        "go_history_caption": "History reads oldest to newest: `.` pass, `x` fail, `!` the driver never reached the model (excluded from the rate). A genuinely mixed row means the run you opened decided the verdict, not the code.",
    },
    "zh": {
        "language": "语言 / Language",
        # shared
        "no_reports": "暂无报告，请先运行测试。",
        "score": "分数",
        "threshold": "阈值",
        "turn_count": "对话轮数",
        "reason": "原因",
        "passed": "通过",
        "failed": "失败",
        "pass_rate": "通过率",
        "total_cases": "总用例数",
        "case": "用例",
        "status_passed_label": "通过阈值",
        "status_failed_label": "低于阈值",
        # Reports page
        "report_title": "📋 报告详情",
        "select_report": "选择报告",
        "filters": "🔍 筛选",
        "report_filters": "📊 报告筛选",
        "filter_by_model": "模型",
        "filter_by_category": "类别",
        "all_models": "所有模型",
        "all_categories": "所有类别",
        "status": "状态",
        "status_all": "全部",
        "status_passed": "通过",
        "status_failed": "失败",
        "minimum_score": "最低分数",
        "sort_by": "排序方式",
        "sort_name": "名称",
        "sort_score_high": "分数（从高到低）",
        "sort_score_low": "分数（从低到高）",
        "sort_turns": "对话轮数",
        "showing_cases": "显示 {n} / {total} 个测试用例",
        "test_cases": "测试用例",
        "no_cases_match": "没有用例符合当前筛选条件。",
        "eval_reason": "📝 评测原因",
        "root_cause_breakdown": "🔍 失败原因分布",
        "root_cause": "🔍 根本原因",
        "rc_category": "类别",
        "rc_explanation": "说明",
        "rc_count": "数量",
        "rc_share": "占比",
        "transcript": "💬 对话记录",
        "no_turns": "暂无对话记录",
        "user_turn": "👤 用户（第 {i} 轮）：",
        "assistant_turn": "🤖 助手（第 {i} 轮）：",
        # Compare page
        "compare_title": "⚖️ 对比运行",
        "compare_caption": "选择 2–6 份报告，比较通过率和各用例分数。",
        "no_reports_compare": "暂无报告——请先运行测试。",
        "reports_to_compare": "选择要对比的报告",
        "pick_two": "请至少选择两份报告。",
        "summary": "摘要",
        "pass_rate_chart": "通过率",
        "per_case_scores": "各用例分数",
        "drill_into": "深入查看用例",
        "not_in_report": "该报告中无此用例。",
        "col_report": "报告",
        "col_topic": "主题",
        "col_model": "模型",
        "col_cases": "用例数",
        "col_passed": "通过数",
        "col_pass_rate": "通过率 (%)",
        "col_avg_score": "平均分",
        # Go Eval page
        "go_title": "Go 评测",
        "go_tab_run": "单次运行",
        "go_tab_stability": "{n} 次运行的稳定性",
        "go_report": "报告",
        "go_no_reports": "还没有 Go 评测报告。先启动评测栈并运行：",
        "go_judged_by": "被测模型 **{sut}** · 评审模型 **{judge}**",
        "go_same_family": "评审模型 **{judge}** 与被测模型 **{sut}** 同属一个模型家族。主观标准上的分数偏乐观；下方的断言不受影响。",
        "go_col_asserts": "断言",
        "go_col_failed_assert": "失败断言",
        "go_col_mem": "记忆",
        "go_col_turns": "轮数",
        "go_col_scored": "计分轮次",
        "go_col_rate": "通过率",
        "go_col_verdict": "结论",
        "go_col_history": "历史",
        "go_col_drive_errors": "驱动失败",
        "go_assertions": "**断言** — 看的是线上字段，不是主观判断",
        "go_no_asserts": "未声明",
        "go_judged_score": "**评审得分** — 依据用例自带的标准",
        "go_rubric_but_assert": "过了评分标准，但断言失败。评审模型看的是文字，断言查的是实际发上线的内容。",
        "go_context": "背景 — {label} · 已灌入 {n} 条记忆",
        "go_user": "用户",
        "go_assistant": "助手",
        "go_no_alert": "无提示",
        "go_v_stable_pass": "稳定通过",
        "go_v_stable_fail": "稳定失败",
        "go_v_never_ran": "未运行",
        "go_v_flaky": "不稳定 ({ok}/{n})",
        "go_v_fixed": "已修复 (连续 {n} 次)",
        "go_v_regressed": "出现回退 (连续 {n} 次)",
        "go_history_caption": "历史从旧到新：`.` 通过，`x` 失败，`!` 驱动未触及模型（不计入通过率）。真正混合的行意味着结论取决于你打开的是哪一次，而不是代码。",
    },
}


# Where the choice actually lives.
#
# "ui_lang" is a widget key, and Streamlit drops widget state for any widget the
# current run did not render. Only two pages rendered the toggle, so switching to
# any other page discarded the selection and coming back showed English again —
# the docstring below used to claim it persisted across pages, which was the one
# thing it did not do.
#
# A plain (non-widget) key is never garbage-collected, so the toggle reads from
# it, writes back to it, and any page can restore it whether or not it draws the
# radio.
_PERSIST_KEY = "_ui_lang_choice"


def get_lang() -> str:
    import streamlit as st
    return st.session_state.get(_PERSIST_KEY, "en")


def t(key: str, **kwargs: object) -> str:
    lang = get_lang()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def _remember_lang() -> None:
    import streamlit as st
    st.session_state[_PERSIST_KEY] = st.session_state.get("ui_lang", "en")


def lang_toggle() -> None:
    """Render the sidebar language toggle. Safe to call from every page."""
    import streamlit as st
    # Seed the widget from the persisted choice before it renders, so a page
    # reached after a language switch comes up in the language that was chosen.
    st.session_state.setdefault("ui_lang", get_lang())
    st.sidebar.radio(
        t("language"),
        options=["en", "zh"],
        format_func=lambda x: "English" if x == "en" else "中文",
        key="ui_lang",
        on_change=_remember_lang,
        horizontal=True,
    )
    # Also mirror on plain reruns: on_change only fires when the user clicks.
    _remember_lang()
