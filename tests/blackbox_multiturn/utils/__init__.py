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
