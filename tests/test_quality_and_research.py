"""Acceptance tests for `deye.core.quality` and `deye.research`.

Covers Category 5 (semantic research) and Category 6 (evidence quality)
rows: FTS5-backed fast/deep search, domain filtering, highlights,
find_similar, extractive answer, source-quality scoring, duplicate
removal, change monitoring.

All tests are stdlib-only. No network.
"""
from __future__ import annotations

from types import SimpleNamespace

from deye.core.quality import (
    change_monitor,
    deduplicate,
    quality_report,
    score_source,
)
from deye.research import (
    build_index,
    deep_search,
    domain_filter,
    extractive_answer,
    fast_search,
    find_similar,
    highlights,
    FTSIndex,
)


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def test_score_source_prefers_trusted_https_with_recent_fresh():
    r = {
        "url": "https://arxiv.org/abs/2401.12345",
        "title": "A paper",
        "excerpt": "x" * 300,
        "content_hash": "sha256:abc",
        "retrieved_at": "2026-07-30T00:00:00+00:00",
    }
    s = score_source(r)
    assert s.score >= 0.6
    assert "trusted_domain" in s.factors
    assert "https" in s.factors
    assert "excerpt_length" in s.factors


def test_score_source_penalises_aggregator_and_http():
    r = {
        "url": "http://alice.medium.com/post/abc",
        "title": "opinion",
        "excerpt": "short",
    }
    s = score_source(r)
    assert s.score < 0.3
    assert s.factors.get("aggregator_penalty") == -0.10
    assert "non-https" in " ".join(s.reasons).lower()


def test_score_source_score_is_clipped_to_unit_interval():
    r = {"url": "https://arxiv.org/x", "title": "t", "excerpt": "x" * 500,
         "content_hash": "h", "retrieved_at": "2026-01-01T00:00:00+00:00"}
    s = score_source(r)
    assert 0.0 <= s.score <= 1.0


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_deduplicate_collapses_url_and_hash_and_shingle():
    rows = [
        {"url": "https://example.com/a?utm_source=x", "content_hash": "h1",
         "excerpt": "lorem ipsum dolor sit amet consectetur adipiscing elit sed do"},
        {"url": "https://example.com/a", "content_hash": "h1",
         "excerpt": "lorem ipsum dolor sit amet consectetur adipiscing elit sed do"},
        # different URL, same hash
        {"url": "https://mirror.com/a", "content_hash": "h1",
         "excerpt": "different words entirely and not similar"},
        # different hash, near-identical excerpt (only last word differs)
        {"url": "https://blogspot.com/x", "content_hash": "h2",
         "excerpt": "lorem ipsum dolor sit amet consectetur adipiscing elit sed done"},
        {"url": "https://novel.com/y", "content_hash": "h3",
         "excerpt": "wholly unrelated content about something else entirely"},
    ]
    # shingle_threshold=0.5 tolerates single-word differences over ~10-word excerpts
    kept, clusters = deduplicate(rows, shingle_threshold=0.5)
    assert len(kept) == 2
    reasons = {c.reason for c in clusters}
    assert reasons >= {"exact_url", "content_hash", "shingle_overlap"}


def test_deduplicate_empty_input():
    kept, clusters = deduplicate([])
    assert kept == []
    assert clusters == []


# ---------------------------------------------------------------------------
# Change monitoring
# ---------------------------------------------------------------------------

class _FakeStore:
    def __init__(self, table: dict[str, dict | None]):
        self._table = table

    def changed_since(self, url):
        return self._table.get(url)


def test_change_monitor_reports_change_and_no_change():
    store = _FakeStore({
        "https://a": {"url": "https://a", "changed": True,
                      "latest": "hnew", "previous": "hold"},
        "https://b": {"url": "https://b", "changed": False,
                      "latest": "h", "previous": "h"},
        "https://c": None,
    })
    reports = change_monitor(store, ["https://a", "https://b", "https://c"])
    by_url = {r.url: r for r in reports}
    assert by_url["https://a"].changed is True
    assert by_url["https://b"].changed is False
    assert by_url["https://c"].changed is False
    assert "fewer than 2" in by_url["https://c"].detail


# ---------------------------------------------------------------------------
# Quality report convenience
# ---------------------------------------------------------------------------

def test_quality_report_summary_shape():
    rows = [
        {"url": "https://arxiv.org/x", "title": "t", "excerpt": "x" * 300,
         "content_hash": "h1"},
        {"url": "https://arxiv.org/x", "title": "t", "excerpt": "x" * 300,
         "content_hash": "h1"},  # exact duplicate
    ]
    r = quality_report(rows)
    assert r["input_count"] == 2
    assert r["kept_count"] == 1
    assert len(r["clusters"]) == 1
    assert r["top_scored"][0]["score"] > 0


# ---------------------------------------------------------------------------
# FTS index + search
# ---------------------------------------------------------------------------

def _seed_rows():
    return [
        {"url": "https://a.com/1", "title": "sqlite fts5 tutorial",
         "excerpt": "how to use FTS5 for keyword search in SQLite databases",
         "connector": "web", "content_hash": "h1"},
        {"url": "https://b.com/2", "title": "chess openings guide",
         "excerpt": "the Sicilian defence remains popular at all levels",
         "connector": "web", "content_hash": "h2"},
        {"url": "https://c.com/3", "title": "python typing tips",
         "excerpt": "use TypeVar and Protocol for structural typing in python",
         "connector": "web", "content_hash": "h3"},
    ]


def test_fast_and_deep_search_return_relevant_rows():
    idx = FTSIndex()
    idx.replace_from(_seed_rows())
    fast = fast_search(idx, "fts5")
    assert fast
    assert fast[0]["url"] == "https://a.com/1"
    deep = deep_search(idx, "typing python", limit=3)
    assert deep
    assert deep[0]["url"] == "https://c.com/3"


def test_search_empty_query_returns_nothing():
    idx = FTSIndex()
    idx.replace_from(_seed_rows())
    assert fast_search(idx, "") == []


def test_domain_filter_include_and_exclude():
    rows = [
        {"url": "https://arxiv.org/a"},
        {"url": "https://wikipedia.org/b"},
        {"url": "https://spam.example/c"},
    ]
    inc = domain_filter(rows, include=["arxiv.org", "wikipedia.org"])
    assert {r["url"] for r in inc} == {"https://arxiv.org/a", "https://wikipedia.org/b"}
    exc = domain_filter(rows, exclude=["spam.example"])
    assert {r["url"] for r in exc} == {"https://arxiv.org/a", "https://wikipedia.org/b"}


def test_highlights_extract_windows_around_query_terms():
    body = "The quick brown fox jumps over the lazy dog. Foxes are cunning."
    h = highlights(body, "fox")
    assert h
    assert any("fox" in s.lower() for s in h)


def test_find_similar_uses_shingle_overlap():
    rows = [
        {"url": "https://a.com/1",
         "excerpt": "sqlite fts5 keyword search full text index tokenizer porter unicode"},
        {"url": "https://b.com/2",
         "excerpt": "sqlite fts5 keyword search full text index tokenizer porter results"},
        {"url": "https://c.com/3",
         "excerpt": "completely unrelated blueberries and gardening tips for spring"},
    ]
    sim = find_similar(rows, "https://a.com/1", min_score=0.1, limit=3)
    assert sim
    assert sim[0]["url"] == "https://b.com/2"
    assert sim[0]["score"] > 0


def test_find_similar_returns_empty_when_url_absent():
    assert find_similar([], "https://none") == []


# ---------------------------------------------------------------------------
# Grounded extractive answer
# ---------------------------------------------------------------------------

def test_extractive_answer_grounded_with_citations():
    rows = [
        {"url": "https://arxiv.org/x", "title": "sqlite fts5 tutorial",
         "excerpt": "SQLite FTS5 supports Porter tokenizer for keyword search "
                    "in a compact, fast, in-process index."},
    ]
    ans = extractive_answer(rows, "FTS5 tokenizer")
    assert ans.citations
    assert "SQLite" in ans.answer
    assert ans.confidence > 0


def test_extractive_answer_no_evidence_case():
    ans = extractive_answer([], "no data")
    assert "No supporting evidence" in ans.answer
    assert ans.confidence == 0.0


# ---------------------------------------------------------------------------
# Convenience: build_index over a fake EvidenceStore
# ---------------------------------------------------------------------------

def test_build_index_reads_from_store():
    fake_rows = _seed_rows()

    class _S:
        db_path = None  # not needed for in_memory=True

        def query(self, q, limit=200):
            return list(fake_rows)

    idx = build_index(_S(), in_memory=True, limit=100)
    hits = fast_search(idx, "sqlite")
    assert hits and hits[0]["url"] == "https://a.com/1"
