"""Unit tests for hybrid KB retrieval — RRF fusion + branch fallback logic.

Real DB / embedding API are not exercised here. Branch results are stubbed
so we can verify fusion behaviour deterministically.
"""

from src.db.models import GeneralKbEntry
from src.memory.kb_retrieval import GeneralKbHit, _rrf_fuse, format_general_kb


def _e(id_: str, content: str = "x") -> GeneralKbEntry:
    return GeneralKbEntry(
        id=id_,
        domain="care",
        content=content,
        keywords_en=[],
        keywords_cn=[],
        citations=[],
    )


def test_rrf_empty_branches_returns_empty():
    assert _rrf_fuse([], [], [], top_k=4) == []


def test_rrf_single_branch_returns_in_order():
    fts = [_e("a"), _e("b"), _e("c")]
    out = _rrf_fuse([], fts, [], top_k=4)
    assert [h.id for h in out] == ["a", "b", "c"]
    assert all(h.branches == ("fts",) for h in out)


def test_rrf_top_k_truncates():
    fts = [_e(f"e{i}") for i in range(10)]
    out = _rrf_fuse([], fts, [], top_k=3)
    assert len(out) == 3
    assert [h.id for h in out] == ["e0", "e1", "e2"]


def test_rrf_promotes_multi_branch_hits():
    """An entry that appears in two branches should outrank one that
    appears once even at a higher rank in its single branch."""
    a = _e("a")
    b = _e("b")
    c = _e("c")
    # b is rank-1 in fts. a is rank-3 in fts AND rank-1 in vector (so two-branch)
    vector = [(a, 0.1)]
    fts = [b, c, a]
    out = _rrf_fuse(vector, fts, [], top_k=3)
    ids = [h.id for h in out]
    assert ids[0] == "a", f"expected a to be top from multi-branch boost, got {ids}"


def test_rrf_branches_reported():
    a = _e("a")
    out = _rrf_fuse([(a, 0.1)], [a], [a], top_k=1)
    assert len(out) == 1
    assert set(out[0].branches) == {"vector", "fts", "exact"}


def test_format_empty_returns_empty_string():
    assert format_general_kb([]) == ""


def test_format_includes_id_and_content():
    hits = [
        GeneralKbHit(
            id="indoor_cat_enrichment",
            domain="care",
            content="Indoor cats need vertical space and daily play.",
            keywords_en=[],
            keywords_cn=[],
            citations=[],
            rrf_score=0.5,
            branches=("vector",),
        ),
    ]
    out = format_general_kb(hits)
    assert "[indoor_cat_enrichment]" in out
    assert "vertical space" in out
