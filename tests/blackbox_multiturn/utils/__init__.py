def parse_filename(name: str) -> dict[str, str]:
    # Pattern: {topic}_report_{model}_v{timestamp}[__{git_ref}].json
    # The optional `__{git_ref}` suffix labels the code branch/tag the run was
    # exercised against (used to triage and compare runs across revisions).
    stem = name.replace(".json", "")
    parts = stem.split("_report_")
    topic = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    git_ref = ""
    if "__" in rest:
        rest, git_ref = rest.rsplit("__", 1)

    if "_v" in rest:
        model, ts = rest.rsplit("_v", 1)
    else:
        model, ts = rest, ""
    return {"topic": topic, "model": model, "timestamp": ts, "git_ref": git_ref}
