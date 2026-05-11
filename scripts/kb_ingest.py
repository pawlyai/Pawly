"""
Ingest src/llm/prompts/general_kb.yaml into the general_kb_entry table.

Usage:
    python scripts/kb_ingest.py
    python scripts/kb_ingest.py --dry-run        # parse + embed, skip DB write
    python scripts/kb_ingest.py --delete-stale   # also drop rows whose id is not in the yaml

Requires:
    - GOOGLE_API_KEY env var (for gemini text-embedding-004)
    - DATABASE_URL pointed at a postgres with the pgvector extension and
      the general_kb_entry table created (alembic upgrade head).

The script is idempotent — re-running upserts the same content (and re-
embeds it). Cheap: 100-200 entries × 200 tokens × $0.025/1M tokens is
fractions of a cent. Re-run after editing the yaml to refresh embeddings.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml

# Force-add project root to PYTHONPATH so the script is runnable from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select, text  # noqa: E402

from src.db.engine import get_session_factory, init_engine  # noqa: E402
from src.db.models import GeneralKbEntry  # noqa: E402
from src.llm.embeddings import embed_documents  # noqa: E402

YAML_PATH = ROOT / "src" / "llm" / "prompts" / "general_kb.yaml"


def _validate_entry(entry: dict, idx: int) -> None:
    """Fail loudly on malformed entries — easier than debugging silent skips."""
    required = {"id", "domain", "content"}
    missing = required - set(entry)
    if missing:
        raise ValueError(f"entry #{idx} missing required keys: {missing}")
    if not isinstance(entry["id"], str) or not entry["id"].strip():
        raise ValueError(f"entry #{idx} id must be a non-empty string")
    if not isinstance(entry["content"], str) or len(entry["content"]) < 30:
        raise ValueError(
            f"entry {entry['id']!r}: content must be a non-trivial string "
            f"(got {len(entry.get('content', '')) if entry.get('content') else 0} chars)"
        )
    if entry["domain"] not in (
        "care", "behavior", "stage", "region", "nutrition", "breed_care",
    ):
        raise ValueError(f"entry {entry['id']!r}: unknown domain {entry['domain']!r}")


def _normalise_entry(entry: dict) -> dict:
    """Ensure optional fields are lists of strings."""
    return {
        "id": entry["id"].strip(),
        "domain": entry["domain"],
        "content": entry["content"].strip(),
        "keywords_en": [str(k).strip() for k in entry.get("keywords_en", []) if str(k).strip()],
        "keywords_cn": [str(k).strip() for k in entry.get("keywords_cn", []) if str(k).strip()],
        "citations": [str(c).strip() for c in entry.get("citations", []) if str(c).strip()],
    }


async def _upsert(entries: list[dict]) -> None:
    factory = get_session_factory()
    async with factory() as session:
        for e in entries:
            # Upsert via INSERT ... ON CONFLICT to keep it deterministic
            # (SQLAlchemy doesn't have a portable upsert without dialect-specific calls)
            await session.execute(
                text(
                    """
                    INSERT INTO general_kb_entry
                        (id, domain, content, keywords_en, keywords_cn, citations,
                         embedding, created_at, updated_at)
                    VALUES
                        (:id, :domain, :content, :keywords_en, :keywords_cn, :citations,
                         CAST(:embedding AS vector), NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        domain = EXCLUDED.domain,
                        content = EXCLUDED.content,
                        keywords_en = EXCLUDED.keywords_en,
                        keywords_cn = EXCLUDED.keywords_cn,
                        citations = EXCLUDED.citations,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                    """
                ),
                {
                    "id": e["id"],
                    "domain": e["domain"],
                    "content": e["content"],
                    "keywords_en": e["keywords_en"],
                    "keywords_cn": e["keywords_cn"],
                    "citations": e["citations"],
                    "embedding": str(e["embedding"]),
                },
            )
        await session.commit()


async def _delete_stale(active_ids: set[str]) -> int:
    factory = get_session_factory()
    async with factory() as session:
        existing = await session.execute(select(GeneralKbEntry.id))
        existing_ids = {row[0] for row in existing}
        stale = existing_ids - active_ids
        if not stale:
            return 0
        await session.execute(delete(GeneralKbEntry).where(GeneralKbEntry.id.in_(stale)))
        await session.commit()
        return len(stale)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="parse + embed, do not write DB")
    parser.add_argument(
        "--delete-stale",
        action="store_true",
        help="delete rows whose id is not in the current yaml",
    )
    args = parser.parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY env var is required", file=sys.stderr)
        return 2

    if not YAML_PATH.exists():
        print(f"ERROR: yaml not found at {YAML_PATH}", file=sys.stderr)
        return 2

    with YAML_PATH.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict) or "entries" not in raw:
        print("ERROR: yaml must have a top-level `entries:` list key", file=sys.stderr)
        return 2

    entries_raw = raw["entries"] or []
    if not entries_raw:
        print("yaml has zero entries — nothing to ingest. Exiting.")
        return 0

    # Validate + normalise before any network call so we fail fast on yaml bugs.
    for i, e in enumerate(entries_raw):
        _validate_entry(e, i)
    entries = [_normalise_entry(e) for e in entries_raw]

    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        dupes = [x for x in ids if ids.count(x) > 1]
        print(f"ERROR: duplicate ids in yaml: {set(dupes)}", file=sys.stderr)
        return 2

    print(f"[kb_ingest] parsed {len(entries)} entries; calling gemini text-embedding-004...")
    texts = [e["content"] for e in entries]
    embeddings = await embed_documents(texts, concurrency=4)
    print(f"[kb_ingest] embedded {len(embeddings)} entries (dim={len(embeddings[0])})")

    for e, emb in zip(entries, embeddings, strict=True):
        e["embedding"] = emb

    if args.dry_run:
        print("[kb_ingest] --dry-run: skipping DB write.")
        return 0

    await init_engine()
    await _upsert(entries)
    print(f"[kb_ingest] upserted {len(entries)} rows into general_kb_entry")

    if args.delete_stale:
        active = {e["id"] for e in entries}
        n = await _delete_stale(active)
        if n:
            print(f"[kb_ingest] deleted {n} stale rows")
        else:
            print("[kb_ingest] no stale rows")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
