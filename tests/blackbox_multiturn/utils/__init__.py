from typing import Any


def parse_filename(name: str) -> dict[str, str]:
    # Pattern: {topic}_report_{model}_v{timestamp}.json
    stem = name.replace(".json", "")
    parts = stem.split("_report_")
    topic = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    if "_v" in rest:
        model, ts = rest.rsplit("_v", 1)
    else:
        model, ts = rest, ""
    return {"topic": topic, "model": model, "timestamp": ts}


def compute_report_stats(report: dict[str, Any]) -> tuple[int, int, int, float]:
    """Return (total, passed, failed, pass_rate%) for a report.

    Counts are derived from the ``cases`` array when present so partial runs —
    where ``summary.total_cases`` is the planned count and
    ``passed_threshold``/``below_threshold`` may be missing — still report the
    real numbers. Falls back to summary fields only when cases is empty.
    """
    cases = report.get("cases") or []
    if cases:
        total = len(cases)
        passed = sum(1 for c in cases if c.get("status") == "passed_threshold")
        failed = sum(1 for c in cases if c.get("status") == "below_threshold")
    else:
        summary = report.get("summary") or {}
        total = summary.get("total_cases", 0)
        passed = summary.get("passed_threshold", 0)
        failed = summary.get("below_threshold", 0)
    pass_rate = (passed / total * 100) if total else 0.0
    return total, passed, failed, pass_rate
