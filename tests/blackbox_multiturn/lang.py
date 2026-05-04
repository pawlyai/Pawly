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
    },
}


def get_lang() -> str:
    import streamlit as st
    return st.session_state.get("ui_lang", "en")


def t(key: str, **kwargs: object) -> str:
    lang = get_lang()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def lang_toggle() -> None:
    """Render a language toggle in the sidebar; persists across pages via session_state."""
    import streamlit as st
    st.sidebar.radio(
        t("language"),
        options=["en", "zh"],
        format_func=lambda x: "English" if x == "en" else "中文",
        index=0 if get_lang() == "en" else 1,
        key="ui_lang",
        horizontal=True,
    )
