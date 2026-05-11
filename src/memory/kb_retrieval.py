"""
Hybrid retrieval for general_kb_entry: keyword + vector fused via RRF.

Used for general pet-care knowledge (care / behaviour / life-stage / region-
specific norms) outside the symptom-triage SOP that src/llm/retrievers.py
handles via pure keyword match.

Retrieval flow:
    1. Vector branch:  embed query  → cosine similarity top-k
    2. Keyword branch: postgres FTS over content  → top-k
    3. Keyword exact:  array overlap on keywords_en/keywords_cn → top-k
    4. Reciprocal-rank fusion of the three result lists, returning top final-k

The function returns empty list when:
    - Query is empty
    - DB has no rows (KB not yet ingested)
    - All branches return zero hits with score below floor

Public API:
    retrieve_general_kb(query: str, top_k: int = 4) -> list[GeneralKbHit]
    format_general_kb(hits: list[GeneralKbHit]) -> str
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session_factory
from src.db.models import GeneralKbEntry
from src.llm.embeddings import embed_query
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cosine similarity in pgvector: distance ranges 0 (identical) → 2 (opposite).
# Tightened in v2: was 0.4 (similarity >= 0.6), now 0.25 (similarity >= 0.875)
# to avoid injecting semantically-adjacent-but-task-irrelevant entries.
# Verified on edge / emotional / longitudinal regressions in Week 1 eval —
# loose cosine was pulling general knowledge into memory-driven scenarios.
_VECTOR_DISTANCE_CEILING = 0.25
_BRANCH_K = 8           # per-branch fetch count
_RRF_K_CONSTANT = 60    # standard RRF dampener
_MIN_RRF_SCORE = 0.005  # entries below this are dropped


@dataclass
class GeneralKbHit:
    id: str
    domain: str
    content: str
    keywords_en: list[str]
    keywords_cn: list[str]
    citations: list[str]
    rrf_score: float
    branches: tuple[str, ...]  # which branches contributed: ("vector", "fts", "exact")


async def retrieve_general_kb(
    query: str,
    top_k: int = 4,
    session: Optional[AsyncSession] = None,
) -> list[GeneralKbHit]:
    """Hybrid retrieve top_k entries for *query*. Returns [] on any failure
    or when no branch finds a relevant hit."""
    if not query or not query.strip():
        return []

    if session is None:
        factory = get_session_factory()
        async with factory() as s:
            return await _retrieve_in_session(query, top_k, s)
    return await _retrieve_in_session(query, top_k, session)


async def _retrieve_in_session(
    query: str,
    top_k: int,
    session: AsyncSession,
) -> list[GeneralKbHit]:
    # ── Vector branch ─────────────────────────────────────────────────────────
    vector_rows: list[tuple[GeneralKbEntry, float]] = []
    try:
        query_embedding = await embed_query(query)
        vector_rows = await _vector_search(session, query_embedding, _BRANCH_K)
    except Exception as exc:
        # Embedding API failure or no embeddings indexed yet — keep going with
        # keyword branches only.
        logger.warning("kb vector branch failed", error=str(exc))

    # ── Keyword: postgres FTS over content ────────────────────────────────────
    try:
        fts_rows = await _fts_search(session, query, _BRANCH_K)
    except Exception as exc:
        logger.warning("kb fts branch failed", error=str(exc))
        fts_rows = []

    # ── Keyword: exact match on keyword arrays ────────────────────────────────
    try:
        exact_rows = await _exact_keyword_search(session, query, _BRANCH_K)
    except Exception as exc:
        logger.warning("kb exact branch failed", error=str(exc))
        exact_rows = []

    # ── RRF fusion ────────────────────────────────────────────────────────────
    return _rrf_fuse(vector_rows, fts_rows, exact_rows, top_k=top_k)


async def _vector_search(
    session: AsyncSession,
    embedding: list[float],
    k: int,
) -> list[tuple[GeneralKbEntry, float]]:
    """pgvector cosine distance search. Returns (entry, distance) tuples
    with distance <= _VECTOR_DISTANCE_CEILING."""
    sql = text(
        """
        SELECT id, domain, content, keywords_en, keywords_cn, citations,
               embedding <=> CAST(:q AS vector) AS distance
        FROM general_kb_entry
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :k
        """
    )
    result = await session.execute(sql, {"q": str(embedding), "k": k})
    out: list[tuple[GeneralKbEntry, float]] = []
    for row in result.mappings():
        if row["distance"] > _VECTOR_DISTANCE_CEILING:
            continue
        entry = GeneralKbEntry(
            id=row["id"],
            domain=row["domain"],
            content=row["content"],
            keywords_en=list(row["keywords_en"] or []),
            keywords_cn=list(row["keywords_cn"] or []),
            citations=list(row["citations"] or []),
        )
        out.append((entry, float(row["distance"])))
    return out


async def _fts_search(
    session: AsyncSession,
    query: str,
    k: int,
) -> list[GeneralKbEntry]:
    """Postgres english FTS. plainto_tsquery is forgiving on user input."""
    sql = text(
        """
        SELECT id, domain, content, keywords_en, keywords_cn, citations,
               ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)) AS rank
        FROM general_kb_entry
        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :k
        """
    )
    result = await session.execute(sql, {"q": query, "k": k})
    return [
        GeneralKbEntry(
            id=row["id"],
            domain=row["domain"],
            content=row["content"],
            keywords_en=list(row["keywords_en"] or []),
            keywords_cn=list(row["keywords_cn"] or []),
            citations=list(row["citations"] or []),
        )
        for row in result.mappings()
    ]


async def _exact_keyword_search(
    session: AsyncSession,
    query: str,
    k: int,
) -> list[GeneralKbEntry]:
    """Match any token of the query against keywords_en/keywords_cn arrays.
    English tokens are lowercased; Chinese characters are matched as-is.
    """
    lower = query.lower()
    # Build candidate token list:
    # - english: split by whitespace, keep >=3 char tokens
    # - chinese: use the raw substrings (the yaml entries hold full phrases)
    en_tokens = [t for t in lower.split() if len(t) >= 3]
    sql = text(
        """
        SELECT id, domain, content, keywords_en, keywords_cn, citations
        FROM general_kb_entry
        WHERE keywords_en && CAST(:en AS text[])
           OR EXISTS (
               SELECT 1 FROM unnest(keywords_cn) kw
               WHERE :cn LIKE '%' || kw || '%'
           )
        LIMIT :k
        """
    )
    result = await session.execute(
        sql, {"en": en_tokens, "cn": query, "k": k}
    )
    return [
        GeneralKbEntry(
            id=row["id"],
            domain=row["domain"],
            content=row["content"],
            keywords_en=list(row["keywords_en"] or []),
            keywords_cn=list(row["keywords_cn"] or []),
            citations=list(row["citations"] or []),
        )
        for row in result.mappings()
    ]


def _rrf_fuse(
    vector_rows: list[tuple[GeneralKbEntry, float]],
    fts_rows: list[GeneralKbEntry],
    exact_rows: list[GeneralKbEntry],
    top_k: int,
) -> list[GeneralKbHit]:
    """Reciprocal-rank fusion across the three branches.

    RRF score for entry e = sum over branches b: 1 / (k + rank_b(e))
    where rank is 1-indexed. Entries missing from a branch contribute 0.
    """
    scores: dict[str, float] = {}
    entries: dict[str, GeneralKbEntry] = {}
    branches: dict[str, set[str]] = {}

    def add(rank: int, entry: GeneralKbEntry, branch: str) -> None:
        scores[entry.id] = scores.get(entry.id, 0.0) + 1.0 / (_RRF_K_CONSTANT + rank)
        entries[entry.id] = entry
        branches.setdefault(entry.id, set()).add(branch)

    for r, (entry, _dist) in enumerate(vector_rows, start=1):
        add(r, entry, "vector")
    for r, entry in enumerate(fts_rows, start=1):
        add(r, entry, "fts")
    for r, entry in enumerate(exact_rows, start=1):
        add(r, entry, "exact")

    fused = sorted(
        (
            GeneralKbHit(
                id=eid,
                domain=entries[eid].domain,
                content=entries[eid].content,
                keywords_en=entries[eid].keywords_en,
                keywords_cn=entries[eid].keywords_cn,
                citations=entries[eid].citations,
                rrf_score=score,
                branches=tuple(sorted(branches[eid])),
            )
            for eid, score in scores.items()
            if score >= _MIN_RRF_SCORE
        ),
        key=lambda h: -h.rrf_score,
    )
    return fused[:top_k]


def format_general_kb(hits: list[GeneralKbHit]) -> str:
    """Format hits for injection into <retrieved_general_knowledge>. Caller
    drops the tag entirely if this returns empty string (matches the
    retrieved_followups / special_scenarios convention)."""
    if not hits:
        return ""
    parts: list[str] = []
    for h in hits:
        # ID is the human-readable slug from yaml — surfacing it gives the
        # model a hook to refer to without verbatim-quoting the content.
        parts.append(f"[{h.id}] {h.content.strip()}")
    return "\n\n".join(parts)
